# Governance

This document is the operational contract around the Language Teacher Agent. The
live machine-readable version is the [Agent Card](../src/english_teacher/agent_card.json),
served at `/api/agent-card` and `/.well-known/agent-card.json`.

## 1. Identity and ownership

| Item | Value |
| --- | --- |
| Agent id | `el-abid/english-teacher-agent` |
| Product | CEFR A1-C2 tutor for English and French |
| Business owner | El Abid, product owner for education |
| Technical owner | El Abid, maintainer |
| Runtime | FastAPI + LangGraph, Google Gemini |
| Current version | `0.2.0` |
| Incident procedure | [RUNBOOK.md](RUNBOOK.md) |

Ownership is not decorative. The business owner decides which levels, languages
and skills are in scope. The technical owner owns the prompts, policy thresholds,
deployment and incident response. One person can hold both roles today; the card
keeps the two responsibilities separate so they can be handed over.

## 2. Responsibilities

The agent:

1. Runs a three-question placement check for the chosen language and level.
2. Teaches the static CEFR syllabus one task at a time, in the target language.
3. Scores grammar, vocabulary, reading and writing after each answer.
4. Offers the level exam only when the readiness gate passes, and waits for consent.
5. Grades objective exam items in Python and the writing task with a rubric.
6. Promotes exactly one level on a pass, or remediates failed points on a fail.

The model never changes a score, a level or a threshold. Those are Python policy.

## 3. Scope and limits

In scope:

- English and French, CEFR A1 to C2.
- Grammar, vocabulary, reading and writing.
- One student per browser session or terminal thread.

Out of scope:

- Listening and speaking assessment. No audio capture, playback or pronunciation
  scoring.
- Promotion without a passed exam.
- Multi-tenant billing, classroom rosters or teacher administration.
- Horizontal scaling on a shared SQLite file.

Guardrails:

- The readiness gate and pass mark live in `policy.py`, not in a prompt.
- A failed exam creates remediation for the exact failed points before a retake.
- Student text is excluded from logs unless `ENGLISH_TEACHER_LOG_PROMPTS=1`.
- The kill switch blocks new sessions and turns without deleting existing data.

## 4. Versioning policy

SemVer, with Git tags shaped `vMAJOR.MINOR.PATCH`.

| Bump | When | Examples |
| --- | --- | --- |
| Major | Breaking change to the graph contract, API shape or stored state | rename a resume payload field, change checkpoint schema |
| Minor | New capability, language, endpoint or tool, backward compatible | add a third language, add the Agent Card endpoint |
| Patch | Bug fix, prompt tuning, performance or configuration adjustment | fix an accent correction, lower a timeout |

Every release updates `pyproject.toml`, `src/english_teacher/__init__.py`, the
Agent Card JSON and `CHANGELOG.md`. A test enforces that the three version strings
match. Tags are created only after the suite passes.

Rollback is a version checkout, not a reverse edit:

```bash
git fetch --tags
git checkout v0.1.0
docker compose up -d --build
```

Before rolling back, check whether the current release changed the SQLite
checkpoint schema. If it did, restore the matching database snapshot from the
data volume.

## 5. Kill switch

The switch is a small JSON file, by default a sibling of `sessions.sqlite`:

```json
{
  "active": true,
  "reason": "wrong correction reported",
  "actor": "on-call",
  "since": "2026-10-28T14:00:00+00:00",
  "updated_at": "2026-10-28T14:00:00+00:00"
}
```

Effective state is the file **or** `ENGLISH_TEACHER_KILL_SWITCH=1`. The
environment override cannot be cleared by the API or the CLI; unset it and
restart the process.

When active:

- `POST /api/sessions` returns `503` with `Retry-After: 60`.
- `POST /api/sessions/{id}/messages` returns `503`.
- `GET /api/sessions/{id}`, `/api/health`, `/api/governance`,
  `/api/agent-card`, `/dashboard` and `/governance` stay available.
- The CLI refuses to start or continue a session.

Activate and clear it with the operator CLI:

```bash
uv run english-teacher-governance on --reason "wrong correction reported" --actor "on-call"
uv run english-teacher-governance status
uv run english-teacher-governance off --reason "fix verified" --actor "on-call"
```

Or through the admin API, when `ENGLISH_TEACHER_ADMIN_TOKEN` is configured:

```bash
curl -X POST http://127.0.0.1:8000/api/admin/kill-switch \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ENGLISH_TEACHER_ADMIN_TOKEN" \
  -d '{"active": true, "reason": "wrong correction reported", "actor": "on-call"}'
```

The admin API is hidden with `404` when no token is configured, and rejects a
wrong token with `403`. Every change is written to the events database as a
`governance` event.

## 6. Security boundaries

- Secrets exist only in environment variables: provider key, admin token and SMTP
  password. They are never placed in prompts, logs, the Agent Card or responses.
- The Agent Card names the environment variable, never its value.
- Use a dedicated Gemini key and a dedicated admin token. Do not reuse personal
  credentials.
- HTTPS is terminated by the reverse proxy or cloud platform. The container
  listens on plain HTTP only on its private network.
- The demo student UI is unauthenticated. Put it behind SSO, a VPN or a private
  network before real student use.
- Responses set `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer` and a restrictive `Permissions-Policy`.

## 7. Review cadence

At each release:

- [ ] Version bumped in all three places and `CHANGELOG.md` updated.
- [ ] Agent Card still matches the real endpoints, model and limits.
- [ ] `uv run ruff check src tests scripts` passes.
- [ ] `uv run pytest` passes.
- [ ] Kill switch tested in a drill, including the `503` path.
- [ ] Rollback tag identified.
- [ ] Owners and contacts still current.
