from typing import NamedTuple


class BooleanResult(NamedTuple):
    ok: bool
    message: str | None = None

    def __bool__(self) -> bool:
        return self.ok

    def __str__(self) -> str:
        return f"[{self.ok}]" + (f" {self.message}" if self.message else "")
