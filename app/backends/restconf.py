import ipaddress
import os
import re

import requests

from app.backends import planning

TIMEOUT = 8  # Live รอ 20 วินาทีต่อกรณี ต้องสั้นพอ

def _error(code):
    return {"status": "error", "result": code}

def _auth():
    return os.environ.get("ROUTER_USER", ""), os.environ.get("ROUTER_PASS", "")

def _native_args(desired_interface):
    """Return (loopback number, IPv4Interface); raise ValueError if malformed."""
    name = desired_interface["name"]
    match = re.fullmatch(r"Loopback(\d+)", name) if isinstance(name, str) else None
    if not match:
        raise ValueError("unsupported interface name")
    return int(match.group(1)), ipaddress.IPv4Interface(desired_interface["ipv4"])


def get_interface_state(
    router,
    interface_name,
    http_get=None,
):
    """Return normalized interface status using RESTCONF."""
    # http_get = http_get or _real_get
    http_get = http_get or (lambda u: requests.get(u, auth=_auth(), verify=False, timeout=TIMEOUT,
                                                   headers={"Accept": "application/yang-data+json"}))  # real transport
    url = (f"https://{router}/restconf/data/"
           f"ietf-interfaces:interfaces/interface={interface_name}")
    #TODO: 404 → {"status":"ok","result":"not_found","interface":None}
    #       401/403 → authentication_failed
    #       status อื่นที่ไม่ใช่ 2xx → backend_failed
    try:
        response = http_get(url)
        if response.status_code == 404:
            return {"status":"ok","result":"not_found","interface":None}
        if response.status_code in (401, 403):
            return _error("authentication_failed")
        if not (200 <= response.status_code < 300):
            return _error("backend_failed")
    #TODO: Decode Data Form REST CONF
    # parse response.json()["ietf-interfaces:interface"]
    #       - description (ไม่มี → None)
    #       - enabled true/false → "up"/"down"
    #       - ietf-ip:ipv4 → address[0] → ip + netmask → "a.b.c.d/prefix"
    #         (prefix: ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen)
    #       - parse พัง (KeyError/ValueError/TypeError/IndexError) → backend_failed
        data = response.json()["ietf-interfaces:interface"]
        description = data.get("description")
        # Admin_state Data
        enabled = data.get("enabled", False)
        admin_state = "up" if enabled else "down"
        # Load IP Data
        ipv4_info = data["ietf-ip:ipv4"]["address"][0]
        ip_addr = ipv4_info["ip"]
        netmask = ipv4_info["netmask"]
        # Format Prefix IP
        prefixlen = ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
        ipv4_cidr = f"{ip_addr}/{prefixlen}"
        # Parse -> Json
        return {
            "status": "ok",
            "result": "found",
            "interface": {
                "name": interface_name,
                "description": description,
                "admin_state": admin_state,
                "ipv4": ipv4_cidr,
            },
        }
    # Catch Error Form Parsing
    except (KeyError, ValueError, TypeError, IndexError):
        # ดักจับกรณีโครงสร้าง JSON ไม่ตรงตามสเปก หรือ Parse พัง
        return _error("backend_failed")
    except PermissionError:
        return _error("authentication_failed")
    except (ConnectionError, requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return _error("connection_failed")  # requests ConnectionError ไม่ใช่ subclass ของ built-in
    except Exception:
        return _error("backend_failed")

def plan_interface(
    router,
    desired_interface,
    http_get=None,
):
    """Return create/update/no_change plan using RESTCONF status."""

    # 1. ประกาศฟังก์ชันย่อยสำหรับส่งไปเป็น callback
    def fetch_state(r, name):
        return get_interface_state(r, name, http_get)

    # 2. ส่ง fetch_state และ return ผลลัพธ์ออกไปทันที
    return planning.plan_interface(router, desired_interface, fetch_state)


def apply_interface(
    router,
    desired_interface,
    http_put=None,
):
    """Apply complete desired interface state using RESTCONF."""
    http_put = http_put or (lambda u, json: requests.put(u, json=json, auth=_auth(), verify=False, timeout=TIMEOUT,
                                                         headers={"Content-Type": "application/yang-data+json",
                                                                  "Accept": "application/yang-data+json"}))  # real transport
    try:
        number, ip = _native_args(desired_interface)
    except (ValueError, TypeError, KeyError, AttributeError):
        # ipv4 / ชื่อ interface ผิดรูปแบบ → ยังไม่ได้ติดต่อ router
        return _error("backend_failed")

    url = (f"https://{router}/restconf/data/"
           f"Cisco-IOS-XE-native:native/interface/Loopback={number}")
     #TODO: ip → address → primary → address / mask (เป็น str)
    payload = {
        "Cisco-IOS-XE-native:Loopback": {
            "name": number,  # int
            "description": str(desired_interface["description"]),
            "ip": {
                "address": {
                    "primary": {
                        "address": str(ip.ip),  # IP address (str)
                        "mask": str(
                            ip.network.netmask
                        ),  # Subnet mask (str)
                    }
                }
            },
        }
    }

    #TODO: admin_state == "down" → payload[...]["shutdown"] = [None] "up" → ห้ามมี key shutdown เลย
    if desired_interface.get("admin_state") == "down":
        payload["Cisco-IOS-XE-native:Loopback"]["shutdown"] = [None]
    
    #TODO: 200/201/204 → {"status":"ok","result":"applied"}
    #       401/403 → authentication_failed, อื่น ๆ → backend_failed
    try:
        response = http_put(url, json=payload)
        if response.status_code in (200, 201, 204):
            return {"status": "ok", "result": "applied"}
        elif response.status_code in (401, 403):
            return _error("authentication_failed")
        else:
            return _error("backend_failed")
    except PermissionError:
            return _error("authentication_failed")
    except (ConnectionError, requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return _error("connection_failed")
    except Exception:
        return _error("backend_failed")  # เดิม return exc (ไม่ใช่ dict)

