# Release v2.4.2

## Improvements

- MCP-based tool integrations (such as CoinGecko) are now configured with a single per-service control instead of a long per-tool list, and always expose whatever the remote service currently offers. There is no longer any need to re-sync when a provider changes its tools.

## Bug Fixes

- Fixed an issue where MCP-based tools could silently stop working after the remote provider changed its set of available tools.
