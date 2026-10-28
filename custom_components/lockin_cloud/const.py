"""Constants for the Lockin Cloud integration."""

from __future__ import annotations

DOMAIN = "lockin_cloud"

BASE_URL = "https://device-server-2c.dding.net"
SIGN_SECRET = "87f2be668896e243c4c13755b3b9ed9d"
APP_KEY = "8da5ee01647719e67c49d82d"

CONF_ACCESS_TOKEN = "access_token"
CONF_DEVICE_UUID = "device_uuid"

DEFAULT_SCAN_INTERVAL = 60
REQUEST_TIMEOUT = 20

# locker_status.doorstate: 1 = open, 2 = closed (verified against live device)
DOOR_STATE_MAP: dict[int, str] = {1: "open", 2: "closed"}

# Lock model prefixes (PFPL* = Lockin P series)
LOCK_MODEL_PREFIXES = ("PFPL", "P")
