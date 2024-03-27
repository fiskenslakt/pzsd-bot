from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

metadata = MetaData()

pzsd_user = Table(
    "pzsd_user",
    metadata,
    Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("name", Text, nullable=False),
    Column("discord_snowflake", Text, nullable=False),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
)

ledger = Table(
    "ledger",
    metadata,
    Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    ),
    Column("bestower", ForeignKey("pzsd_user.id"), nullable=False),
    Column("recipient", ForeignKey("pzsd_user.id"), nullable=False),
    Column("points", BigInteger, nullable=False),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
)
