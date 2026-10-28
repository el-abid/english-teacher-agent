# Changelog

All notable changes to this project. Versions follow [SemVer](https://semver.org/):
`MAJOR.MINOR.PATCH`. Git tags use `vMAJOR.MINOR.PATCH`.

## [0.2.0] - 2026-10-28

### Added

- **Agent Card** at `src/english_teacher/agent_card.json`, served at
  `/api/agent-card` and `/.well-known/agent-card.json`, with owners,
  responsibilities, resources, limits, data handling, security and versioning.
- **Governance page** at `/governance` that renders the live card and suspension
  state.
- **Kill switch** backed by `kill-switch.json`, enforced on new sessions and new
  turns. Reads and logs stay available while the switch is active.
- **Admin API** `POST /api/admin/kill-switch`, protected by `X-Admin-Token`
  against `ENGLISH_TEACHER_ADMIN_TOKEN`.
- **Operator CLI** `english-teacher-governance status|on|off`.
- **Break-glass override** `ENGLISH_TEACHER_KILL_SWITCH=1`, which no API call can
  clear.
- **Incident runbook** in `docs/RUNBOOK.md`, plus `docs/GOVERNANCE.md` and
  `docs/DEPLOYMENT.md`.
- **Container deployment** with `Dockerfile`, `docker-compose.yml`, a non-root
  user, a health check and a persistent `/data` volume.
- **Security headers** on every response: `nosniff`, `DENY` framing,
  `no-referrer` and a restrictive permissions policy.
- **Governance events** in the local dashboard, with its own filter.
- 24 governance tests covering the card, SemVer, the switch, the admin API,
  enforcement, the page, the CLI and the deployment artefacts.

### Changed

- `GET /api/health` now reports `version` and `kill_switch`.
- `GET /api/dashboard` now includes `version` and the live `kill_switch` state.
- The web UI shows the version and switch state, and links to the Agent Card.
- The version is now `0.2.0` in `pyproject.toml`, the package and the card.

## [0.1.0] - 2026-10-28

### Added

- CEFR A1 to C2 English tutor with placement, teaching, assessment, exams,
  promotion and remediation.
- French teacher `Mme Laurent` with a 30-topic syllabus and a language picker.
- LangGraph flow, FastAPI web UI, terminal CLI, local dashboard, token and cost
  accounting, Langfuse tracing and email alerts.
