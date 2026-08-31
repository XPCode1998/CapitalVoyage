import httpx

from app.notification.base import Notifier


class FeishuNotifier(Notifier):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, event) -> None:
        self.send_text(event.message)

    def send_text(self, message: str) -> None:
        text = message if message.startswith("【钱途 CapitalVoyage】") else f"【钱途 CapitalVoyage】{message}"
        response = httpx.post(
            self.webhook_url,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=10,
        )
        response.raise_for_status()
        # Feishu may return HTTP 200 even if the webhook verification fails.
        try:
            body = response.json()
        except ValueError:
            return
        code = body.get("code", body.get("StatusCode", 0)) if isinstance(body, dict) else 0
        if code not in (0, None):
            detail = body.get("msg", body.get("StatusMessage", "未知错误"))
            raise RuntimeError(f"飞书机器人拒绝了消息（{code}）：{detail}")
