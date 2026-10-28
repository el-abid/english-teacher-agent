# Incident Runbook

Use this runbook when the tutor gives a wrong correction, breaks policy, exposes
data, fails repeatedly or degrades a key metric. The goal is to contain first and
diagnose second.

**Owner:** technical owner named in the Agent Card.
**Escalation:** business owner when the incident affects students or requires a
public statement.

## Severity

| Level | Example | Response |
| --- | --- | --- |
| SEV-1 | student data exposed, secrets leaked, systematic wrong level promotion | kill switch immediately, notify both owners |
| SEV-2 | repeated wrong corrections, provider outage, exam impossible to submit | kill switch if writes make it worse, respond within the hour |
| SEV-3 | single bad answer, slow turn, cosmetic UI issue | no kill switch, normal fix and release |

## 1. Detection

Triggers:

- A student or teacher reports an incorrect correction or an unfair exam result.
- A policy violation: promotion without a pass, level jump, invisible failure.
- An unexpected tool or provider error, or a burst of `502` responses.
- Dashboard errors, token or cost spike, or Langfuse error spans.
- A secret appears outside its environment variable.

First evidence to collect, without editing anything:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/governance
curl "http://127.0.0.1:8000/api/dashboard?limit=100"
```

Record the first bad turn's thread id, timestamp and phase from the dashboard.
Do not paste student text into the ticket unless `ENGLISH_TEACHER_LOG_PROMPTS`
was explicitly enabled.

## 2. Containment

Stop new mutations before investigating:

```bash
uv run english-teacher-governance on --reason "SEV-2 wrong correction" --actor "on-call"
uv run english-teacher-governance status
```

In Docker:

```bash
docker compose exec tutor /app/.venv/bin/english-teacher-governance \
  on --reason "SEV-2 wrong correction" --actor "on-call"
```

Or through the admin API:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/kill-switch \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ENGLISH_TEACHER_ADMIN_TOKEN" \
  -d '{"active": true, "reason": "SEV-2 wrong correction", "actor": "on-call"}'
```

Confirm that `POST /api/sessions` now returns `503` and that reads still work.
Notify the business owner for SEV-1 and SEV-2. Keep the thread ids and the
release tag. Do not delete SQLite files during containment.

If the process itself is compromised or the provider key leaked, also stop the
container and rotate the key before any restart.

## 3. Remediation

1. Identify the smallest cause: prompt, policy threshold, model change, bad
   deployment or data.
2. Reproduce with the scripted tests before touching the live model.
3. Patch on a branch, add a regression test, run the full suite.
4. If the cause is the current release and a fix will take time, roll back:

```bash
git fetch --tags
git tag --list
git checkout v0.1.0
docker compose up -d --build
```

5. Restore the matching SQLite snapshot if the rollback changes the checkpoint
   schema. Keep a copy of the incident database first.
6. Record the root cause, the affected thread ids, the release tag and the tests
   added.

## 4. Recovery

1. Run the full suite and the kill switch drill once more.
2. Clear the switch:

```bash
uv run english-teacher-governance off --reason "fix verified" --actor "on-call"
```

3. Confirm `/api/health` reports `kill_switch: off` and `/api/governance` reports
   `active`.
4. Run one placement and one teaching turn on a disposable session.
5. Check the dashboard for new errors and the expected token cost.
6. Watch for one hour on SEV-1, thirty minutes on SEV-2, then close the incident.
7. Tag the fix with a patch release and update `CHANGELOG.md`.

If `ENGLISH_TEACHER_KILL_SWITCH=1` is set in the environment, clearing the file is
not enough. Unset the variable and restart the process.

## Incident record template

```text
Incident:
Severity:
Detected at (UTC):
Detected by:
Thread ids:
Release / tag:
Symptom:
Containment (time, actor):
Root cause:
Fix / rollback:
Tests added:
Recovery verified at:
Follow-up owner and date:
```

## Useful commands

```bash
# Local
uv run english-teacher-governance status
uv run english-teacher-governance on --reason "..." --actor "..."
uv run english-teacher-governance off --reason "..." --actor "..."
uv run ruff check src tests scripts
uv run pytest

# Containers
docker compose ps
docker compose logs --tail=200 tutor
docker compose exec tutor /app/.venv/bin/english-teacher-governance status
docker compose restart tutor
```

## What not to do

- Do not edit `kill-switch.json` by hand while the service is running; use the
  CLI or the admin API so the change is recorded.
- Do not delete `sessions.sqlite` or `events.sqlite` to "reset" an incident.
- Do not rotate a key by putting the new value in a prompt or a commit.
- Do not promote, demote or re-grade a student manually without recording why.
