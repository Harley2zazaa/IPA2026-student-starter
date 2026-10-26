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

invalid = {"status": "error", "result": "invalid_event"}
URL_PATH = "/webhook"  # spec ตายตัว ไม่อ่านจาก env

class WebexEventHandler:
    def __init__(self, client, bot_person_id, processor=None):
        self.client = client
        self.bot_person_id = bot_person_id
        self.processor = processor or process_request

    def handle_event(self, event):
        # 1) กรอง event (ใช้ .get() ให้ทน event ที่ไม่มี data)
        # ตรวจสอบว่าเป็น message event ชนิด created และมี data["id"]
        if not isinstance(event, dict):
            return None
        resource = event.get("resource")
        event_type = event.get("event")
        data = event.get("data") or {}
        if not isinstance(data, dict):
            return None
        #TODO: resource == "messages" และ event == "created" และมี data["id"]
        #       ไม่ผ่าน → return None (ไม่ส่งข้อความ)
        if resource != "messages" or event_type != "created" or not data.get("id"):
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

        room_id = message["roomId"]  # ตอบห้องต้นทางเสมอ ห้าม hard-code
        files = message.get("files") or []
        mentioned_people = message.get("mentionedPeople")

        # 3) ตัดสินผลตามจำนวนไฟล์
        #TODO: len(files) > 1 → response = {"status":"error","result":"multiple_attachments"}
        #                        (ห้าม download / ห้ามเรียก processor)
        #       len(files) == 0 → processor(mentioned, None, self.bot_person_id)
        #       len(files) == 1 → ดู 12.4.1 ด้านล่าง
        if len(files) > 1:
            response = {"status": "error", "result": "multiple_attachments"}

        elif len(files) == 0:
            try:
                response = self.processor(mentioned_people, None, self.bot_person_id)
            except Exception:  # กัน bot เงียบ
                log.exception("failed to process request")
                response = {"status": "error", "result": "backend_failed"}

        else:  # len(files) == 1
            try:
                file_bytes = self.client.download_file(files[0])

                with TemporaryDirectory() as tmp_dir:
                    file_path = Path(tmp_dir) / "request.yaml"
                    file_path.write_bytes(file_bytes)
                    response = self.processor(
                        mentioned_people, file_path, self.bot_person_id
                    )
            except Exception:  # กัน bot เงียบ (Live นับเป็น timeout)
                log.exception("failed to process request")
                response = {"status": "error", "result": "backend_failed"}
        
        # 4) ส่งผลกลับ
        #TODO: self.client.send_message(room_id, json.dumps(response))
        #       return response
        self.client.send_message(room_id, json.dumps(response))
        return response
        pass

def make_http_handler(submit_event):
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            #TODO: self.path == "/health" → 200 {"status":"ok","result":"healthy"}
            if self.path == "/health":
                self._send_json(200, {"status": "ok", "result": "healthy"})
            else:
                self._send_json(404, {"status": "error", "result": "not_found"})
            # pass

        def do_POST(self):
            #TODO: path ไม่ใช่ "/webhook" → 404
            if self.path != URL_PATH:
                return self._send_json(404, {"status": "error", "result": "not_found"})
            
            # if self.path != "/webhook":
            #     return self._send_json(404, {"status": "error", "result": "not_found"})
    
            #TODO: อ่าน Content-Length (ไม่มี/ไม่ใช่ตัวเลข/ติดลบ/0/เกิน MAX_BODY → 400 invalid_event)
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError: # none
                return self._send_json(400, invalid)
            if length < 1 or length > MAX_BODY: #  below 0 over max body
                return self._send_json(400, invalid)
            #TODO: body = self.rfile.read(length); json.loads → ไม่ใช่ dict หรือ parse พัง → 400
            try:
                event = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError): # parse พัง
                return self._send_json(400, invalid)  
            if not isinstance(event, dict): # not dict
                return self._send_json(400, invalid)
            #TODO: submit_event(event)  แล้วตอบ 200 {"status":"ok","result":"accepted"}
            #       (ห้ามรอผลประมวลผล และห้าม submit ถ้า body ไม่ถูกต้อง)
            submit_event(event)
            self._send_json(200, {"status": "ok", "result": "accepted"})
            # pass

        def log_message(self, format, *args):    # ปิด log ซ้ำซ้อนของ http.server
            log.debug(format, *args)

    return Handler


def main():
    logging.basicConfig(level=logging.INFO)
    host = os.environ.get("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.environ.get("WEBHOOK_PORT", "8000"))

    client = WebexClient()
    #TODO: หา bot_person_id ด้วย GET {WEBEX_API_BASE}/people/me
    #       (ใช้ client.session.get(..., headers=client.headers, timeout=10).json()["id"])
    response = client.session.get(
        f"{WEBEX_API_BASE}/people/me",
        headers=client.headers,
        timeout=10,
    )
    response.raise_for_status()
    bot_person_id = response.json()["id"]

    handler = WebexEventHandler(client, bot_person_id)

    executor = ThreadPoolExecutor(max_workers=1)   # ทีละคำขอ กัน router ซ้อนกัน
    def run_event(event):
        try:
            handler.handle_event(event)
        except Exception:
            log.exception("failed to handle event")
            
    def submit_event(event):
        #TODO: executor.submit(...) โดยห่อด้วย try/except + log
        #       เพื่อไม่ให้ exception ใน thread หายเงียบ
        try:
            executor.submit(run_event, event)
        except Exception:
            log.exception("failed to submit event")
        # pass
    server = ThreadingHTTPServer((host, port), make_http_handler(submit_event))
    log.info("listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()