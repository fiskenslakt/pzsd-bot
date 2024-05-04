from enum import Enum

from pydantic_settings import BaseSettings


class EnvConfig(BaseSettings, env_file=".env", extra="ignore"):
    """Default config to pull from .env file."""


class _Bot(EnvConfig):
    token: str
    log_level: str = "INFO"


Bot = _Bot()


class _Channels(EnvConfig):
    # where point transactions get logged
    points_log: int = 1223525487578710016


Channels = _Channels()


class Colors(Enum):
    white = 0xFFFFFF
    red = 0xFF0000
    yellowy = 0xA8A434


class _DB(EnvConfig):
    pguser: str = "postgres"
    pgpassword: str = "password"
    pghost: str = "localhost"
    pgport: int = 5432
    pgdatabase: str = "pzsd"


DB = _DB()

DB_CONNECTION_STR = "postgresql+asyncpg://{}:{}@{}:{}/{}".format(
    DB.pguser,
    DB.pgpassword,
    DB.pghost,
    DB.pgport,
    DB.pgdatabase,
)

POINT_MAX_VALUE = 9223372036854775807
POINT_MIN_VALUE = ~POINT_MAX_VALUE
