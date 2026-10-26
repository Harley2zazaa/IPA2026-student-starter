import ipaddress
import os
import re
import subprocess
import tempfile
import json
ANSIBLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ansible")

def _error(code):
    return {"status": "error", "result": code}

#from app.backends.errors import code_for, error
def _real_run_playbook(variables):
    #เขียน variables เป็นไฟล์ JSON ชั่วคราว
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(variables, f)
        vars_file = f.name
    #ทดสอบ เรียก ansible-playbook
    try:
        result = subprocess.run(
            ["ansible-playbook", "-i", os.path.join(ANSIBLE_DIR, "inventory.ini"),
             os.path.join(ANSIBLE_DIR, "apply_interface.yml"),
             "-e", f"ansible_host={variables['router']}",
             "-e", f"@{vars_file}"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "ANSIBLE_HOST_KEY_CHECKING": "False"},
        )
    except subprocess.TimeoutExpired:
        raise ConnectionError("timeout")
    finally:
        os.remove(vars_file)   # ลบไฟล์ชั่วคราว
    # ตรวจผลลัพธ์แล้ว raise exception ให้ตรงประเภท
    out = (result.stdout + result.stderr).lower()
    if result.returncode == 0:
        return
    # 1) credential ถูกปฏิเสธ (Ansible รายงานเป็น UNREACHABLE! + "authentication failed" จึงต้องเช็กก่อน)
    if any(k in out for k in ("authentication failed", "authentication", "permission denied", "invalid credentials")):
        raise PermissionError(out)
    # 2) playbook/inventory พัง (parse/syntax error) ใช้ exit code 4 เหมือน unreachable
    #    แต่ไม่ใช่ปัญหาการเชื่อมต่อ -> backend_failed
    if any(k in out for k in ("yaml parsing failed", "syntax error", "error! ",
                              "could not be found", "no hosts matched",
                              "couldn't resolve module", "the module cisco.ios")):
        raise RuntimeError(out)
    # 3) router ต่อไม่ได้จริง (ข้อความ fatal เท่านั้น เพราะ "unreachable=0" อยู่ใน PLAY RECAP ทุกครั้ง)
    if "unreachable!" in out or "timed out" in out or "connection refused" in out \
            or "no route to host" in out:
        raise ConnectionError(out)
    # 4) ที่เหลือ (task ล้มเหลว, rc 2 ฯลฯ) -> backend_failed
    raise RuntimeError(out)

def apply_interface(
    router,
    desired_interface,
    run_playbook=None, #run_playbook: function ที่ใช้รัน (ถ้าไม่ส่งมาจะใช้ของจริง)
):
    """Apply complete desired interface state using Ansible."""
    run_playbook = run_playbook or _real_run_playbook # ถ้าไม่ส่ง mock มา ให้ใช้ _real_run_playbook (pattern แบบ dependency injection)
    try:
        name = desired_interface["name"]
        if not isinstance(name, str) or not re.fullmatch(r"Loopback\d+", name):
            raise ValueError("unsupported interface name")
        ip = ipaddress.IPv4Interface(desired_interface["ipv4"])
        variables = {
            "router": router,
            "interface_name": name,
            "description": str(desired_interface["description"]),
            "ipv4_address": str(ip.ip),
            "netmask": str(ip.network.netmask),
            "shutdown": desired_interface["admin_state"] == "down",   # bool
        }
    except (ValueError, TypeError, KeyError, AttributeError):
        return _error("backend_failed")
    try:
        run_playbook(variables)         # ต้องเรียกครั้งเดียว
    except PermissionError:
        return _error("authentication_failed")
    except (ConnectionError, TimeoutError):
        return _error("connection_failed")
    except Exception:
        return _error("backend_failed")  # เดิม return exc (ไม่ใช่ dict)
    return {"status": "ok", "result": "applied"}