"""WebSocket chat with MCP tool integration + REST endpoints for MCP status."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from api.dependencies import get_manager
from api.schemas import MCPStatusResponse, MessageResponse
from core.product_manager import ProductManager
from data import db

# Each WebSocket connection creates its own ProductManager so that chat
# history, product context, and MCP state are fully isolated per client.

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_mcp_status_payload(
    manager: ProductManager,
    *,
    message_override: str | None = None,
) -> dict[str, object]:
    has_token = manager.chat_has_mcp
    initialized = manager.chat_mcp_initialized
    if initialized:
        message = "MCP bagli"
    elif has_token:
        message = "Token var, baglanti bekleniyor"
    else:
        message = "MCP token yok"

    return {
        "type": "mcp_status",
        "has_token": has_token,
        "initialized": initialized,
        "tool_count": manager.chat_mcp_tool_count,
        "tools": manager.chat_mcp_tools,
        "message": message_override or message,
    }


# ── REST endpoints for MCP ───────────────────────────────────────────────────

@router.get("/api/mcp/status", response_model=MCPStatusResponse)
async def mcp_status(
    manager: ProductManager = Depends(get_manager),
) -> MCPStatusResponse:
    """Check MCP connection status."""
    payload = _build_mcp_status_payload(manager)
    return MCPStatusResponse(**payload)


@router.post("/api/mcp/initialize", response_model=MCPStatusResponse)
async def mcp_initialize(
    manager: ProductManager = Depends(get_manager),
) -> MCPStatusResponse:
    """Initialize MCP connection."""
    success, message = await manager.initialize_mcp()
    return MCPStatusResponse(
        has_token=manager.chat_has_mcp,
        initialized=success,
        message=message,
    )


@router.post("/api/chat/clear", response_model=MessageResponse)
async def clear_chat(
    manager: ProductManager = Depends(get_manager),
) -> MessageResponse:
    """Clear chat history."""
    manager.clear_chat_history()
    return MessageResponse(message="Chat gecmisi temizlendi")


# ── WebSocket chat ───────────────────────────────────────────────────────────

@router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket) -> None:
    """Multi-turn AI chat with MCP tool calling support.

    A fresh ProductManager is instantiated for every connection so that
    conversation history and product context are fully isolated between
    clients.  The instance is closed when the connection ends.
    """
    await ws.accept()
    manager = ProductManager()  # per-connection instance — NOT the global singleton
    send_lock = asyncio.Lock()
    active_chat_task: asyncio.Task | None = None
    notify_on_cancel = True

    async def send_json(payload: dict[str, object]) -> None:
        async with send_lock:
            await ws.send_json(payload)

    async def cancel_active_chat(*, notify: bool) -> bool:
        nonlocal active_chat_task, notify_on_cancel
        if active_chat_task is None or active_chat_task.done():
            return False
        notify_on_cancel = notify
        manager.cancel_chat_request()
        active_chat_task.cancel()
        return True

    await ws.send_json(_build_mcp_status_payload(manager))

    # Auto-initialize MCP if token is configured
    if manager.chat_has_mcp and not manager.chat_mcp_initialized:
        try:
            success, msg = await manager.initialize_mcp()
            await send_json(_build_mcp_status_payload(manager, message_override=msg))
        except Exception as e:
            await send_json(_build_mcp_status_payload(manager, message_override=str(e)))

    try:
        receive_task = asyncio.create_task(ws.receive_text())
        while True:
            wait_tasks: set[asyncio.Task] = {receive_task}
            if active_chat_task is not None:
                wait_tasks.add(active_chat_task)

            done, _ = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)

            if active_chat_task is not None and active_chat_task in done:
                try:
                    active_chat_task.result()
                except asyncio.CancelledError:
                    if notify_on_cancel:
                        await send_json({
                            "type": "cancelled",
                            "message": "Istek kullanici tarafindan durduruldu.",
                        })
                except Exception as e:
                    logger.error("Chat error: %s", e)
                    await send_json({"type": "error", "content": str(e)})
                finally:
                    active_chat_task = None
                    notify_on_cancel = True

            if receive_task not in done:
                continue

            try:
                raw = receive_task.result()
            except WebSocketDisconnect:
                raise
            receive_task = asyncio.create_task(ws.receive_text())

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await send_json({"type": "error", "content": "Invalid JSON"})
                continue

            action = payload.get("action", "message")

            if action == "set_context":
                product_id = payload.get("product_id")
                if product_id:
                    product = await db.get_product(product_id)
                    score = await db.get_latest_score(product_id) if product else None
                    manager.set_chat_product_context(product, score)
                    await send_json({
                        "type": "context_set",
                        "product_id": product_id,
                        "product_name": product.name if product else "",
                    })
                continue

            if action == "clear":
                await cancel_active_chat(notify=False)
                manager.clear_chat_history()
                await send_json({"type": "cleared"})
                continue

            if action == "cancel":
                await cancel_active_chat(notify=True)
                continue

            if active_chat_task is not None:
                await send_json({
                    "type": "error",
                    "content": "Calisan bir chat istegi var. Once Stop ile iptal edin.",
                })
                continue

            user_message = payload.get("message", "")
            if not user_message:
                await send_json({"type": "error", "content": "Bos mesaj"})
                continue

            product_id = payload.get("product_id")
            if product_id:
                product = await db.get_product(product_id)
                score = await db.get_latest_score(product_id) if product else None
                manager.set_chat_product_context(product, score)

            await send_json({"type": "thinking"})
            notify_on_cancel = True
            active_chat_task = asyncio.create_task(_stream_chat_response(manager, user_message, send_json))

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
    finally:
        # Cancel any in-flight requests before tearing down this connection's manager.
        manager.cancel_chat_request()
        if 'receive_task' in locals():
            receive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await receive_task
        if active_chat_task is not None:
            active_chat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await active_chat_task
        # Release HTTP clients and MCP connection owned by this per-connection instance.
        with contextlib.suppress(Exception):
            await manager.close()


async def _stream_chat_response(
    manager: ProductManager,
    user_message: str,
    send_json: Callable[[dict[str, object]], Awaitable[None]],
) -> None:
    async for event in manager.stream_chat_message(user_message):
        await send_json(event)


@router.websocket("/ws/progress")
async def ws_progress(ws: WebSocket) -> None:
    """Progress updates for long-running operations."""
    await ws.accept()
    try:
        while True:
            await ws.receive_text()
            await ws.send_json({"type": "ping", "message": "connected"})
    except WebSocketDisconnect:
        logger.info("Progress WebSocket disconnected")
