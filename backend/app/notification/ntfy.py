import httpx

from app.notification.base import Notifier


class NtfyNotifier(Notifier):
    def __init__(self, webhook_url: str): self.webhook_url = webhook_url
    def send(self, event) -> None:
        response = httpx.post(self.webhook_url, content=event.message.encode("utf-8"), headers={"Title": "CapitalVoyage"}, timeout=10)
        response.raise_for_status()

