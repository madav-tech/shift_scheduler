from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shift_scheduler.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Person(Base):
    __tablename__ = "person"
    __table_args__ = (CheckConstraint("role IN ('commander','operator')", name="ck_person_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    presence_periods: Mapped[list["PresencePeriod"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
        order_by="PresencePeriod.start_date",
    )


class PresencePeriod(Base):
    __tablename__ = "presence_period"
    __table_args__ = (CheckConstraint("end_date >= start_date", name="ck_period_end_ge_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("person.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    person: Mapped[Person] = relationship(back_populates="presence_periods")


class Shift(Base):
    __tablename__ = "shift"
    __table_args__ = (
        CheckConstraint("kind IN ('morning','noon','night')", name="ck_shift_kind"),
        UniqueConstraint("date", "kind", name="uq_shift_date_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)

    assignments: Mapped[list["ShiftAssignment"]] = relationship(
        back_populates="shift",
        cascade="all, delete-orphan",
        order_by="ShiftAssignment.slot, ShiftAssignment.position",
    )


class ShiftAssignment(Base):
    __tablename__ = "shift_assignment"
    __table_args__ = (
        CheckConstraint("slot IN ('commander','operator')", name="ck_assign_slot"),
        UniqueConstraint("shift_id", "slot", "position", name="uq_assign_shift_slot_position"),
        UniqueConstraint("shift_id", "person_id", name="uq_assign_shift_person"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shift_id: Mapped[int] = mapped_column(
        ForeignKey("shift.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    slot: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    shift: Mapped[Shift] = relationship(back_populates="assignments")
    person: Mapped[Person] = relationship()


class EditLog(Base):
    __tablename__ = "edit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
