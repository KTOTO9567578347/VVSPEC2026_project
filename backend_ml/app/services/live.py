"""Раздача свежей телеметрии подписчикам WebSocket.

gRPC-сервер работает в своих потоках, а WebSocket'ы — в event loop FastAPI,
поэтому publish() перекидывает данные в loop через call_soon_threadsafe.
"""

import asyncio
import logging
import threading
from collections import defaultdict
from typing import Any

log = logging.getLogger(__name__)

ALL = "*"


class LiveHub:
    def __init__(self, queue_size: int = 100):
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._queue_size = queue_size

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        self._loop = loop

    def subscribe(self, robot_id: str | None = None) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        with self._lock:
            self._subs[robot_id or ALL].add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue, robot_id: str | None = None) -> None:
        with self._lock:
            key = robot_id or ALL
            self._subs[key].discard(q)
            if not self._subs[key]:
                del self._subs[key]

    def subscribers_count(self) -> int:
        with self._lock:
            return sum(len(s) for s in self._subs.values())

    def publish(self, robot_id: str, points: list[dict[str, Any]]) -> None:
        """Можно вызывать из любого потока."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        with self._lock:
            if not self._subs.get(robot_id) and not self._subs.get(ALL):
                return
        message = {"robot_id": robot_id, "points": points}
        try:
            loop.call_soon_threadsafe(self._dispatch, robot_id, message)
        except RuntimeError:
            pass  # loop уже закрывается

    def _dispatch(self, robot_id: str, message: dict[str, Any]) -> None:
        with self._lock:
            queues = list(self._subs.get(robot_id, ())) + list(self._subs.get(ALL, ()))
        for q in queues:
            if q.full():
                # медленный клиент — выкидываем самое старое сообщение
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(message)
