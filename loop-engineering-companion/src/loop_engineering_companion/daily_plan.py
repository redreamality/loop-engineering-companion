from __future__ import annotations

from argparse import ArgumentParser
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo
import json
import sqlite3

from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError


class Item(BaseModel):
    id: str
    title: str
    status: str
    due_at: str | None = None
    owner: str | None = None
    waiting_on: str | None = None


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority_items: list[str]
    schedulable_items: list[str]
    missing_information: list[str]
    excluded_items: list[str]
    warnings: list[str]


class ApprovalRejected(RuntimeError):
    """The approval did not match the current review artifact."""


BUSINESS_TZ = ZoneInfo("Asia/Vladivostok")
RULE_VERSION = "daily-plan:v1"
VALIDATOR_VERSION = "draft-schema:v1"
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 30
RETRY_WINDOW_SECONDS = 300


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_task_id(business_date: str, rule_version: str = "v1") -> str:
    return f"daily-plan:{business_date}:{rule_version}"


def ensure_column(
    db: sqlite3.Connection,
    *,
    table: str,
    column: str,
    declaration: str,
) -> None:
    columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def open_db(database_path: Path | str) -> sqlite3.Connection:
    db = sqlite3.connect(database_path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA busy_timeout = 5000")
    db.execute(
        """CREATE TABLE IF NOT EXISTS loop_tasks (
           task_id TEXT PRIMARY KEY,
           business_date TEXT NOT NULL,
           rule_version TEXT NOT NULL,
           status TEXT NOT NULL,
           current_run_id TEXT,
           input_hash TEXT,
           output_link TEXT,
           artifact_version TEXT,
           artifact_hash TEXT,
           last_validation_json TEXT,
           approver TEXT,
           approval_reason TEXT,
           approval_valid_until TEXT,
           approved_at TEXT,
           feedback_version TEXT,
           feedback_json TEXT,
           claimed_feedback_version TEXT,
           retry_count INTEGER NOT NULL DEFAULT 0,
           retry_started_at TEXT,
           next_retry_at TEXT,
           updated_at TEXT NOT NULL)"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS loop_runs (
           run_id TEXT PRIMARY KEY,
           task_id TEXT NOT NULL REFERENCES loop_tasks(task_id),
           status TEXT NOT NULL,
           started_at TEXT NOT NULL,
           ended_at TEXT,
           input_hash TEXT,
           validator_version TEXT,
           validation_json TEXT,
           model_cost_amount REAL NOT NULL DEFAULT 0,
           platform_cost_amount REAL NOT NULL DEFAULT 0,
           cost_currency TEXT NOT NULL DEFAULT 'USD',
           error_type TEXT)"""
    )
    for column, declaration in {
        "feedback_version": "TEXT",
        "feedback_json": "TEXT",
        "claimed_feedback_version": "TEXT",
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "retry_started_at": "TEXT",
        "next_retry_at": "TEXT",
    }.items():
        ensure_column(
            db,
            table="loop_tasks",
            column=column,
            declaration=declaration,
        )
    db.execute(
        """CREATE TABLE IF NOT EXISTS loop_events (
           event_id INTEGER PRIMARY KEY AUTOINCREMENT,
           task_id TEXT NOT NULL REFERENCES loop_tasks(task_id),
           event_type TEXT NOT NULL,
           observed_at TEXT NOT NULL,
           task_status TEXT NOT NULL,
           input_hash TEXT,
           detail_json TEXT NOT NULL)"""
    )
    return db


def append_event(
    db: sqlite3.Connection,
    *,
    task_id: str,
    event_type: str,
    observed_at: str,
    task_status: str,
    input_hash: str | None,
    detail: dict[str, object],
) -> None:
    db.execute(
        """INSERT INTO loop_events
           (task_id, event_type, observed_at, task_status, input_hash, detail_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            task_id,
            event_type,
            observed_at,
            task_status,
            input_hash,
            json.dumps(detail, ensure_ascii=False, sort_keys=True),
        ),
    )


def claim_task(
    db: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str,
    business_date: str,
    input_hash: str | None,
    rule_version: str = RULE_VERSION,
) -> bool:
    now = utc_now()
    now_value = datetime.fromisoformat(now)
    db.execute("BEGIN IMMEDIATE")
    db.execute(
        """INSERT OR IGNORE INTO loop_tasks
           (task_id, business_date, rule_version, status, updated_at)
           VALUES (?, ?, ?, 'discovered', ?)""",
        (task_id, business_date, rule_version, now),
    )
    row = db.execute(
        """SELECT status, input_hash, feedback_version, claimed_feedback_version,
                  retry_count, retry_started_at, next_retry_at
           FROM loop_tasks WHERE task_id = ?""",
        (task_id,),
    ).fetchone()
    assert row is not None
    status = row["status"]
    duplicate_reason: str | None = None
    if status in {"completed", "awaiting_review", "running"}:
        duplicate_reason = f"status_{status}"
    elif status == "needs_input":
        if input_hash == row["input_hash"]:
            duplicate_reason = "input_digest_unchanged"
    elif status == "retryable_failed":
        retry_started_at = row["retry_started_at"]
        next_retry_at = row["next_retry_at"]
        retry_count = int(row["retry_count"])
        if retry_started_at is None or next_retry_at is None:
            db.execute(
                """UPDATE loop_tasks SET status = 'manual_handoff', updated_at = ?
                   WHERE task_id = ? AND status = 'retryable_failed'""",
                (now, task_id),
            )
            append_event(
                db,
                task_id=task_id,
                event_type="retry_schedule_missing",
                observed_at=now,
                task_status="manual_handoff",
                input_hash=input_hash,
                detail={"previous_status": status},
            )
            db.commit()
            return False
        retry_window_used = now_value - datetime.fromisoformat(retry_started_at)
        if retry_count >= MAX_RETRIES or retry_window_used >= timedelta(
            seconds=RETRY_WINDOW_SECONDS
        ):
            db.execute(
                """UPDATE loop_tasks SET status = 'manual_handoff', updated_at = ?
                   WHERE task_id = ? AND status = 'retryable_failed'""",
                (now, task_id),
            )
            append_event(
                db,
                task_id=task_id,
                event_type="retry_budget_exhausted",
                observed_at=now,
                task_status="manual_handoff",
                input_hash=input_hash,
                detail={
                    "retry_count": retry_count,
                    "retry_started_at": retry_started_at,
                },
            )
            db.commit()
            return False
        if datetime.fromisoformat(next_retry_at) > now_value:
            duplicate_reason = "next_retry_at_not_due"
    elif status == "rejected":
        feedback_version = row["feedback_version"]
        if (
            feedback_version is None
            or feedback_version == row["claimed_feedback_version"]
        ):
            duplicate_reason = "feedback_version_unchanged"
    elif status != "discovered":
        duplicate_reason = f"status_{status}_not_claimable"

    if duplicate_reason is not None:
        append_event(
            db,
            task_id=task_id,
            event_type="duplicate_arrival",
            observed_at=now,
            task_status=status,
            input_hash=input_hash,
            detail={"reason": duplicate_reason},
        )
        db.commit()
        return False

    retry_count = int(row["retry_count"])
    next_retry_count = retry_count + 1 if status == "retryable_failed" else 0
    retry_started_at = row["retry_started_at"] if status == "retryable_failed" else None
    claimed_feedback_version = row["claimed_feedback_version"]
    if status == "rejected":
        claimed_feedback_version = row["feedback_version"]
    db.execute(
        """INSERT INTO loop_runs
           (run_id, task_id, status, started_at, input_hash)
           VALUES (?, ?, 'running', ?, ?)""",
        (run_id, task_id, now, input_hash),
    )
    db.execute(
        """UPDATE loop_tasks
           SET status = 'running', current_run_id = ?, input_hash = ?,
               claimed_feedback_version = ?, retry_count = ?,
               retry_started_at = ?, next_retry_at = NULL, updated_at = ?
           WHERE task_id = ?""",
        (
            run_id,
            input_hash,
            claimed_feedback_version,
            next_retry_count,
            retry_started_at,
            now,
            task_id,
        ),
    )
    append_event(
        db,
        task_id=task_id,
        event_type="run_claimed",
        observed_at=now,
        task_status="running",
        input_hash=input_hash,
        detail={
            "previous_status": status,
            "run_id": run_id,
            "retry_count": next_retry_count,
            "feedback_version": claimed_feedback_version,
        },
    )
    db.commit()
    return True


def build_draft(items: list[Item], business_date: str) -> Draft:
    eligible = [item for item in items if item.status == "open" and not item.waiting_on]
    return Draft(
        priority_items=[
            item.id
            for item in eligible
            if item.due_at and item.due_at <= business_date and item.owner
        ],
        schedulable_items=[
            item.id
            for item in eligible
            if item.due_at and item.due_at > business_date and item.owner
        ],
        missing_information=[
            item.id for item in eligible if not item.due_at or not item.owner
        ],
        excluded_items=[
            item.id for item in items if item.status != "open" or item.waiting_on
        ],
        warnings=[],
    )


def stage_draft(
    db: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str,
    draft: Draft,
    artifact_dir: Path,
) -> dict[str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    output_path = artifact_dir / f"{run_id}-draft.json"
    artifact_version = f"{run_id}:draft:v1"
    artifact_bytes = json.dumps(
        draft.model_dump(), ensure_ascii=False, indent=2
    ).encode("utf-8")
    output_path.write_bytes(artifact_bytes)
    artifact_hash = sha256(artifact_bytes).hexdigest()
    validation = {
        "status": "passed",
        "schema": "Draft-v1",
        "validator_version": VALIDATOR_VERSION,
        "required_arrays": 5,
    }
    validation_json = json.dumps(validation, ensure_ascii=False, sort_keys=True)
    ended_at = utc_now()
    db.execute("BEGIN IMMEDIATE")
    changed = db.execute(
        """UPDATE loop_tasks
           SET status = 'awaiting_review', output_link = ?,
               artifact_version = ?, artifact_hash = ?,
               last_validation_json = ?, updated_at = ?
           WHERE task_id = ? AND status = 'running' AND current_run_id = ?""",
        (
            str(output_path),
            artifact_version,
            artifact_hash,
            validation_json,
            ended_at,
            task_id,
            run_id,
        ),
    )
    if changed.rowcount != 1:
        db.rollback()
        raise RuntimeError("任务已不在本次 running 状态，拒绝覆盖")
    db.execute(
        """UPDATE loop_runs
           SET status = 'succeeded', ended_at = ?, validator_version = ?,
               validation_json = ?
           WHERE run_id = ?""",
        (ended_at, VALIDATOR_VERSION, validation_json, run_id),
    )
    db.commit()
    return {
        "output_path": str(output_path),
        "artifact_version": artifact_version,
        "artifact_hash": artifact_hash,
    }


def parse_deadline(value: str) -> datetime:
    deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if deadline.tzinfo is None:
        raise ApprovalRejected(
            "valid_until 必须带时区，例如 2026-08-16T09:00:00+10:00"
        )
    if deadline <= datetime.now(timezone.utc):
        raise ApprovalRejected("不能创建已经过期的批准")
    return deadline


def approve(
    db: sqlite3.Connection,
    *,
    task_id: str,
    artifact_version: str,
    artifact_hash: str,
    approver: str,
    reason: str,
    valid_until: str,
) -> None:
    if not approver.strip() or not reason.strip():
        raise ApprovalRejected("approver 和 reason 不能为空")
    parse_deadline(valid_until)
    now = utc_now()
    db.execute("BEGIN IMMEDIATE")
    changed = db.execute(
        """UPDATE loop_tasks
           SET status = 'completed', approver = ?, approval_reason = ?,
               approval_valid_until = ?, approved_at = ?, updated_at = ?
           WHERE task_id = ? AND status = 'awaiting_review'
             AND artifact_version = ? AND artifact_hash = ?""",
        (
            approver.strip(),
            reason.strip(),
            valid_until,
            now,
            now,
            task_id,
            artifact_version,
            artifact_hash,
        ),
    )
    if changed.rowcount != 1:
        db.rollback()
        current = db.execute(
            """SELECT status, artifact_version, artifact_hash
               FROM loop_tasks WHERE task_id = ?""",
            (task_id,),
        ).fetchone()
        state = current["status"] if current else "missing"
        current_version = current["artifact_version"] if current else "-"
        current_hash = current["artifact_hash"] if current else "-"
        raise ApprovalRejected(
            f"不能批准 {task_id}：状态={state}，"
            f"当前版本={current_version}，当前哈希={current_hash}"
        )
    db.commit()


def reject(
    db: sqlite3.Connection,
    *,
    task_id: str,
    artifact_version: str,
    artifact_hash: str,
    feedback_version: str,
    reviewer: str,
    reason: str,
) -> None:
    if not feedback_version.strip() or not reviewer.strip() or not reason.strip():
        raise ApprovalRejected("feedback_version、reviewer 和 reason 不能为空")
    now = utc_now()
    feedback = json.dumps(
        {"reviewer": reviewer.strip(), "reason": reason.strip()},
        ensure_ascii=False,
        sort_keys=True,
    )
    db.execute("BEGIN IMMEDIATE")
    changed = db.execute(
        """UPDATE loop_tasks
           SET status = 'rejected', feedback_version = ?, feedback_json = ?,
               updated_at = ?
           WHERE task_id = ? AND status = 'awaiting_review'
             AND artifact_version = ? AND artifact_hash = ?
             AND COALESCE(claimed_feedback_version, '') <> ?""",
        (
            feedback_version.strip(),
            feedback,
            now,
            task_id,
            artifact_version,
            artifact_hash,
            feedback_version.strip(),
        ),
    )
    if changed.rowcount != 1:
        db.rollback()
        raise ApprovalRejected("拒绝失败：状态、产物版本、哈希或反馈版本不是当前值")
    append_event(
        db,
        task_id=task_id,
        event_type="review_rejected",
        observed_at=now,
        task_status="rejected",
        input_hash=None,
        detail={
            "artifact_version": artifact_version,
            "feedback_version": feedback_version.strip(),
            "reviewer": reviewer.strip(),
        },
    )
    db.commit()


def classify_failure(exc: Exception) -> str:
    if isinstance(
        exc,
        (ValidationError, json.JSONDecodeError, UnicodeError, FileNotFoundError),
    ):
        return "needs_input"
    if isinstance(exc, (PermissionError, IsADirectoryError)):
        return "failed_permanent"
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return "retryable_failed"
    if isinstance(exc, sqlite3.OperationalError):
        message = str(exc).lower()
        if "locked" in message or "busy" in message:
            return "retryable_failed"
    return "manual_handoff"


def record_failure(
    db: sqlite3.Connection,
    *,
    task_id: str,
    run_id: str,
    exc: Exception,
) -> str:
    if db.in_transaction:
        db.rollback()
    ended_at = utc_now()
    failure_status = classify_failure(exc)
    db.execute("BEGIN IMMEDIATE")
    current = db.execute(
        """SELECT input_hash, retry_count, retry_started_at FROM loop_tasks
           WHERE task_id = ? AND status = 'running' AND current_run_id = ?""",
        (task_id, run_id),
    ).fetchone()
    assert current is not None
    next_retry_at: str | None = None
    if failure_status == "retryable_failed":
        retry_started_at = current["retry_started_at"] or ended_at
        retry_window_used = datetime.fromisoformat(ended_at) - datetime.fromisoformat(
            retry_started_at
        )
        if int(current["retry_count"]) >= MAX_RETRIES or retry_window_used >= timedelta(
            seconds=RETRY_WINDOW_SECONDS
        ):
            failure_status = "manual_handoff"
        else:
            next_retry_at = (
                datetime.fromisoformat(ended_at)
                + timedelta(seconds=RETRY_DELAY_SECONDS)
            ).isoformat()
        db.execute(
            """UPDATE loop_tasks
               SET status = ?, retry_started_at = ?, next_retry_at = ?, updated_at = ?
               WHERE task_id = ? AND status = 'running' AND current_run_id = ?""",
            (
                failure_status,
                retry_started_at,
                next_retry_at,
                ended_at,
                task_id,
                run_id,
            ),
        )
    else:
        db.execute(
            """UPDATE loop_tasks SET status = ?, updated_at = ?
               WHERE task_id = ? AND status = 'running' AND current_run_id = ?""",
            (failure_status, ended_at, task_id, run_id),
        )
    db.execute(
        """UPDATE loop_runs
           SET status = 'failed', ended_at = ?, error_type = ?
           WHERE run_id = ?""",
        (ended_at, type(exc).__name__, run_id),
    )
    append_event(
        db,
        task_id=task_id,
        event_type="run_failed",
        observed_at=ended_at,
        task_status=failure_status,
        input_hash=current["input_hash"],
        detail={
            "run_id": run_id,
            "error_type": type(exc).__name__,
            "next_retry_at": next_retry_at,
        },
    )
    db.commit()
    return failure_status


def run_once(
    *,
    database_path: Path,
    input_path: Path,
    artifact_dir: Path,
    business_date: str | None = None,
) -> dict[str, Any]:
    selected_date = business_date or datetime.now(BUSINESS_TZ).date().isoformat()
    date.fromisoformat(selected_date)
    task_id = make_task_id(selected_date)
    run_id = f"run-{uuid4().hex}"
    input_bytes: bytes | None = None
    input_error: Exception | None = None
    try:
        input_bytes = input_path.read_bytes()
        input_hash = sha256(input_bytes).hexdigest()
    except Exception as exc:
        input_hash = sha256(
            f"unreadable:{type(exc).__name__}:{exc}".encode("utf-8")
        ).hexdigest()
        input_error = exc
    db = open_db(database_path)
    claimed = claim_task(
        db,
        task_id=task_id,
        run_id=run_id,
        business_date=selected_date,
        input_hash=input_hash,
    )
    if not claimed:
        status = db.execute(
            "SELECT status FROM loop_tasks WHERE task_id = ?", (task_id,)
        ).fetchone()["status"]
        event = db.execute(
            """SELECT event_type, detail_json FROM loop_events
               WHERE task_id = ? ORDER BY event_id DESC LIMIT 1""",
            (task_id,),
        ).fetchone()
        db.close()
        return {
            "task_id": task_id,
            "status": "idempotent_skip",
            "current_status": status,
            "evidence": (
                {"event_type": event["event_type"], "detail": json.loads(event["detail_json"])}
                if event
                else None
            ),
        }
    try:
        if input_error is not None:
            raise input_error
        assert input_bytes is not None
        items = TypeAdapter(list[Item]).validate_json(input_bytes)
        draft = build_draft(items, selected_date)
        artifact = stage_draft(
            db,
            task_id=task_id,
            run_id=run_id,
            draft=draft,
            artifact_dir=artifact_dir,
        )
    except Exception as exc:
        record_failure(db, task_id=task_id, run_id=run_id, exc=exc)
        db.close()
        raise
    db.close()
    return {
        "task_id": task_id,
        "run_id": run_id,
        "status": "awaiting_review",
        **artifact,
    }


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Daily plan loop companion example")
    commands = parser.add_subparsers(dest="command", required=True)
    run_command = commands.add_parser("run")
    run_command.add_argument("--database", type=Path, default=Path("loop.db"))
    run_command.add_argument("--input", type=Path, default=Path("examples/tasks.json"))
    run_command.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    run_command.add_argument("--business-date")
    approve_command = commands.add_parser("approve")
    approve_command.add_argument("task_id")
    approve_command.add_argument("--database", type=Path, default=Path("loop.db"))
    approve_command.add_argument("--artifact-version", required=True)
    approve_command.add_argument("--artifact-hash", required=True)
    approve_command.add_argument("--approver", required=True)
    approve_command.add_argument("--reason", required=True)
    approve_command.add_argument("--valid-until", required=True)
    reject_command = commands.add_parser("reject")
    reject_command.add_argument("task_id")
    reject_command.add_argument("--database", type=Path, default=Path("loop.db"))
    reject_command.add_argument("--artifact-version", required=True)
    reject_command.add_argument("--artifact-hash", required=True)
    reject_command.add_argument("--feedback-version", required=True)
    reject_command.add_argument("--reviewer", required=True)
    reject_command.add_argument("--reason", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        result = run_once(
            database_path=args.database,
            input_path=args.input,
            artifact_dir=args.artifacts,
            business_date=args.business_date,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    db = open_db(args.database)
    try:
        if args.command == "approve":
            approve(
                db,
                task_id=args.task_id,
                artifact_version=args.artifact_version,
                artifact_hash=args.artifact_hash,
                approver=args.approver,
                reason=args.reason,
                valid_until=args.valid_until,
            )
        else:
            reject(
                db,
                task_id=args.task_id,
                artifact_version=args.artifact_version,
                artifact_hash=args.artifact_hash,
                feedback_version=args.feedback_version,
                reviewer=args.reviewer,
                reason=args.reason,
            )
    finally:
        db.close()
    print(f"{args.task_id} / {args.artifact_version} -> {args.command}")


if __name__ == "__main__":
    main()
