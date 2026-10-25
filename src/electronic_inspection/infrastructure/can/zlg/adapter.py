import logging
from collections.abc import Iterable
from threading import Event, Lock, Thread

from electronic_inspection.application.ports import CanfdPort
from electronic_inspection.infrastructure.can.models import CanFrame
from electronic_inspection.infrastructure.can.zlg.device import ZcanDevice

logger = logging.getLogger(__name__)


class ZcanWakeupAdapter(CanfdPort):
    def __init__(
        self,
        device: ZcanDevice,
        frames: Iterable[CanFrame],
        *,
        interval: float = 0.1,
    ) -> None:
        self._device = device
        self._frames = tuple(frames)
        self._interval = interval
        if not self._frames:
            raise ValueError("at least one wakeup frame must be configured")
        if self._interval <= 0:
            raise ValueError("interval must be positive")

        self._stop_event = Event()
        self._state_lock = Lock()
        self._sender_thread: Thread | None = None
        self._background_error: Exception | None = None
        self._owns_device = False

    def start_wakeup(self) -> None:
        with self._state_lock:
            if self._sender_thread is not None and self._sender_thread.is_alive():
                return

            self._background_error = None
            self._stop_event.clear()
            if not self._device.is_open:
                self._device.open()
                self._owns_device = True

            try:
                self._send_frames()
            except Exception:
                self._close_owned_device()
                raise

            self._sender_thread = Thread(
                target=self._send_loop,
                name="zcan-wakeup-sender",
                daemon=True,
            )
            self._sender_thread.start()
            logger.info(
                "CAN wakeup started with %d frames at %.3fs interval",
                len(self._frames),
                self._interval,
            )

    def stop_wakeup(self) -> None:
        with self._state_lock:
            sender_thread = self._sender_thread
            self._sender_thread = None
            self._stop_event.set()

        if sender_thread is not None:
            sender_thread.join()

        close_error: Exception | None = None
        try:
            self._close_owned_device()
        except Exception as error:
            close_error = error

        background_error = self._background_error
        self._background_error = None
        logger.info("CAN wakeup stopped")

        if background_error is not None:
            raise RuntimeError("CAN wakeup sender failed") from background_error
        if close_error is not None:
            raise close_error

    def _send_loop(self) -> None:
        try:
            while not self._stop_event.wait(self._interval):
                self._send_frames()
        except Exception as error:
            self._background_error = error
            self._stop_event.set()
            logger.exception("CAN wakeup sender failed")

    def _send_frames(self) -> None:
        for frame in self._frames:
            self._device.send(frame)

    def _close_owned_device(self) -> None:
        if self._owns_device:
            self._owns_device = False
            self._device.close()
