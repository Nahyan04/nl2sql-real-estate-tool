from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import (
    Column,
    Date,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    insert,
)
from sqlalchemy.pool import StaticPool


@pytest.fixture
def sqlite_engine():
    """In-memory SQLite engine holding a miniature of the real-estate schema.

    StaticPool + check_same_thread=False so the same in-memory database is
    reachable from any thread the test harness runs queries on.
    """
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = MetaData()

    communities = Table(
        "communities",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name_en", String(255), nullable=False),
    )
    transactions = Table(
        "transactions",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("community_id", Integer, ForeignKey("communities.id"), nullable=False),
        Column("transaction_date", Date, nullable=False),
        Column("price_aed", Numeric(14, 2), nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            insert(communities),
            [{"id": 1, "name_en": "Yas Island"}, {"id": 2, "name_en": "Al Reem Island"}],
        )
        # 600 rows so the default 500-row cap actually bites
        connection.execute(
            insert(transactions),
            [
                {
                    "id": i,
                    "community_id": 1 if i % 2 else 2,
                    "transaction_date": dt.date(2025, 1, 1) + dt.timedelta(days=i % 365),
                    "price_aed": 1_000_000 + i,
                }
                for i in range(1, 601)
            ],
        )

    yield engine
    engine.dispose()
