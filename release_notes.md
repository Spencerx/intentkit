# Release v2.1.2

## Improvements

- Existing tasks are now moved to team ownership automatically when the autonomous service starts — no manual migration step per environment. The import is skipped once tasks are present; if it cannot run yet, the service retries every minute and raises a single alert.
- The migration now tolerates malformed legacy task data instead of failing as a whole.
