"""Unit tests for the extraction layer using a mocked HTTP session."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from fxpipeline.config import Settings
from fxpipeline.extract import ExtractError, build_session, fetch_time_series


def test_build_session_mounts_adapters(settings: Settings) -> None:
    session = build_session(settings)
    try:
        assert session.get_adapter("https://api.frankfurter.app") is not None
        assert session.get_adapter("http://example.test") is not None
    finally:
        session.close()


def test_fetch_owns_session_closes_it(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {"base": "USD", "rates": {"2024-01-01": {"EUR": 0.9}}}
    fake = _FakeSession(_FakeResponse(200, payload))
    monkeypatch.setattr("fxpipeline.extract.build_session", lambda _s: fake)

    result = fetch_time_series(settings, "2024-01-01", "2024-01-02", "USD", ("EUR",))
    assert result == payload
    # When the function builds its own session, it must close it.
    assert fake.closed is True


class _FakeResponse:
    """Minimal stand-in for :class:`requests.Response`."""

    def __init__(
        self,
        status_code: int = 200,
        payload: dict[str, Any] | None = None,
        *,
        raise_json: bool = False,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self._raise_json = raise_json
        self.text = text

    def json(self) -> dict[str, Any]:
        if self._raise_json:
            raise ValueError("no json")
        return self._payload


class _FakeSession:
    """Captures the last GET call and returns a canned response."""

    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response
        self.last_url: str | None = None
        self.last_params: dict[str, Any] | None = None
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        self.last_url = url
        self.last_params = kwargs.get("params")
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    def close(self) -> None:
        self.closed = True


def test_fetch_time_series_success(settings: Settings) -> None:
    payload = {"base": "USD", "rates": {"2024-01-01": {"EUR": 0.9}}}
    session = _FakeSession(_FakeResponse(200, payload))

    result = fetch_time_series(
        settings,
        "2024-01-01",
        "2024-01-03",
        "USD",
        ("EUR", "HNL"),
        session=session,
    )

    assert result == payload
    assert session.last_url == "https://api.frankfurter.app/2024-01-01..2024-01-03"
    assert session.last_params == {"base": "USD", "symbols": "EUR,HNL"}
    # Caller-provided session must NOT be closed by the function.
    assert session.closed is False


def test_fetch_time_series_non_200_raises(settings: Settings) -> None:
    session = _FakeSession(_FakeResponse(503, {}, text="upstream down"))
    with pytest.raises(ExtractError, match="unexpected status 503"):
        fetch_time_series(
            settings, "2024-01-01", "2024-01-02", "USD", ("EUR",), session=session
        )


def test_fetch_time_series_invalid_json_raises(settings: Settings) -> None:
    session = _FakeSession(_FakeResponse(200, raise_json=True))
    with pytest.raises(ExtractError, match="invalid JSON"):
        fetch_time_series(
            settings, "2024-01-01", "2024-01-02", "USD", ("EUR",), session=session
        )


def test_fetch_time_series_missing_rates_key(settings: Settings) -> None:
    session = _FakeSession(_FakeResponse(200, {"base": "USD"}))
    with pytest.raises(ExtractError, match="missing 'rates' key"):
        fetch_time_series(
            settings, "2024-01-01", "2024-01-02", "USD", ("EUR",), session=session
        )


def test_fetch_time_series_network_error(settings: Settings) -> None:
    session = _FakeSession(requests.ConnectionError("boom"))
    with pytest.raises(ExtractError, match=r"request to .* failed"):
        fetch_time_series(
            settings, "2024-01-01", "2024-01-02", "USD", ("EUR",), session=session
        )
