class ElectronicInspectionError(Exception):
    pass


class VerificationError(ElectronicInspectionError):
    def __init__(
        self,
        operation: str,
        expected: bytes,
        actual: bytes,
    ) -> None:
        self.operation = operation
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"{operation} verification failed: "
            f"expected={expected.hex(' ')}, actual={actual.hex(' ')}"
        )


class UnsupportedModeError(ElectronicInspectionError):
    pass


class MdcStartupTimeoutError(ElectronicInspectionError, TimeoutError):
    pass
