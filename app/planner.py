MANAGED = ("ipv4", "description", "admin_state")

def build_plan(desired_interface, current_interface):
    """
    Compare desired interface state with normalized current state
    and return a plan according to specs/plan-spec-v1.md.
    """
    # TODO: implement
    if current_interface is None: # Don't have Interface
        operation = "create"
        changes = {f: {"to": desired_interface[f]} for f in MANAGED} # Fetch Data to Create Interface
    else: # Interface already exists
        changes = {f: {"from": current_interface.get(f), "to": desired_interface[f]} # <- Dictionary Comprehension ที่นิยมใช้ในการทำ Diff / Delta Tracking
                   for f in MANAGED if current_interface.get(f) != desired_interface[f]}
        operation = "update" if changes else "no_change"
    return {"status": "ok", "result": "planned","operation": operation, "changes": changes}
    pass
