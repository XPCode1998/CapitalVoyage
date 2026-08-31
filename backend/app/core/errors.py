from __future__ import annotations


class DomainError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def domain_error(code: str, message: str, status_code: int = 400) -> DomainError:
    return DomainError(code, message, status_code)

