"""Part 4 student implementation."""

import yaml

from app.core import validate_request
from app.dispatcher import dispatch_request            # tests patch ชื่อนี้ใน module นี้
from app.request_handler import validate_webex_envelope


def process_request(mentioned_people, attachment_path, bot_person_id):
    # 1) ตรวจ envelope → ได้ error ก็คืนทันที (ไม่ dispatch)
    #TODO
    envelope_error = validate_webex_envelope(mentioned_people,attachment_path,bot_person_id)
    if envelope_error is not None:
        return envelope_error
    
    # 2) โหลด YAML "ครั้งเดียว" (attachment_path เป็น Path)
    #    yaml.YAMLError / UnicodeDecodeError → {"status":"error","result":"invalid_yaml"}
    #TODO
    try:
        with open(attachment_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, UnicodeDecodeError):
        return {"status": "error", "result": "invalid_yaml"}
    # 3) validate_request(data) → ถ้า status == "error" คืนทันที
    #TODO
    validation = validate_request(data)
    if validation.get("status") == "error":
        return validation
    # 4) ผ่านทั้งหมดค่อย dispatch และคืนผล backend ตรง ๆ
    #TODO: return dispatch_request(data)
    return dispatch_request(data)
    #       (tests ตรวจว่า dispatch ได้รับ data ตัวเดียวกับที่ parse มา)
    pass