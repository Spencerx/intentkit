import os

from intentkit.config.config import Config, config

_LANGSMITH_ENV_VARS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
)

_LANGFUSE_ENV_VARS = (
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
    "LANGFUSE_HOST",
)


def _clear_tracing_env(monkeypatch):
    for var in (*_LANGSMITH_ENV_VARS, *_LANGFUSE_ENV_VARS):
        monkeypatch.delenv(var, raising=False)


def test_load_strips_matching_surrounding_quotes(monkeypatch):
    monkeypatch.setenv("QUOTE_TEST_KEY", '"intentkit"')
    assert config.load("QUOTE_TEST_KEY") == "intentkit"

    monkeypatch.setenv("QUOTE_TEST_KEY", "'intentkit'")
    assert config.load("QUOTE_TEST_KEY") == "intentkit"

    monkeypatch.setenv("QUOTE_TEST_KEY", "plain")
    assert config.load("QUOTE_TEST_KEY") == "plain"

    # Mismatched quotes are kept as-is
    monkeypatch.setenv("QUOTE_TEST_KEY", "\"mismatched'")
    assert config.load("QUOTE_TEST_KEY") == "\"mismatched'"


def test_export_langsmith_env_enabled(monkeypatch):
    for var in _LANGSMITH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(config, "langsmith_tracing", True)
    monkeypatch.setattr(config, "langsmith_api_key", "ls-test-key")
    monkeypatch.setattr(config, "langsmith_project", "intentkit")
    monkeypatch.setattr(config, "langsmith_endpoint", None)

    config._export_langsmith_env()

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_TRACING"] == "true"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_API_KEY"] == "ls-test-key"
    assert os.environ["LANGSMITH_PROJECT"] == "intentkit"
    assert "LANGSMITH_ENDPOINT" not in os.environ


def test_export_langsmith_env_disabled_without_key(monkeypatch):
    for var in _LANGSMITH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(config, "langsmith_tracing", True)
    monkeypatch.setattr(config, "langsmith_api_key", None)
    monkeypatch.setattr(config, "langsmith_project", "intentkit")
    monkeypatch.setattr(config, "langsmith_endpoint", None)

    config._export_langsmith_env()

    for var in (
        "LANGSMITH_TRACING",
        "LANGSMITH_TRACING_V2",
        "LANGCHAIN_TRACING",
        "LANGCHAIN_TRACING_V2",
    ):
        assert os.environ[var] == "false"
    assert "LANGSMITH_API_KEY" not in os.environ
    assert "LANGSMITH_PROJECT" not in os.environ


def test_langfuse_takes_precedence_over_langsmith(monkeypatch):
    _clear_tracing_env(monkeypatch)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test-key")
    # Avoid initializing the real Langfuse client / global hook during the test.
    called = {}
    monkeypatch.setattr(
        Config, "_setup_langfuse", lambda self: called.setdefault("ran", True)
    )

    cfg = Config()

    assert cfg.langfuse_tracing is True
    assert cfg.langsmith_tracing is False
    # LangSmith must be force-disabled in the env so it does not also trace.
    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert called.get("ran") is True


def test_langsmith_used_when_no_langfuse(monkeypatch):
    _clear_tracing_env(monkeypatch)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test-key")
    monkeypatch.setattr(Config, "_setup_langfuse", lambda self: None)

    cfg = Config()

    assert cfg.langfuse_tracing is False
    assert cfg.langsmith_tracing is True
    assert os.environ["LANGSMITH_TRACING"] == "true"


def test_langfuse_disabled_without_both_keys(monkeypatch):
    _clear_tracing_env(monkeypatch)
    # Only the public key is present — not enough to enable Langfuse.
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test-key")
    monkeypatch.setattr(Config, "_setup_langfuse", lambda self: None)

    cfg = Config()

    assert cfg.langfuse_tracing is False
    # LangSmith stays enabled because Langfuse did not take over.
    assert cfg.langsmith_tracing is True
