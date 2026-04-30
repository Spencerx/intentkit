# Release v1.2.4

## Bug Fixes

- Fixed a regression introduced in v1.2.3 where Gemini rejected every audio, video, and document attachment with an "empty mimeType" error before the model ever saw the content. Media attachments are now sent with an explicit content-type hint so the model can actually open them.
