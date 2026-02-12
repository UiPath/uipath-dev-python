"""WebSocket endpoint handler."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from uipath.dev.models.chat import get_user_message, get_user_message_event
from uipath.dev.models.data import ChatData
from uipath.dev.server.ws.protocol import ClientCommand, parse_client_message

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle WebSocket connections for real-time event streaming."""
    server = websocket.app.state.server
    manager = server.connection_manager

    await manager.connect(websocket)

    try:
        while True:
            data: dict[str, Any] = await websocket.receive_json()
            command, payload = parse_client_message(data)

            if command == ClientCommand.SUBSCRIBE.value:
                run_id = payload.get("run_id", "")
                if run_id:
                    manager.subscribe(websocket, run_id)
                    logger.debug(f"Client subscribed to run {run_id}")

            elif command == ClientCommand.UNSUBSCRIBE.value:
                run_id = payload.get("run_id", "")
                if run_id:
                    manager.unsubscribe(websocket, run_id)
                    logger.debug(f"Client unsubscribed from run {run_id}")

            elif command == ClientCommand.CHAT_MESSAGE.value:
                run_id = payload.get("run_id", "")
                text = payload.get("text", "")
                if run_id and text:
                    await _handle_chat_message(server, run_id, text)

            elif command == ClientCommand.DEBUG_STEP.value:
                run_id = payload.get("run_id", "")
                if run_id:
                    run = server.run_service.get_run(run_id)
                    if run:
                        server.run_service.step_debug(run)

            elif command == ClientCommand.DEBUG_CONTINUE.value:
                run_id = payload.get("run_id", "")
                if run_id:
                    run = server.run_service.get_run(run_id)
                    if run:
                        server.run_service.continue_debug(run)

            elif command == ClientCommand.DEBUG_STOP.value:
                run_id = payload.get("run_id", "")
                if run_id:
                    run = server.run_service.get_run(run_id)
                    if run:
                        server.run_service.stop_debug(run)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket error")
        manager.disconnect(websocket)


async def _handle_chat_message(server: Any, run_id: str, text: str) -> None:
    """Process an incoming chat message from a WebSocket client."""
    run = server.run_service.get_run(run_id)
    if run is None:
        return

    if run.status == "running":
        return  # Ignore while processing

    if run.status == "suspended":
        # Try JSON parse for resume data
        import json

        try:
            run.resume_data = json.loads(text)
        except json.JSONDecodeError:
            run.resume_data = text

        debug_bridge = server.run_service.get_debug_bridge(run.id)
        if debug_bridge:
            asyncio.create_task(server.run_service.resume_debug(run, run.resume_data))
        else:
            asyncio.create_task(server.run_service.execute(run))
    else:
        # Regular chat message
        msg = get_user_message(text)
        msg_ev = get_user_message_event(text)

        chat_data = ChatData(event=msg_ev, message=msg, run_id=run.id)
        server._on_chat(chat_data)

        run.add_event(msg_ev)
        run.input_data = {"messages": [msg.model_dump(by_alias=True)]}

        asyncio.create_task(server.run_service.execute(run))
