# Release v1.2.2

## Improvements

- Streamlined how the team lead delegates to its built-in sub-agents. The "task manager" was folded into the agent manager, since autonomous tasks always belong to an agent. Operators now have a single destination for everything about a team agent — creating it, configuring it, and scheduling its autonomous tasks — which removes a class of routing mistakes the lead used to make between the two near-identical helpers.

## Bug Fixes

- Fixed an issue where the agent manager could suggest skills that were not actually enabled in the current deployment. The skill catalog shown to the LLM is now filtered against the system configuration, so unavailable categories never end up in a generated agent draft.

## Other

- Refreshed Go integration dependencies.
