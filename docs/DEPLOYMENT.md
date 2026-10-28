# Deployment

The app is a single FastAPI process with two SQLite files. That is enough for a
classroom, a demo or a small pilot. It is not a horizontally scaled service.

## Local

```powershell
uv sync
copy .env.example .env
uv run english-teacher-web
```

Open http://127.0.0.1:8000. The Agent Card is at `/governance`, the logs at
`/dashboard`.

## Docker

Build and run with a named volume so sessions survive a container restart:

```bash
docker build -t english-teacher-agent:0.2.0 .
docker run --rm -p 8000:8000 \
  --env-file .env \
  -e ENGLISH_TEACHER_HOST=0.0.0.0 \
  -e ENGLISH_TEACHER_DB=/data/sessions.sqlite \
  -e ENGLISH_TEACHER_EVENTS_DB=/data/events.sqlite \
  -e ENGLISH_TEACHER_KILL_SWITCH_FILE=/data/kill-switch.json \
  -v tutor-data:/data \
  english-teacher-agent:0.2.0
```

The image runs as UID 10001, not root. It contains a health check against
`/api/health`. The SQLite files and the kill switch live in `/data`.

## Docker Compose

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f tutor
```

Compose reads `.env`, mounts the `tutor-data` volume and applies
`no-new-privileges`. Stop with `docker compose down`; keep the volume unless you
intend to delete student data.

## Cloud platforms

The container is portable. The platform must provide:

- A public HTTPS endpoint in front of port `8000`.
- A persistent volume mounted at `/data`.
- Secret environment variables, never committed to the repository.
- One replica. SQLite does not support safe multi-replica writes.

### Azure Container Apps

1. Push the image to Azure Container Registry.
2. Create a Container App with ingress on port `8000` and external HTTPS.
3. Mount an Azure Files share at `/data`.
4. Put `GOOGLE_API_KEY`, `ENGLISH_TEACHER_ADMIN_TOKEN` and the SMTP password in
   Container Apps secrets, then reference them as environment variables.
5. Set `min replicas = max replicas = 1`.
6. Set the health probe to `/api/health`.

### Render

1. Create a Web Service from the GitHub repository, runtime Docker.
2. Add a persistent disk mounted at `/data` (paid plan; a free instance loses
   SQLite on redeploy).
3. Add the environment variables from `.env.example` in the dashboard.
4. Set the health check path to `/api/health`.
5. Keep one instance.

### Railway

1. Create a project from the repository; Railway detects the Dockerfile.
2. Attach a volume at `/data`.
3. Add the environment variables in the service settings.
4. Generate a public domain; Railway terminates HTTPS.
5. Keep one replica.

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `GOOGLE_API_KEY` | yes | Gemini provider key |
| `ENGLISH_TEACHER_MODEL` | no | defaults to `google_genai:gemini-3.1-flash-lite` |
| `ENGLISH_TEACHER_DB` | no | sessions SQLite path |
| `ENGLISH_TEACHER_EVENTS_DB` | no | events SQLite path |
| `ENGLISH_TEACHER_KILL_SWITCH_FILE` | no | switch state path |
| `ENGLISH_TEACHER_KILL_SWITCH` | no | break-glass override, `1` suspends |
| `ENGLISH_TEACHER_ADMIN_TOKEN` | for admin API | protects the kill switch endpoint |
| `ENGLISH_TEACHER_LOG_PROMPTS` | no | `1` stores message text in local logs |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | no | enables tracing |
| `ALERT_EMAIL_TO` / `ALERT_SMTP_*` | no | enables email alerts |
| `ENGLISH_TEACHER_DAILY_TOKEN_BUDGET` | no | token budget before an alert |

## TLS and least privilege

- Terminate TLS at the platform or a reverse proxy. Do not expose Uvicorn
  directly to the internet over HTTP.
- Use a dedicated Gemini key with the smallest quota that fits the pilot.
- Use a separate random admin token, not a personal password.
- Set `ENGLISH_TEACHER_LOG_PROMPTS=0` unless you have a documented reason and a
  retention policy.
- Restrict who can read the persistent volume; it contains student names and
  messages.
- Put the student UI behind SSO, a VPN or a private network before real use.

## Health and rollback

```bash
curl https://your-host/api/health
curl https://your-host/api/governance
```

A healthy response reports `status: ok`, the version and `kill_switch: off`.
Rollback by deploying the previous image tag, for example
`english-teacher-agent:0.1.0`, and restore the matching database snapshot if the
schema changed. The full procedure is in [RUNBOOK.md](RUNBOOK.md).
