"""Part 4 student implementation."""

import os
import time

import requests

WEBEX_API_BASE = 'https://webexapis.com/v1'
TIMEOUT = 10
RETRY_STATUS = (429, 502, 503, 504)  # Webex ชั่วคราวไม่พร้อม → ลองใหม่
MAX_ATTEMPTS = 3


class WebexClient:
    def __init__(self, token=None, session=None):
        #TODO: token = token or os.environ.get("WEBEX_BOT_TOKEN")
        #       ไม่มี → raise PermissionError
        #       self.session = session or requests.Session()
        self.token = token or os.environ.get("WEBEX_BOT_TOKEN")
        if not self.token:
            raise PermissionError("Webex bot token is missing")
        self.session = session or requests.Session()
        pass

    @property
    def headers(self):
        #TODO: {"Authorization": f"Bearer {self.token}"}
        return {"Authorization": f"Bearer {self.token}"}
        pass

    def get_message(self, message_id):
        # fake session: get(url, headers, timeout)
        #TODO: self.session.get(f"{WEBEX_API_BASE}/messages/{message_id}",
        #                        headers=self.headers, timeout=TIMEOUT)
        #       → raise_for_status() → return .json()
        url = f"{WEBEX_API_BASE}/messages/{message_id}"
        response = self.session.get(url, headers=self.headers, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
        pass

    def download_file(self, file_url):
        #TODO: GET file_url ด้วย headers + timeout → raise_for_status() → return .content (bytes)
        response = self.session.get(file_url, headers=self.headers, timeout=TIMEOUT)
        response.raise_for_status()
        return response.content
        pass

    def send_message(self, room_id, text):
        # fake session: post(url, headers, json, timeout)
        #TODO: self.session.post(f"{WEBEX_API_BASE}/messages", headers=self.headers,
        #                         json={"roomId": room_id, "text": text}, timeout=TIMEOUT)
        #       → raise_for_status() → return .json()
        url = f"{WEBEX_API_BASE}/messages"
        payload = {"roomId": room_id, "text": text}
        for attempt in range(MAX_ATTEMPTS):
            response = self.session.post(url, headers=self.headers, json=payload, timeout=TIMEOUT)
            # 429/502/503/504 → รอแล้วลองใหม่ (รอบสุดท้ายปล่อยให้ raise_for_status แจ้ง error)
            if getattr(response, "status_code", None) in RETRY_STATUS and attempt < MAX_ATTEMPTS - 1:
                time.sleep(2 ** attempt)  # รอ 1s, 2s
                continue
            break
        response.raise_for_status()
        return response.json()
        pass