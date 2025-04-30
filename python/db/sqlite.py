import sqlite3
import threading
import base64
from db.interface import DBInterface


class SQLiteDB(DBInterface):
    def __init__(self, db_path: str = "sqlite.db"):
        self.db_path = db_path
        self._lock = threading.Lock()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self._lock:
            conn = self._get_conn()
            c = conn.cursor()

            c.execute("PRAGMA journal_mode=WAL;")  # concurrent readers + writers
            c.execute("PRAGMA synchronous=OFF;")  # skip fsync on commits
            c.execute("PRAGMA wal_autocheckpoint=0;")  # no auto-checkpoint stalls
            c.execute("PRAGMA mmap_size=268435456;")  # allow 256 MB mmap reads
            c.execute("PRAGMA temp_store=MEMORY;")  # keep temp tables in RAM
            c.execute("PRAGMA cache_size=20000;")  # ~80 MB page cache

            c.execute(
                """
            CREATE TABLE tasks (
              id           TEXT PRIMARY KEY,
              git_uri      TEXT NOT NULL,
              status       TEXT NOT NULL,
              created_at   TEXT NOT NULL,
              started_at   TEXT,
              finished_at  TEXT
            );
            """
            )

            c.execute(
                """
            CREATE TABLE logs (
              id        INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id   TEXT NOT NULL,
              timestamp TEXT NOT NULL,
              line      TEXT NOT NULL,
              FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            """
            )
            c.execute("CREATE INDEX idx_logs_task_id ON logs(task_id);")

            c.execute(
                """
            CREATE TABLE content_chunks (
              task_id TEXT NOT NULL,
              seq     INTEGER NOT NULL,
              data    TEXT    NOT NULL,   -- base64-encoded slice
              PRIMARY KEY(task_id, seq),
              FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            """
            )
            conn.commit()
            conn.close()

    def create_task(self, task_id, git_uri, created_at):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO tasks (id, git_uri, status, created_at) VALUES (?, ?, ?, ?)",
                (task_id, git_uri, "queued", created_at),
            )
            conn.commit()
            conn.close()

    def update_task_status(self, task_id, status, started_at=None, finished_at=None):
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
            conn.commit()
            conn.close()

    def update_task_content(self, task_id, blob_bytes: bytes):
        """
        Split the ZIP bytes into ~256KB chunks, base64 each slice,
        and insert into content_chunks.
        """
        chunk_size = 256 * 1024
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM content_chunks WHERE task_id = ?", (task_id,))
            seq = 0
            for offset in range(0, len(blob_bytes), chunk_size):
                slice_ = blob_bytes[offset : offset + chunk_size]
                b64 = base64.b64encode(slice_).decode("ascii")
                cur.execute(
                    "INSERT INTO content_chunks(task_id, seq, data) VALUES (?, ?, ?)",
                    (task_id, seq, b64),
                )
                seq += 1
            conn.commit()
            conn.close()

    def get_task(self, task_id: str) -> dict:
        conn = self._get_conn()
        row = conn.execute(
            """
          SELECT
            t.id, t.git_uri, t.status, t.created_at, t.started_at, t.finished_at,
            CASE WHEN EXISTS(
              SELECT 1 FROM content_chunks cc WHERE cc.task_id = t.id
            ) THEN 1 ELSE 0 END AS has_content
          FROM tasks t
          WHERE t.id = ?
        """,
            (task_id,),
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_tasks(self):
        conn = self._get_conn()
        rows = conn.execute(
            """
          SELECT
            t.id, t.git_uri, t.status, t.created_at, t.started_at, t.finished_at,
            CASE WHEN EXISTS(
              SELECT 1 FROM content_chunks cc WHERE cc.task_id = t.id
            ) THEN 1 ELSE 0 END AS has_content
          FROM tasks t
          ORDER BY t.created_at
        """
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def stream_task_content(self, task_id):
        """
        Generator of raw bytes: re-decode each base64 chunk in order.
        """
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT data FROM content_chunks WHERE task_id = ? ORDER BY seq", (task_id,)
        )
        for row in cur:
            yield base64.b64decode(row["data"])
        conn.close()

    def add_log(self, task_id, timestamp, line):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO logs (task_id, timestamp, line) VALUES (?, ?, ?)",
                (task_id, timestamp, line),
            )
            conn.commit()
            conn.close()

    def get_logs(self, task_id):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, timestamp, line FROM logs WHERE task_id = ? ORDER BY id",
            (task_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_logs_since(self, task_id, after_id):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, timestamp, line FROM logs WHERE task_id = ? AND id > ? ORDER BY id",
            (task_id, after_id),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
