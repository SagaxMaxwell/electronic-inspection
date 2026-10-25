from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class ConfigWord:
    value: bytes
    name: str = field(default_factory=lambda: uuid4().hex)
    description: str | None = None


@dataclass
class DtcPolicy:
    dtc_table: dict[int, str] = field(default_factory=dict)
    whitelist: set[int] = field(default_factory=set)


@dataclass
class SensorUpgradePolicy:
    sensors: list[str] = field(default_factory=list)
    upgrade_probability: float = 0.5


@dataclass(frozen=True)
class SecurityCredentials:
    secret_key: bytes
    level_1_key: bytes
    level_11_key: bytes
    anti_theft_key: bytes
