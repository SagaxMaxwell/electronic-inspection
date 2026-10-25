import logging
from collections.abc import Mapping
from pathlib import Path

from electronic_inspection.application.exceptions import (
    UnsupportedModeError,
    VerificationError,
)
from electronic_inspection.application.ports import (
    MdcPort,
    PackagePort,
    ProvisioningCryptoPort,
    SecurityAccessPort,
    UdsPort,
)
from electronic_inspection.application.specifications import (
    ConfigWordWriteSpec,
    DidWriteSpec,
    EcuResetSpec,
    ModeSwitchSpec,
    RoutineStartSpec,
    SecurityAccessSpec,
)
from electronic_inspection.domain.enums import MdcMode

logger = logging.getLogger(__name__)
ModeValues = Mapping[MdcMode, bytes]


class ElectronicInspectionService:
    def __init__(
        self,
        uds_port: UdsPort,
        mdc_port: MdcPort,
        package_port: PackagePort,
        provisioning_crypto_port: ProvisioningCryptoPort,
        security_access_port: SecurityAccessPort,
        *,
        mode_values: ModeValues,
    ) -> None:
        self._uds = uds_port
        self._mdc = mdc_port
        self._package = package_port
        self._crypto = provisioning_crypto_port
        self._security_access = security_access_port
        self._mode_values = dict(mode_values)

    def line_flashing(self, package_path: Path) -> None:
        raise NotImplementedError()

    def read_and_verify_did(
        self,
        identifier: int,
        expected: bytes,
        *,
        operation: str | None = None,
    ) -> bytes:
        actual = self._uds.read_data_by_identifier(identifier=identifier)
        if actual != expected:
            raise VerificationError(
                operation=operation or f"DID 0x{identifier:04X}",
                expected=expected,
                actual=actual,
            )
        return actual

    def enter_extended_session(self) -> bytes:
        logger.debug("entering extended diagnostic session")
        return self._uds.diagnostic_session_control(session_type=0x03)

    def security_unlock(
        self,
        spec: SecurityAccessSpec,
    ) -> bytes:
        seed_sub_function = spec.seed_sub_function
        key_sub_function = seed_sub_function + 1
        logger.debug(
            "starting security access: seed=0x%02X, key=0x%02X",
            seed_sub_function,
            key_sub_function,
        )
        self.enter_extended_session()
        seed = self._uds.request_security_seed(level=seed_sub_function)
        key = self._security_access.calculate_key(level=seed_sub_function, seed=seed)
        response = self._uds.send_security_key(level=key_sub_function, key=key)
        logger.debug("security access completed at level 0x%02X", seed_sub_function)
        return response

    def write_did_and_verify(
        self,
        write_spec: DidWriteSpec,
        reset_spec: EcuResetSpec | None = None,
    ) -> bytes:
        self._uds.write_data_by_identifier(
            identifier=write_spec.identifier, data=write_spec.data
        )
        if reset_spec is not None:
            self.reset_and_wait(spec=reset_spec)
        return self.read_and_verify_did(
            identifier=write_spec.identifier,
            expected=write_spec.data,
        )

    def reset_and_wait(self, spec: EcuResetSpec) -> bytes:
        logger.info("resetting ECU with type 0x%02X", spec.reset_type)
        response = self._uds.ecu_reset(reset_type=spec.reset_type)
        self._mdc.wait_until_reachable(
            timeout=spec.ready_timeout,
        )
        logger.info("ECU reset completed")
        return response

    def write_vin(self, vin: bytes) -> bytes:
        logger.info("writing VIN through DID 0xF190")
        actual = self._uds.write_data_by_identifier(identifier=0xF190, data=vin)
        logger.info("VIN written through DID 0xF190")
        return actual

    def read_vin(self) -> bytes:
        return self._uds.read_data_by_identifier(identifier=0xF190)

    def clear_dtc(self, group_of_dtc: bytes = b"\xff\xff\xff") -> bytes:
        logger.info("clearing diagnostic information")
        return self._uds.clear_diagnostic_information(group_of_dtc=group_of_dtc)

    def read_dtc_information(
        self,
        sub_function: int = 0x02,
        status_mask: int = 0xFF,
    ) -> bytes:
        return self._uds.read_dtc_information(
            sub_function=sub_function,
            status_mask=status_mask,
        )

    def control_dtc_setting(self, setting: int) -> bytes:
        return self._uds.control_dtc_setting(setting=setting)

    def routine_control(
        self,
        routine_id: int,
        data: bytes = b"",
        control_type: int = 0x01,
    ) -> bytes:
        return self._uds.routine_control(
            control_type=control_type,
            routine_id=routine_id,
            data=data,
        )

    def write_config_word(
        self,
        write_spec: ConfigWordWriteSpec,
        reset_spec: EcuResetSpec | None = None,
    ) -> bytes:
        logger.info("writing configuration word to DID 0x%04X", write_spec.identifier)
        self.enter_extended_session()
        self._uds.write_data_by_identifier(
            identifier=write_spec.identifier,
            data=write_spec.config_word.value,
        )
        if reset_spec is not None:
            self.reset_and_wait(spec=reset_spec)
        actual = self.read_and_verify_did(
            identifier=write_spec.identifier,
            expected=write_spec.config_word.value,
            operation=f"configuration word at DID 0x{write_spec.identifier:04X}",
        )
        logger.info("configuration word verified for DID 0x%04X", write_spec.identifier)
        return actual

    def write_level_1_key(
        self,
        security_access_spec: SecurityAccessSpec,
        routine_spec: RoutineStartSpec,
    ) -> bytes:
        logger.info(
            "provisioning level 1 key through routine 0x%04X",
            routine_spec.routine_id,
        )
        encrypted = self._crypto.encrypt_level_1_key(routine_spec.data)
        self.security_unlock(spec=security_access_spec)
        return self.routine_control(routine_id=routine_spec.routine_id, data=encrypted)

    def write_level_11_key(
        self,
        security_access_spec: SecurityAccessSpec,
        routine_spec: RoutineStartSpec,
    ) -> bytes:
        logger.info(
            "provisioning level 11 key through routine 0x%04X",
            routine_spec.routine_id,
        )
        encrypted = self._crypto.encrypt_level_11_key(routine_spec.data)
        self.security_unlock(spec=security_access_spec)
        return self.routine_control(routine_id=routine_spec.routine_id, data=encrypted)

    def write_anti_theft_key(
        self,
        security_access_spec: SecurityAccessSpec,
        routine_spec: RoutineStartSpec,
    ) -> bytes:
        self.security_unlock(spec=security_access_spec)
        return self.routine_control(
            routine_id=routine_spec.routine_id, data=routine_spec.data
        )

    def filling_device_certificate(
        self,
        security_access_spec: SecurityAccessSpec,
        routine_spec: RoutineStartSpec,
    ) -> bytes:
        logger.info(
            "provisioning device certificate through routine 0x%04X",
            routine_spec.routine_id,
        )
        encrypted = self._crypto.encrypt_certificate(routine_spec.data)
        self.security_unlock(spec=security_access_spec)
        return self.routine_control(routine_id=routine_spec.routine_id, data=encrypted)

    def switch_mode(
        self,
        security_access_spec: SecurityAccessSpec,
        mode_switch_spec: ModeSwitchSpec,
    ) -> bytes:
        try:
            value = self._mode_values[mode_switch_spec.mode]
        except KeyError as error:
            raise UnsupportedModeError(
                f"unsupported mode {mode_switch_spec.mode}"
            ) from error
        self.security_unlock(spec=security_access_spec)
        logger.info(
            "switching MDC mode to %s through DID 0x%04X",
            mode_switch_spec.mode,
            mode_switch_spec.identifier,
        )
        response = self._uds.write_data_by_identifier(
            identifier=mode_switch_spec.identifier,
            data=value,
        )
        logger.info(
            "MDC mode switched to %s through DID 0x%04X",
            mode_switch_spec.mode,
            mode_switch_spec.identifier,
        )
        return response

    def verify_version_info(self, version_info: Mapping[int, bytes]) -> None:
        logger.info(
            "verifying version information for %d DIDs",
            len(version_info),
        )
        for identifier, expected in version_info.items():
            self.read_and_verify_did(
                identifier=identifier,
                expected=expected,
            )
        logger.info(
            "version information verified for %d DIDs",
            len(version_info),
        )
