MANAGED = ("ipv4", "description", "admin_state")


def build_plan(desired_interface, current_interface):
    if current_interface is None:
        # ยังไม่มี interface บน router → create
        operation = "create"
        changes = {f: {"to": desired_interface[f]} for f in MANAGED}
    else:
        # มีอยู่แล้ว → เทียบทีละฟิลด์ เก็บเฉพาะที่ต่าง
        changes = {
            f: {"from": current_interface.get(f), "to": desired_interface[f]}
            for f in MANAGED
            if current_interface.get(f) != desired_interface[f]
        }
        operation = "update" if changes else "no_change"

    return {
        "status": "ok",
        "result": "planned",
        "operation": operation,
        "changes": changes,
    }