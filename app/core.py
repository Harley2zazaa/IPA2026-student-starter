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
        return _error("invalid_yaml")

    if type(data.get("version")) is not int or data["version"] != 1: # Check Version  (.get กัน KeyError, != 1 กัน 0/-1)
        return _error("invalid_version")
    
    #router: missing_router, then invalid_router if it is not one of the allowed router addresses.
    if "router" not in data : 
        return _error("missing_router")
    if not isinstance(data["router"], str) or data["router"] not in ALLOWED_ROUTERS:
        return _error("invalid_router")

    # method: missing_method, then invalid_method if unknown.
    if "method" not in data:
        return _error("missing_method")
    if not isinstance(data["method"], str) or data["method"] not in CAPABILITIES: # Check Method (isinstance กัน unhashable)
        return _error("invalid_method")

    # action: missing_action, then invalid_action if unsupported by the selected method.
    if "action" not in data:
        return _error("missing_action")
    if not isinstance(data["action"], str) or data["action"] not in CAPABILITIES[data["method"]]:  # Check Action X method
        return _error("invalid_action")

    # desired, desired.interface, and desired.interface.name: missing_desired, missing_interface, or missing_interface_name
    if "desired" not in data or not isinstance(data["desired"], dict):
        return _error("missing_desired")

    if "interface" not in data["desired"] or not isinstance(data["desired"]["interface"], dict):
        return _error("missing_interface")

    if not data["desired"]["interface"].get("name"): #Check Interface name (ไม่มี/ว่าง/None)
        return _error("missing_interface_name")
    # plan and apply only: missing_ipv4, missing_description, missing_admin_state, then invalid_admin_state.
    if data['action'] in FULL_STATE_ACTIONS:
        if "ipv4" not in data["desired"]["interface"]:
            return _error("missing_ipv4")
        if "description" not in data["desired"]["interface"]:
            return _error("missing_description")
        if "admin_state" not in data["desired"]["interface"]:
            return _error("missing_admin_state")
        if not isinstance(data["desired"]["interface"]["admin_state"], str) or data["desired"]["interface"]["admin_state"] not in VALID_ADMIN_STATES:
            return _error("invalid_admin_state")
        
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
