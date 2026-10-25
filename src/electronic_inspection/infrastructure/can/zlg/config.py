from dataclasses import dataclass
from enum import IntEnum


class ZcanDeviceType(IntEnum):
    USBCANFD_200U = 41
    USBCANFD_100U = 42
    USBCANFD_MINI = 43
    USBCANFD_800U = 59
    USBCANFD_400U = 76
    USBCANFD_800H = 85


@dataclass(frozen=True)
class ZcanDeviceConfig:
    device_type: ZcanDeviceType = ZcanDeviceType.USBCANFD_800U
    device_index: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.device_type, ZcanDeviceType):
            raise TypeError("device_type must be a ZcanDeviceType")
        if self.device_index < 0:
            raise ValueError("device_index must not be negative")


@dataclass(frozen=True)
class ZcanChannelConfig:
    channel_index: int
    nominal_bitrate: int = 500_000
    data_bitrate: int = 2_000_000
    enable_termination_resistor: bool = True

    def __post_init__(self) -> None:
        if self.channel_index < 0:
            raise ValueError("channel_index must not be negative")
        if self.nominal_bitrate <= 0:
            raise ValueError("nominal_bitrate must be positive")
        if self.data_bitrate <= 0:
            raise ValueError("data_bitrate must be positive")
