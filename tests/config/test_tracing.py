"""Tests for Langfuse tracing setup (intentkit.config.tracing)."""

from intentkit.config import tracing


class _FakeLangfuse:
    instances: list[dict] = []

    def __init__(self, **kwargs):
        _FakeLangfuse.instances.append(kwargs)


class _FakeHandler:
    created = 0

    def __init__(self, *args, **kwargs):
        _FakeHandler.created += 1


def _reset(monkeypatch):
    """Reset module + fake state so each test starts from a clean process."""
    _FakeLangfuse.instances = []
    _FakeHandler.created = 0
    monkeypatch.setattr(tracing, "_hook_registered", False)
    monkeypatch.setattr(tracing, "_langfuse_handler_var", None)

    registered: list = []
    monkeypatch.setattr("langfuse.Langfuse", _FakeLangfuse)
    monkeypatch.setattr("langfuse.langchain.CallbackHandler", _FakeHandler)
    monkeypatch.setattr(
        "langchain_core.tracers.context.register_configure_hook",
        lambda *a, **k: registered.append((a, k)),
    )
    return registered


def test_setup_langfuse_initializes_client_and_handler(monkeypatch):
    registered = _reset(monkeypatch)

    result = tracing.setup_langfuse(
        public_key="pk-test",
        secret_key="sk-test",
        base_url="https://example.langfuse.test",
        environment="local",
        release="v1.2.3",
    )

    assert result is True
    # Client constructed with the sanitized config values.
    assert _FakeLangfuse.instances == [
        {
            "public_key": "pk-test",
            "secret_key": "sk-test",
            "base_url": "https://example.langfuse.test",
            "environment": "local",
            "release": "v1.2.3",
            "tracing_enabled": True,
        }
    ]
    # Hook registered once, with the handler living as the contextvar default so
    # it attaches to runs in any context/thread.
    assert len(registered) == 1
    assert _FakeHandler.created == 1
    assert tracing._langfuse_handler_var is not None
    assert isinstance(tracing._langfuse_handler_var.get(), _FakeHandler)
    # The registered hook points at the same contextvar the handler lives in.
    assert registered[0][0][0] is tracing._langfuse_handler_var


def test_setup_langfuse_runs_once_per_process(monkeypatch):
    registered = _reset(monkeypatch)

    _ = tracing.setup_langfuse(
        public_key="pk",
        secret_key="sk",
        base_url=None,
        environment="local",
        release=None,
    )
    _ = tracing.setup_langfuse(
        public_key="pk",
        secret_key="sk",
        base_url=None,
        environment="local",
        release=None,
    )

    # The second call is a no-op: the hook is registered once, and the client
    # and handler are never rebuilt (so background threads are not leaked).
    assert len(registered) == 1
    assert len(_FakeLangfuse.instances) == 1
    assert _FakeHandler.created == 1
