# Release v2.0.3

## Improvements

- Removed a superseded internal agent-management component that had already been fully replaced by the team lead experience, trimming the codebase with no change to existing behavior.
- Made agent creation and editing a little faster by reusing the cached catalog of available tools instead of rebuilding it on every request.
