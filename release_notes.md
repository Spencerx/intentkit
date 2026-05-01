# Release v1.2.5

## Bug Fixes

- Fixed audio, video, and document attachments still failing with an "empty mimeType" error against Gemini, despite v1.2.4. The previous attempt added a content-type hint to the request and relied on the LangChain adapter to fetch the file and pass it through correctly; in production that path still produced empty values. The platform now downloads the file itself before calling the model and hands the bytes plus an explicit content type directly to Gemini, which removes the empty-mimeType failure mode entirely. The content type is derived from the file's HTTP headers, falling back to its extension and a per-type default so it is never empty.
