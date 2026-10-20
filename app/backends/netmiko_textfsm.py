import os
import re

from netmiko import ConnectHandler
from netmiko import NetmikoAuthenticationException
def _code_for(exc):
    # 1) auth ก่อน เพราะ PermissionError เป็น subclass ของ OSError
    if isinstance(exc, (PermissionError,NetmikoAuthenticationException)):
        return "authentication_failed"
    # 2) connection
    if isinstance(exc, (ConnectionError)):
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
        ip_info, descriptions = netmiko_get(router, interface_name)
    except Exception as exc:
        # Netmiko auth exception → authentication_failed
        # Netmiko timeout → connection_failed
        # TextFSM / อื่น ๆ → backend_failed
        return _error(_code_for(exc))

    #TODO: หา record ใน ip_info ที่ interface == interface_name
    #       ไม่มี (หรือ ip_info ว่าง) → {"status":"ok","result":"not_found","interface":None}
    record = None
    if ip_info:
        for item in ip_info:
            if item.get("interface") == interface_name:
                record = item
                break
    #       ไม่มี (หรือ ip_info ว่าง) → {"status":"ok","result":"not_found","interface":None}
    if not record:
        return {"status": "ok", "result": "not_found", "interface": None}
    #TODO: ipv4 = ip_address[0] + "/" + prefix_length[0]  (prefix_length เป็น str)
    ip_addr = record["ip_address"][0] if isinstance(record.get("ip_address"), list) else record.get("ip_address")
    prefix_len = record["prefix_length"][0] if isinstance(record.get("prefix_length"), list) else record.get("prefix_length")
    ipv4 = f"{ip_addr}/{prefix_len}"
    #TODO: admin_state: "administratively down" ใน link_status → "down" ไม่งั้น "up"
    link_status = record.get("link_status", "")
    if isinstance(link_status, list) and link_status:
        link_status = link_status[0]
    
    admin_state = "down" if "administratively down" in str(link_status).lower() else "up"
    #TODO: description: หาใน descriptions โดยเทียบ _normalize_port(port) กับ interface_name     #       ไม่เจอ → None
    description = None
    if descriptions:
        for desc in descriptions:
            port = desc.get("port") or desc.get("interface")
            if port and _normalize_port(port) == interface_name:
                description = desc.get("description")
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
    raise NotImplementedError


def delete_interface(
    router,
    interface_name,
    netmiko_delete=None,
):
    """Delete an interface using Netmiko."""
    netmiko_delete = netmiko_delete
    try:
        outcome = netmiko_delete(router, interface_name)
    except Exception as exc:
        return _error(_code_for(exc))
    
    if outcome == "deleted":
        return {"status": "ok", "result": "deleted"}
    elif outcome == "not_found":
        return {"status": "ok", "result": "not_found", "interface": None}
    else:
        return _error("backend_failed")
    raise NotImplementedError
