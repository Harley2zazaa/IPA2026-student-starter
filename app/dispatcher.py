"""Part 4 student implementation."""

from app.backends import ansible, netconf, netmiko_textfsm, restconf
ROUTES = {
    ("restconf", "status"): (restconf, "get_interface_state"),
    ("restconf","plan"): (restconf, "plan_interface"),
    ("restconf","apply"): (restconf, "apply_interface"),
    ("netconf","status"): (netconf, "get_interface_state"),
    ("netconf","plan"): (netconf, "plan_interface"),
    ("netconf","apply"): (netconf, "apply_interface"),
    ("ansible","apply"): (ansible, "apply_interface"),
    ("netmiko-textfsm","status"): (netmiko_textfsm, "get_interface_state"),
    ("netmiko-textfsm","delete"): (netmiko_textfsm, "delete_interface"),
    #TODO: เติมให้ครบ 9 คู่ (ดูตารางใน README)
}

def dispatch_request(data):
    module, name = ROUTES[(data["method"], data["action"])]
    function = getattr(module, name)            # ค้นหาตอนเรียก
    interface = data["desired"]["interface"]
    router = data["router"]

    #TODO: action เป็น status/delete → function(router, interface["name"])
    #       action เป็น plan/apply    → function(router, interface)
    #       (ส่ง positional 2 ตัวเท่านั้น)
    if data["action"] in ("status","delete"):
        return function(router, interface["name"])
    return function(router, interface)
    pass
