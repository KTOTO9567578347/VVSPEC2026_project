import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas import PointOut

router = APIRouter(tags=["live"])


@router.websocket("/ws/live")
async def live(websocket: WebSocket, robot_id: str | None = None):
    """Live-телеметрия. Без robot_id — от всех роботов.

    Сообщение: {"robot_id": "...", "points": [PointOut, ...]} — приходит на каждый батч.
    """
    hub = websocket.app.state.hub
    await websocket.accept()
    queue = hub.subscribe(robot_id)

    async def sender():
        while True:
            msg = await queue.get()
            await websocket.send_json(
                {
                    "robot_id": msg["robot_id"],
                    "points": [PointOut.from_row(p).model_dump() for p in msg["points"]],
                }
            )

    async def receiver():
        # клиенту слать ничего не нужно, ждём только закрытия
        while True:
            await websocket.receive_text()

    tasks = [asyncio.create_task(sender()), asyncio.create_task(receiver())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        hub.unsubscribe(queue, robot_id)
