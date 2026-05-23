# Release v1.2.13

## Improvements

- Added Google's newly released Gemini 3.5 Flash to the model catalog, available via both the Google native key and OpenRouter. The model offers stronger reasoning than the Gemini 3 Flash tier while keeping the full 1M-token context, native image / audio / video / PDF inputs, and Flash-class latency, giving team agents a new mid-tier multimodal option.
- Refreshed DeepSeek's official pricing to reflect DeepSeek's current promotional discount: DeepSeek V4 Pro on the official key is now 75% off (running through 2026-05-31), and the cache-hit input rate on DeepSeek V4 Flash drops to one tenth of its launch price. Agents that route through the DeepSeek native key automatically benefit from the lower rates. OpenRouter routes for the same models are unaffected.
- Bumped locked dependencies to current upstream releases.
