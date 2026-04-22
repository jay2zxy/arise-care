from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.stream import StreamSession

router = APIRouter()


@router.websocket("/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    session = StreamSession(ws)
    session.start()
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if "bytes" in msg and msg["bytes"] is not None:
                await session.handle_chunk(msg["bytes"])
            elif "text" in msg and msg["text"] is not None:
                # reserved: control frames like {"type":"stop"}
                if msg["text"] == "stop":
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await session.close()
