import asyncio
import logging
from collections import abc
from datetime import datetime


class Scheduler:
    def __init__(self, name: str):
        self.name = name
        self._logger = logging.getLogger(f"{__name__}.{name}")
        self.tasks: dict[str, asyncio.Task] = {}

    async def _run_later(
        self, delay: float, task_id: str, coroutine: abc.Coroutine
    ) -> None:
        self._logger.info(
            "Waiting %s seconds before awaiting task with id=%s", delay, task_id
        )
        await asyncio.sleep(delay)

        self._logger.info("Awaiting task with id=%s", task_id)
        await coroutine
        self._logger.info("Finished task with id=%s", task_id)

    def create_task(self, task_id: str, coroutine: abc.Coroutine) -> None:
        task = asyncio.create_task(coroutine, name=f"{self.name}_{task_id}")
        self.tasks[task_id] = task

        self._logger.info("Scheduled task with id=%s", task_id)

    def schedule(
        self, run_at: datetime, task_id: str, coroutine: abc.Coroutine
    ) -> None:
        now = datetime.now(run_at.tzinfo)
        delay = (run_at - now).total_seconds()
        if delay > 0:
            coroutine = self._run_later(delay, task_id, coroutine)

        self.create_task(task_id, coroutine)

    def cancel(self, task_id: str) -> None:
        self._logger.info("Canceling task with id=%s", task_id)

        try:
            task = self.tasks.pop(task_id)
        except KeyError:
            self._logger.warning(
                "Failed to cancel task, no task found with id=%s", task_id
            )
        else:
            task.cancel()
            self._logger.info("Canceled task with id=%s", task_id)

    def cancel_all(self) -> None:
        self._logger.info("Canceling all tasks")

        for task_id in self.tasks.copy():
            self.cancel(task_id)
