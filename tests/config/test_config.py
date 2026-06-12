import os

from intentkit.config.config import config

_LANGSMITH_ENV_VARS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_ENDPOINT",
)


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
