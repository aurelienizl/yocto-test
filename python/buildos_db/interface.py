# -----------------------------------------------------------------------------
# LIBRARY: buildos_db
# FILE: buildos_db/interface.py
# AUTHOR: aurelien.izoulet
# LICENSE: Apache License 2.0
# -----------------------------------------------------------------------------

import abc
from typing import List, Dict, Optional, Iterator


class DBInterface(abc.ABC):
    """Abstract persistence interface for BuildOS.

    The model hierarchy is:
        GitRepository 1 ── * GitTask 1 ── * (Log, ContentChunk)
    """

    # ---------------------------------------------------------------------
    # bootstrap
    # ---------------------------------------------------------------------
    @abc.abstractmethod
    def init_db(self) -> None:
        """(Re-)create the schema **and** pre-load repositories from $SERVE."""

    # ---------------------------------------------------------------------
    # repositories
    # ---------------------------------------------------------------------
    @abc.abstractmethod
    def add_repository(
        self, repo_id: str, git_uri: str, name: str, created_at: str
    ) -> None: ...

    @abc.abstractmethod
    def get_repositories(self) -> List[Dict]: ...

    @abc.abstractmethod
    def get_repository(self, repo_id: str) -> Optional[Dict]: ...

    # ---------------------------------------------------------------------
    # tasks
    # ---------------------------------------------------------------------
    @abc.abstractmethod
    def create_task(self, task_id: str, repo_id: str, created_at: str) -> None: ...

    @abc.abstractmethod
    def update_task_status(
        self,
        task_id: str,
        status: str,
        started_at: Optional[str] = None,
        finished_at: Optional[str] = None,
    ) -> None: ...

    @abc.abstractmethod
    def get_tasks_for_repo(self, repo_id: str) -> List[Dict]: ...

    @abc.abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict]: ...

    # ---------------------------------------------------------------------
    # content (unchanged)
    # ---------------------------------------------------------------------
    @abc.abstractmethod
    def update_task_content(self, task_id: str, content: bytes) -> None: ...

    @abc.abstractmethod
    def stream_task_content(self, task_id: str) -> Iterator[bytes]: ...

    # ---------------------------------------------------------------------
    # logging (unchanged)
    # ---------------------------------------------------------------------
    @abc.abstractmethod
    def add_log(self, task_id: str, timestamp: str, line: str) -> None: ...

    @abc.abstractmethod
    def get_logs(self, task_id: str) -> List[Dict]: ...

    @abc.abstractmethod
    def get_logs_since(self, task_id: str, after_id: int) -> List[Dict]: ...
