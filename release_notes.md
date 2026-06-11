# Release v2.3.0

## New Features

- LangSmith tracing support: agent conversation runs now carry filterable metadata — environment, agent, team, user, channel, conversation thread, app and model — so all deployments can share a single LangSmith project and still be filtered by any of these dimensions. Multi-turn conversations are grouped in the LangSmith Threads view. Chat title generation calls are tagged and named as well. Tracing stays off unless the standard LangSmith environment variables are set on the server.

## Improvements

- Test runs never send traces to LangSmith, even when tracing is enabled in the developer's local environment.
