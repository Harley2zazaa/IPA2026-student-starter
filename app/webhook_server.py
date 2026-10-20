"""Part 4 student implementation."""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from app.integration import process_request
from app.webex_client import WEBEX_API_BASE, WebexClient

log = logging.getLogger(__name__)
MAX_BODY = 1_000_000


class WebexEventHandler:
    def __init__(self, client, bot_person_id, processor=None):
        self.client = client
        self.bot_person_id = bot_person_id
        self.processor = processor or process_request

    def handle_event(self, event):
        # 1) กรอง event (ใช้ .get() ให้ทน event ที่ไม่มี data)
        # ตรวจสอบว่าเป็น message event ชนิด created และมี data["id"]
        resource = event.get("resource")
        event_type = event.get("event")
        data = event.get("data") or {}
        #TODO: resource == "messages" และ event == "created" และมี data["id"]
        #       ไม่ผ่าน → return None (ไม่ส่งข้อความ)
        if resource != "messages" or event_type != "created" or "id" not in data:
            return None
        
        #TODO: data.get("personId") == self.bot_person_id → return None "ก่อน" get_message
        # เช็ก personId จาก data ก่อนเรียก API (ป้องกันบอทประมวลผลข้อความตัวเอง)
        if data.get("personId") == self.bot_person_id:
            return None
        
        # 2) ดึงข้อความ
        #TODO: message = self.client.get_message(message_id)
        #       message["personId"] == bot_person_id → return None (กัน reply loop)
        #       room_id = message["roomId"]            # ตอบห้องนี้เสมอ ห้าม hard-code
        #       files = message.get("files") or []
        message_id = data["id"]
        message = self.client.get_message(message_id)

        # เช็ก personId จากรายละเอียดข้อความอีกครั้งเพื่อกัน Reply Loop
        if message.get("personId") == self.bot_person_id:
            return None

        room_id = message["roomId"]
        files = message.get("files") or []
        text = message.get("text", "")

        # 3) ตัดสินผลตามจำนวนไฟล์
        #TODO: len(files) > 1 → response = {"status":"error","result":"multiple_attachments"}
        #                        (ห้าม download / ห้ามเรียก processor)
        #       len(files) == 0 → processor(mentioned, None, self.bot_person_id)
        #       len(files) == 1 → ดู 12.4.1 ด้านล่าง
        if len(files) > 1:
            # กรณีมีมากกว่า 1 ไฟล์: ห้ามดาวน์โหลด และห้ามเรียก processor
            response = {"status": "error", "result": "multiple_attachments"}

        elif len(files) == 0:
            # กรณีไม่มีไฟล์: ส่งข้อความให้ processor โดยไฟล์เป็น None
            response = self.processor(text, None, self.bot_person_id)

        else: # len(files) == 1
            # กรณีมี 1 ไฟล์: ดาวน์โหลดไฟล์ลงโฟลเดอร์ชั่วคราวแล้วส่งให้ processor
            file_url = files[0]
            file_bytes = self.client.download_file(file_url)

            with TemporaryDirectory() as tmp_dir:
                file_path = Path(tmp_dir) / "downloaded_file"
                file_path.write_bytes(file_bytes)
                
                # เรียก processor ภายใน context manager ของ TemporaryDirectory 
                response = self.processor(text, str(file_path), self.bot_person_id)
        
        # 4) ส่งผลกลับ
        #TODO: self.client.send_message(room_id, json.dumps(response))
        #       return response
        self.client.send_message(room_id, json.dumps(response))
        return response
        pass