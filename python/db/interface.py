import abc
from typing import Iterator, List, Optional, Dict


class DBInterface(abc.ABC):
    @abc.abstractmethod
    def init_db(self) -> None:
        """Initialize or migrate the schema."""
        pass

    @abc.abstractmethod
    def create_task(self, task_id: str, git_uri: str, created_at: str) -> None:
        """Insert a new queued task."""
        pass

    @abc.abstractmethod
    def update_task_status(
        self,
        task_id: str,
        status: str,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> None:
        """Update status (and optional timestamps) of a task."""
        pass

    @abc.abstractmethod
    def update_task_content(self, task_id: str, content: bytes) -> None:
        """
        Store the full ZIP bytes (or an equivalent binary representation)
        for a given task.
        """
        pass

    @abc.abstractmethod
    def stream_task_content(self, task_id: str) -> Iterator[bytes]:
        """
        Stream the ZIP bytes back in chunks (e.g. for large files).
        Yields successive bytes objects until complete.
        """
        pass

    @abc.abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict]:
        """
        Return metadata for a single task (no raw blobs),
        e.g. {'id': ..., 'git_uri': ..., 'status': ..., ..., 'has_content': 0|1}
        """
        pass

    @abc.abstractmethod
    def get_tasks(self) -> List[Dict]:
        """
        Return a list of all tasks’ metadata (no raw blobs),
        each including a has_content flag.
        """
        pass

    @abc.abstractmethod
    def add_log(self, task_id: str, timestamp: str, line: str) -> None:
        """Append a line to the logs for a given task."""
        pass

    @abc.abstractmethod
    def get_logs(self, task_id: str) -> List[Dict]:
        """
        Return all log rows for a task as a list of dicts:
        [{'id': ..., 'timestamp': ..., 'line': ...}, ...]
        """
        pass

    @abc.abstractmethod
    def get_logs_since(self, task_id: str, after_id: int) -> List[Dict]:
        """
        Return log rows for a task with id > after_id.
        """
        pass
