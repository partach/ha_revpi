"""Constants for the Revolution Pi integration."""

from typing import Final

DOMAIN: Final = "ha_revpi"

# Connection settings
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_POLL_INTERVAL: Final = "poll_interval"

# Connection types
CONNECTION_TYPE_LOCAL: Final = "local"
CONNECTION_TYPE_TCP: Final = "tcp"
CONF_CONNECTION_TYPE: Final = "connection_type"

DEFAULT_HOST: Final = "localhost"
DEFAULT_PORT: Final = 0  # 0 = local access
DEFAULT_POLL_INTERVAL: Final = 1  # seconds

# piCtory configuration file path
CONF_CONFIGRSC: Final = "configrsc"
DEFAULT_CONFIGRSC: Final = "/var/www/revpi/pictory/projects/config.rsc"

# RevPi IO types (from revpimodio2)
IO_TYPE_INP: Final = 300
IO_TYPE_OUT: Final = 301
IO_TYPE_MEM: Final = 302

# Module type identifiers based on Kunbus catalog numbers
MODULE_TYPE_DIO: Final = "dio"
MODULE_TYPE_AIO: Final = "aio"
MODULE_TYPE_RELAY: Final = "ro"
MODULE_TYPE_MIO: Final = "mio"
MODULE_TYPE_CORE: Final = "core"
MODULE_TYPE_CONNECT: Final = "connect"
MODULE_TYPE_GATE: Final = "gate"

# Catalog number prefixes for module identification
CATALOG_DIO_PREFIXES: Final = ("RevPiDIO", "RevPiDI", "RevPiDO")
CATALOG_AIO_PREFIXES: Final = ("RevPiAIO",)
CATALOG_MIO_PREFIXES: Final = ("RevPiMIO",)
CATALOG_RELAY_PREFIXES: Final = ("RevPiRO",)
CATALOG_CORE_PREFIXES: Final = ("RevPiCore", "RevPiConnect", "RevPiFlat")

# Device name keywords used as fallback when catalogNr doesn't match
# (on real hardware catalogNr is often a product code like "PR100xxx")
CORE_NAME_KEYWORDS: Final = ("core", "connect", "flat")
DIO_NAME_KEYWORDS: Final = ("dio", " di", " do")
AIO_NAME_KEYWORDS: Final = ("aio",)
MIO_NAME_KEYWORDS: Final = ("mio",)
RELAY_NAME_KEYWORDS: Final = (" ro",)

# Known core/system IO name prefixes — these should never be exposed as mV sensors
CORE_IO_PREFIXES: Final = (
    "Core_",
    "RevPiStatus",
    "RevPiIOCycle",
    "RevPiLED",
    "RS485ErrorCnt",
    "RS485ErrorLimit",
    "RevPiOutput",
    "RevPiInput",
)

PLATFORMS: Final = ["sensor", "switch", "number", "select"]

# Core device identifier suffix
CORE_DEVICE_SUFFIX: Final = "_core"
