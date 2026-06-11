# Release v2.1.0

## New Features

- Autonomous tasks now belong to the team instead of a single agent. A task can target a specific agent, or leave the choice to the team lead, which delegates each run to the right agent.
- Every task run is now recorded as an execution: status, how it was triggered, duration, token and credit usage, and a result preview, with the complete per-run log available from the new task detail page.
- Tasks can be started on demand with the new "Run Now" action, in addition to their schedule.
- A new task-manager assistant under the team lead handles tasks in conversation: create, edit, retarget, or remove scheduled tasks by simply asking the lead.
- Tasks record who created them.

## Improvements

- Overlapping runs of the same task are prevented automatically, and runs orphaned by a service restart are cleaned up on the next run.
- The scheduler process is leaner: agent and lead executions are routed to the core service instead of running inside the scheduler.
- Fixed the long-standing issue where task logs could not be viewed; logs are now reliably available per run.

## Upgrade Notes

- After deploying, run `python scripts/migrate_autonomous_to_team.py` once to move existing per-agent tasks to their teams. The script is idempotent; agents without a team are skipped with a warning. The legacy task data on agents is kept for this release and will be removed in the next one.
