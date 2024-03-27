"""add users

Revision ID: e0d89d644b1b
Revises: 8119e0e270cd
Create Date: 2024-03-27 16:15:16.870170

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e0d89d644b1b"
down_revision: Union[str, None] = "8119e0e270cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO pzsd_user (name, discord_snowflake) values ('derek', '170208380739256320')"
    )
    op.execute(
        "INSERT INTO pzsd_user (name, discord_snowflake) values ('seth', '908384941824442421')"
    )
    op.execute(
        "INSERT INTO pzsd_user (name, discord_snowflake) values ('ryan', '905469479096561695')"
    )
    op.execute(
        "INSERT INTO pzsd_user (name, discord_snowflake) values ('zach', '908378485997858886')"
    )
    op.execute(
        "INSERT INTO pzsd_user (name, discord_snowflake) values ('hutch', '749838983134969867')"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM pzsd_user WHERE discord_snowflake IN "
        "('170208380739256320', '908384941824442421', '905469479096561695', '908378485997858886', '749838983134969867')"
    )
