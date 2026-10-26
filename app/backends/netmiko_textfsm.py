import logging
import os
import re

from netmiko import ConnectHandler
from netmiko import NetmikoAuthenticationException, NetmikoTimeoutException
from textfsm import TextFSMError

logger = logging.getLogger(__name__)

def _code_for(exc):
    # 1) auth ก่อน เพราะ PermissionError เป็น subclass ของ OSError
    if isinstance(exc, (PermissionError,NetmikoAuthenticationException)):
        return "authentication_failed"
    # 2) connection
    if isinstance(exc, (ConnectionError, TimeoutError, NetmikoTimeoutException)):
        return "connection_failed"
    # 3) RPCError, RuntimeError, อื่น ๆ
    return "backend_failed"

def _error(code):
    return {"status": "error", "result": code}


def _normalize_port(port):
    """Lo123 → Loopback123"""
    return re.sub(r"^Lo(?=\d)", "Loopback", port)

def get_interface_state(
    router,
    interface_name,
    netmiko_get=None,
):
    """Return normalized interface status using Netmiko + TextFSM."""
    netmiko_get = netmiko_get
    try:
        if netmiko_get:
            ip_info, descriptions = netmiko_get(router, interface_name)
        else:  # real transport
            conn = ConnectHandler(device_type="cisco_ios", host=router,
                                  username=os.environ.get("ROUTER_USER", ""),
                                  password=os.environ.get("ROUTER_PASS", ""),
                                  timeout=8, conn_timeout=8)
            try:
                try:
                    ip_info = conn.send_command(f"show ip interface {interface_name}", use_textfsm=True)
                except TextFSMError:
                    # IOS ตอบ "% Invalid input" (ไม่มี interface) → template Error rule → ถือว่า not_found
                    ip_info = []
                descriptions = conn.send_command("show interfaces description", use_textfsm=True)
            finally:
                conn.disconnect()
    except Exception as exc:
        # Netmiko auth exception → authentication_failed
        # Netmiko timeout → connection_failed
        # TextFSM / อื่น ๆ → backend_failed
        logger.exception("get_interface_state failed")
        return _error(_code_for(exc))

    #TODO: หา record ใน ip_info ที่ interface == interface_name
    #       ไม่มี (หรือ ip_info ว่าง) → {"status":"ok","result":"not_found","interface":None}
    record = None
    if isinstance(ip_info, list):  # TextFSM คืน str เมื่อ parse ไม่ได้
        for item in ip_info:
            if item.get("interface") == interface_name:
                record = item
                break
    #       ไม่มี (หรือ ip_info ว่าง) → {"status":"ok","result":"not_found","interface":None}
    if not record:
        return {"status": "ok", "result": "not_found", "interface": None}
    #TODO: ipv4 = ip_address[0] + "/" + prefix_length[0]  (prefix_length เป็น str)
    def _first(value):
        if isinstance(value, list):
            return value[0] if value else None
        return value

    ip_addr = _first(record.get("ip_address"))
    prefix_len = _first(record.get("prefix_length"))
    ipv4 = f"{ip_addr}/{prefix_len}" if ip_addr and prefix_len not in (None, "") else None
    link_status = _first(record.get("link_status")) or ""

    admin_state = "down" if "administratively down" in str(link_status).lower() else "up"
    description = None
    if isinstance(descriptions, list):
        for desc in descriptions:
            port = desc.get("port") or desc.get("interface")
            if port and _normalize_port(port) == interface_name:
                description = desc.get("description") or None
                break
    # Formating and return
    return {
        "status": "ok",
        "result": "found",
        "interface": {
            "name": interface_name,
            "ipv4": ipv4,
            "admin_state": admin_state,
            "description": description
        }
    }


def delete_interface(
    router,
    interface_name,
    netmiko_delete=None,
):
    """Delete an interface using Netmiko."""
    netmiko_delete = netmiko_delete
    try:
        if netmiko_delete:
            outcome = netmiko_delete(router, interface_name)
        else:  # real: เช็ก -> ลบ -> verify (ใช้ get_interface_state ที่มีอยู่)
            before = get_interface_state(router, interface_name)
            if before["status"] == "error":
                return before
            if before["result"] == "not_found":
                outcome = "not_found"
            else:
                conn = ConnectHandler(device_type="cisco_ios", host=router,
                                      username=os.environ.get("ROUTER_USER", ""),
                                      password=os.environ.get("ROUTER_PASS", ""),
                                      timeout=8, conn_timeout=8)
                try:
                    # เก็บ output ไว้ดู: ถ้ามี "%" แสดงว่า IOS ปฏิเสธคำสั่ง
                    out = conn.send_config_set([f"no interface {interface_name}"])
                    logger.info("config output: %s", out)
                finally:
                    conn.disconnect()
                after = get_interface_state(router, interface_name)
                # verify รอบสอง error → ส่ง error จริงต่อ ไม่กลืนเป็น backend_failed
                if after["status"] == "error":
                    return after
                # not_found หลังลบ = ลบสำเร็จ / ยังอยู่ = IOS ไม่ยอมลบ → None → backend_failed
                if after["result"] == "not_found":
                    outcome = "deleted"
                else:
                    outcome = None
    except Exception as exc:
        logger.exception("delete_interface failed")
        return _error(_code_for(exc))
    
    if outcome == "deleted":
        return {"status": "ok", "result": "deleted"}
    elif outcome == "not_found":
        return {"status": "ok", "result": "not_found", "interface": None}
    else:
        return _error("backend_failed")