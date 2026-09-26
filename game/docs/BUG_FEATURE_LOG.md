# Bug and feature log

## Human rule - effective for future work, 2026-09-25

Prioritize getting the game playable. Fix severe current blockers immediately;
record small bugs, potential issues and optional features here, then continue the
assigned milestone. Do not turn every finding into a prerequisite or side project.
This rule applies going forward only: existing M1a review/fix requirements remain
unchanged. Do not reopen, downgrade or waive those findings under this rule.

### Triage

| Priority | Meaning | Action |
|---|---|---|
| P0 - severe | Crash/hang, save loss/corruption, memory corruption, cannot boot/build the required image, or required gameplay/progression cannot proceed | Fix now before dependent work; notify the current owner when their files are involved |
| P1 - important | Confirmed gameplay defect with a workable path, or a defect in a system not yet used by the current playable route | Log with impact and a concrete revisit trigger; fix in the relevant milestone, without blocking unrelated work |
| P2 - minor | Cosmetic defect, small behavior mismatch, maintainability issue or unconfirmed potential problem | Log evidence/uncertainty; defer until related work or polish |
| Feature | Optional improvement or new scope | Record benefit and dependencies; implement only when assigned or approved as part of the plan |

Priority follows actual impact and reachability, not how easy a problem is to
imagine. A suspected severe failure warrants a bounded check now; call it confirmed
only when evidence supports that. Escalate deferred issues when a new feature makes
them active, their impact increases, or they block a required route.

Existing required milestone features remain required; this log does not silently
make them optional or declare unfinished work complete. Link planned work to its
milestone instead of duplicating its full specification here. No extra permission
is needed for fixes already within assigned scope. Coordinate shared-file ownership
without editing another agent's active implementation behind them.

### Review and work discipline

- Review reports separate severe blockers from nonblocking follow-ups. A minor or
  potential issue alone does not hold the next milestone; record it and continue.
- Make one concise entry per issue. Include observed evidence or mark suspicion,
  player impact, priority, owner (or unassigned), status and revisit milestone/trigger.
- For bugs, include reproduction/expected versus actual behavior when known. For
  features, include intended benefit, scope and dependencies. Link detailed review
  notes instead of repeating them. Do not invent a repro or claim a test was run.
- Keep investigation proportional. Do not derail playable work for broad cleanup,
  speculative hardening, refactors or optional source-parity improvements.
- On fixing an entry, record verification and commit when available. Keep a short
  resolved record so another agent does not rediscover or silently reopen it.
- Follow existing clean-only build, VDP2-menu, source/drop and milestone review
  requirements. This rule changes triage, not technical constraints or ownership.

## Issue tracking format

Use GitHub-style issue records below. These are local records, not published
GitHub issues. If later moved to GitHub, link the real issue and use its number;
do not invent GitHub issue numbers or claim an issue was filed remotely.

Labels: `bug` or `enhancement`; `priority: P0`, `priority: P1` or `priority: P2`
for bugs; `needs-triage` for unconfirmed findings. Feature priority is assigned
when scoped. Track assignee and milestone separately, as on GitHub.
State is **Open** or **Closed**; resolution is **Completed**, **Not planned** or
**Duplicate**. Open does not imply blocked: severity and dependencies determine
whether work stops. Optional features stay in backlog until assigned.

### Issue index

| ID | Title | Labels | Assignee | Milestone / revisit trigger | State |
|---|---|---|---|---|---|

No new entries yet. Historical M1a findings remain in
[M1A_REVIEW.md](M1A_REVIEW.md) under their existing review requirements.
Use local IDs `BUG-001`, `FEAT-001`, etc.; never reuse an ID. Add one index row and
one issue body per finding. Templates below are examples, not open issues.

## Bug report template

### BUG-NNN: Brief description of the failure

**Labels:** `bug`, `priority: P2` (or appropriate priority), `needs-triage` if unconfirmed

**Assignee:** Unassigned

**Milestone:** Relevant milestone or Backlog

**State:** Open

**Revisit trigger:** Specific dependency, affected feature integration or polish pass

#### Description

What fails and how it affects the player. State whether reproduced or suspected.

#### Steps to reproduce

1. Start from the relevant scene/save/controller state.
2. Perform the triggering action.
3. Observe the failure.

#### Expected behavior

Describe the intended result; link source behavior or an agreed requirement.

#### Actual behavior

Describe what was observed. For a potential issue, state that reproduction is
pending and give the code evidence; do not invent observed behavior.

#### Environment

- Build/commit:
- Emulator/version and 4 MB cart configuration, or host-test environment:
- Controller mode:
- Scene/room/save state:

#### Evidence and related work

Logs, screenshots, test output, relevant file/symbol and linked reviews/issues.
Include only available evidence; do not require screenshots for a code-only finding.

#### Acceptance criteria

- [ ] Reproduction no longer fails, or suspicion resolved with evidence.
- [ ] Relevant gameplay path remains working.
- [ ] Appropriate verification recorded; runtime versus host evidence distinguished.

#### Resolution

Fill when closed: fix summary or reason not planned/duplicate, verification,
commit/PR if available and date. Keep the issue record after closing.

## Feature request template

### FEAT-NNN: Brief description of the requested capability

**Labels:** `enhancement`

**Assignee:** Unassigned

**Milestone:** Backlog until assigned

**State:** Open

**Scope decision:** Proposed / approved with reference

**Revisit trigger:** Relevant milestone or explicit assignment

#### Problem or player benefit

What need this solves and why it matters to playable progress.

#### Proposed behavior

Concrete player-facing result. Separate required scope from optional additions.

#### Alternatives considered

Briefly list meaningful alternatives, including existing behavior if sufficient.
Omit if none are relevant; do not invent extra research work.

#### Dependencies and scope

Required systems/assets, affected files/owner, source reference where applicable,
and what remains outside the request. Link existing milestone plans rather than
duplicating their required features. A logged request is not authorization to start.

#### Acceptance criteria

- [ ] Agreed player-facing behavior works.
- [ ] Dependencies and applicable source/drop rules satisfied.
- [ ] Appropriate tests/runtime evidence recorded.

#### Resolution

Fill when closed: delivered behavior or reason not planned/duplicate, verification,
commit/PR if available and date.
