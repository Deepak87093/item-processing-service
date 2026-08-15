from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint
)

from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class IdempotencyRecord (Base):
    __tablename__="idempotency_records"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id"),
        nullable=False
    )

    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    response: Mapped[str|None] = mapped_column(
        Text,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default= lambda: datetime.now(timezone.utc),
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_idempotency_key"
        ),
    )