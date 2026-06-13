# Release v2.5.0

## New Features

- Added Langfuse as an observability option alongside the existing LangSmith integration. Each deployment chooses a tracing service through its configuration: when Langfuse credentials are provided it is used automatically and LangSmith is turned off; otherwise LangSmith continues to be used. This makes it easy to evaluate both services and settle on the one that fits best.
