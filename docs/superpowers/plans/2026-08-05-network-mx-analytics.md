# network + MX check + query analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (same-session inline execution). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Assisted recruiter-network command, DNS MX validation before sending, and per-query reply analytics feeding `optimize`, per `docs/superpowers/specs/2026-08-05-network-mx-analytics-design.md`.

**Architecture:** Author + query tags captured at scrape time flow through offers into `kb.applications`. `network` reads those tags and tracks state in `kb["network"]` (no LinkedIn automation; opens default browser). MX check is a raw stdlib UDP DNS query in `mailer.py`, enforced in `applying.apply_to_offer`. `optimizer.py` gains a pure `build_query_stats` injected into its prompt.

**Tech Stack:** Python 3.10+ stdlib only (socket, struct, webbrowser). unittest.

## Global Constraints

Same as the 2026-08-05 apply/dashboard/sync plan: repo root `C:\Users\joseg\.jobhunter`, Spanish CLI text without emojis, no nested-quote/triple-quoted f-strings, tests never touch real config/kb, Spanish conventional commits on `feature/network-mx-analytics` with the session trailer.

### Task 1: DNS MX check in `mailer.py` + gate in `applying.py`

- Test: `tests/test_mailer.py` append `DomainAcceptsMailTests` — `_build_mx_query` ends with qtype 15/class 1; `_parse_mx_response`: an>0 → True, rcode 3 → False, rcode 0 an=0 → False, wrong txid → None, short → None; bad email ("", "sin-arroba") → False without network.
- Implement `_build_mx_query(domain, txid)`, `_parse_mx_response(data, txid)`, `domain_accepts_mail(email, resolver=("8.8.8.8", 53), timeout=3.0)` (any exception → None).
- Test: `tests/test_applying.py` — patch `jobhunter.applying.domain_accepts_mail`: existing send tests patched to True; new: False+interactive → Prompt alt email used as recipient and persisted; False+interactive+empty alt → skipped; False+non-interactive → skipped; None → sends. Skip check entirely when `test_email` is set.
- Implement gate in `apply_to_offer` after the `if not do_send` block, before SMTP.
- Live smoke: `domain_accepts_mail` on `nubelity.com` (True) vs `nuvelity.com` (expected False) vs `gmail.com` (True).
- Commit: `feat(mailer): validacion MX del dominio antes de enviar`.

### Task 2: query + author tags end-to-end

- Scraper: posts-extraction JS adds `author_url` (first `a[href*="/in/"]` in the closest listitem, no query params) and `author_name` (anchor text first line).
- Pipeline: tag `pi["query"] = query` in the Phase 1 dedup loop; Phase 2 accepted offers copy `query`, `author_url`, `author_name` from the post.
- `applying.apply_to_offer`: kb record gains `query`, `author_url`, `author_name` (None for manual `apply`).
- Test: `tests/test_applying.py` sent test asserts the three fields persist from the job dict.
- Commit: `feat(pipeline): etiquetar query y autor del post hasta el historial`.

### Task 3: `build_query_stats` + optimizer injection

- Test: `tests/test_agents_optimizer.py` append — stats string contains query with sent/replied counts sorted by replies; empty when no tagged apps; prompt includes `RENDIMIENTO REAL POR QUERY` when kb has tagged apps (patch `call_gemini`, inspect prompt) and omits it otherwise.
- Implement `build_query_stats(applications, top=15)` in `agents/optimizer.py`; inject into the prompt next to `run_stats` with the keep/drop instruction.
- Commit: `feat(optimize): rendimiento real por query en el prompt`.

### Task 4: `jobhunter network` command

- Test: `tests/test_cli_network.py` — `build_network_queue` dedups by profile vs `kb["network"]` and within itself, skips apps without `author_url`, newest first; `cmd_network` flow with mocked Prompt/Confirm/webbrowser/save_kb: open+confirm → entry `invited`, `x` → `skipped`, `q` → stops; empty queue prints the explanation that authors are captured from now on.
- Implement `jobhunter/cli/network.py` (`build_network_queue`, `cmd_network`), wire dispatcher `network` + help rows + guardrail note (~100 invites/week cap is LinkedIn-wide; keep manual pace moderate).
- Commit: `feat(network): cola asistida de reclutadores para conectar`.

### Task 5: docs + finish

- README + CLAUDE.md command lists; full suite; py_compile new files; grep for forbidden f-string patterns.
- Commit: `docs: documentar network, validacion MX y analitica por query`.
- finishing-a-development-branch: push, PR, CI, ask merge.
