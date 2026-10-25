from enum import StrEnum


class MdcMode(StrEnum):
    FACTORY = "factory"
    USER = "user"
    TEST = "test"


class MdcPlane(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
