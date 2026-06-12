# Release v2.3.1

## Improvements

- LangSmith tracing settings are now managed by the system configuration: values can come from environment variables or the AWS secret, the trace project name defaults to "intentkit", and stray legacy tracing variables in the deployment can no longer flip the tracing switch.
- Configuration values accidentally wrapped in quotes (a common mistake in docker environment blocks) are now sanitized automatically for all settings.
