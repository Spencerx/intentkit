# Release v1.2.6

## Improvements

- Audio, video, and document attachments now reach every model that claims to support them, not just Gemini. The previous release used a Google-specific delivery format and silently blocked the same attachment from reaching, for example, an OpenAI- or OpenRouter-routed model that supports audio. The platform now uses a provider-agnostic delivery shape that LangChain translates into each provider's native format (OpenAI's `input_audio`, Anthropic's `document`, Gemini's `inlineData`, etc.), so the model capability flags configured per model are the single source of truth.
