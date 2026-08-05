# Design: assisted recruiter network, MX pre-send check, per-query analytics

Date: 2026-08-05
Status: approved by user (selected from proposed options, conversation 2026-08-05)

## Context

Three improvements selected by the user after the apply/dashboard/sync release:

1. Grow the LinkedIn network with recruiters so searches surface more posts —
   **assisted mode** (full automation of invites is a top ban vector; a ban
   would also kill the scraping session).
2. Two recent bounces were caused by a typo'd domain (`nuvelity.com` instead
   of `nubelity.com`). Validate the recipient domain before sending.
3. `optimize` has no signal about which queries produce offers that get
   replies. Feed reconciliation results back per query.

## Feature A: author capture + `jobhunter network` (assisted)

- During scraping, capture the post author per listitem: first anchor matching
  `a[href*="/in/"]` gives `author_url` (path only, no query params) and
  `author_name` (anchor text, first line). Stored on each post; carried onto
  offers (`author_url`, `author_name`) and into `kb.applications` records.
- New command `jobhunter network`:
  - Builds a queue of recruiter candidates from `kb.applications` (newest
    first): entries with `author_url`, deduped, excluding profiles already in
    `kb["network"]`.
  - Interactive loop per candidate: shows name, company, job title, applied
    date; options `(a)` open profile in the DEFAULT browser (`webbrowser` —
    the user's logged-in browser, where they click "Conectar" themselves),
    `(x)` skip, `(q)` quit. After opening, asks if the invite was sent.
  - Persists to `kb["network"]`: `{profile_url, name, company, status:
    "invited"|"skipped", date}`. Never auto-clicks anything on LinkedIn.
  - Prints a guardrail note: keep manual invites moderate (LinkedIn caps
    ~100/week for everyone).

## Feature B: MX validation before sending

- `jobhunter/mailer.py` gains `domain_accepts_mail(email) -> True|False|None`:
  - Minimal DNS MX query over UDP (stdlib socket, no new deps, no
    locale-dependent `nslookup` parsing): question type MX (15) to the public
    resolver `8.8.8.8:53`, 3s timeout.
  - `True` = answer count > 0; `False` = NOERROR/NXDOMAIN with zero MX
    answers; `None` = network error/timeout (unknown, never blocks).
- `applying.apply_to_offer` checks before sending (only when result is
  `False`):
  - Interactive: warn `El dominio X no tiene registros de correo (posible
    typo)` and prompt for an alternative email (empty = skip this offer).
  - Non-interactive (`--auto`): skip the offer, counted as skipped with the
    reason printed.
- Existing tests that reach the send path mock `domain_accepts_mail`.

## Feature C: per-query analytics feeding optimize

- Pipeline tags each scraped post with the `query` that found it; the tag
  flows to the offer and into the `kb.applications` record (field `query`).
  `apply` records have no query (manual).
- `agents/optimizer.py` builds a per-query performance block from
  `kb.applications` (only entries having `query`): sent count and replied
  count per query, sorted by replies then sent, top 15. Injected into the
  prompt as `RENDIMIENTO REAL POR QUERY` with an instruction to keep/expand
  patterns from queries that got replies and drop patterns with sends but no
  replies. Omitted when no tagged data exists yet.

## Out of scope

- Automated connection requests or invite notes (ban risk).
- Follow-up emails (not selected).
- Dashboard rendering of network/query data (can come later).

## Tests

unittest, existing style: DNS packet build/parse with crafted bytes; author
extraction via fake page; network queue building + dedup vs kb["network"]
(command loop with mocked Prompt/webbrowser); query tag propagation into kb
record via `apply_to_offer`; optimizer prompt includes per-query block when
data exists and omits it when not; MX gate paths in `apply_to_offer`
(interactive alternate email / non-interactive skip / None never blocks).
