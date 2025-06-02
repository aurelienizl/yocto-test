# -----------------------------------------------------------------------------
# buildos_db/sqlite.py
# -----------------------------------------------------------------------------
import base64
import datetime
import os
import sqlite3
import threading
import uuid
from typing import Dict, Iterator, List, Optional

from .interface import DBInterface

SCHEMA_SQL = """
CREATE TABLE repositories (
  id         TEXT PRIMARY KEY,
  git_uri    TEXT NOT NULL UNIQUE,
  name       TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE tasks (
  id          TEXT PRIMARY KEY,
  repo_id     TEXT NOT NULL,
  status      TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  started_at  TEXT,
  finished_at TEXT,
  FOREIGN KEY (repo_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE TABLE logs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id   TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  line      TEXT NOT NULL,
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_logs_task_id ON logs(task_id);

CREATE TABLE content_chunks (
  task_id TEXT NOT NULL,
  seq     INTEGER NOT NULL,
  data    TEXT NOT NULL,
  PRIMARY KEY (task_id, seq),
  FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
"""

class SQLiteDB(DBInterface):
    """Concrete implementation using a single‑file WAL‑enabled SQLite DB."""

    def __init__(self, db_path: str = "sqlite.db"):
        self.db_path = db_path
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # ------------------------------------------------------------------
    # bootstrap
    # ------------------------------------------------------------------
    def init_db(self):
        """Drop & recreate schema **and** seed repo table from $SERVE."""
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()

            cur.executescript(
                """DROP TABLE IF EXISTS content_chunks;
                   DROP TABLE IF EXISTS logs;
                   DROP TABLE IF EXISTS tasks;
                   DROP TABLE IF EXISTS repositories;"""
            )

            # performance pragmas (same as v1)
            cur.executescript(
                """PRAGMA journal_mode=WAL;
                   PRAGMA synchronous=OFF;
                   PRAGMA wal_autocheckpoint=0;
                   PRAGMA mmap_size=268435456;
                   PRAGMA temp_store=MEMORY;
                   PRAGMA cache_size=20000;"""
            )

            cur.executescript(SCHEMA_SQL)
            now = datetime.datetime.utcnow().isoformat()

            # seed repositories from env
            for uri in [u.strip() for u in os.getenv("SERVE", "").split(",") if u.strip()]:
                repo_id = str(uuid.uuid4())
                name_parts = uri.rstrip(".git").split("/")[-2:]
                display_name = "/".join(name_parts)
                cur.execute(
                    "INSERT INTO repositories (id, git_uri, name, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (repo_id, uri, display_name, now),
                )

            conn.commit()
            conn.close()
            return True  # handy for testing

    # ------------------------------------------------------------------
    # repositories
    # ------------------------------------------------------------------
    def add_repository(self, repo_id: str, git_uri: str, name: str,
                       created_at: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO repositories (id, git_uri, name, created_at) "
                "VALUES (?, ?, ?, ?)",
                (repo_id, git_uri, name, created_at),
            )
            conn.commit(); conn.close()

    def get_repositories(self) -> List[Dict]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT r.*, (SELECT COUNT(1) FROM tasks t WHERE t.repo_id = r.id)
                 AS task_count
                 FROM repositories r
                 ORDER BY r.name"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_repository(self, repo_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM repositories WHERE id = ?", (repo_id,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # tasks
    # ------------------------------------------------------------------
    def create_task(self, task_id: str, repo_id: str, created_at: str):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO tasks (id, repo_id, status, created_at) "
                "VALUES (?, ?, 'queued', ?)",
                (task_id, repo_id, created_at),
            )
            conn.commit(); conn.close()

    def update_task_status(self, task_id: str, status: str,
                           started_at: Optional[str] = None,
                           finished_at: Optional[str] = None):
        with self._lock:
            conn = self._get_conn()
            sql = "UPDATE tasks SET status = ?"
            params = [status]
            if started_at:
                sql += ", started_at = ?"
                params.append(started_at)
            if finished_at:
                sql += ", finished_at = ?"
                params.append(finished_at)
            sql += " WHERE id = ?"
            params.append(task_id)
            conn.execute(sql, tuple(params))
            conn.commit(); conn.close()

    def get_tasks_for_repo(self, repo_id: str) -> List[Dict]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT t.*, CASE WHEN EXISTS(SELECT 1 FROM content_chunks cc
                 WHERE cc.task_id = t.id) THEN 1 ELSE 0 END AS has_content
                 FROM tasks t WHERE t.repo_id = ? ORDER BY t.created_at DESC""",
            (repo_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_task(self, task_id: str) -> Optional[Dict]:
        conn = self._get_conn()
        row = conn.execute(
            """SELECT t.*, CASE WHEN EXISTS(SELECT 1 FROM content_chunks cc
                 WHERE cc.task_id = t.id) THEN 1 ELSE 0 END AS has_content
                 FROM tasks t WHERE t.id = ?""",
            (task_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # content (unchanged)
    # ------------------------------------------------------------------
    def update_task_content(self, task_id: str, blob_bytes: bytes):
        chunk_size = 256 * 1024
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM content_chunks WHERE task_id = ?", (task_id,))
            for seq, offset in enumerate(range(0, len(blob_bytes), chunk_size)):
                slice_ = blob_bytes[offset:offset + chunk_size]
                b64 = base64.b64encode(slice_).decode("ascii")
                cur.execute(
                    "INSERT INTO content_chunks (task_id, seq, data) VALUES (?, ?, ?)",
                    (task_id, seq, b64),
                )
            conn.commit(); conn.close()

    def stream_task_content(self, task_id: str) -> Iterator[bytes]:
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT data FROM content_chunks WHERE task_id = ? ORDER BY seq",
            (task_id,),
        )
        for row in cur:
            yield base64.b64decode(row["data"])
        conn.close()

    # ------------------------------------------------------------------
    # logging (unchanged)
    # ------------------------------------------------------------------
    def add_log(self, task_id: str, timestamp: str, line: str):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO logs (task_id, timestamp, line) VALUES (?, ?, ?)",
                (task_id, timestamp, line),
            )
            conn.commit(); conn.close()

    def get_logs(self, task_id: str) -> List[Dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, timestamp, line FROM logs WHERE task_id = ? ORDER BY id",
            (task_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_logs_since(self, task_id: str, after_id: int) -> List[Dict]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT id, timestamp, line FROM logs WHERE task_id = ? AND id > ?
                 ORDER BY id""",
            (task_id, after_id),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
