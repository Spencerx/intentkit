# Release v1.2.17

## New Features

- Agents now report the current time together with a numeric Unix timestamp, so tools and workflows that need an exact machine-readable time value can use it directly.

## Improvements

- Agents running on OpenRouter models with Internet Search enabled can now read full web pages natively, on top of searching — giving more complete and reliable answers when they need details from a specific page.
- Made timekeeping consistent across every agent: all models now use the same built-in time tool, so the time format and behavior no longer depend on the underlying model provider.
