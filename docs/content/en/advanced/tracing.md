# Tracing & Observability

IntentKit can send a full trace of every agent run to an external observability platform. A trace captures each step the agent took — the prompts sent to the model, the model's replies, every tool call and its result, token usage, latency and errors. It is the fastest way to understand *why* an agent behaved the way it did, to debug failures, and to monitor cost and performance in production.

Two platforms are supported: **LangSmith** and **Langfuse**. They do the same job, so you only configure **one** of them. Tracing is entirely optional — if neither is configured, agents run normally without it.

## Choosing a backend

Only one backend is active at a time. The choice is made automatically from environment variables:

- If Langfuse keys are set, **Langfuse** is used (and LangSmith is turned off, even if LangSmith variables are also present).
- Otherwise, if LangSmith is configured, **LangSmith** is used.
- If neither is set, tracing is disabled.

This makes it easy to compare the two: configure one, look at its traces, then switch by changing environment variables and restarting. No code changes are required. To move from Langfuse back to LangSmith, remove the Langfuse keys.

## LangSmith

[LangSmith](https://www.langchain.com/langsmith) is LangChain's hosted tracing and evaluation platform.

### Register

1. Sign up at [smith.langchain.com](https://smith.langchain.com).
2. Open **Settings → API Keys** and create an API key.

### Configure

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...        # your API key
LANGSMITH_PROJECT=intentkit       # optional, defaults to "intentkit"
# LANGSMITH_ENDPOINT=             # optional, only for self-hosted or non-default region
```

Tracing turns on only when `LANGSMITH_TRACING=true` **and** an API key is set. Traces appear in your LangSmith project, grouped by the project name.

## Langfuse

[Langfuse](https://langfuse.com) is an open-source LLM observability platform. You can use their managed cloud or self-host it.

### Register

**Cloud:** sign up at [cloud.langfuse.com](https://cloud.langfuse.com), create a project, then open **Settings → API Keys** and create a key pair (a public key and a secret key).

**Self-hosted:** follow the [Langfuse self-hosting guide](https://langfuse.com/self-hosting). You get the same public/secret key pair from your own instance.

### Configure

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
# LANGFUSE_BASE_URL=https://cloud.langfuse.com   # optional, defaults to Langfuse Cloud
```

Langfuse is enabled as soon as **both** keys are present. Set `LANGFUSE_BASE_URL` to your own URL when self-hosting (the older name `LANGFUSE_HOST` is also accepted). Each conversation is grouped into a single session, so a whole chat appears as one session in the Langfuse UI.

## Where to set these

These values are loaded like every other IntentKit setting — from environment variables (for example a `.env` file or your deployment's environment) or from AWS Secrets Manager. Quotes around values are stripped automatically. See [Configuration](../configuration/) for the general configuration mechanism.

## Verifying

Start the API server, send a message to an agent, then open your LangSmith project or Langfuse dashboard — the run should appear within a few seconds. On startup the logs also confirm when Langfuse is active (a line reading `Langfuse tracing enabled`).
