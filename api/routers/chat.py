"""WebSocket chat with MCP tool integration + REST endpoints for MCP status."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from api.dependencies import get_manager
from api.schemas import MCPStatusResponse, MessageResponse
from core.product_manager import ProductManager
from data import db

logger = logging.getLogger(__name__)

router = APIRouter()


# ── REST endpoints for MCP ───────────────────────────────────────────────────

@router.get("/api/mcp/status", response_model=MCPStatusResponse)
async def mcp_status(
    manager: ProductManager = Depends(get_manager),
) -> MCPStatusResponse:
    """Check MCP connection status."""
    cfg = manager.get_config()
    has_token = bool(cfg.ikas_mcp_token)
    initialized = manager.chat_mcp_initialized
    return MCPStatusResponse(
        has_token=has_token,
        initialized=initialized,
        message="MCP bagli" if initialized else ("Token var, baglanti bekleniyor" if has_token else "MCP token yok"),
    )


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
    """Multi-turn AI chat with MCP tool calling support."""
    await ws.accept()
    manager = get_manager()

    # Auto-initialize MCP if token is configured
    if manager.chat_has_mcp and not manager.chat_mcp_initialized:
        try:
            success, msg = await manager.initialize_mcp()
            await ws.send_json({"type": "mcp_status", "initialized": success, "message": msg})
        except Exception as e:
            await ws.send_json({"type": "mcp_status", "initialized": False, "message": str(e)})

    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "content": "Invalid JSON"})
                continue

            action = payload.get("action", "message")

            if action == "set_context":
                product_id = payload.get("product_id")
                if product_id:
                    product = db.get_product(product_id)
                    score = db.get_latest_score(product_id) if product else None
                    manager.set_chat_product_context(product, score)
                    await ws.send_json({"type": "context_set", "product_id": product_id})
                continue

            if action == "clear":
                manager.clear_chat_history()
                await ws.send_json({"type": "cleared"})
                continue

            # Default: send message
            user_message = payload.get("message", "")
            if not user_message:
                await ws.send_json({"type": "error", "content": "Bos mesaj"})
                continue

            # Set product context if provided
            product_id = payload.get("product_id")
            if product_id:
                product = db.get_product(product_id)
                score = db.get_latest_score(product_id) if product else None
                manager.set_chat_product_context(product, score)

            await ws.send_json({"type": "thinking"})

            try:
                response = await manager.send_chat_message(user_message)

                await ws.send_json({
                    "type": "response",
                    "content": response.content,
                    "thinking": response.thinking,
                    "tool_results": response.tool_results,
                    "error": response.error,
                    "meta": response.meta,
                })
            except Exception as e:
                logger.error("Chat error: %s", e)
                await ws.send_json({"type": "error", "content": str(e)})

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")


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
