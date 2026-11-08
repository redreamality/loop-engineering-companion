from pathlib import Path
from uuid import uuid4
import os

import psycopg
import pytest


POSTGRES_DSN = os.environ.get("TEST_POSTGRES_DSN")
PROJECT_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    not POSTGRES_DSN,
    reason="Set TEST_POSTGRES_DSN to run the real PostgreSQL fixture",
)


@pytest.fixture
def postgres() -> psycopg.Connection:
    schema = f"loop_fixture_{uuid4().hex}"
    connection = psycopg.connect(POSTGRES_DSN, autocommit=True)
    connection.execute(f'CREATE SCHEMA "{schema}"')
    connection.execute(f'SET search_path TO "{schema}"')
    connection.execute((PROJECT_ROOT / "sql/maturity_schema.sql").read_text("utf-8"))
    try:
        yield connection
    finally:
        connection.execute("SET search_path TO public")
        connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
        connection.close()


def insert_evidence(
    connection: psycopg.Connection,
    *,
    evidence_id: str,
    review_id: str,
    system_version: str,
    claimed_level: int,
) -> None:
    connection.execute(
        """INSERT INTO maturity_evidence (
               evidence_id, loop_id, review_id, dimension, claimed_level,
               evidence_type, evidence_uri, observed_at, valid_until,
               system_version, reviewer, status
           ) VALUES (
               %s, 'customer-email', %s, 'A', %s,
               'production', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '30 days',
               %s, 'reviewer-01', 'accepted'
           )""",
        (
            evidence_id,
            review_id,
            claimed_level,
            f"evidence://{evidence_id}",
            system_version,
        ),
    )


def current_claim(
    connection: psycopg.Connection,
    *,
    review_id: str,
    system_version: str,
) -> int:
    query = (PROJECT_ROOT / "sql/maturity_current_snapshot.sql").read_text("utf-8")
    row = connection.execute(
        query,
        ("customer-email", review_id, system_version),
    ).fetchone()
    assert row is not None
    return row[4]


def test_old_review_and_version_cannot_raise_the_current_claim(
    postgres: psycopg.Connection,
) -> None:
    insert_evidence(
        postgres,
        evidence_id="old-l3",
        review_id="review-2026-q1",
        system_version="system-v1",
        claimed_level=3,
    )
    insert_evidence(
        postgres,
        evidence_id="current-l1",
        review_id="review-2026-q2",
        system_version="system-v2",
        claimed_level=1,
    )

    assert current_claim(
        postgres,
        review_id="review-2026-q2",
        system_version="system-v2",
    ) == 1

    postgres.execute(
        "UPDATE maturity_evidence SET claimed_level = 4 WHERE evidence_id = 'old-l3'"
    )
    assert current_claim(
        postgres,
        review_id="review-2026-q2",
        system_version="system-v2",
    ) == 1
