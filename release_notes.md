# Release v1.2.0

## New Features

- Added Xiaomi's MiMo Token Plan as a built-in LLM provider. Operators with a MiMo subscription can now plug in `MIMO_PLAN_API_KEY` to make the new `mimo-v2.5-pro` and `mimo-v2.5` models available to agents directly, without going through OpenRouter.

## Breaking Changes

- The MiniMax provider environment variable was renamed from `MINIMAX_API_KEY` to `MINIMAX_PLAN_API_KEY` to reflect that the integration uses the MiniMax subscription plan. Deployments that referenced the old name need to update their configuration; there is no automatic fallback.
