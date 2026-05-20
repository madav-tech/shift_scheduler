from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shift_scheduler.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Person(Base):
    __tablename__ = "person"
    __table_args__ = (CheckConstraint("role IN ('commander','operator')", name="ck_person_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)

    presence_periods: Mapped[list["PresencePeriod"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        order_by="PresencePeriod.start_date",
    )


class PresencePeriod(Base):
    __tablename__ = "presence_period"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_period_end_ge_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person] = relationship(back_populates="presence_periods")
