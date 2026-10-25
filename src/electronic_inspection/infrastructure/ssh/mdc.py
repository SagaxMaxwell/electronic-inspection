import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from paramiko import AutoAddPolicy, SSHClient
from ping3 import ping

from electronic_inspection.application.exceptions import MdcStartupTimeoutError
from electronic_inspection.application.ports import MdcPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SshConnectionConfig:
    host: str
    port: int = 22
    username: str = "root"
    password: str | None = None
    connect_timeout: float = 10.0
    allow_unknown_host: bool = False


@contextmanager
def ssh_client_context(config: SshConnectionConfig) -> Iterator[SSHClient]:
    logger.debug("opening SSH connection to %s:%d", config.host, config.port)
    client = SSHClient()
    client.load_system_host_keys()
    if config.allow_unknown_host:
        client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(
        hostname=config.host,
        username=config.username,
        password=config.password,
        port=config.port,
        timeout=config.connect_timeout,
    )
    try:
        logger.debug("SSH connection opened to %s:%d", config.host, config.port)
        yield client
    finally:
        client.close()
        logger.debug("SSH connection closed to %s:%d", config.host, config.port)


class SshMdcAdapter(MdcPort):
    def __init__(self, ssh_config: SshConnectionConfig) -> None:
        self._ssh_config = ssh_config

    def reboot(self) -> None:
        logger.info("rebooting MDC at %s", self._ssh_config.host)
        self._execute_command(command="reboot")

    def wait_until_reachable(self, timeout: float) -> None:
        logger.info(
            "waiting for MDC at %s to become reachable",
            self._ssh_config.host,
        )
        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            response_time = ping(
                self._ssh_config.host,
                timeout=min(1.0, remaining),
            )
            if response_time is not None and response_time is not False:
                logger.info("MDC at %s is reachable", self._ssh_config.host)
                return

            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.5, remaining))

        raise MdcStartupTimeoutError(
            f"timed out after {timeout:g}s waiting for MDC at "
            f"{self._ssh_config.host} to become reachable"
        )

    def collect_logs(self, local_path: Path) -> None:
        raise NotImplementedError("MDC log collection is not implemented")

    def _execute_command(self, command: str) -> str:
        logger.debug(
            "executing SSH command at %s",
            self._ssh_config.host,
        )
        with ssh_client_context(config=self._ssh_config) as client:
            _, stdout, stderr = client.exec_command(command)
            output = stdout.read().decode("utf-8")
            error_output = stderr.read().decode("utf-8")
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                details = error_output.strip() or "no error output"
                raise RuntimeError(
                    f"command {command!r} failed with exit status {exit_status}: "
                    f"{details}"
                )
            logger.debug("SSH command completed at %s", self._ssh_config.host)
            return output
