# Release v2.6.3

## Improvements

- Observability traces (Langfuse) now record a more accurate per-request cost: when the provider reports the actual charge (e.g. OpenRouter) it is used directly, otherwise the cost is computed from the model catalog — and cached input tokens are now priced at their discounted rate instead of being undercounted. No user-facing changes.
