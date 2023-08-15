import asyncio
from typing import Callable, Union


class AsyncPool:
    def __init__(self, pool_size: int) -> None:
        self._pool_size = pool_size
        self._has_done = False
        self._tasks = asyncio.Queue()
        self._results = asyncio.Queue()
        self._workers = [
            asyncio.create_task(self._worker()) for _ in range(self._pool_size)
        ]

    async def _worker(self):
        while self._results.qsize() < self._pool_size:
            worker_id, coroutine, kwargs = await self._tasks.get()
            result = await coroutine(**kwargs)
            await self._results.put({worker_id: result})

    async def add_worker(
        self, worker_id: Union[str, int], coroutine: Callable, **kwargs
    ):
        await self._tasks.put((worker_id, coroutine, kwargs))

    async def start(self):
        results = []
        await asyncio.gather(*self._workers)

        for _ in range(self._results.qsize()):
            results.append(await self._results.get())

        return results
