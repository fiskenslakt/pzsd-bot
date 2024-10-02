import re
from enum import Enum

from pydantic_settings import BaseSettings


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

POINT_MAX_VALUE = 9223372036854775807
POINT_MIN_VALUE = ~POINT_MAX_VALUE
