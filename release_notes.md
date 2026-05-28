# Release v1.2.14

## Improvements

- Activity links pushed into WeChat can now be served through a separate CDN domain for faster in-app loading. When `WECHAT_BASE_URL` is configured, share links inside WeChat messages are rewritten from the canonical app domain to the CDN domain at send time. Other channels (Telegram), persisted chat history, and frontend responses continue to use the canonical app domain unchanged.
- Bumped locked dependencies to current upstream releases.
