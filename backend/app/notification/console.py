import logging

from app.notification.base import Notifier


class ConsoleNotifier(Notifier):
    def send(self, event) -> None:
        logging.getLogger("capital_voyage.alert").info("%s", event.message)

