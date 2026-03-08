"""WebSocket endpoints for AI chat and progress streaming."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.dependencies import get_manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket) -> None:
    """Interactive AI chat — receives user messages and streams responses."""
    await ws.accept()
    manager = get_manager()

    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            user_message = payload.get("message", "")
            product_id = payload.get("product_id")

            if not user_message:
                await ws.send_json({"type": "error", "message": "Empty message"})
                continue

            await ws.send_json({"type": "thinking", "message": "AI is processing..."})

            try:
                from core.ai_client import create_ai_client
                from config.settings import get_config

                config = get_config()
                ai = create_ai_client(config)

                system_prompt = (
                    "Sen bir e-ticaret SEO uzmanisin. "
                    "Kullanicinin urun icerik sorularina yardimci ol."
                )

                context = ""
                if product_id:
                    from data import db
                    product = db.get_product(product_id)
                    if product:
                        context = (
                            f"\nUrun: {product.name}\n"
                            f"Aciklama: {product.description[:500]}\n"
                            f"Meta Title: {product.meta_title}\n"
                            f"Meta Desc: {product.meta_description}\n"
                        )

                full_message = user_message + context
                response = ai.generate(system_prompt, full_message)

                await ws.send_json({
                    "type": "response",
                    "message": response,
                    "usage": getattr(ai, "last_usage", {}),
                })

            except Exception as e:
                logger.error("Chat error: %s", e)
                await ws.send_json({"type": "error", "message": str(e)})

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")


@router.websocket("/ws/progress")
async def ws_progress(ws: WebSocket) -> None:
    """Progress updates for long-running operations (batch rewrite, fetch)."""
    await ws.accept()

    try:
        while True:
            # Client sends a ping or the server sends progress updates
            # This is a placeholder — actual progress will be wired to
            # ProductManager operations via an event queue
            await ws.receive_text()
            await ws.send_json({"type": "ping", "message": "connected"})
    except WebSocketDisconnect:
        logger.info("Progress WebSocket disconnected")
