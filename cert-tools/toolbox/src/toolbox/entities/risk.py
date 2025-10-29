from enum import Enum


class Risk(str, Enum):
    STABLE = "stable"
    CANDIDATE = "candidate"
    BETA = "beta"
    EDGE = "edge"

    @classmethod
    def validate(cls, value: str) -> bool:
        try:
            Risk(value.lower())
            return True
        except ValueError:
            return False
