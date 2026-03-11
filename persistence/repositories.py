from __future__ import annotations

import json
import sqlite3

from persistence.models import (
    AuditEvent,
    BatchRecord,
    CampaignRecord,
    DeadLetterRecord,
    ExperimentJob,
    ExperimentResult,
    LineageRecord,
)


class SqliteExperimentRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    campaign_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    snapshot_fingerprint TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    iteration INTEGER NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    parent_candidate_id TEXT,
                    domain TEXT NOT NULL,
                    dataset_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    trace_id TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    attempt INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS results (
                    job_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    score REAL NOT NULL,
                    metrics_json TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    error TEXT,
                    PRIMARY KEY (job_id, attempt)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dead_letters (
                    job_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    attempts INTEGER NOT NULL,
                    reason TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lineage_records (
                    job_id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    parent_candidate_id TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    campaign_id TEXT NOT NULL,
                    iteration INTEGER NOT NULL,
                    optimizer_state_json TEXT NOT NULL,
                    best_score REAL NOT NULL,
                    best_parameters_json TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    PRIMARY KEY (campaign_id, iteration)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    batch_id TEXT,
                    job_id TEXT,
                    attempt INTEGER,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._ensure_column(conn, "jobs", "trace_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "jobs", "candidate_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "jobs", "parent_candidate_id", "TEXT")
            self._ensure_column(conn, "results", "trace_id", "TEXT NOT NULL DEFAULT ''")

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        columns = {row[1] for row in rows}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def upsert_campaign(self, campaign: CampaignRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO campaigns (campaign_id, status, snapshot_fingerprint)
                VALUES (?, ?, ?)
                ON CONFLICT(campaign_id) DO UPDATE SET
                  status=excluded.status,
                  snapshot_fingerprint=excluded.snapshot_fingerprint
                """,
                (campaign.campaign_id, campaign.status, campaign.snapshot_fingerprint),
            )

    def upsert_batch(self, batch: BatchRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO batches (batch_id, campaign_id, iteration, status)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(batch_id) DO UPDATE SET
                  status=excluded.status
                """,
                (batch.batch_id, batch.campaign_id, batch.iteration, batch.status),
            )

    def insert_job(self, job: ExperimentJob) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs
                (job_id, campaign_id, batch_id, candidate_id, parent_candidate_id, domain, dataset_id, strategy_id, parameters_json, seed, trace_id, priority, attempt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.job_id,
                    job.campaign_id,
                    job.batch_id,
                    job.candidate_id,
                    job.parent_candidate_id,
                    job.domain,
                    job.dataset_id,
                    job.strategy_id,
                    json.dumps(job.parameters, sort_keys=True),
                    job.seed,
                    job.trace_id,
                    job.priority,
                    job.attempt,
                ),
            )

    def insert_lineage(self, record: LineageRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO lineage_records
                (job_id, campaign_id, batch_id, candidate_id, parent_candidate_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (record.job_id, record.campaign_id, record.batch_id, record.candidate_id, record.parent_candidate_id),
            )

    def insert_result(self, result: ExperimentResult) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO results
                (job_id, campaign_id, batch_id, attempt, status, score, metrics_json, trace_id, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.job_id,
                    result.campaign_id,
                    result.batch_id,
                    result.attempt,
                    result.status,
                    result.score,
                    json.dumps(result.metrics, sort_keys=True),
                    result.trace_id,
                    result.error,
                ),
            )
            return cursor.rowcount > 0

    def insert_dead_letter(self, record: DeadLetterRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO dead_letters
                (job_id, campaign_id, batch_id, attempts, reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (record.job_id, record.campaign_id, record.batch_id, record.attempts, record.reason),
            )

    def list_results_for_batch(self, batch_id: str) -> list[ExperimentResult]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id, campaign_id, batch_id, attempt, status, score, metrics_json, trace_id, error
                FROM results
                WHERE batch_id = ?
                ORDER BY job_id ASC, attempt ASC
                """,
                (batch_id,),
            ).fetchall()
        return [
            ExperimentResult(
                job_id=row[0],
                campaign_id=row[1],
                batch_id=row[2],
                attempt=row[3],
                status=row[4],
                score=row[5],
                metrics=json.loads(row[6]),
                trace_id=row[7],
                error=row[8],
            )
            for row in rows
        ]

    def count_results(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM results").fetchone()
            return int(row[0])

    def count_dead_letters(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM dead_letters").fetchone()
            return int(row[0])

    def count_lineage_records(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM lineage_records").fetchone()
            return int(row[0])

    def log_event(self, event: AuditEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_events
                (trace_id, event_type, campaign_id, batch_id, job_id, attempt, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.trace_id,
                    event.event_type,
                    event.campaign_id,
                    event.batch_id,
                    event.job_id,
                    event.attempt,
                    json.dumps(event.payload or {}, sort_keys=True),
                ),
            )

    def list_events(self, campaign_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT trace_id, event_type, campaign_id, batch_id, job_id, attempt, payload_json
                FROM audit_events
                WHERE campaign_id = ?
                ORDER BY event_id ASC
                """,
                (campaign_id,),
            ).fetchall()
        return [
            {
                "trace_id": row[0],
                "event_type": row[1],
                "campaign_id": row[2],
                "batch_id": row[3],
                "job_id": row[4],
                "attempt": row[5],
                "payload": json.loads(row[6]),
            }
            for row in rows
        ]

    def save_checkpoint(
        self,
        *,
        campaign_id: str,
        iteration: int,
        optimizer_state: dict,
        best_score: float,
        best_parameters: dict,
        trace_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO checkpoints
                (campaign_id, iteration, optimizer_state_json, best_score, best_parameters_json, trace_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    iteration,
                    json.dumps(optimizer_state, sort_keys=True),
                    best_score,
                    json.dumps(best_parameters, sort_keys=True),
                    trace_id,
                ),
            )

    def get_latest_checkpoint(self, campaign_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT iteration, optimizer_state_json, best_score, best_parameters_json, trace_id
                FROM checkpoints
                WHERE campaign_id = ?
                ORDER BY iteration DESC
                LIMIT 1
                """,
                (campaign_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "iteration": int(row[0]),
            "optimizer_state": json.loads(row[1]),
            "best_score": float(row[2]),
            "best_parameters": json.loads(row[3]),
            "trace_id": row[4],
        }

    def get_campaign_status(self, campaign_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM campaigns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def get_batch_status(self, batch_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status FROM batches WHERE batch_id = ?",
                (batch_id,),
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def dump_results(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT job_id, score, metrics_json FROM results ORDER BY job_id ASC"
            ).fetchall()
        return [
            {"job_id": job_id, "score": score, "metrics": json.loads(metrics_json)}
            for job_id, score, metrics_json in rows
        ]
