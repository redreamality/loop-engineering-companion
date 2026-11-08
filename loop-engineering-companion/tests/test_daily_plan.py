from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sqlite3

import pytest
from pydantic import ValidationError

from loop_engineering_companion.daily_plan import (
    ApprovalRejected,
    Draft,
    approve,
    claim_task,
    classify_failure,
    make_task_id,
    open_db,
    record_failure,
    reject,
    run_once,
)


SAMPLE_ITEMS = [
    {
        "id": "T-104",
        "title": "确认发布范围",
        "status": "open",
        "due_at": "2026-08-15",
        "owner": "Remy",
    },
    {
        "id": "T-207",
        "title": "等待客户确认",
        "status": "open",
        "due_at": "2026-08-14",
        "owner": "Remy",
        "waiting_on": "客户 A",
    },
    {
        "id": "T-301",
        "title": "补全复盘记录",
        "status": "open",
        "due_at": None,
        "owner": None,
    },
]


def write_items(path: Path) -> None:
    path.write_text(json.dumps(SAMPLE_ITEMS, ensure_ascii=False), encoding="utf-8")


def future_deadline() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()


def test_task_id_uses_the_declared_format() -> None:
    assert make_task_id("2026-08-15") == "daily-plan:2026-08-15:v1"


def test_draft_keeps_warnings_and_rejects_unknown_fields() -> None:
    payload = {
        "priority_items": [],
        "schedulable_items": [],
        "missing_information": [],
        "excluded_items": [],
        "warnings": ["需要人工复核"],
    }
    assert Draft.model_validate(payload).warnings == ["需要人工复核"]
    with pytest.raises(ValidationError):
        Draft.model_validate({**payload, "unexpected": True})


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (FileNotFoundError(), "needs_input"),
        (json.JSONDecodeError("bad", "x", 0), "needs_input"),
        (PermissionError(), "failed_permanent"),
        (TimeoutError(), "retryable_failed"),
        (sqlite3.OperationalError("database is locked"), "retryable_failed"),
        (RuntimeError("programming defect"), "manual_handoff"),
    ],
)
def test_failure_classification_is_explicit(exc: Exception, expected: str) -> None:
    assert classify_failure(exc) == expected


def test_run_approval_and_idempotent_skip(tmp_path: Path) -> None:
    input_path = tmp_path / "tasks.json"
    database_path = tmp_path / "loop.db"
    artifact_dir = tmp_path / "artifacts"
    write_items(input_path)

    result = run_once(
        database_path=database_path,
        input_path=input_path,
        artifact_dir=artifact_dir,
        business_date="2026-08-15",
    )
    assert result["status"] == "awaiting_review"
    assert Path(result["output_path"]).exists()

    second = run_once(
        database_path=database_path,
        input_path=input_path,
        artifact_dir=artifact_dir,
        business_date="2026-08-15",
    )
    assert second["task_id"] == "daily-plan:2026-08-15:v1"
    assert second["status"] == "idempotent_skip"
    assert second["current_status"] == "awaiting_review"
    assert second["evidence"]["event_type"] == "duplicate_arrival"
    assert second["evidence"]["detail"]["reason"] == "status_awaiting_review"

    db = open_db(database_path)
    duplicate = db.execute(
        """SELECT event_type, detail_json FROM loop_events
           WHERE task_id = ? ORDER BY event_id DESC LIMIT 1""",
        (result["task_id"],),
    ).fetchone()
    assert duplicate["event_type"] == "duplicate_arrival"
    assert json.loads(duplicate["detail_json"])["reason"] == "status_awaiting_review"
    with pytest.raises(ApprovalRejected):
        approve(
            db,
            task_id=result["task_id"],
            artifact_version=result["artifact_version"],
            artifact_hash="0" * 64,
            approver="reviewer-01",
            reason="核对完成",
            valid_until=future_deadline(),
        )
    assert db.execute(
        "SELECT status FROM loop_tasks WHERE task_id = ?", (result["task_id"],)
    ).fetchone()["status"] == "awaiting_review"

    approve(
        db,
        task_id=result["task_id"],
        artifact_version=result["artifact_version"],
        artifact_hash=result["artifact_hash"],
        approver="reviewer-01",
        reason="已核对任务来源、日期和排除项",
        valid_until=future_deadline(),
    )
    row = db.execute(
        """SELECT status, approver, approval_reason, artifact_hash,
                  last_validation_json
           FROM loop_tasks WHERE task_id = ?""",
        (result["task_id"],),
    ).fetchone()
    db.close()
    assert row["status"] == "completed"
    assert row["approver"] == "reviewer-01"
    assert row["artifact_hash"] == result["artifact_hash"]
    assert json.loads(row["last_validation_json"])["status"] == "passed"


def test_schema_preserves_the_book_audit_contract(tmp_path: Path) -> None:
    db = open_db(tmp_path / "loop.db")
    task_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(loop_tasks)").fetchall()
    }
    run_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(loop_runs)").fetchall()
    }
    db.close()
    assert {
        "business_date",
        "rule_version",
        "current_run_id",
        "input_hash",
        "feedback_version",
        "feedback_json",
        "claimed_feedback_version",
        "retry_count",
        "retry_started_at",
        "next_retry_at",
        "last_validation_json",
    } <= task_columns
    assert {
        "input_hash",
        "validator_version",
        "validation_json",
        "model_cost_amount",
        "platform_cost_amount",
        "cost_currency",
    } <= run_columns


def test_missing_input_is_recorded_as_needs_input(tmp_path: Path) -> None:
    database_path = tmp_path / "loop.db"
    with pytest.raises(FileNotFoundError):
        run_once(
            database_path=database_path,
            input_path=tmp_path / "missing.json",
            artifact_dir=tmp_path / "artifacts",
            business_date="2026-08-15",
        )
    db = open_db(database_path)
    task = db.execute(
        "SELECT status, current_run_id FROM loop_tasks"
    ).fetchone()
    run = db.execute(
        "SELECT status, error_type FROM loop_runs"
    ).fetchone()
    db.close()
    assert task["status"] == "needs_input"
    assert run["status"] == "failed"
    assert run["error_type"] == "FileNotFoundError"


def test_needs_input_requires_changed_input_and_records_duplicate(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "loop.db"
    input_path = tmp_path / "tasks.json"
    with pytest.raises(FileNotFoundError):
        run_once(
            database_path=database_path,
            input_path=input_path,
            artifact_dir=tmp_path / "artifacts",
            business_date="2026-08-15",
        )

    repeated = run_once(
        database_path=database_path,
        input_path=input_path,
        artifact_dir=tmp_path / "artifacts",
        business_date="2026-08-15",
    )
    assert repeated["status"] == "idempotent_skip"

    db = open_db(database_path)
    assert db.execute("SELECT COUNT(*) FROM loop_runs").fetchone()[0] == 1
    signal = db.execute(
        """SELECT event_type, detail_json FROM loop_events
           ORDER BY event_id DESC LIMIT 1"""
    ).fetchone()
    assert signal["event_type"] == "duplicate_arrival"
    assert json.loads(signal["detail_json"])["reason"] == "input_digest_unchanged"
    db.close()

    write_items(input_path)
    recovered = run_once(
        database_path=database_path,
        input_path=input_path,
        artifact_dir=tmp_path / "artifacts",
        business_date="2026-08-15",
    )
    assert recovered["status"] == "awaiting_review"


def test_retry_waits_until_due_and_stops_at_budget(tmp_path: Path) -> None:
    db = open_db(tmp_path / "loop.db")
    task_id = make_task_id("2026-08-15")
    assert claim_task(
        db,
        task_id=task_id,
        run_id="run-initial",
        business_date="2026-08-15",
        input_hash="input-v1",
    )
    record_failure(
        db,
        task_id=task_id,
        run_id="run-initial",
        exc=TimeoutError(),
    )

    assert not claim_task(
        db,
        task_id=task_id,
        run_id="run-too-early",
        business_date="2026-08-15",
        input_hash="input-v1",
    )
    db.execute(
        "UPDATE loop_tasks SET next_retry_at = ? WHERE task_id = ?",
        ("2000-01-01T00:00:00+00:00", task_id),
    )
    assert claim_task(
        db,
        task_id=task_id,
        run_id="run-retry-1",
        business_date="2026-08-15",
        input_hash="input-v1",
    )
    record_failure(
        db,
        task_id=task_id,
        run_id="run-retry-1",
        exc=TimeoutError(),
    )
    db.execute(
        """UPDATE loop_tasks
           SET retry_count = 2, next_retry_at = ? WHERE task_id = ?""",
        ("2000-01-01T00:00:00+00:00", task_id),
    )
    assert not claim_task(
        db,
        task_id=task_id,
        run_id="run-over-budget",
        business_date="2026-08-15",
        input_hash="input-v1",
    )
    assert db.execute("SELECT COUNT(*) FROM loop_runs").fetchone()[0] == 2
    events = [
        (row["event_type"], json.loads(row["detail_json"]))
        for row in db.execute(
            "SELECT event_type, detail_json FROM loop_events ORDER BY event_id"
        )
    ]
    assert any(
        event_type == "duplicate_arrival"
        and detail["reason"] == "next_retry_at_not_due"
        for event_type, detail in events
    )
    assert any(event_type == "retry_budget_exhausted" for event_type, _ in events)
    status = db.execute(
        "SELECT status FROM loop_tasks WHERE task_id = ?", (task_id,)
    ).fetchone()["status"]
    assert status == "manual_handoff"
    db.close()


def test_rejected_task_requires_new_feedback_version(tmp_path: Path) -> None:
    database_path = tmp_path / "loop.db"
    input_path = tmp_path / "tasks.json"
    artifact_dir = tmp_path / "artifacts"
    write_items(input_path)
    first = run_once(
        database_path=database_path,
        input_path=input_path,
        artifact_dir=artifact_dir,
        business_date="2026-08-15",
    )
    db = open_db(database_path)
    reject(
        db,
        task_id=first["task_id"],
        artifact_version=first["artifact_version"],
        artifact_hash=first["artifact_hash"],
        feedback_version="feedback-v1",
        reviewer="reviewer-01",
        reason="回查 T-104 的截止日期",
    )
    db.close()
    second = run_once(
        database_path=database_path,
        input_path=input_path,
        artifact_dir=artifact_dir,
        business_date="2026-08-15",
    )
    assert second["status"] == "awaiting_review"

    db = open_db(database_path)
    with pytest.raises(ApprovalRejected):
        reject(
            db,
            task_id=second["task_id"],
            artifact_version=second["artifact_version"],
            artifact_hash=second["artifact_hash"],
            feedback_version="feedback-v1",
            reviewer="reviewer-01",
            reason="重复反馈不得再次消费",
        )
    reject(
        db,
        task_id=second["task_id"],
        artifact_version=second["artifact_version"],
        artifact_hash=second["artifact_hash"],
        feedback_version="feedback-v2",
        reviewer="reviewer-01",
        reason="补充新的修改要求",
    )
    db.close()
    third = run_once(
        database_path=database_path,
        input_path=input_path,
        artifact_dir=artifact_dir,
        business_date="2026-08-15",
    )
    assert third["status"] == "awaiting_review"
    db = open_db(database_path)
    assert db.execute("SELECT COUNT(*) FROM loop_runs").fetchone()[0] == 3
    versions = [
        row["feedback_version"]
        for row in db.execute(
            "SELECT feedback_version FROM loop_tasks WHERE task_id = ?",
            (third["task_id"],),
        )
    ]
    assert versions == ["feedback-v2"]
    db.close()
