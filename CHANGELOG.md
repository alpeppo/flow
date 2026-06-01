# Changelog

## v0.5.0 — Internationalization (2026-06-01)

Flow now speaks English as its canonical language. German users on a macOS
locale starting with `de` (`de_DE`, `de_AT`, `de_CH`) keep the German UI;
everyone else sees English. No in-app toggle — the system locale decides
at app boot.

### Why

Flow is a public open-source / portfolio project. The repo, README, and
landing page already spoke English; the app itself was German-only. English
reviewers opening the repo and then the app would see the mismatch. v0.5.0
removes that gap and makes the app shippable to non-German users.

### What changed

- **New `src/wnflow/i18n.py` module** with `detect_locale()`, `t(key)`, and
  a flat dict of ~90 translation keys × 2 languages.
- **All user-visible Python strings** route through `t()`: 13 `notify(...)`
  calls in `app.py` (titles normalized `"worknetic-flow"` → `"Flow"` at the
  same time), the 6 menubar entries, the 3 mode labels.
- `MODE_LABELS` dict replaced with `mode_label(mode)` function so the
  locale is re-resolved per call, not frozen at module import.
- **All user-visible JS strings** in `web/index.html` use a JS-side
  `t(key, vars)` / `tPlural(baseKey, n, vars)` resolver. The translation
  dict is pushed once at boot by Python via the new `getLocale` bridge
  action.
- **Locale-ready render queue**: `whenLocaleReady(fn)` defers the first
  `loadHistory` / `loadSettings` until `applyLocale` has arrived, so DE
  users don't see an EN-flash on first open.
- **Generic `data-i18n` re-render** in `applyLocale` keeps static HTML
  attributes synced when locale changes.
- **`docs/install.sh`** localizes terminal output via
  `LC_ALL > LC_MESSAGES > LANG` (macOS override order). Curl-piped bash
  with no env vars defaults to English. ~27 i18n keys covering every
  user-visible echo.

### Quality

- 130 tests, all green (up from 120).
- 10 new tests in `tests/test_i18n.py` — locale detection, EN/DE lookup,
  defensive fallback for unknown keys, key-set parity enforcement, plus
  a guard against `MODE_LABELS` frozen-dict regression.

### Convention

Commit messages on this release branch are written in English to match
the release theme and to read naturally for international portfolio
reviewers on GitHub. CLAUDE.md's "German conversation, English code" rule
still applies to in-session discussion.

### Known follow-ups

- Settings → Language dropdown options come from Python as native language
  names (`Deutsch`, `English`, `Français`, …) — convention for
  language-name dropdowns; no translation needed.
- TOML save failure when hotwords come back from the WKWebView bridge as
  `NSArray` instead of `list` — pre-existing bug, not introduced here.
  Tracked for v0.5.1.

---

## v0.4.0 — Security hardening (2026-06-01)

Triggered by an independent security audit (`docs/security-audit-v0.4.0.md`).
Eight findings addressed, two intentionally deferred (CI build attestation,
macOS Keychain — both documented in the audit).

### Security

- **API-key, history, and log files are now `0600`** (owner-only read).
  `config.toml` is rewritten with tight permissions on every save; new
  history entries and log writes do the same. Reduces lateral-process
  exposure on multi-tenant Macs and limits sensitive content in backups.
- **AppleScript injection in `notify.py` closed** by passing message/title
  as argv to `osascript -e ... -- message title`, no longer interpolated
  into the script body. Closes a path where Groq API error messages could
  break out of the AppleScript string literal.
- **Log rotation** via `RotatingFileHandler` (5 MB × 3 backups). Chatty
  third-party libraries (`httpx`, `httpcore`, `urllib3`, `huggingface_hub`,
  `hf_xet`) now log at WARNING, eliminating the model-load spam in
  `wnflow.log`.

### Privacy

- **"Alle löschen"** button in Settings → Verlauf, with a native confirm
  dialog. Settings tab also shows the current history count.
- Default `LoggingConfig.keep_transcripts` stays `False` so new installs
  never log raw dictations by default.

### UX

- **Recording cap reintroduced at 10 minutes** (was unbounded since v0.3.0).
  Existing user TOMLs with the v0.2 default (`60.0`) or the v0.3 default
  (`0.0`) are migrated automatically to `600.0`. Explicit user choices
  (anything outside `{0.0, 60.0}`) are kept untouched.
- **Pill timer warns visually** before the cap:
  - 9:00 → yellow (`#febc2e`)
  - 9:30 → orange (`#ff8c2e`)
  - 9:45 → red blinking at 2 Hz (`#ff5f57`)
  - 10:00 → auto-stop (existing mic behavior)
- All user-visible German strings now use real umlauts (ä, ö, ü, ß) per
  CLAUDE.md rule. A reusable `scripts/fix_umlauts.sh` keeps future
  regressions cheap to revert.

### Engineering

- **Version single-source-of-truth** via `importlib.metadata`. `pyproject.toml`,
  `wnflow.spec`, and the startup log are now in sync automatically.
  PyInstaller bundle ships the package's dist-info via `copy_metadata` so
  `importlib.metadata.version("worknetic-flow")` resolves at runtime.
- **`threading.Lock` in `HotkeyListener`** guards the Timer-thread race on
  `_pending_ptt_timer`, `_pending_ptt_mode`, and `_last_tap_time`. The
  THREADING NOTE docstring documents the invariant.
- **`MainWindow.dispose()`** to break the intentional `_BridgeHandler`
  retain cycle on shutdown. Called from `app._quit()`.

### Test suite

- **120 tests, all green** (up from 103).
- New test modules:
  - `tests/test_version_metadata.py` — `__version__` shape + pyproject parity.
  - `tests/test_config_chmod.py` — 0600 on save, migration from `{0.0, 60.0}` → 600.0.
  - `tests/test_notify_safety.py` — AppleScript injection regression.
  - `tests/test_history_clear.py` — chmod + `clear()` semantics.
  - `tests/test_logging_rotation.py` — RotatingFileHandler attached, chatty libs WARNING.
  - `tests/test_hotkey_thread_safety.py` — `_lock` attribute + acquisition.

### Deferred to v0.5+

- **macOS Keychain** for API-key storage (notarization required first for the ACL story to work cleanly).
- **CI build attestation** via `actions/attest-build-provenance` (needs a GitHub Actions workflow set up first).
- **`clear_history` confirmation as in-UI dialog** (currently uses native `confirm()` for v0.4.0 simplicity).

### Documentation

- `docs/security-audit-v0.4.0.md` — independent verification of the
  external review, with per-finding threat-model and fix proposals. Lives
  in the repo so reviewers can see the trail.
- `plans/v0.4.0-security-hardening.md` — the implementation plan this
  changelog summarizes.
