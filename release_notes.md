# Release v1.2.3

## New Features

- WeChat voice messages now reach audio-capable models as actual audio. Previously, voice notes were uploaded as raw SILK files that no model could read, so the model would just see a URL with a `.silk` extension in the prompt and politely refuse. They are now transcoded to MP3 inside the WeChat integration before upload, then delivered to the model through a proper audio attachment so Gemini (and any other audio-capable model added in the future) can actually listen to them.
- Audio, video, and document attachments now follow the same rules as images. When an attachment type matches the model's capabilities the file is forwarded to the model as a media input; when it does not, the user gets a clear, type-specific message telling them their current model can't accept that kind of input. This replaces the previous behavior where non-image attachments silently turned into a URL embedded in the prompt text.

## Improvements

- Tightened the WeChat attachment summary so a voice message and a separately-attached file are both counted correctly when shown back as a "User sent ..." preview.
