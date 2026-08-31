from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, event) -> None:
        raise NotImplementedError


class NullNotifier(Notifier):
    def send(self, event) -> None:
        return None
