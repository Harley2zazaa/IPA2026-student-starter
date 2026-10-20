import yaml

ALLOWED_ROUTERS = {f"10.0.29.{n}" for n in range(101, 106)}

CAPABILITIES = { # Condition
    "restconf": {"status", "plan", "apply"},
    "netconf": {"status", "plan", "apply"},
    "ansible": {"apply"},
    "netmiko-textfsm": {"status", "delete"},
}

FULL_STATE_ACTIONS = {"plan", "apply"}
VALID_ADMIN_STATES = {"up", "down"}

def _error(code):
    return {"status": "error", "result": code}

def validate_request(data):
    """
    Validate one IPA2026 desired-state request.

    Return a response dictionary according to
    specs/response-spec-v1.md.
    """
    # TODO: implement
    # Dict Checking
    if not isinstance(data, dict) : # It is dict ?
        return _error("no_yaml")

    if type(data["version"]) is not int or data["version"] > 1: # Check Version
        return _error("invalid_version")

    if "router" not in data : # Check Router
        return _error("missing_router")
         
    if data["method"] not in CAPABILITIES: # Check Method
        return _error("invalid_method")

    if data["action"] not in CAPABILITIES[data["method"]]:  # Check Action X method
        return _error("invalid_action")

    # desire / interface / name / plan / apply
    if "name" not in data["desired"]["interface"]: #Check Interface name
        return _error("missing_interface_name")

    return {"status": "ok", "result": "accepted"}




def process_request_file(path):
    """
    Read a YAML request file, validate it,
    and return a response dictionary.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, UnicodeDecodeError):
        # หากเกิดข้อผิดพลาดในการอ่านไฟล์หรือแปลง YAML ให้ส่ง error 'invalid_yaml'
        return _error("invalid_yaml")
    # ส่ง data ไปให้ validate_request ประมวลผลต่อ
    return validate_request(data)
