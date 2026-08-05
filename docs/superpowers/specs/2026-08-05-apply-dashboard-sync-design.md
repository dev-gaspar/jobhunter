# Design: apply command, local dashboard, email reconciliation

Date: 2026-08-05
Status: approved by user (conversation 2026-08-05)

## Context

JobHunter today only discovers offers through bulk LinkedIn scraping (`jobhunter run`).
Three gaps identified by the user:

1. No way to apply to a single posting the user already found (a `lnkd.in` link or
   pasted post text).
2. No visual overview of accumulated history and metrics.
3. No feedback loop: which sent emails were answered, which bounced, which were
   delivered but ignored.

Decisions made with the user:

- Dashboard scope: **history + metrics only** (no live run streaming).
- Reconciliation: **IMAP read-only, no tracking pixel**. "Left on read" is not
  detectable with plain-text email; "no reply after N days" is the honest proxy.

## Feature 1: `jobhunter apply`

### CLI

```
jobhunter apply <url>            # lnkd.in / linkedin.com post link
jobhunter apply "texto..."       # quoted post text
jobhunter apply                  # no arg: interactive paste mode
jobhunter apply ... --dry        # generate CV/email, do not send
jobhunter apply ... --test x@y   # send to own email instead of recruiter
```

- Input detection: argument matching `^https?://` is a link; anything else is text.
- Paste mode: read lines from stdin until a line containing only `.` (sentinel) or
  EOF. Avoids shell-quoting problems with emojis/newlines in PowerShell.
- Minimum text length 50 chars, same threshold as the pipeline.

### Flow

1. **Link path**: launch Playwright persistent context (`SESSION_DIR`, same as
   pipeline), goto URL (lnkd.in redirects to linkedin.com), wait for load, extract
   the post text (post container selectors with a fallback to the page main text),
   collect emails with `extract_emails`. Session-expired detection identical to
   pipeline (`login`/`signin` in URL -> tell user to run `jobhunter login`).
2. **Analysis**: `agent_filter(cfg, text)`. Show its conclusion (title, company,
   relevance, reason).
   - If `is_job` false or `is_relevant` false: show the reason and ask
     "aplicar de todas formas?" — the user picked this post, the filter informs
     but never blocks.
   - Missing `contact_email`: prompt the user to type one (offer any email found
     by `extract_emails` as default). Abort if none provided.
   - Missing title/company: prompt with sensible defaults instead of silently
     using placeholders.
3. **Generate + send**: same behavior as pipeline Phase 3 (CV via `agent_cv` +
   PDF, email via `agent_email`, preview panel, s/x/e confirm, SMTP send, retry
   x3). Application saved to `knowledge.json` with `mode: "manual"` and the new
   `subject` field (see Feature 3).

### Refactor

Extract pipeline Phase 3 per-offer logic (generate CV -> generate email ->
preview/confirm -> send -> record) from `cmd_run` into a shared module
`jobhunter/applying.py` exposing `apply_to_offer(cfg, kb, job, *, test_email,
dry_run, interactive, preview_send_all)`. `pipeline.cmd_run` and `cli/apply.py`
both call it. Behavior of `run` must not change (existing tests keep passing).

## Feature 2: `jobhunter dashboard`

### CLI

```
jobhunter dashboard              # serve on 127.0.0.1:4090 and open browser
jobhunter dashboard --port 5000
```

### Implementation

- `jobhunter/cli/dashboard.py`: stdlib `http.server.ThreadingHTTPServer`; no new
  dependencies. Binds 127.0.0.1 only. Ctrl+C stops it.
- Routes:
  - `GET /` -> serves `jobhunter/assets/dashboard.html` (single self-contained
    file: inline CSS + vanilla JS, dark aesthetic matching the CLI, no emojis,
    no external requests).
  - `GET /api/data` -> JSON computed by `jobhunter/metrics.py` from
    `knowledge.json`:
    - totals: sent (non-test), replied, bounced, no_reply, unknown
    - rates: reply_rate and bounce_rate over delivered (= sent - bounced)
    - sends per ISO week (last 12 weeks)
    - per-run funnel: posts -> offers -> sent (from `kb.runs`)
    - applications list: date, job_title, company, sent_to, status,
      days_since_sent, reply_date
- Page renders: summary cards, funnel table, weekly bars (CSS only),
  applications table with client-side text filter. Refresh = reload.

## Feature 3: `jobhunter sync`

### CLI

```
jobhunter sync                   # reconcile via Gmail IMAP
jobhunter sync --days 90         # look-back window (default 60)
```

### Implementation

- `jobhunter/inbox.py`: IMAP client (`imaplib`, `imap.gmail.com:993` SSL) using
  existing `smtp_email` / `smtp_password` (Gmail app passwords cover IMAP).
- Exactly **2 IMAP searches** per sync (not one per application):
  1. `INBOX` `SINCE <oldest pending sent date>` -> fetch From/Date/Subject
     headers only.
  2. Same window filtered to `mailer-daemon`/`postmaster` senders -> fetch full
     text to find which recipient address bounced.
  - IMAP `SINCE` needs locale-independent `DD-Mon-YYYY`; month names hardcoded.
- Matching against `kb.applications`:
  - Skip apps where `sent_to != recruiter_email` (test sends) -> status `test`.
  - **replied**: inbox message From == `recruiter_email` (case-insensitive) with
    date >= app date. If several apps share the recruiter email, the reply is
    assigned to the most recent app sent before the reply.
  - **bounced**: a bounce message body mentions `sent_to`.
  - Precedence: replied > bounced (a real reply proves delivery).
  - Otherwise **no_reply**.
- Persisted per application: `status`, `status_checked_at`, `reply_date`,
  `reply_subject` (when replied). Terminal statuses (`replied`, `bounced`) are
  not re-checked on later syncs; `no_reply` is.
- New sends (both `run` and `apply`) additionally store `subject` so future
  matching can use `Re: <subject>` heuristics; v1 matches by From only.
- CLI output: rich table of changes + summary panel (enviados, respondidos,
  rebotados, sin respuesta, tasas). All user-facing text Spanish, `[OK]`-style
  markers, no emojis.
- Errors: IMAP auth failure -> explain Gmail IMAP must be enabled and app
  password valid; network failure -> retry x2 then abort without touching kb.

## Cross-cutting

- Dispatcher (`cli/main.py`): new commands `apply`, `dashboard`, `sync`;
  `help.py` updated.
- Docs: README command table + CLAUDE.md architecture section.
- Python 3.10 compatible (no nested-quote f-strings), Windows-first.
- `.gitignore`: add `config.json.bak` (contains secrets).
- Tests (unittest, existing style): input detection, paste sentinel, filter
  override path (mocked agents), `applying.apply_to_offer` happy path (mocked
  SMTP), metrics aggregation from a fixture kb, IMAP matching logic against
  fake headers (replied/bounced/precedence/multi-app), dashboard `/api/data`
  handler. `pipeline` regression: existing tests must pass unchanged.

## Out of scope

- Tracking pixel / open detection (rejected: spam risk, needs public server).
- Live run streaming in the dashboard.
- Auto-replies to recruiter responses.
