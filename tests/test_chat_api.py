"""Tests for chat MCP status and initialization endpoints."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_manager
from api.routers import chat


class _RestMcpManagerStub:
    def __init__(
        self,
        *,
        has_token: bool,
        initialized: bool,
        tool_count: int = 0,
        tools: list[dict[str, str]] | None = None,
        initialize_result: tuple[bool, str] = (False, ""),
    ) -> None:
        self.chat_has_mcp = has_token
        self.chat_mcp_initialized = initialized
        self.chat_mcp_tool_count = tool_count
        self.chat_mcp_tools = tools or []
        self._initialize_result = initialize_result
        self.initialize_calls = 0

    async def initialize_mcp(self) -> tuple[bool, str]:
        self.initialize_calls += 1
        success, message = self._initialize_result
        self.chat_mcp_initialized = success
        return success, message

    def clear_chat_history(self) -> None:
        return None


def _build_test_app(manager) -> FastAPI:
    app = FastAPI()
    app.include_router(chat.router)
    app.dependency_overrides[get_manager] = lambda: manager
    return app


def test_mcp_status_endpoint_reports_waiting_connection_state():
    manager = _RestMcpManagerStub(
        has_token=True,
        initialized=False,
        tool_count=0,
        tools=[],
    )
    app = _build_test_app(manager)

    with TestClient(app) as client:
        response = client.get("/api/mcp/status")

    assert response.status_code == 200
    assert response.json() == {
        "has_token": True,
        "initialized": False,
        "tool_count": 0,
        "tools": [],
        "message": "Token var, baglanti bekleniyor",
    }


def test_mcp_status_endpoint_reports_ready_tools():
    manager = _RestMcpManagerStub(
        has_token=True,
        initialized=True,
        tool_count=2,
        tools=[
            {"name": "listOrder", "description": "Order query"},
            {"name": "listCustomer", "description": "Customer query"},
        ],
    )
    app = _build_test_app(manager)

    with TestClient(app) as client:
        response = client.get("/api/mcp/status")

    assert response.status_code == 200
    assert response.json() == {
        "has_token": True,
        "initialized": True,
        "tool_count": 2,
        "tools": [
            {"name": "listOrder", "description": "Order query"},
            {"name": "listCustomer", "description": "Customer query"},
        ],
        "message": "MCP bagli",
    }


def test_mcp_initialize_endpoint_returns_initialize_result():
    manager = _RestMcpManagerStub(
        has_token=True,
        initialized=False,
        initialize_result=(True, "MCP baglantisi basarili! 2 operasyon hazir."),
    )
    app = _build_test_app(manager)

    with TestClient(app) as client:
        response = client.post("/api/mcp/initialize")

    assert response.status_code == 200
    assert response.json() == {
        "has_token": True,
        "initialized": True,
        "tool_count": 0,
        "tools": [],
        "message": "MCP baglantisi basarili! 2 operasyon hazir.",
    }
    assert manager.initialize_calls == 1


def test_chat_websocket_auto_initializes_mcp_on_connect(monkeypatch):
    app = FastAPI()
    app.include_router(chat.router)

    class _WsManagerStub:
        def __init__(self) -> None:
            self.chat_has_mcp = True
            self.chat_mcp_initialized = False
            self.chat_mcp_tool_count = 0
            self.chat_mcp_tools: list[dict[str, str]] = []

        def get_chat_active_skill(self):
            return None

        def cancel_chat_request(self) -> bool:
            return False

        def clear_chat_history(self) -> None:
            return None

        def set_chat_product_context(self, product, score=None) -> None:
            return None

        def set_chat_store_context(self) -> None:
            return None

        async def initialize_mcp(self) -> tuple[bool, str]:
            self.chat_mcp_initialized = True
            self.chat_mcp_tool_count = 2
            self.chat_mcp_tools = [
                {"name": "listOrder", "description": "Order query"},
                {"name": "listCustomer", "description": "Customer query"},
            ]
            return True, "MCP bagli"

        def stream_chat_message(self, message: str):
            async def _events():
                if False:  # pragma: no cover
                    yield {}

            return _events()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(chat, "ProductManager", _WsManagerStub)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/chat") as ws:
            initial_mcp = ws.receive_json()
            initial_skill = ws.receive_json()
            initialized_mcp = ws.receive_json()

    assert initial_mcp == {
        "type": "mcp_status",
        "has_token": True,
        "initialized": False,
        "tool_count": 0,
        "tools": [],
        "message": "Token var, baglanti bekleniyor",
    }
    assert initial_skill == {
        "type": "skill_status",
        "active_skill": None,
        "message": "Aktif skill yok",
    }
    assert initialized_mcp == {
        "type": "mcp_status",
        "has_token": True,
        "initialized": True,
        "tool_count": 2,
        "tools": [
            {"name": "listOrder", "description": "Order query"},
            {"name": "listCustomer", "description": "Customer query"},
        ],
        "message": "MCP bagli",
    }
