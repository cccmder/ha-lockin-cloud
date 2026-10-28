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

# Key lists (passwords / fingerprints / cards) and the account topology barely
# change, so they are refreshed far less often than the live device state.
AUX_REFRESH_INTERVAL = 600

# locker_status.doorstate: 1 = open, 2 = closed (verified against a live device)
DOOR_STATE_MAP: dict[int, str] = {1: "open", 2: "closed"}

# family_record[].eventid 2203 is a door-open event (seen on live data).
OPEN_EVENT_IDS: frozenset[int] = frozenset({2203})

# family_record[].detail.source -> how the door was opened.
# Verified against live data: source 2 matched /api/lock/v1/pwd id "1047"
# (a temporary password) and source 3 matched /api/lock/v1/fp id 4 ("张三").
# 1 and 2 are both passwords; 2 is the temporary / one-off flavour, whose key
# name is already "临时", so the rendered text stays "临时使用密码开锁".
SOURCE_METHOD: dict[int, str] = {
    1: "密码",
    2: "密码",
    3: "指纹",
    4: "门卡",
    5: "钥匙",
    6: "手机",
    7: "蓝牙钥匙",
    8: "人脸",
    9: "胁迫指纹",
}

# Gateway models served by /api/gateway/v1/info.
GATEWAY_MODELS: tuple[str, ...] = ("DC-MC02",)
