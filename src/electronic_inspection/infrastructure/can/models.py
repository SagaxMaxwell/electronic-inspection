from dataclasses import dataclass, field
from pathlib import Path

from cantools.database import can, load_file


@dataclass(frozen=True)
class CanDeviceAddress:
    host: str
    port: int


@dataclass
class CanFrameSpec:
    frame_id: int
    channel_id: int
    name: str
    description: str | None = None
    signals: dict[str, int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class CanFrame:
    arbitration_id: int
    data: bytes
    channel_index: int
    is_extended_id: bool = False
    is_fd: bool = True
    bitrate_switch: bool = True

    def __post_init__(self) -> None:
        max_arbitration_id = 0x1FFFFFFF if self.is_extended_id else 0x7FF
        if not 0 <= self.arbitration_id <= max_arbitration_id:
            raise ValueError("arbitration_id is outside the valid CAN range")
        if self.channel_index < 0:
            raise ValueError("channel_index must not be negative")
        max_length = 64 if self.is_fd else 8
        if len(self.data) > max_length:
            raise ValueError(f"frame data must not exceed {max_length} bytes")
        if self.bitrate_switch and not self.is_fd:
            raise ValueError("bitrate_switch is only valid for CAN FD frames")


@dataclass
class CanMessagePlan:
    dbc_path: Path
    frames: list[CanFrameSpec] = field(default_factory=list)

    @property
    def dbc_database(self) -> can.Database:
        database = load_file(self.dbc_path)
        if not isinstance(database, can.Database):
            raise TypeError(f"{self.dbc_path} is not a CAN database")
        return database

    @property
    def messages(self) -> dict[tuple[int, int], CanFrame]:
        messages: dict[tuple[int, int], CanFrame] = {}
        database = self.dbc_database
        for frame in self.frames:
            try:
                message = database.get_message_by_frame_id(frame.frame_id)
            except KeyError as error:
                raise LookupError(
                    f"CAN/CAN FD message 0x{frame.frame_id:X} not found"
                ) from error

            signals = {
                signal.name: signal.initial if signal.initial is not None else 0
                for signal in message.signals
            }
            signals.update(frame.signals)
            messages[(frame.frame_id, frame.channel_id)] = CanFrame(
                arbitration_id=message.frame_id,
                channel_index=frame.channel_id,
                is_extended_id=message.is_extended_frame,
                is_fd=message.is_fd,
                bitrate_switch=message.is_fd,
                data=message.encode(signals, strict=True),
            )
        return messages
