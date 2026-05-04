from __future__ import annotations

import logging

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import NotifyProviderConfig


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
        self.send_key = _normalize_send_key(send_key)
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


class FeishuNotifier:
    def __init__(self, webhook: str) -> None:
        self.webhook = (webhook or "").strip()
        self.session = build_http_session()

    def send_markdown(self, title: str, markdown_body: str) -> bool:
        if not self.webhook:
            logging.warning("Feishu webhook is not configured. Skip notification.")
            return False

        # Feishu custom bots accept plain text reliably; markdown is kept in the text body.
        text = f"{title}\n\n{markdown_body}"
        payload = {
            "msg_type": "text",
            "content": {
                "text": text,
            },
        }
        try:
            response = self.session.post(self.webhook, json=payload, timeout=10)
            response.raise_for_status()
            payload = response.json()
            success = payload.get("code") == 0
            if success:
                logging.info("Feishu notification sent: %s", title)
            else:
                logging.warning("Feishu notification failed: %s", payload)
            return success
        except Exception:
            logging.exception("Unexpected error while sending Feishu notification.")
            return False


class WebhookNotifier:
    def __init__(self, webhook: str) -> None:
        self.webhook = (webhook or "").strip()
        self.session = build_http_session()

    def send_markdown(self, title: str, markdown_body: str) -> bool:
        if not self.webhook:
            logging.warning("Webhook URL is not configured. Skip notification.")
            return False

        payload = {
            "title": title,
            "text": markdown_body,
            "markdown": markdown_body,
        }
        try:
            response = self.session.post(self.webhook, json=payload, timeout=10)
            response.raise_for_status()
            logging.info("Webhook notification sent: %s", title)
            return True
        except Exception:
            logging.exception("Unexpected error while sending webhook notification.")
            return False


class MultiNotifier:
    def __init__(self, notifiers: list[object]) -> None:
        self.notifiers = notifiers

    def send_markdown(self, title: str, markdown_body: str) -> bool:
        if not self.notifiers:
            logging.warning("No notification provider configured. Skip notification.")
            return False

        success = False
        for notifier in self.notifiers:
            send = getattr(notifier, "send_markdown")
            success = bool(send(title, markdown_body)) or success
        return success


def build_notifier(providers: list[NotifyProviderConfig]) -> MultiNotifier:
    notifiers: list[object] = []
    for provider in providers:
        if provider.type == "serverchan":
            notifiers.append(ServerChanNotifier(provider.send_key))
        elif provider.type == "feishu":
            notifiers.append(FeishuNotifier(provider.webhook))
        elif provider.type == "webhook":
            notifiers.append(WebhookNotifier(provider.webhook))
        else:
            logging.warning("Unsupported notification provider ignored: %s", provider.type)
    return MultiNotifier(notifiers)


def _normalize_send_key(send_key: str) -> str:
    key = (send_key or "").strip()
    if "ftqq.com" in key:
        key = key.split("?", 1)[0].rstrip("/")
        key = key.rsplit("/", 1)[-1]
    if key.endswith(".send"):
        key = key[: -len(".send")]
    return key
