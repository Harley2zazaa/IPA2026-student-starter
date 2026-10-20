import ipaddress
import os
import subprocess
import tempfile
import json
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
            ["ansible-playbook", "-i", "ansible/inventory.ini",
             "ansible/apply_interface.yml",
             "-e", f"ansible_host={variables['router']}",
             "-e", f"@{vars_file}"],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "ANSIBLE_HOST_KEY_CHECKING": "False"},
        )
    except subprocess.TimeoutExpired:
        raise ConnectionError("timeout")
    finally:
        os.remove(vars_file)   # ลบไฟล์ชั่วคราว
    # ตรวจผลลัพธ์แล้ว raise exception ให้ตรงประเภท -> Throw Erro ไปให้ตัวก่อนหน้า
    out = (result.stdout + result.stderr).lower() # บรรทัดนี้เป็นการ รวมข้อความที่ ansible-playbook พิมพ์ออกมาทั้งหมด แล้วแปลงเป็นตัวพิมพ์เล็ก เพื่อเอาไปค้นหาคำสำคัญ
    if "authentication" in out or "permission denied" in out:
        raise PermissionError(out)
    if result.returncode == 4: 
        raise ConnectionError(out)
    if result.returncode != 0:
        raise RuntimeError(out)

def apply_interface(
    router,
    desired_interface,
    run_playbook=None, #run_playbook: function ที่ใช้รัน (ถ้าไม่ส่งมาจะใช้ของจริง)
):
    """Apply complete desired interface state using Ansible."""
    run_playbook = run_playbook or _real_run_playbook # ถ้าไม่ส่ง mock มา ให้ใช้ _real_run_playbook (pattern แบบ dependency injection)
    ip = ipaddress.IPv4Interface(desired_interface["ipv4"])
    variables = {
        "router": router,
        "interface_name": desired_interface["name"],
        "description": desired_interface["description"],
        "ipv4_address": str(ip.ip),
        "netmask": str(ip.network.netmask),
        "shutdown": desired_interface["admin_state"] == "down",   # bool
    }
    try:
        run_playbook(variables)         # ต้องเรียกครั้งเดียว
    except PermissionError:
        return _error("authentication_failed")
    except ConnectionError:
        return _error("connection_failed")
    except RuntimeError:
        return _error("backend_failed")
    except Exception as exc:
        return exc
    return {"status": "ok", "result": "applied"}
    raise NotImplementedError
