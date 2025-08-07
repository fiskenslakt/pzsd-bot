import enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID


class ReminderStatus(enum.Enum):
    pending = "pending"
    failed = "failed"


class TriggerResponseType(enum.Enum):
    standard = "standard"
    reply = "reply"
    reaction = "reaction"


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
    Column("name", Text, nullable=False, unique=True),
    Column("discord_snowflake", Text, nullable=True, unique=True),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    Column("is_active", Boolean, nullable=False, server_default=text("true")),
    Column("point_giver", Boolean, nullable=False, server_default=text("false")),
    Column("timezone", Text, nullable=True),
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

trigger_group = Table(
    "trigger_group",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("is_active", Boolean, nullable=False, server_default=text("true")),
    Column("owner", BigInteger, nullable=False),  # discord ID
    Column(
        "response_type",
        Enum(TriggerResponseType),
        nullable=False,
        server_default="standard",
    ),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    Column("updated_at", DateTime, server_default=func.now(), nullable=False),
)

trigger_pattern = Table(
    "trigger_pattern",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("pattern", Text, nullable=False),
    Column(
        "group_id",
        Integer,
        ForeignKey("trigger_group.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("is_regex", Boolean, nullable=False),
)

trigger_response = Table(
    "trigger_response",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "group_id",
        Integer,
        ForeignKey("trigger_group.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("response", Text, nullable=False),
)

reminder = Table(
    "reminder",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner", BigInteger, nullable=False),  # discord ID
    Column("channel_id", BigInteger, nullable=False),
    Column("original_message_id", BigInteger, nullable=False),
    Column("reminder_text", Text, nullable=True),
    Column("remind_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    Column("is_recurring", Boolean, nullable=False),
    Column("recurrence_interval", Integer, nullable=True),  # in seconds
    Column(
        "status",
        Enum(ReminderStatus),
        nullable=False,
        default=ReminderStatus.pending,
    ),
)
