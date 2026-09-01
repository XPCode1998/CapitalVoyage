import httpx

from app.core.enums import AlertEventType
from app.notification.base import Notifier
from app.notification.payload import AlertNotification


class FeishuNotifier(Notifier):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, event) -> None:
        if isinstance(event, AlertNotification):
            self.send_alert_card(event)
            return
        self.send_text(event.message)

    def send_text(self, message: str) -> None:
        text = message if message.startswith("【钱途 CapitalVoyage】") else f"【钱途 CapitalVoyage】{message}"
        self._post({"msg_type": "text", "content": {"text": text}})

    def send_alert_card(self, alert: AlertNotification) -> None:
        ready = alert.event_type == AlertEventType.READY_TO_RETURN.value
        title = "可返航 · READY TO RETURN" if ready else "接近返航 · NEAR RETURN"
        state_text = "可执行" if ready else "持续监控"
        delta_label = "超过目标" if ready else "距目标"
        delta = alert.net_return - alert.target_return if ready else alert.distance_to_target
        delta_text = f"+{self._points(delta)}" if ready else f"还差 {self._points(delta)}"
        footer = (
            "请及时确认返航操作；实际成交以券商行情为准。"
            if ready
            else "尚未满足返航条件，请继续观察行情变化。"
        )
        quote_time = alert.quote_time.strftime("%m-%d %H:%M:%S") if alert.quote_time else "待更新"
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "template": "green" if ready else "orange",
                "title": {"tag": "plain_text", "content": title},
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{alert.symbol} · {alert.security_name}**\n{alert.voyage_no} · 舱位 {alert.slot_no:02d} · {state_text}",
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**当前净收益**\n<font color='{self._return_color(ready)}'>{self._percent(alert.net_return)}</font>"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**目标收益**\n{self._percent(alert.target_return)}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**{delta_label}**\n{delta_text}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**可返航数量**\n{alert.remaining_quantity:,} 份"}},
                    ],
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"参考买一价 **¥{self._price(alert.monitor_price)}**　·　目标参考价 **¥{self._price(alert.target_price)}**",
                    },
                },
                {"tag": "note", "elements": [{"tag": "plain_text", "content": f"行情更新 {quote_time} · 每 {alert.interval_minutes} 分钟更新"}]},
                {"tag": "note", "elements": [{"tag": "plain_text", "content": footer}]},
            ],
        }
        self._post({"msg_type": "interactive", "card": card})

    def _post(self, payload: dict) -> None:
        response = httpx.post(self.webhook_url, json=payload, timeout=10)
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

    @staticmethod
    def _percent(value) -> str:
        return f"{value * 100:+.2f}%"

    @staticmethod
    def _points(value) -> str:
        return f"{value * 100:.2f}pp"

    @staticmethod
    def _price(value) -> str:
        return format(value, "f").rstrip("0").rstrip(".")

    @staticmethod
    def _return_color(ready: bool) -> str:
        return "green" if ready else "orange"
