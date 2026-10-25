import logging
from collections.abc import Iterable
from types import TracebackType
from typing import Self

from electronic_inspection.infrastructure.can.models import CanFrame
from electronic_inspection.infrastructure.can.zlg.api import (
    ChannelHandle,
    DeviceHandle,
    ZcanApi,
)
from electronic_inspection.infrastructure.can.zlg.config import (
    ZcanChannelConfig,
    ZcanDeviceConfig,
)

logger = logging.getLogger(__name__)


class ZcanDevice:
    def __init__(
        self,
        api: ZcanApi,
        device_config: ZcanDeviceConfig,
        channel_configs: Iterable[ZcanChannelConfig],
    ) -> None:
        self._api = api
        self._device_config = device_config
        self._channel_configs = tuple(channel_configs)
        if not self._channel_configs:
            raise ValueError("at least one channel must be configured")
        channel_indexes = [config.channel_index for config in self._channel_configs]
        if len(channel_indexes) != len(set(channel_indexes)):
            raise ValueError("channel indexes must be unique")

        self._device_handle: DeviceHandle | None = None
        self._channel_handles: dict[int, ChannelHandle] = {}

    @property
    def is_open(self) -> bool:
        return self._device_handle is not None

    def open(self) -> None:
        if self.is_open:
            raise RuntimeError("ZCAN device is already open")

        logger.info(
            "opening ZCAN device type=%d index=%d",
            self._device_config.device_type,
            self._device_config.device_index,
        )
        device_handle = self._api.open_device(
            device_type=self._device_config.device_type,
            device_index=self._device_config.device_index,
        )

        started_channels: list[ChannelHandle] = []
        try:
            for config in self._channel_configs:
                channel_handle = self._api.initialize_channel(
                    device_handle=device_handle,
                    config=config,
                )
                self._api.start_channel(channel_handle)
                started_channels.append(channel_handle)
                self._channel_handles[config.channel_index] = channel_handle
        except Exception:
            for channel_handle in reversed(started_channels):
                self._api.reset_channel(channel_handle)
            self._channel_handles.clear()
            self._api.close_device(device_handle)
            raise

        self._device_handle = device_handle
        logger.info("ZCAN device opened with %d channels", len(self._channel_handles))

    def close(self) -> None:
        if self._device_handle is None:
            return

        first_error: Exception | None = None
        for channel_handle in reversed(tuple(self._channel_handles.values())):
            try:
                self._api.reset_channel(channel_handle)
            except Exception as error:
                first_error = first_error or error

        self._channel_handles.clear()
        device_handle = self._device_handle
        self._device_handle = None
        try:
            self._api.close_device(device_handle)
        except Exception as error:
            first_error = first_error or error

        logger.info("ZCAN device closed")
        if first_error is not None:
            raise first_error

    def send(self, frame: CanFrame) -> None:
        channel_handle = self._get_channel_handle(frame.channel_index)
        sent_count = self._api.transmit(channel_handle, [frame])
        if sent_count != 1:
            raise RuntimeError(f"expected to send 1 frame, sent {sent_count}")

    def receive(
        self,
        channel_index: int,
        *,
        max_frames: int = 100,
        timeout_ms: int = 100,
    ) -> list[CanFrame]:
        if max_frames <= 0:
            raise ValueError("max_frames must be positive")
        if timeout_ms < 0:
            raise ValueError("timeout_ms must not be negative")
        channel_handle = self._get_channel_handle(channel_index)
        return self._api.receive(channel_handle, max_frames, timeout_ms)

    def _get_channel_handle(self, channel_index: int) -> ChannelHandle:
        if not self.is_open:
            raise RuntimeError("ZCAN device is not open")
        try:
            return self._channel_handles[channel_index]
        except KeyError as error:
            raise ValueError(f"channel {channel_index} is not configured") from error

    def __enter__(self) -> Self:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
