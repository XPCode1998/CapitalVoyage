import httpx

from app.notification.base import Notifier


class FeishuNotifier(Notifier):
    def __init__(self, webhook_url: str): self.webhook_url = webhook_url
    def send(self, event) -> None:
        response = httpx.post(self.webhook_url, json={"msg_type": "text", "content": {"text": event.message}}, timeout=10)
        response.raise_for_status()

