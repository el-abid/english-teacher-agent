# English Teacher Agent (LangGraph)

A CEFR English tutor for high-school students. The student picks a starting level
(A1 to C2), works through short lessons, and gets promoted only after passing the
level exam. A failed exam sends them into a targeted review of the exact points
that failed, then they retake it.

Two front ends share the same graph: a terminal chat and a web UI with a chat
panel and live skill bars.

## Run it

```powershell
cd english-teacher-agent
uv sync
copy .env.example .env      # then put your GOOGLE_API_KEY in .env
uv run english-teacher-web  # http://127.0.0.1:8000
```

Terminal instead of the browser:

```powershell
uv run python -m english_teacher.cli --level B1 --name Yassine
```

The web server keeps each browser session in `sessions.sqlite`, so a page reload
or a server restart resumes the same conversation.

Tests need no API key, they run the graph with a scripted model:

```powershell
uv run pytest -q
```

## What the student experiences

1. They pick a starting level on the start screen (or answer "B1" in the terminal).
2. Three placement questions seed their skill profile.
3. Lessons arrive one task at a time. Each answer is graded and folded into four
   skill scores: grammar, vocabulary, reading, writing.
4. When the numeric gate passes, the tutor *suggests* the exam and waits. The
   student can decline and keep practising.
5. The exam: multiple-choice items plus one writing task.
6. Pass: promotion to the next level. Fail: the failure points become a review
   plan, the tutor drills them, then offers a retake.

## Why the model does not give grades

The LLM writes lessons, feedback, exam items and the exam conversation. It never
decides a promotion on its own.

| Decision | Decided by | File |
| --- | --- | --- |
| Skill mastery after an answer | exponential moving average | `policy.py` |
| Ready for the exam | thresholds + evidence count | `policy.py` |
| Tutor thinks they are ready | LLM opinion, can only delay | `nodes/teaching.py` |
| Multiple-choice score | answer key comparison in Python | `policy.py` |
| Writing score | LLM rubric, clamped to 0..1 | `nodes/exam_flow.py` |
| Pass or fail | weighted score plus per-skill floor | `policy.py` |
| Review plan | failed items and failed skills | `nodes/exam_flow.py` |

Default gates: at least 3 completed topics, every skill at 0.60 with 2+
observations, mean 0.68, exam pass mark 0.70, no exam skill under 0.50. All
configurable from the environment.

## Graph shape

```
START
  -> intake                 (level choice, syllabus plan)
  -> placement_quiz         (3 questions, interrupt)
  -> grade_placement
  -> teacher_turn           (one explanation + one task)
  -> wait_student           (interrupt: the student's turn)
  -> assess_answer
  -> check_readiness        -> advance_topic -> teacher_turn
                            -> offer_exam    -> wait_student
                                               -> handle_exam_decision
                                                  -> build_exam -> wait_student
                                                     -> grade_exam -> review_exam
                                                        -> advance_level -> teacher_turn | END
                                                        -> remediation   -> wait_student
                            -> teacher_turn
```

Every pause is a LangGraph `interrupt()`, resumed with `Command(resume="...")`.
The pause is checkpointed in sqlite, so a session survives a crash or a restart.
The web API reads that checkpoint to redraw the transcript after a reload.

## HTTP API

| Route | Purpose |
| --- | --- |
| `GET /` | the web UI |
| `GET /api/health` | status plus the model in use |
| `GET /api/levels` | A1 to C2 with labels |
| `POST /api/sessions` | start a session: `{name, level, goal}` |
| `GET /api/sessions/{id}` | snapshot: reply, transcript, mastery, exam result |
| `POST /api/sessions/{id}/messages` | resume the pause with `{message}` |
| `GET /api/dashboard` | local totals and recent events as JSON |
| `GET /dashboard` | the logs and tokens page |

Interactive docs at `/api/docs`.

## Tracing with Langfuse

Tracing is off until you give it keys:

```powershell
$env:LANGFUSE_PUBLIC_KEY="pk-lf-..."
$env:LANGFUSE_SECRET_KEY="sk-lf-..."
# optional for self-hosted: $env:LANGFUSE_HOST="https://langfuse.example.com"
uv run english-teacher-web
```

Then every web request and CLI session exports a trace. The LangGraph thread id
becomes the Langfuse **session id**, so a conversation reloaded in the browser
stays one session in the Langfuse UI. The student's name is the user id, and the
level (`B1`, `A2`...) plus `web`/`cli` are tags. `GET /api/health` reports
`"tracing": "langfuse"` once keys are picked up, `"off"` otherwise.

Without keys the tutor never imports Langfuse and makes no tracing network call.
An unreachable Langfuse cannot break a lesson either: the handler is built inside
a try/except and dropped on failure (`tracing.py`).

To check ingestion without running a lesson:

```powershell
uv run python scripts/langfuse_check.py --send       # one test span, then list traces
uv run python scripts/langfuse_check.py --session web-3656f1da0347
```

It prints the host, the auth result, and a clickable trace URL per row.

## Logs, tokens and email alerts

Langfuse is the long-term shared view. The app keeps its own copy in
`events.sqlite` so you do not have to open another service to see what happened.
Open <http://127.0.0.1:8000/dashboard>, or click **Logs & tokens** in the tutor
sidebar.

One row per turn, per model call, and per error:

| Kind | Written when | Carries |
| --- | --- | --- |
| `turn` | a student message is handled | latency, thread id, student name |
| `llm` | a model call ends | tokens in/out, model, latency, cost |
| `error` | a turn or model call fails | exception text, latency |
| `alert` | an alert is triggered | what was sent |

The top cards show today's turns, model calls, tokens, estimated cost, errors and
how much of the daily budget is used. The table filters by kind and refreshes
every 5 seconds.

Token counts come from the model's own usage metadata, collected by a LangChain
callback (`observability.py`). Cost is an estimate at the prices in
`ENGLISH_TEACHER_PRICE_INPUT_PER_M` and `ENGLISH_TEACHER_PRICE_OUTPUT_PER_M`.
Prompt and student text is **not** stored by default; the `detail` column holds
routing labels (`phase`, `level`, `topic`). Set `ENGLISH_TEACHER_LOG_PROMPTS=1`
to append the student's message to that column.

### Enable email alerts

A recipient and a server are all it takes. Without them nothing is sent and no
network call happens. Two naming schemes work, so an existing Flask-Mail `.env`
needs no changes:

| Meaning | App name (wins) | Fallback |
| --- | --- | --- |
| recipient | `ALERT_EMAIL_TO` | `MAIL_DEFAULT_SENDER`, then `MAIL_USERNAME` |
| server | `ALERT_SMTP_HOST` | `MAIL_SERVER` |
| port | `ALERT_SMTP_PORT` | `MAIL_PORT` |
| login | `ALERT_SMTP_USER` | `MAIL_USERNAME` |
| password | `ALERT_SMTP_PASSWORD` | `MAIL_PASSWORD` |
| sender | `ALERT_EMAIL_FROM` | `MAIL_DEFAULT_SENDER`, then `MAIL_USERNAME` |
| encryption | `ALERT_SMTP_TLS` (`starttls`/`ssl`/`none`) | `MAIL_USE_TLS`, `MAIL_USE_SSL` |

```dotenv
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=you@gmail.com
MAIL_DEFAULT_SENDER=you@gmail.com
# MAIL_PASSWORD is exported by the OS, not written here
ENGLISH_TEACHER_DAILY_TOKEN_BUDGET=200000
```

`MAIL_PASSWORD` can stay out of `.env`: `load_env_file()` uses `setdefault`, so a
variable already exported by the OS is never overwritten. Gmail needs 2FA on and
an App Password, not your normal account password.

Check the setup and send one test mail:

```powershell
uv run python scripts/alert_check.py          # config report, no network, no secrets
uv run python scripts/alert_check.py --send   # deliver a test email
```

The report prints where each value came from and only the length of the
password, never the password.

Two alerts exist:

1. **Budget:** fires when today's token total crosses the daily budget, at most
   once per day. Set the budget to `0` to disable it.
2. **Failure:** fires when a turn or model call raises, at most once per 15
   minutes per failure point.

Sending runs on a daemon thread, so a slow SMTP server never delays a student.
A failed send never raises into the lesson, and the alert is logged locally
either way. Restart the server after editing `.env`; `GET /api/health` reports
`"alerts": "email"` once it is picked up.

## Project layout

| Path | Role |
| --- | --- |
| `src/english_teacher/graph.py` | nodes, edges, conditional routing, checkpointer |
| `src/english_teacher/state.py` | `TeacherState` shared by every node |
| `src/english_teacher/cefr.py` | levels, skills, 30-topic syllabus |
| `src/english_teacher/policy.py` | mastery maths, readiness gate, exam scoring |
| `src/english_teacher/prompts.py` | teacher persona and every prompt |
| `src/english_teacher/nodes/intake.py` | level choice, placement quiz and grading |
| `src/english_teacher/nodes/teaching.py` | lesson turn, assessment, readiness check |
| `src/english_teacher/nodes/exam_flow.py` | exam offer, generation, grading, promotion, remediation |
| `src/english_teacher/nodes/interaction.py` | the single interrupt that waits for the student |
| `src/english_teacher/server.py` | FastAPI app and the `english-teacher-web` entry point |
| `src/english_teacher/tracing.py` | Langfuse wiring: session/user metadata, safe no-op |
| `src/english_teacher/observability.py` | local event store, token meter, cost estimate |
| `src/english_teacher/alerts.py` | SMTP alerts with once-a-day and cooldown rules |
| `src/english_teacher/web/` | HTML, CSS and vanilla JS for the tutor and dashboard |
| `scripts/langfuse_check.py` | send a test span, list traces with URLs |
| `scripts/alert_check.py` | report alert config, optionally send a test mail |
| `tests/` | 62 tests: policy rules, prompt plumbing, tracing, API, observability, alerts |

## Tuning

| Variable | Default | Effect |
| --- | --- | --- |
| `ENGLISH_TEACHER_MODEL` | `google_genai:gemini-3.1-flash-lite` | any `init_chat_model` string |
| `ENGLISH_TEACHER_TEMPERATURE` | `0.3` | lesson creativity |
| `ENGLISH_TEACHER_MIN_LESSONS` | `3` | topics before an exam is possible |
| `ENGLISH_TEACHER_MIN_SKILL` | `0.60` | per-skill bar for readiness |
| `ENGLISH_TEACHER_PASS_MARK` | `0.70` | exam pass mark |
| `ENGLISH_TEACHER_EXAM_ITEMS` | `8` | multiple-choice item count |
| `ENGLISH_TEACHER_EXAM_MCQ_WEIGHT` | `0.6` | objective vs writing weight |
| `ENGLISH_TEACHER_OFFER_COOLDOWN` | `3` | turns before offering the exam again |
| `ENGLISH_TEACHER_DB` | `./sessions.sqlite` | sqlite file for the web server |
| `ENGLISH_TEACHER_HOST` | `127.0.0.1` | web server bind address |
| `ENGLISH_TEACHER_PORT` | `8000` | web server port |
| `LANGFUSE_PUBLIC_KEY` | unset | enables tracing together with the secret key |
| `LANGFUSE_SECRET_KEY` | unset | Langfuse secret key |
| `LANGFUSE_HOST` | Langfuse cloud | self-hosted Langfuse URL |
| `ENGLISH_TEACHER_EVENTS_DB` | `./events.sqlite` | local log database |
| `ENGLISH_TEACHER_PRICE_INPUT_PER_M` | `0.10` | USD per million input tokens |
| `ENGLISH_TEACHER_PRICE_OUTPUT_PER_M` | `0.40` | USD per million output tokens |
| `ENGLISH_TEACHER_LOG_PROMPTS` | `0` | store prompt text in the local log |
| `ENGLISH_TEACHER_DAILY_TOKEN_BUDGET` | `0` | daily token budget, `0` disables |
| `ALERT_EMAIL_TO` | `MAIL_DEFAULT_SENDER` | alert recipient |
| `ALERT_SMTP_HOST` | `MAIL_SERVER` | SMTP server, enables email |
| `ALERT_SMTP_PORT` | `MAIL_PORT`, else `587` | SMTP port |
| `ALERT_SMTP_USER` | `MAIL_USERNAME` | SMTP login |
| `ALERT_SMTP_PASSWORD` | `MAIL_PASSWORD` | SMTP password or app password |
| `ALERT_EMAIL_FROM` | `MAIL_DEFAULT_SENDER` | sender address |
| `ALERT_SMTP_TLS` | `MAIL_USE_TLS` | `starttls`, `ssl` or `none` |

Adding a topic means adding one dict to `SYLLABUS` in `cefr.py`. No prompt needs
to change.

## Extending

- **Real speaking and listening:** add a speech-to-text node that produces a
  transcript, then reuse `assess_answer`. Add `listening`/`speaking` back to
  `SKILLS` in `cefr.py` when the audio pipeline exists.
- **Streaming responses:** swap the web route for `graph.stream(...,
  stream_mode="updates")` and push tokens to the page with SSE.
- **Human teacher review:** before `advance_level`, add an approval interrupt.
  The exam result is already a structured object in state.
- **Authentication:** sessions are keyed by an unguessable thread id, but there is
  no login and no student database yet.

## Limits to know about

- Text only. No audio pipeline, and the mastery model tracks four skills.
- The writing score comes from an LLM rubric. Keep a human spot check for real
  certification.
- One thread is one student session. Losing the browser's stored thread id means
  starting over.
- The graph retries invalid exam JSON once, then raises. It does not silently
  ship a broken exam.
