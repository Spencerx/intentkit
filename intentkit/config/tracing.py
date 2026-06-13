"""Langfuse tracing setup.

LangSmith attaches to every LangChain run through global env vars (handled in
``config.py``). Langfuse instead needs a callback handler, so we register that
handler through LangChain's global configure-hook — the same mechanism the
LangSmith SDK uses internally. Once registered, the handler is added to every
run's callback manager automatically, with no per-invocation wiring.

Only one tracing backend is active at a time; ``config.py`` gives Langfuse
precedence and disables LangSmith when Langfuse keys are present, so a single
deployment can A/B the two backends by swapping env vars.
"""

import logging
from contextvars import ContextVar
from typing import Any

logger = logging.getLogger(__name__)

# The hook reads this contextvar in whatever context a run executes. Setup runs
# at import time (root context), but the agent loop may run in a different
# thread/context, so we cannot rely on a ``.set()`` value propagating there.
# Instead the handler becomes the contextvar's *default*, which ``.get()``
# returns in every context — async tasks, worker threads, fresh contexts alike.
# The var is therefore (re)created in setup with the handler baked in as default.
_langfuse_handler_var: ContextVar[Any] | None = None
_hook_registered = False


def setup_langfuse(
    *,
    public_key: str,
    secret_key: str,
    base_url: str | None,
    environment: str,
    release: str | None,
) -> bool:
    """Initialize the global Langfuse client and attach its LangChain handler.

    The handler is wired through ``register_configure_hook`` so LangChain adds
    it to every callback manager it builds — covering agent runs and every
    ad-hoc LLM call without touching their call sites.

    Runs once per process: the first call configures the client, builds the
    handler and registers the hook; later calls are no-ops (so the client and
    its background threads are never rebuilt). Returns ``True`` when Langfuse
    tracing is active.
    """
    global _langfuse_handler_var, _hook_registered
    if _hook_registered:
        return True
    try:
        from langchain_core.tracers.context import register_configure_hook
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError:
        logger.warning("langfuse not installed; Langfuse tracing disabled")
        return False

    # Configure the process-wide Langfuse singleton from the sanitized config
    # values. The handler resolves this client via get_client().
    _ = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        base_url=base_url,
        environment=environment,
        release=release,
        tracing_enabled=True,
    )

    # Handler as contextvar default => attaches to runs in any context/thread.
    _langfuse_handler_var = ContextVar(
        "langfuse_callback_handler", default=CallbackHandler()
    )
    register_configure_hook(_langfuse_handler_var, True)
    _hook_registered = True
    logger.info("Langfuse tracing enabled (base_url=%s)", base_url or "default")
    return True
