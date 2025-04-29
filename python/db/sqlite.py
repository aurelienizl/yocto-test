import sqlite3
import threading
from db.interface import DBInterface

class SQLiteDB(DBInterface):
    def __init__(self, db_path: str = 'sqlite'):
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
            c.execute('PRAGMA journal_mode=WAL;')
            c.execute('PRAGMA synchronous=NORMAL;')
            c.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                git_uri TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            );
            ''')
            c.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                line TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            );
            ''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_logs_task_id ON logs(task_id);')
            conn.commit()
            conn.close()

    def create_task(self, task_id, git_uri, created_at):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                'INSERT INTO tasks (id, git_uri, status, created_at) VALUES (?, ?, ?, ?)',
                (task_id, git_uri, 'queued', created_at)
            )
            conn.commit()
            conn.close()

    def update_task_status(self, task_id, status, started_at=None, finished_at=None):
        with self._lock:
            conn = self._get_conn()
            sql = 'UPDATE tasks SET status = ?'
            params = [status]
            if started_at:
                sql += ', started_at = ?'
                params.append(started_at)
            if finished_at:
                sql += ', finished_at = ?'
                params.append(finished_at)
            sql += ' WHERE id = ?'
            params.append(task_id)
            conn.execute(sql, tuple(params))
            conn.commit()
            conn.close()

    def add_log(self, task_id, timestamp, line):
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                'INSERT INTO logs (task_id, timestamp, line) VALUES (?, ?, ?)',
                (task_id, timestamp, line)
            )
            conn.commit()
            conn.close()

    def get_task(self, task_id):
        conn = self._get_conn()
        c = conn.cursor()
        c.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_tasks(self):
        conn = self._get_conn()
        rows = conn.execute('SELECT * FROM tasks ORDER BY created_at').fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_logs(self, task_id):
        conn = self._get_conn()
        rows = conn.execute(
            'SELECT id, timestamp, line FROM logs WHERE task_id = ? ORDER BY id',
            (task_id,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_logs_since(self, task_id, after_id):
        conn = self._get_conn()
        rows = conn.execute(
            'SELECT id, timestamp, line FROM logs WHERE task_id = ? AND id > ? ORDER BY id',
            (task_id, after_id)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]