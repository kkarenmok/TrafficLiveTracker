"""Create and seed the shared bus stops table."""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone


revision = "20260716_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = op.create_table(
        "bus_stops",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("routes", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": "490003314R",
                "name": "Mare Street / Victoria Park Road Stop R",
                "routes": [],
                "position": 0,
                "created_at": datetime(2026, 7, 16, tzinfo=timezone.utc),
            },
            {
                "id": "490007624S",
                "name": "Mare Street / Victoria Park Road Stop Q",
                "routes": [],
                "position": 1,
                "created_at": datetime(2026, 7, 16, tzinfo=timezone.utc),
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("bus_stops")
