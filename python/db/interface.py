import abc

class DBInterface(abc.ABC):
    @abc.abstractmethod
    def init_db(self):
        pass

    @abc.abstractmethod
    def create_task(self, task_id: str, git_uri: str, created_at: str):
        pass

    @abc.abstractmethod
    def update_task_status(
        self,
        task_id: str,
        status: str,
        started_at: str = None,
        finished_at: str = None
    ):
        pass

    @abc.abstractmethod
    def add_log(self, task_id: str, timestamp: str, line: str):
        pass

    @abc.abstractmethod
    def get_task(self, task_id: str) -> dict:
        pass

    @abc.abstractmethod
    def get_tasks(self) -> list:
        pass

    @abc.abstractmethod
    def get_logs(self, task_id: str) -> list:
        pass

    @abc.abstractmethod
    def get_logs_since(self, task_id: str, after_id: int) -> list:
        pass