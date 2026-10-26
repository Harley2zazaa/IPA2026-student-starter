import os
import re
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import ipaddress
from ncclient import manager
from ncclient.transport.errors import AuthenticationError, SSHError, TransportError
from ncclient.operations.rpc import RPCError
from ncclient.operations import RPCError

from app.backends import planning

NS = {
    "if": "urn:ietf:params:xml:ns:yang:ietf-interfaces",
    "ip": "urn:ietf:params:xml:ns:yang:ietf-ip",
}


FILTER = """<interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
  <interface><name>{name}</name></interface>
</interfaces>""" # ใช้ <name> ตาม tests (ไม่ใช่ <n>)

def _code_for(exc):
    # 1) auth ก่อน เพราะ PermissionError เป็น subclass ของ OSError
    if isinstance(exc, (PermissionError, AuthenticationError)):
        return "authentication_failed"
    # 2) connection
    if isinstance(exc, (ConnectionError, TimeoutError, SSHError, TransportError, OSError)):
        return "connection_failed"
    # 3) RPCError, RuntimeError, อื่น ๆ
    return "backend_failed"

def _error(code):
    return {"status": "error", "result": code}

def _connect(router):
    return manager.connect(
        host=router, port=830,
        username=os.environ.get("ROUTER_USER", ""),
        password=os.environ.get("ROUTER_PASS", ""),
        hostkey_verify=False, look_for_keys=False, allow_agent=False,
        timeout=8,
    )

def get_interface_state(router, interface_name, netconf_get_config=None):
    netconf_get_config = netconf_get_config 
    try:
        if netconf_get_config:
            xml_text = netconf_get_config(router, FILTER.format(name=interface_name))
        else:  # real transport
            with _connect(router) as m:
                xml_text = m.get_config(source="running", filter=("subtree", FILTER.format(name=interface_name))).data_xml
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return _error("backend_failed")
    except Exception as exc:
        return _error(_code_for(exc))
    #TODO: root.find(".//if:interface", NS) เป็น None → not_found
    node = root.find(".//if:interface", NS)
    if node is None:
        return {"status": "ok", "result": "not_found", "interface": None}
    
    #TODO: อ่าน if:description, if:enabled, ip:ipv4/ip:address (ip + netmask)
    #       .text ต้อง .strip() (XML มี whitespace/newline)
    #       แล้วคืน {"status":"ok","result":"found","interface":{...}}
    def text(parent, path):
        n = parent.find(path, NS)
        return n.text.strip() if n is not None and n.text else None

    ip, mask = text(node, ".//ip:ipv4/ip:address/ip:ip"), text(node, ".//ip:ipv4/ip:address/ip:netmask")
    try:
        ipv4 = f"{ip}/{ipaddress.IPv4Network(f'0.0.0.0/{mask}').prefixlen}" if ip and mask else None
    except (ValueError,RuntimeError):
        return _error("backend_failed")
    

    return {"status": "ok", "result": "found", "interface": {
        "name": interface_name,
        "ipv4": ipv4,
        "description": text(node, "if:description"),
        "admin_state": "up" if (text(node, "if:enabled") or "").lower() == "true" else "down",
    }}


def plan_interface(
    router,
    desired_interface,
    netconf_get_config=None,
):
    """Return create/update/no_change plan using NETCONF status."""
    return planning.plan_interface(
        router, desired_interface,
        lambda r, name: get_interface_state(r, name, netconf_get_config),
    )
    # raise NotImplementedError

CONFIG_TEMPLATE = """<config
    xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"
    xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
  <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
    <interface>
      <Loopback nc:operation="replace">
        <name>{number}</name>
        <description>{description}</description>
        <ip><address><primary>
          <address>{address}</address><mask>{mask}</mask>
        </primary></address></ip>
{shutdown}
      </Loopback>
    </interface>
  </native>
</config>"""

def apply_interface(router, desired_interface, netconf_edit_config=None):
    netconf_edit_config = netconf_edit_config 

    try:
        name = desired_interface["name"]
        match = re.fullmatch(r"Loopback(\d+)", name) if isinstance(name, str) else None
        if not match:
            raise ValueError("unsupported interface name")
        number = match.group(1)
        ip = ipaddress.IPv4Interface(desired_interface["ipv4"])
        address = str(ip.ip)
        mask = str(ip.network.netmask)
        description = escape(str(desired_interface["description"]))
        shutdown = "<shutdown/>" if desired_interface["admin_state"] == "down" else ""
    except (ValueError, TypeError, KeyError, AttributeError):
        return _error("backend_failed")

    config_xml = CONFIG_TEMPLATE.format(
        number=number, description=description,
        address=address, mask=mask, shutdown=shutdown,
    )
    try:
        if netconf_edit_config:
            netconf_edit_config(router, config_xml)
        else:  # real transport
            with _connect(router) as m:
                m.edit_config(target="running", config=config_xml)
    except Exception as exc:
        return _error(_code_for(exc))
    return {"status": "ok", "result": "applied"}