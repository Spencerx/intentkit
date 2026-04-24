# Release v0.18.0

## New Features

- WeChat agents now accept voice, video, and file messages in addition to images. Users can send an audio note, a short video, or a document and the agent will receive the content directly instead of a "type not supported" fallback.

## Improvements

- Expanded the catalog of selectable LLM models — the latest DeepSeek, Claude Opus, Kimi, and MiMo releases are now available when configuring agents.
- When an agent's underlying model returns an empty response (for example, Gemini rejecting a malformed tool call), the conversation thread now recovers automatically instead of becoming stuck. The offending turn is cleaned up, and internal logs capture the surrounding tool-call history so engineers can diagnose the cause.

## Other

- Refreshed internal dependencies across the Python backend and Go integrations.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.60...v0.18.0
