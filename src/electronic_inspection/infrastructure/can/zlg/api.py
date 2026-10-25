from collections.abc import Sequence
from typing import Protocol

from electronic_inspection.infrastructure.can.models import CanFrame
from electronic_inspection.infrastructure.can.zlg.config import ZcanChannelConfig

type DeviceHandle = int
type ChannelHandle = int


class ZcanApi(Protocol):
    def open_device(self, device_type: int, device_index: int) -> DeviceHandle: ...

    def close_device(self, device_handle: DeviceHandle) -> None: ...

    def initialize_channel(
        self,
        device_handle: DeviceHandle,
        config: ZcanChannelConfig,
    ) -> ChannelHandle: ...

    def start_channel(self, channel_handle: ChannelHandle) -> None: ...

    def reset_channel(self, channel_handle: ChannelHandle) -> None: ...

    def transmit(
        self,
        channel_handle: ChannelHandle,
        frames: Sequence[CanFrame],
    ) -> int: ...

    def receive(
        self,
        channel_handle: ChannelHandle,
        max_frames: int,
        timeout_ms: int,
    ) -> list[CanFrame]: ...
