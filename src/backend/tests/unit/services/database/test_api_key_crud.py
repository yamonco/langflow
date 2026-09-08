import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.database.models.api_key.crud import check_key
from langflow.services.settings.base import Settings


def _api_key_session():
    user = MagicMock()
    api_key = SimpleNamespace(id=uuid4(), user=user)
    result = MagicMock()
    result.first.return_value = api_key
    session = AsyncMock()
    session.exec.return_value = result
    return session, api_key, user


def test_disable_track_apikey_usage_reads_langflow_environment(monkeypatch):
    monkeypatch.setenv("LANGFLOW_DISABLE_TRACK_APIKEY_USAGE", "true")

    assert Settings().disable_track_apikey_usage is True


@pytest.mark.asyncio
async def test_check_key_skips_usage_update_when_tracking_disabled():
    session, _, user = _api_key_session()
    settings_service = SimpleNamespace(settings=SimpleNamespace(disable_track_apikey_usage=True))
    update_total_uses = AsyncMock()

    with (
        patch(
            "langflow.services.database.models.api_key.crud.get_settings_service",
            return_value=settings_service,
        ),
        patch(
            "langflow.services.database.models.api_key.crud.update_total_uses",
            update_total_uses,
        ),
    ):
        authenticated_user = await check_key(session, "test-key")
        await asyncio.sleep(0)

    assert authenticated_user is user
    update_total_uses.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_key_preserves_background_usage_update_when_tracking_enabled():
    session, api_key, user = _api_key_session()
    settings_service = SimpleNamespace(settings=SimpleNamespace(disable_track_apikey_usage=False))
    update_started = asyncio.Event()
    release_update = asyncio.Event()
    update_finished = asyncio.Event()

    async def blocked_update(_):
        update_started.set()
        try:
            await release_update.wait()
        finally:
            update_finished.set()

    update_total_uses = AsyncMock(side_effect=blocked_update)

    with (
        patch(
            "langflow.services.database.models.api_key.crud.get_settings_service",
            return_value=settings_service,
        ),
        patch(
            "langflow.services.database.models.api_key.crud.update_total_uses",
            update_total_uses,
        ),
    ):
        authenticated_user = await asyncio.wait_for(check_key(session, "test-key"), timeout=1)
        await asyncio.wait_for(update_started.wait(), timeout=1)

        assert authenticated_user is user
        assert not update_finished.is_set()

        release_update.set()
        await asyncio.wait_for(update_finished.wait(), timeout=1)

    update_total_uses.assert_awaited_once_with(api_key.id)
