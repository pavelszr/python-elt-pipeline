"""Extraction layer: fetch raw FX rates from the Frankfurter API.

Network access is isolated here so that the transform layer stays pure and
unit-testable. HTTP calls use bounded timeouts and exponential-backoff retries
on transient failures.
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Settings
from .logging_conf import get_logger

logger = get_logger("extract")

# Status codes worth retrying: rate limiting and transient server errors.
_RETRY_STATUS = (429, 500, 502, 503, 504)


class ExtractError(RuntimeError):
    """Raised when rates cannot be retrieved from the upstream API."""


def build_session(settings: Settings) -> requests.Session:
    """Create a :class:`requests.Session` with retry/backoff configured.

    Args:
        settings: Runtime settings carrying retry and backoff parameters.

    Returns:
        A session whose HTTP/HTTPS adapters retry transient failures.
    """
    retry = Retry(
        total=settings.max_retries,
        connect=settings.max_retries,
        read=settings.max_retries,
        backoff_factor=settings.backoff_factor,
        status_forcelist=_RETRY_STATUS,
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _build_url(settings: Settings, start: str, end: str) -> str:
    """Build the Frankfurter time-series endpoint URL for a date range."""
    return f"{settings.api_base_url}/{start}..{end}"


def fetch_time_series(
    settings: Settings,
    start: str,
    end: str,
    base: str,
    symbols: tuple[str, ...],
    *,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Fetch raw time-series rates for an inclusive date range.

    Args:
        settings: Runtime settings (timeout, retries, base URL).
        start: Inclusive ISO start date (``YYYY-MM-DD``).
        end: Inclusive ISO end date (``YYYY-MM-DD``).
        base: Base currency (e.g. ``"USD"``).
        symbols: Target currencies to quote against the base.
        session: Optional pre-built session (chiefly for testing).

    Returns:
        The decoded JSON payload from Frankfurter. The relevant key is
        ``"rates"``: a mapping of date -> {symbol -> rate}.

    Raises:
        ExtractError: On network errors, non-2xx responses, or malformed JSON.
    """
    owns_session = session is None
    session = session or build_session(settings)
    url = _build_url(settings, start, end)
    params = {"base": base, "symbols": ",".join(symbols)}

    logger.info("fetching url=%s base=%s symbols=%s", url, base, ",".join(symbols))

    try:
        response = session.get(
            url,
            params=params,
            timeout=settings.request_timeout,
            headers={"Accept": "application/json"},
        )
    except requests.RequestException as exc:  # network/timeout/connection
        raise ExtractError(f"request to {url} failed: {exc}") from exc
    finally:
        if owns_session:
            session.close()

    if response.status_code != 200:
        raise ExtractError(
            f"unexpected status {response.status_code} from {url}: "
            f"{response.text[:200]}"
        )

    try:
        payload: dict[str, Any] = response.json()
    except ValueError as exc:
        raise ExtractError(f"invalid JSON from {url}: {exc}") from exc

    if "rates" not in payload:
        raise ExtractError(f"missing 'rates' key in response from {url}")

    logger.info("fetched days=%d", len(payload["rates"]))
    return payload
