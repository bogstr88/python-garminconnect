"""Idle keep-alive connections are dropped before the next API call.

Garmin closes keep-alive connections that sit idle. Without this, the first
request after a long gap goes out on a dead connection, fails with
"Remote end closed connection without response" and only succeeds on the
retry (logging a warning each time).
"""

from unittest.mock import MagicMock, patch

from garminconnect.client import Client


def _client() -> Client:
    c = Client()
    resp = MagicMock(status_code=200)
    resp.json.return_value = {}
    c._api_session = MagicMock()
    c._api_session.request.return_value = resp
    return c


def _call(c: Client, at: float) -> None:
    with patch("garminconnect.client.time.monotonic", return_value=at), \
            patch.object(Client, "is_authenticated", new=False), \
            patch.object(Client, "get_api_headers", return_value={}):
        c._run_request("GET", "/x")


def test_calls_close_together_share_the_connection() -> None:
    c = _client()
    _call(c, 1000.0)
    _call(c, 1030.0)
    assert c._api_session.close.call_count == 0
    assert c._api_session.request.call_count == 2


def test_a_call_after_a_long_gap_starts_on_a_fresh_connection() -> None:
    c = _client()
    _call(c, 1000.0)
    _call(c, 1000.0 + Client.API_IDLE_RESET_S + 1)
    assert c._api_session.close.call_count == 1
    assert c._api_session.request.call_count == 2, "the call itself still goes out"
    _call(c, 1000.0 + Client.API_IDLE_RESET_S + 5)
    assert c._api_session.close.call_count == 1, "the gap is measured from the last call"


def test_the_first_call_never_resets() -> None:
    c = _client()
    _call(c, 5.0)
    assert c._api_session.close.call_count == 0
