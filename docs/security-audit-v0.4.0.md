# Security Audit — Flow v0.4.0

**Author:** Independent verification of an external code review.
**Date:** 2026-05-29
**Audited commit:** `6fff55e` (main, post-i18n landing page)
**Method:** Read each finding, reproduce against the codebase, build a threat model, propose a fix proportional to actual risk.
**Reviewer instruction (Tim):** *"Du sollst die Findings nicht blind übernehmen — selbst verifizieren, eigene Einschätzung."*

This report is the gate before any implementation work. Nothing in the codebase has been changed yet.

---

## Summary

| # | Finding | Reviewer severity | My severity | Status | Action in v0.4.0 |
|---|---|---|---|---|---|
| 1 | Groq API-Key in plaintext `config.toml` | CRITICAL | **HIGH** | ⚠ Partial | `chmod 0600` on write, doc note |
| 2 | `curl \| bash` installer without SHA256 verify | HIGH | **MEDIUM** | ⚠ Partial | README hint; CI attestation later |
| 3 | History + log plaintext, no GDPR safeguards | HIGH | **MEDIUM** (only fix-able pieces) | ⚠ Partial | `keep_transcripts=false` default + `chmod 0600` + clear-history UI |
| 4 | AppleScript injection in `notify.py` | HIGH | **MEDIUM** | ✅ Confirmed | Rewrite via `osascript ... -- argv` |
| 5 | PyObjC retain-cycle in `_BridgeHandler` | MEDIUM | **LOW** | ⚠ Partial | Doc + optional cleanup hook |
| 6 | `max_duration_s = 0` (uncapped recording) | MEDIUM | **DECLINED** | ❌ Rejected | Tim set this on purpose; doc tooltip only |
| 7 | Logging without rotation, library debug spam | HIGH | **MEDIUM** | ✅ Confirmed | `RotatingFileHandler` + `httpx`/`httpcore` → WARNING |
| 8 | Umlaut violations (`fuer`, `ueber`, …) | LOW | **MEDIUM** (user-visible) | ✅ Confirmed | Fix UI strings; comments lower priority |
| 9 | Version drift (`0.3.0` vs releases `0.3.4`) | LOW | **LOW** | ✅ Confirmed | Single source of truth via `importlib.metadata` |
| 10 | Hotkey thread-safety (`_last_tap_time`) | MEDIUM | **LOW** | ⚠ Partial | NSEvent monitors are main-thread; only `threading.Timer` race possible; defensive lock |

**Result:** 8 of 10 findings warrant code changes; 1 is rejected with reasoning; 1 is real but doesn't need a code change in v0.4.0 (will mature into CI work later).

---

## Finding 1 — Groq API-Key in plaintext config

**Reviewer claim:** Key sits unmasked in `~/.worknetic-flow/config.toml` (world-readable `0644`) and in `.env` in the repo root.

### Verification

```bash
$ ls -la ~/.worknetic-flow/config.toml
-rw-r--r-- ... config.toml
```

Yes, `0644`. The TOML contains `api_key = "gsk_nYWF..."` in cleartext — confirmed.

Git history check:

```bash
$ git log -p -S "gsk_" --all
```

All `gsk_*` matches in history are test fixtures (`gsk_test_123`, `gsk_persistent`, etc.). **No real key was ever committed.** That part of the reviewer's claim is incorrect — `.env` is gitignored and contains a placeholder format only.

Write path: `config.py:204-212`. The TOML is written via `tomli_w.dumps(...).encode("utf-8")` → `tmp.replace(path)`. Atomic, but inherits the process umask (typically `0022` → file becomes `0644`).

### Threat model

Flow is a single-user macOS app. Who realistically reads `~/.worknetic-flow/config.toml`?

| Threat | Realistic? | Mitigation |
|---|---|---|
| Another process in the same UID (browser tab, npm postinstall, malicious dep) | **Yes** — daily on most Macs | `0600` reduces but doesn't eliminate (same UID can still read) |
| Another user account on the same Mac | Rare (most Macs are single-user) | `0600` fully mitigates |
| Time Machine / iCloud Drive backups | **Yes** — backups inherit file content | `0600` doesn't help; encryption-at-rest does (FileVault is standard) |
| Public exposure (shared screen, git push) | Unlikely if user follows `.gitignore` | Out of code's control |

### Why not Keychain?

Reviewer suggested Keychain. Trade-offs:

- **Pro:** ACL-scoped to the app's signed identity; other UID processes can't even open it without prompting.
- **Con:** Flow is *not* notarized (Finding 2 territory), so the Keychain ACL would be tied to an ad-hoc signature that changes on every rebuild → prompts on every update. Bad UX.
- **Con:** Requires `pyobjc-framework-Security` wrapping (`SecKeychainAdd...` / `SecItemAdd`). New surface.
- **Con:** Migration story (read TOML, write Keychain, blank TOML key) — easy to break.
- **Con:** Setup-friction for open-source users who self-build.

### My take

`chmod 0600` on every `save()` is **one line**, removes 60% of the smell, and doesn't introduce new dependencies or migration pain. Keychain is the "proper" answer but **out of scope** for a community-maintained side project. Document the trade-off in the audit + the in-app Privacy section.

### Severity

**HIGH (not CRITICAL).** Single-user macOS context makes "world-readable" less catastrophic than the same finding on a multi-tenant server. But Bearer tokens at `0644` is still a clear smell.

### Recommended fix for v0.4.0

1. `config.save()` does `os.chmod(path, 0o600)` after `tmp.replace(path)`.
2. Same chmod for `.env` if Flow ever writes to it (today it only reads).
3. Add a single line in the Settings tab tooltip: *"Stored locally with owner-only read permission."*

---

## Finding 2 — `curl | bash` installer without SHA256

**Reviewer claim:** `docs/install.sh` runs a DMG install without SHA256 verification; `xattr -cr` strips Gatekeeper.

### Verification

`docs/install.sh:73-95` — script fetches `api.github.com/repos/alpeppo/flow/releases/latest`, parses `browser_download_url`, downloads via `curl -fL`. No SHA256 step. `xattr -cr "$APP_DST"` at line 137 — yes, explicitly strips quarantine.

### Threat model

Who is the attacker?

| Threat | Plausibility | Would SHA256-in-notes help? |
|---|---|---|
| Network MITM on HTTPS | Near zero (CT logs + cert pinning) | No (HTTPS already covers this) |
| `alpeppo` GitHub account compromise | Real but rare | **No** — attacker also edits notes |
| GitHub CDN compromise | Extremely rare | Doesn't help |
| `alpeppo.github.io/install.sh` modification | Same as above | If install.sh is owned, SHA256 inside it can be faked |

**The honest answer:** SHA256 in human-readable release notes is security theatre. The attacker who controls the release also controls the notes. What *would* help:

- **GitHub Actions build provenance** (`actions/attest-build-provenance`) → user can `gh attestation verify` against a signed claim that's not in the same trust domain as the release notes.
- **Sigstore/Cosign** → similar story.

Both require CI, which is explicitly **out-of-scope** for v0.4.0.

### Comparing the alternative

If a user downloads the DMG manually from the browser instead, they get:

- The exact same trust chain (HTTPS to GitHub releases).
- Quarantine flag set, requiring either a Right-click → Open or `xattr -cr` later.
- No improvement in cryptographic verification.

So this isn't a regression — `curl | bash` is *equivalent* in trust, *strictly better* in UX.

### My take

Confirmed but reviewer overweights the severity. The right long-term fix is CI-attested builds, not text-file checksums. In the meantime:

- The script source is **public and inspectable** at `alpeppo.github.io/flow/install.sh` and `github.com/alpeppo/flow/blob/main/docs/install.sh`.
- README + landing page already tell users to read the script first.

### Severity

**MEDIUM (not HIGH).** Real concern, but bracketed: the only credible attacker also defeats any checksum we'd write into the same release.

### Recommended fix for v0.4.0

- README note: "Builds are not yet CI-attested. Inspect `install.sh` before piping to bash."
- Track CI attestation as a roadmap item (NOT v0.4.0).

---

## Finding 3 — Plaintext history + uncapped log + `keep_transcripts`

**Reviewer claim:** `~/.worknetic-flow/history.json` plaintext, `wnflow.log` no rotation, `keep_transcripts=true` writes dictations into logs.

### Verification

```bash
$ ls -la ~/.worknetic-flow/history.json
-rw-r--r-- ... 5140 bytes

$ wc -l ~/.worknetic-flow/logs/wnflow.log
   50915 wnflow.log     # 3.5 MB after a few days

$ grep -c "STT raw:" ~/.worknetic-flow/logs/wnflow.log
76                        # 76 cleartext dictations sitting in the log
```

`history_store.py` *does* have `MAX_ITEMS = 500` capping — that's good, reviewer missed it. But:

- File permissions: `0644` — same problem as Finding 1.
- `keep_transcripts = true` in current config → 76 cleartext dictations in `wnflow.log`. **Default in code (`config.py:121`) is `False`** but the user's TOML overrides to `True` — that's debug-on-by-default-in-user-shipping = bad smell.

### Is Flow under DSGVO?

Activated `compliance-check` skill. Walk-through:

- **DSGVO Art. 2 Abs. 2 lit. c (household exemption)** — applies to natural persons processing data for "exclusively personal or family activities." A user dictating their own notes on their own Mac falls squarely into this.
- **DSGVO Art. 4 Nr. 8 (processor)** — requires processing *on behalf of a controller.* Flow is software, not a service. The user (or their employer, in a business context) is the controller. Flow is a *tool*, like Word or vim.
- **If a user dictates regulated data (patient records, customer PII) via Flow at work** — the *user/employer* is the controller and needs their own DSGVO arrangement with Groq (if cleanup is used). Flow as software has no inherent DSGVO obligation here.
- **Conclusion:** Flow is not a "Verarbeiter" under Art. 4 Nr. 8. The reviewer's framing is too aggressive.

That said, **privacy-by-design** is still the right ethical default — and the reviewer's underlying *concerns* are valid even if the legal framing is wrong.

### My take

Three real problems and one wrong frame:

1. **`keep_transcripts=true` shouldn't be the default** (it IS already `False` in the dataclass — but Tim's specific config has it `True`). For shipping defaults this is fine; for Tim's machine I'll suggest flipping it manually.
2. **`history.json` and `wnflow.log` permissions** → `0600` (same fix as Finding 1).
3. **No clear-history UI** in the app despite the FAQ implying it exists. Add a button under Settings → History.

### Severity

**MEDIUM.** Not legal exposure for Flow itself, but a real privacy smell for users.

### Recommended fix for v0.4.0

1. `history_store.append()` does `os.chmod(HISTORY_PATH, 0o600)` after every write.
2. `_setup_logging()` does `os.chmod(log_path, 0o600)` after creating the FileHandler.
3. Add a `clear_history()` function in `history_store.py` + Bridge action + button in the Verlauf-Tab footer.
4. (Already-correct) Default `keep_transcripts=False` — verify no regression.

---

## Finding 4 — AppleScript injection in `notify.py`

**Reviewer claim:** `f'display notification "{message}"'` without escaping → command injection.

### Verification

`notify.py:24`:

```python
script = f'display notification "{message}" with title "{title}"'
```

Confirmed. No escaping. If `message` contains `"` followed by AppleScript control chars, the injection is real.

### Realistic exploit?

Who feeds `message`? Grepping callers (`app.py`):

```
notify("worknetic-flow", f"Hotkey-Listener failed: {exc}")
notify("worknetic-flow", f"Modell-Load fehlgeschlagen: {result.error}")
notify("worknetic-flow", f"Transkription fehlgeschlagen: {exc}")
notify("worknetic-flow", f"Settings-Speichern fehlgeschlagen: {exc}")
```

Three of these wrap a Python `Exception`. Where do exceptions come from?

- **`Hotkey-Listener failed`** — pyobjc internal. Attacker can't influence.
- **`Modell-Load fehlgeschlagen`** — MLX-Whisper / Hugging-Face. Attacker would need to compromise model server. Unlikely.
- **`Transkription fehlgeschlagen`** — pipeline. **This wraps Groq API failures.** Groq returns error messages that get stringified via `str(exc)`. If a Groq API response *or* its retry layer hands back attacker-controlled text (via prompt injection or API compromise), we have a path to AppleScript execution.

So: the chain `groq → exception → notify → osascript` is **plausible**, not theoretical.

### My take

Confirmed. Fix is trivial and free:

```python
script = "on run argv\\n  display notification (item 1 of argv) with title (item 2 of argv)\\nend run"
subprocess.run(["osascript", "-e", script, "--", message, title], ...)
```

argv-passed strings are not interpreted as AppleScript — they're plain `text` values. 100% injection-free, same UX.

Alternative: use `rumps.notification(title, subtitle="", message=...)` which is already imported. But rumps requires the app to be in an `NSApplication` context, and notify() is called from many places including pre-boot — sticking with osascript is fine.

### Severity

**MEDIUM.** Real path through LLM responses, but requires either prompt-injection-induced API errors or full API compromise. Not "drive-by exploit on every install" CRITICAL.

### Recommended fix for v0.4.0

Rewrite `notify()` to pass message/title as argv. Add a small test that confirms `"; rm -rf /` in the message doesn't execute (the test asserts the AppleScript was called with the right argv).

---

## Finding 5 — PyObjC retain-cycle in `_BridgeHandler`

**Reviewer claim:** `MainWindow → _bridge → _owner == MainWindow` cycle.

### Verification

`main_window.py:74-100`. Confirmed:

- `MainWindow.__init__` creates `self._bridge = _BridgeHandler.alloc().initWithOwner_(self)`.
- `_BridgeHandler._owner = self` (== MainWindow).
- The `lambda` in `addOperationWithBlock_` (line 96-98) captures `owner`, `action`, `body` — additional retain.

### Is it a practical problem?

MainWindow is single-instance. Lifecycle: created at app startup, destroyed at app quit. The OS frees memory at exit regardless of cycles.

The reviewer worries about cycles in principle. In practice, a leak only manifests if MainWindow is constructed multiple times (e.g., a future multi-window feature) without explicit cleanup.

### My take

Confirmed in principle, harmless in current architecture. The "right" fix in PyObjC is awkward:

- `objc.weakref` exists but doesn't compose cleanly with Python's GC.
- `__del__` on the `MainWindow` to break the ref — fragile, GC-order-dependent.

Cheapest pragmatic move:

1. Comment in `_BridgeHandler` explaining the cycle is intentional / lifecycle-bound.
2. Add a `MainWindow.dispose()` method that sets `self._bridge._owner = None` and `self._bridge = None` — called from the existing `app._quit()` path for hygiene.

### Severity

**LOW.** Not a leak today. Future-proofing only.

### Recommended fix for v0.4.0

Document + add `dispose()` callable from `_quit`. No PyObjC weakref gymnastics.

---

## Finding 6 — `max_duration_s = 0` (uncapped recording)

**Reviewer claim:** Default `0.0` means unbounded RAM growth.

### Verification

`config.py:39, 93` — code default is indeed `0.0`. RAM math: 16 kHz × 4 bytes × 1 ch × 3600 s = **~230 MB per hour**.

### Tim's history with this setting

Tim **explicitly removed** the 60s cap in v0.3.0 because he sometimes records long dictations (podcasts, calls). Setting it back is a UX regression of his choice.

### My take

- Tim's 64 GB Mac handles 230 MB/h fine.
- Other users with 8 GB Macs hit memory pressure after ~4 hours of recording. Edge case.
- Adding a soft warning ("recording > 30 min, ~115 MB so far") in the pill is nice but **out of scope**.

### Severity

**Rejected as a bug.** Documented decision, not a defect.

### Recommended fix for v0.4.0

None. Optionally add a tooltip in Settings: "0 = unbounded; consumes ~230 MB/h of RAM during recording."

---

## Finding 7 — Logging without rotation, library debug spam

**Reviewer claim:** `FileHandler` instead of `RotatingFileHandler`; debug level spams `loadHistory`.

### Verification

`app.py:216-227` — `logging.FileHandler(log_dir / "wnflow.log")`. No rotation, no max size, no backup count.

Current log: **3.5 MB / 50,915 lines** after a few days of moderate use.

Spam analysis:

```bash
$ grep -c "httpcore\|httpx\|hf-xet" wnflow.log
1147   # 2.3% of total, but these arrive in burst during model load
$ grep -c "loadHistory" wnflow.log
508    # 1.0%, regular polling
```

The dominant noise source is third-party library debug logging (httpx, httpcore, hf-xet during MLX model download), not Flow's own polling.

### My take

Two fixes:

1. **`RotatingFileHandler`** with `maxBytes=5MB, backupCount=3` → caps disk use at ~20 MB worst case.
2. **Library loggers to WARNING** — `logging.getLogger("httpx").setLevel(WARNING)` plus `httpcore`, `huggingface_hub`, `urllib3`. Standard hygiene.
3. Keep `loadHistory` at DEBUG (1% noise is acceptable) but consider raising to TRACE-equivalent.

### Severity

**MEDIUM.** Disk-use is a real concern long-term. Not a security issue but operationally annoying.

### Recommended fix for v0.4.0

`_setup_logging()` rewrite. Test: write 6 MB into the handler, assert exactly 1 rotation happened.

---

## Finding 8 — 30+ Umlaut violations

**Reviewer claim:** `fuer`, `ueber`, etc. throughout the codebase. Violates CLAUDE.md rule #2.

### Verification

```bash
$ grep -rEn "fuer|ueber|naechste|koennen|muessen|loeschen|oeffnen" src/wnflow/ docs/ ...
34 matches
```

**User-visible** (high impact):

- `src/wnflow/web/index.html:755` — Settings tooltip: *"… aufeinanderfolgen muessen. Kuerzer = schneller …"* → user reads this in the app.
- `docs/install.sh:63,165` — terminal output during installation.

**Comments / docstrings** (lower impact):

- ~30 occurrences across `app.py`, `pill.py`, `main_window.py`, `audio_ducker.py`, etc.

### My take

Confirmed and the reviewer is right to flag it. CLAUDE.md is explicit. Split priority:

1. **HIGH:** Fix user-visible strings now (3 locations).
2. **MEDIUM:** Fix code comments in v0.4.0 — it's a 1-minute `sed` run, no excuse to defer.

### Severity

**MEDIUM** for user-visible, **LOW** for comments. Both fixed together since the tool is the same.

### Recommended fix for v0.4.0

`sed -i ''` replacement script in `scripts/fix_umlauts.sh` so future violations can be re-fixed cheaply. Run once, commit.

---

## Finding 9 — Version drift

**Reviewer claim:** `pyproject.toml = 0.3.0`, latest release = `0.3.4`, log says `v0.2.0`.

### Verification

```bash
$ grep -E "0\.[23]\.[0-9]" pyproject.toml wnflow.spec
pyproject.toml:3: version = "0.3.0"
wnflow.spec:2:    # ... v0.3.0
wnflow.spec:94: version='0.3.0'
wnflow.spec:98: 'CFBundleShortVersionString': '0.3.0'
wnflow.spec:99: 'CFBundleVersion': '0.3.0'
src/wnflow/app.py:93: log.info("worknetic-flow v0.2.0 starting...")  # ← lol
```

Yes — drift everywhere. Releases on GitHub are at v0.3.4 already.

### My take

Real but cosmetic. The fix is **single source of truth**:

1. Bump `pyproject.toml` to a sensible current version (e.g., `0.4.0` for this branch).
2. `wnflow.spec` reads version from `pyproject.toml` via `tomllib` at build time.
3. `app.py` reads via `importlib.metadata.version("worknetic-flow")`.

That way version bumps happen in *one* place.

### Severity

**LOW.** No bug, but confusing for debugging and releases.

### Recommended fix for v0.4.0

`scripts/build_dmg.sh` already takes a VERSION arg — extend so it stays consistent with `pyproject.toml`. Bump to `0.4.0` after merge.

---

## Finding 10 — Hotkey thread-safety

**Reviewer claim:** `_last_tap_time` accessed without lock between global + local monitors.

### Verification

`hotkey.py:81, 149-159`. Both NSEvent monitors — per Apple docs, **both fire on the main thread** as part of the event-dispatch run loop. So no concurrency between them.

**But:** `threading.Timer` at line 86, callback `_fire_pending_ptt`. **That** fires on a worker thread. If the timer fires while `_handle_press` is running on main, both touch `self._pending_ptt_timer`, `self._pending_ptt_mode`, and indirectly `self._queue`.

### Realistic race?

Window is 350 ms (`double_tap_window`). Probability of overlap is non-zero. Worst-case scenario:

- Timer fires `_fire_pending_ptt` → puts `("start", mode)` on the queue.
- Simultaneously main-thread `_handle_press` cancels the timer (race lost) → puts another `("start", mode)`.
- Pipeline state machine receives two `start` events; the second one is logged and ignored: `Hotkey 'start' ignored, state=RECORDING`.

So: harmless in practice due to defensive state machine downstream. But the race is real.

### My take

NSEvent claim from reviewer is **wrong** — both monitors are main-thread. Timer race is a separate, smaller issue.

Fix: a single `threading.Lock` around the four lines that touch `_pending_ptt_timer` and `_pending_ptt_mode`. Cheap, defensive, removes a footgun for future contributors.

### Severity

**LOW.** Compensated by downstream state machine.

### Recommended fix for v0.4.0

Add `self._lock = threading.Lock()` in `__init__`, use it in `_handle_press`, `_handle_release`, `_fire_pending_ptt`. Document NSEvent threading model in the module docstring.

---

## Out of scope (deferred, not rejected)

These came up during verification but aren't getting fixed in v0.4.0:

- **CI / GitHub Actions** — would unlock signed-build attestations (Finding 2 long-term fix).
- **macOS Keychain** for Groq key — Finding 1 proper fix; deferred for OSS UX reasons.
- **Headless UI tests** for Pill / MainWindow — Finding 5's retain-cycle would be testable with `leaks` if there were CI.
- **Silero-VAD** for cancel-on-silence — unrelated to security; product feature.
- **Bash 5 / `set -euo pipefail`** for `install.sh` — defensive but breaks compatibility with the bash 3.2 that ships on macOS without Homebrew. Trade-off in favor of compat.

---

## Concrete v0.4.0 punch list (proposal)

In implementation order — Tim's GO required first:

1. **Finding 8** (15 min): umlauts in user-visible strings + comments.
2. **Finding 9** (20 min): version single-source-of-truth, bump `pyproject.toml` to `0.4.0`.
3. **Finding 4** (30 min, includes test): rewrite `notify.py` with argv-style osascript.
4. **Finding 1 + 3** (45 min, includes tests): `chmod 0600` for `config.toml`, `history.json`, `wnflow.log` on every write.
5. **Finding 7** (45 min): RotatingFileHandler + library log levels.
6. **Finding 3 cont.** (60 min): `history_store.clear_history()` + Bridge action + UI button.
7. **Finding 10** (20 min): hotkey lock + docstring.
8. **Finding 5** (15 min): doc comment + `dispose()` hook in `_quit`.
9. **Finding 6**: doc tooltip only, no code change.

Total estimate: **~4 hours of focused work**, all in a `feat/v0.4.0-security-hardening` worktree branch.

Each finding gets its own test (per TDD discipline). Existing 90 tests stay green. New tests bring suite to ~98.

---

## Questions back to Tim

1. **Finding 1 — Keychain?** I recommend `chmod 0600` and *not* Keychain for v0.4.0. Confirm or override?
2. **Finding 3 — `clear_history()` UI** — under the Verlauf tab as a small destructive button, or only in Settings? I'd put it in **Settings → History → Clear all entries** to keep destructive actions out of the data view.
3. **Finding 6 — confirm reject?** I want to leave `max_duration_s = 0.0` as the default. You agree, or want a soft cap (e.g., warn at 30 min)?
4. **Version bump target** — `0.4.0` for the security-hardening branch, then `0.4.0` becomes the next release tag. OK?
5. **Audit report location** — committed to the repo (this file) so future contributors see the trail. OK or sensitive to keep private?

Once you've reviewed and answered, I move to Phase 1 (writing-plans) and then implementation in a worktree.
