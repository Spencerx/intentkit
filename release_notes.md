# Release v1.2.7

## Bug Fixes

- Fixed Gemini still rejecting requests with an "empty mimeType in inlineData" error even after v1.2.6, when the conversation had any voice/video/file attachments from before v1.2.4. Those earlier turns were stored in chat history without a content type, and Gemini's adapter failed to recover one from the URL alone, so every subsequent reply in that conversation kept failing. The platform now repairs each historical attachment on the fly — guessing the content type from the URL extension and falling back to a per-type default — and drops the attachment when no reasonable type can be determined, so a single bad legacy attachment can no longer poison an entire conversation.
