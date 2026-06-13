# Release v2.6.0

## New Features

- LLM models served through OpenRouter can now be pinned to a specific upstream provider. When a model defines an origin provider it is locked to that provider with no automatic fallback; models without one continue to let OpenRouter choose. This gives operators precise control over which upstream serves each OpenRouter model.

## Improvements

- The catalog of available LLM models is now defined in a single, easy-to-edit configuration file, replacing the previous comma-separated format and making it simpler to add, adjust, and annotate models.
- Streamlined how model information is sourced: the bundled catalog is now the single source of truth, the unused database-override path was removed, and model lookups are served entirely from memory — removing unnecessary database and cache round-trips.
