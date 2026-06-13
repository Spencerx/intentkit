"""IntentKit API server layer.

Architecture note — why `app/local` and `app/team` look similar but stay
separate:

The `intentkit` package is the open library; `app/local` and `app/team` are
two intentionally independent reference API implementations built on top of
it. `local` is a single-user, unauthenticated API serving the bundled
`frontend/`; `team` is a multi-tenant, authenticated API serving a separate
team frontend (intentcat). Both are examples first, but each also supports
direct deployment as-is.

Their route handlers overlap by design. Do NOT merge them or extract shared
route factories to reduce duplication: each API set must remain a readable,
self-contained example that can evolve independently. Genuinely shared
plumbing (health/metadata/schema routers, channel helpers) lives in
`app/common`; everything route-shaped stays duplicated on purpose.
"""
