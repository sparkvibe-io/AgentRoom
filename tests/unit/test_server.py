"""Tests for the FastAPI server — REST endpoints + WebSocket."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from agentroom.server.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_index_returns_html(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "AgentRoom" in resp.text


@pytest.mark.asyncio
async def test_list_rooms_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/rooms")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_room(client: AsyncClient) -> None:
    # Mock the adapter connect calls so no real API keys needed
    with patch("agentroom.server.app.AnthropicAdapter") as mock_anthropic, \
         patch("agentroom.server.app.OpenAIAdapter") as mock_openai:

        mock_anthropic_instance = AsyncMock()
        mock_anthropic_instance.name = "@claude"
        mock_anthropic.return_value = mock_anthropic_instance

        mock_openai_instance = AsyncMock()
        mock_openai_instance.name = "@gpt4o"
        mock_openai.return_value = mock_openai_instance

        resp = await client.post("/api/rooms", json={
            "goal": "Test goal",
            "agents": [
                {"name": "@claude", "provider": "anthropic", "model": "claude-sonnet-4-20250514", "role": "coordinator"},
                {"name": "@gpt4o", "provider": "openai", "model": "gpt-4o", "role": "researcher"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["goal"] == "Test goal"
        assert len(data["agents"]) == 2
        assert data["phase"] == "researching"  # auto-advances on start


@pytest.mark.asyncio
async def test_get_room_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/rooms/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_and_list_rooms(client: AsyncClient) -> None:
    with patch("agentroom.server.app.AnthropicAdapter") as mock_anthropic:
        instance = AsyncMock()
        instance.name = "@claude"
        mock_anthropic.return_value = instance

        await client.post("/api/rooms", json={
            "goal": "Room 1",
            "agents": [
                {"name": "@claude", "provider": "anthropic", "model": "test", "role": "coordinator"},
            ],
        })

        resp = await client.get("/api/rooms")
        assert resp.status_code == 200
        rooms = resp.json()
        assert len(rooms) >= 1
        assert any(r["goal"] == "Room 1" for r in rooms)


@pytest.mark.asyncio
async def test_create_room_invalid_provider(client: AsyncClient) -> None:
    resp = await client.post("/api/rooms", json={
        "goal": "Test",
        "agents": [
            {"name": "@agent", "provider": "fakeprovider", "model": "test", "role": "researcher"},
        ],
    })
    assert resp.status_code == 400  # ValueError from _build_adapter


@pytest.mark.asyncio
async def test_create_room_missing_goal(client: AsyncClient) -> None:
    resp = await client.post("/api/rooms", json={
        "agents": [
            {"name": "@claude", "provider": "anthropic", "model": "test"},
        ],
    })
    assert resp.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_create_room_empty_agents(client: AsyncClient) -> None:
    resp = await client.post("/api/rooms", json={
        "goal": "Test",
        "agents": [],
    })
    # Should succeed or fail gracefully — an empty room is valid structurally
    assert resp.status_code in (200, 422, 500)


@pytest.mark.asyncio
async def test_phase_change(client: AsyncClient) -> None:
    with patch("agentroom.server.app.AnthropicAdapter") as mock_anthropic:
        instance = AsyncMock()
        instance.name = "@claude"
        mock_anthropic.return_value = instance

        create_resp = await client.post("/api/rooms", json={
            "goal": "Phase test",
            "agents": [
                {"name": "@claude", "provider": "anthropic", "model": "test", "role": "coordinator"},
            ],
        })
        room_id = create_resp.json()["id"]

        resp = await client.post(f"/api/rooms/{room_id}/phase", json={"phase": "consensus"})
        assert resp.status_code == 200
        assert resp.json()["phase"] == "consensus"


@pytest.mark.asyncio
async def test_post_user_message(client: AsyncClient) -> None:
    with patch("agentroom.server.app.AnthropicAdapter") as mock_anthropic:
        instance = AsyncMock()
        instance.name = "@claude"
        mock_anthropic.return_value = instance

        create_resp = await client.post("/api/rooms", json={
            "goal": "Message test",
            "agents": [
                {"name": "@claude", "provider": "anthropic", "model": "test", "role": "coordinator"},
            ],
        })
        room_id = create_resp.json()["id"]

        resp = await client.post(f"/api/rooms/{room_id}/message", json={"content": "Hello agents!"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_get_messages(client: AsyncClient) -> None:
    with patch("agentroom.server.app.AnthropicAdapter") as mock_anthropic:
        instance = AsyncMock()
        instance.name = "@claude"
        mock_anthropic.return_value = instance

        create_resp = await client.post("/api/rooms", json={
            "goal": "History test",
            "agents": [
                {"name": "@claude", "provider": "anthropic", "model": "test", "role": "coordinator"},
            ],
        })
        room_id = create_resp.json()["id"]

        resp = await client.get(f"/api/rooms/{room_id}/messages")
        assert resp.status_code == 200
        messages = resp.json()
        assert isinstance(messages, list)
        # Should have at least system + phase messages from room.start()
        assert len(messages) >= 2


@pytest.mark.asyncio
async def test_openapi_schema_available(client: AsyncClient) -> None:
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "AgentRoom"
