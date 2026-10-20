from app.planner import build_plan

def plan_interface(router,desired_interface,get_interface_state,):
    # get_interface_state รับ (router, interface_name) เท่านั้น
    #TODO: 1) status = get_interface_state(router, desired_interface["name"])
    #       2) status["status"] == "error" → return status (ไม่แก้)
    #       3) result == "found" → current = status["interface"]; ไม่งั้น current = None
    #       4) return build_plan(desired_interface, current)
    """Build a Part 2 plan from backend status."""
    status = get_interface_state(router, desired_interface["name"])
    if status == "error":
        return status 
    if status["status"] == "found":
        current = status["interface"]
    else:
        current = None
    
    return build_plan(desired_interface, current)

    raise NotImplementedError
