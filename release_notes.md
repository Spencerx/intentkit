# Release v1.2.12

## Improvements

- Long agent conversations now cost less to persist. Checkpoint storage for chat history switches from a full per-step snapshot to incremental writes, so the same conversation that previously grew its database footprint quadratically with the number of turns now grows linearly. For threads that run dozens of turns, this is a meaningful reduction in both Postgres write volume and total stored bytes; existing threads continue to work without migration.
- Conversations on Anthropic models (Claude family) now use Anthropic's native prompt caching for the system prompt and tool definitions. For agents with long instructions or many tools — which is most of our team agents — this can cut input-token cost by 50-90% on repeated turns within a 5-minute cache window, without changing model behavior.
- Refreshed all LangChain and LangGraph dependency floors to match the actual installed 1.x lockfile, so new installs no longer risk resolving to versions that pre-date the agent and middleware framework we already rely on.
