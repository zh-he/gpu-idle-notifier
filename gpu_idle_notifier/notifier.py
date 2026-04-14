from __future__ import annotations

import logging

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_http_session() -> Session:
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class ServerChanNotifier:
    def __init__(self, send_key: str) -> None:
        self.send_key = send_key
        self.session = build_http_session()

    def send_markdown(self, title: str, markdown_body: str) -> bool:
        if not self.send_key or self.send_key == "your_serverchan_sendkey":
            logging.warning("ServerChan send key is not configured. Skip notification.")
            return False

        url = f"https://sctapi.ftqq.com/{self.send_key}.send"
        try:
            response = self.session.post(
                url,
                data={"title": title, "desp": markdown_body},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            success = payload.get("code") == 0
            if success:
                logging.info("Notification sent: %s", title)
            else:
                logging.warning("Notification failed: %s", payload)
            return success
        except Exception:
            logging.exception("Unexpected error while sending notification.")
            return False
