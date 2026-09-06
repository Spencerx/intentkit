# Release v2.40.0

## Long-Term Memory, Rebuilt

Agents now keep memory as individual facts filed under a fixed set of topics, instead of one free-form note per scope that was rewritten on every update.

- **Facts, not notes.** Each thing an agent learns is recorded as one entry: the fact itself, why it believes it, and whether a person stated it or the agent worked it out. Entries are never edited or deleted — a correction is a newer entry — so nothing an agent was told can be silently lost in a rewrite.
- **What people say outranks what the agent finds.** Every topic's summary is rebuilt from its entries after each write. A person's instruction always wins over the agent's own conclusion, whatever the dates; a later statement replaces an earlier one; and a real contradiction between the two becomes a question the agent will raise rather than a silent pick.
- **Findings age, instructions don't.** Something the agent noticed by itself expires after a topic-specific period and is retired by a daily sweep; something a person said is kept until they say otherwise.
- **A closed list of topics per scope.** Team memory covers the team's profile, the subject of the work, people and roles, working agreements, output conventions, resources, vocabulary and hard rules. Channel memory covers a chat's purpose, subject, participation rules and conventions. User memory covers preferences, role and personal resources. Scheduled-task memory covers setup, cursors, what is already covered, baselines, open threads and method notes. A fact that fits no topic is not recorded.
- **The Memory page is now read-only** and shows each agent's memory by topic. To change what an agent remembers, tell it in a conversation.

**Upgrading:** existing memory notes are kept as they are but are no longer read by agents. After deploying, run `scripts/import_legacy_memories.py --apply` once to split them into the new entries.

## Improvements

- The team lead now records its own memory the same way every agent does; the self-updater assistant only edits its name, avatar and personality.
- Fixed bugs and improved robustness in the memory module.
