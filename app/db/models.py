from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    provider_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_city: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_state: Mapped[str] = mapped_column(String(2), nullable=False)
    provider_zip_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    prices: Mapped[list[Price]] = relationship("Price", back_populates="provider")
    ratings: Mapped[list[StarRating]] = relationship("StarRating", back_populates="provider")


class DRG(Base):
    __tablename__ = "drgs"

    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    prices: Mapped[list[Price]] = relationship("Price", back_populates="drg")


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), nullable=False, index=True)
    drg_code: Mapped[int] = mapped_column(ForeignKey("drgs.code"), nullable=False, index=True)
    total_discharges: Mapped[int | None] = mapped_column(Integer)
    average_covered_charges: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    average_total_payments: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    average_medicare_payments: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    provider: Mapped[Provider] = relationship("Provider", back_populates="prices")
    drg: Mapped[DRG] = relationship("DRG", back_populates="prices")

    __table_args__ = (
        Index("ix_prices_drg_cost", "drg_code", "average_covered_charges"),
    )


class StarRating(Base):
    __tablename__ = "star_ratings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    provider: Mapped[Provider] = relationship("Provider", back_populates="ratings")

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 10", name="ck_star_ratings_range"),
        Index("ix_star_ratings_provider", "provider_id"),
    )


class ZipCode(Base):
    __tablename__ = "zip_codes"

    zip: Mapped[str] = mapped_column(String(10), primary_key=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    __table_args__ = (
        Index("ix_zip_codes_zip", "zip"),
    )


