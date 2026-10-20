from app.core import process_request_file, _error
# def _error(code):
#     return {"status": "error", "result": code}

def validate_webex_envelope(
    mentioned_people,
    attachment_path,
    bot_person_id,
):
    """
    Validate the target bot's actual mention and YAML attachment.
    Return an error response, or None when the envelope is valid.
    """
    # TODO: implement according to the published specifications
    if (not isinstance(bot_person_id, str) or not bot_person_id or not isinstance(mentioned_people, list) or bot_person_id not in mentioned_people):
        return _error("missing_bot_mention")
    
    # bot_person_id เป็น str และไม่ว่าง
    # - mentioned_people เป็น list  (กัน None และ "BOT")
    # - bot_person_id อยู่ใน mentioned_people

    if attachment_path is None: # Check attachfile is null ?
        return _error("no_yaml")
    return None


def handle_webex_request(
    mentioned_people,
    attachment_path,
    bot_person_id,
):
    """
    Validate the envelope, then validate the attached YAML request.
    Return a response dictionary. Do not dispatch to a router.
    """
    # TODO: implement according to the published specifications
    # Step 1: ตรวจสอบ Envelope ด้วย validate_webex_envelope
    envelope_error = validate_webex_envelope(mentioned_people, attachment_path, bot_person_id)
    # ถ้าตรวจพบ Error ให้ส่ง Error กลับไปทันที
    if envelope_error:
        return envelope_error

    # Step 2: ถ้าไม่พบ Error ให้ส่งไฟล์แนบไปตรวจใน core.py
    return process_request_file(attachment_path)
