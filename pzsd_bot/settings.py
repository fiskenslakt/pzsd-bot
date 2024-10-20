import re
from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings

STATIC_DIR = Path(__file__).parent / "static"


class EnvSettings(BaseSettings, env_file=".env", extra="ignore"):
    """Default config to pull from .env file."""


class _Bot(EnvSettings):
    token: str
    log_level: str = "INFO"


Bot = _Bot()


class _Channels(EnvSettings):
    # where point transactions get logged
    points_log: int = 1223525487578710016


Channels = _Channels()


class Colors(Enum):
    white: int = 0xFFFFFF
    red: int = 0xFF0000
    yellowy: int = 0xA8A434


class _DB(EnvSettings):
    pguser: str = "postgres"
    pgpassword: str = "password"
    pghost: str = "localhost"
    pgport: int = 5432
    pgdatabase: str = "pzsd"


DB = _DB()

DB_CONNECTION_STR = f"postgresql+asyncpg://{DB.pguser}:{DB.pgpassword}@{DB.pghost}:{DB.pgport}/{DB.pgdatabase}"


class _PointsSettings(EnvSettings):
    disallowed_names: frozenset = frozenset(
        {
            "everyone",
            "everybody",
            "nobody",
            "noone",
            "no one",
            "someone",
            "something",
            "anyone",
            "anybody",
            "anything",
            "whoever",
            "all",
            "me",
            "myself",
            "ourselves",
            "you",
            "us",
            "them",
            "her",
            "him",
            "this",
            "that",
            "those",
            "these",
        }
    )
    valid_name_pattern: re.Pattern = re.compile(r"[\w '-]+")
    point_pattern: re.Pattern = re.compile(
        r"(?:^| )(?P<point_amount>[+-]?(?:\d+|\d{1,3}(?:,\d{3})*)) "
        r"+points? to "
        r"(?:(?P<recipient_name>[\w'-]+|\"[\w '-]+\")|<@(?P<recipient_id>\d+)>)",
        re.IGNORECASE,
    )
    reply_point_pattern: re.Pattern = re.compile(
        r"(?P<point_amount>[+-]?(?:\d+|\d{1,3}(?:,\d{3})*)) +points?",
        re.IGNORECASE,
    )


PointsSettings = _PointsSettings()


class _DiceSettings(EnvSettings):
    d20_images: Path = STATIC_DIR / "images/dice/D20"


DiceSettings = _DiceSettings()


class _Emoji(EnvSettings):
    dice_0: str = "<:dice_0:1296590662887542907>"
    dice_1: str = "<:dice_1:1296590681229230252>"
    dice_2: str = "<:dice_2:1296590696274198558>"
    dice_3: str = "<:dice_3:1296590711894048789>"
    dice_4: str = "<:dice_4:1296590731313676359>"
    dice_5: str = "<:dice_5:1296590746433884292>"
    dice_6: str = "<:dice_6:1296590761575321600>"
    dice_7: str = "<:dice_7:1296590781980737636>"
    dice_8: str = "<:dice_8:1296590805737279568>"
    dice_9: str = "<:dice_9:1296590835877412915>"
    dice_minus1: str = "<:dice_minus1:1296590875354202132>"
    dice_question: str = "<:dice_question:1296590911647780866>"

    d20_1: str = "<:d20_1:1297690036451414076>"
    d20_2: str = "<:d20_2:1297690054940168212>"
    d20_3: str = "<:d20_3:1297690071125856377>"
    d20_4: str = "<:d20_4:1297690087114543144>"
    d20_5: str = "<:d20_5:1297690105254903829>"
    d20_6: str = "<:d20_6:1297690151677595689>"
    d20_7: str = "<:d20_7:1297690167670210590>"
    d20_8: str = "<:d20_8:1297690188612370622>"
    d20_9: str = "<:d20_9:1297690204748120114>"
    d20_10: str = "<:d20_10:1297700429609828363>"
    d20_11: str = "<:d20_11:1297700431098679348>"
    d20_12: str = "<:d20_12:1297700432419749898>"
    d20_13: str = "<:d20_13:1297700433485234178>"
    d20_14: str = "<:d20_14:1297700434898845736>"
    d20_15: str = "<:d20_15:1297700561143201802>"
    d20_16: str = "<:d20_16:1297700561935663174>"
    d20_17: str = "<:d20_17:1297700562816598098>"
    d20_18: str = "<:d20_18:1297700563630297168>"
    d20_19: str = "<:d20_19:1297700564733526080>"
    d20_20: str = "<:d20_20:1297700565811462266>"

    lol: str = "<:pLol:1076609913654100010>"
    nice: str = "<:nice:1225483836717142026>"

    onehundred: str = ":100:"

    check_mark: str = "\u2705"
    cross_mark: str = "\u274c"


Emoji = _Emoji()

POINT_MAX_VALUE = 9223372036854775807
POINT_MIN_VALUE = ~POINT_MAX_VALUE
