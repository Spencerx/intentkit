"""Guards against silent drift between the Python and Go sides of the
wechat session-expiring trigger string. The two sides must agree on the
literal value or fired notices will be 400-rejected by the API."""

from pathlib import Path

from intentkit.core.team.wechat_session_notice import WECHAT_SESSION_EXPIRING

REPO_ROOT = Path(__file__).resolve().parents[2]
GO_SESSION_TIMER = REPO_ROOT / "integrations" / "wechat" / "bot" / "session_timer.go"


def test_go_constant_matches_python_constant() -> None:
    """The Go-side `SessionTriggerExpiring` const literal must match the
    Python-side `WECHAT_SESSION_EXPIRING`. We grep rather than parse Go
    because the value is a plain string literal — no Go toolchain in the
    Python test runner."""
    src = GO_SESSION_TIMER.read_text()
    expected = f'"{WECHAT_SESSION_EXPIRING}"'
    assert expected in src, (
        f"Python WECHAT_SESSION_EXPIRING={WECHAT_SESSION_EXPIRING!r} "
        f"not found verbatim in {GO_SESSION_TIMER}; the Go and Python sides "
        f"have drifted apart."
    )
