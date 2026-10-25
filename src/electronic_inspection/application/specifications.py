from dataclasses import dataclass

from electronic_inspection.domain.enums import MdcMode
from electronic_inspection.domain.values import ConfigWord


@dataclass(frozen=True)
class EcuResetSpec:
    reset_type: int = 0x01
    ready_timeout: float = 45.0

    def __post_init__(self) -> None:
        if not 0 <= self.reset_type <= 0xFF:
            raise ValueError("reset_type must fit in one byte")
        if self.ready_timeout <= 0:
            raise ValueError("ready_timeout must be positive")


@dataclass(frozen=True)
class SecurityAccessSpec:
    seed_sub_function: int = 0x01

    def __post_init__(self) -> None:
        if not 0x01 <= self.seed_sub_function <= 0x41:
            raise ValueError("seed_sub_function must be between 0x01 and 0x41")
        if self.seed_sub_function % 2 == 0:
            raise ValueError("seed_sub_function must be odd")


@dataclass(frozen=True)
class DidWriteSpec:
    identifier: int
    data: bytes

    def __post_init__(self) -> None:
        if not 0 <= self.identifier <= 0xFFFF:
            raise ValueError("identifier must fit in two bytes")


@dataclass(frozen=True)
class ConfigWordWriteSpec:
    config_word: ConfigWord
    identifier: int

    def __post_init__(self) -> None:
        if not 0 <= self.identifier <= 0xFFFF:
            raise ValueError("identifier must fit in two bytes")


@dataclass(frozen=True)
class RoutineStartSpec:
    data: bytes
    routine_id: int

    def __post_init__(self) -> None:
        if not 0 <= self.routine_id <= 0xFFFF:
            raise ValueError("routine_id must fit in two bytes")


@dataclass(frozen=True)
class ModeSwitchSpec:
    mode: MdcMode
    identifier: int

    def __post_init__(self) -> None:
        if not 0 <= self.identifier <= 0xFFFF:
            raise ValueError("identifier must fit in two bytes")
