# PyMOL-Open-Source quits without crashing (port of upstream v3.2.0.3+2)

**Goal:** Port the only fix in kullik01/pymol-open-source-setup's latest release, v3.2.0.3+2 (PR #52, issue #51): the app no longer segfaults on quit on Linux and macOS. Also bump the app version to 3.2.0.3+2.

**Architecture:** PyMOL quits through `_cmd.quit` → `PExit` (`layer1/P.cpp`) → C `exit()` inside the Qt event loop. `exit()` runs the C++ static destructors, and shiboken's `BindingManager` destructor then crashes on wrappers of Qt objects Qt has already freed. `execapp()` in `distribution/edited/pmg_qt/pymol_qt_gui.py` replaces `pymol._cmd.quit` for the main instance (Linux, macOS) with a function that flushes Python's and the C library's output and calls `os._exit(code)`. When `app.exec()` returns anyway (`QApplication.exit(n)`), it waits at most 5 s for the API lock and quits the same way. The GUI smoke test stops retrying when the test passed but PyMOL crashed on quit (exit 139 or 134).

**Spec:** https://github.com/kullik01/pymol-open-source-setup/pull/52 (release v3.2.0.3+2, issue #51)

## Global Constraints

- AGENTS.md: "`distribution/edited/` holds upstream PyMOL files with marked edits (`BEGIN EDITED CODE SEGMENT`)". The new code goes inside such segments. The `modules/` original does not change, so `distribution/edited/upstream.sha256` stays as it is.
- AGENTS.md: "The app's version lives only in `distribution/pyproject.toml`".
- Python follows `opp-workflow:python-style`; `python3 .opp/style/check.py` judges changed lines. Code copied from upstream gets adapted where the checker asks, for example docstrings with Args/Returns.

## Review Focus

- Embedded instances (`pymol2`, `no_quit`) keep PyMOL's own quit: the replacement hands every `_COb` other than `pymol.cmd._COb` to the original.
- Exit codes pass through: `cmd.quit(n)` ends with `n`, and so does `QApplication.exit(n)`.
- Windows is unchanged, because DLL destructors still run at `ExitProcess` after `os._exit`.
- Headless runs (`-c`) never reach `execapp()`, so the Bazel `app_smoke_test` is unaffected.

## Scope

distribution/edited/pmg_qt/pymol_qt_gui.py
distribution/tests/run_smoke_test.sh
distribution/pyproject.toml
.opp/plans/fix/quit-crash.md

## Done

On Linux and macOS, quitting the built app with `cmd.quit`, by closing the window or with menu Quit exits 0 without a core dump; the smoke tests and `bazel test //distribution/...` pass; the version is 3.2.0.3+2.

## Non-goals

- Fixing the crash in shiboken or in upstream PyMOL's `PExit`.
- Changing quit on Windows.
- Freeing PyMOL's memory before the process ends.
- Porting anything from upstream v3.2.0.3+1 (this repository's `distribution/` already has it, as of PRs #12 and #13).

## Steps

1. Commit this plan.
2. `distribution/edited/pmg_qt/pymol_qt_gui.py`: in `execapp()`, after the high-DPI attribute (line 1248), call `quit_without_exit_handlers()`. Replace `app.exec()` (line 1377) with the bounded lock wait and `end_process(exit_code)`. Add the two functions `quit_without_exit_handlers()` and `end_process(code)` before `offer_to_remove_older_apps`. All of it goes in `BEGIN/END EDITED CODE SEGMENT` blocks and follows upstream's diff in PR #52, adapted to the style checker. Commit.
3. `distribution/tests/run_smoke_test.sh`: after the success check, fail at once without a retry when the log holds `SMOKE TEST OK` and the exit code is 139 or 134. Commit.
4. `distribution/pyproject.toml`: version `3.2.0.3+2`. Commit.

## Edge cases

- `cmd.quit` from a non-GUI thread (startup scripts, the smoke test): the queued `cmd._quit` reaches the replaced `_cmd.quit`.
- `sys.stdout` or `sys.stderr` is `None`, closed or broken: skipped, and `os._exit` still runs.
- Native `printf` output without `fflush`: `ctypes.CDLL(None).fflush(None)` flushes it, as `exit()` did.
- `QApplication.exit(n)` while another thread holds the API lock: the app exits with `n` after about 5 s instead of hanging.
- A `log_open` log is complete after quit, because `internal._quit` closes it before `_cmd.quit` runs.

## Acceptance criteria

- On Linux (Xvfb) and macOS, upstream issue #51's reproduction exits 0 with no core dump on all three quit paths (`cmd.quit`, `window.close()`, `confirm_quit`).
- `cmd.quit(3)` exits 3; `cmd.quit(5)` from the script thread exits 5; `QApplication.exit(4)` exits 4.
- `distribution/tests/run_smoke_test.sh --gui`, run with a stub that prints SMOKE TEST OK, fails at once on exit 139, passes on 0, and fails after two attempts on 1.
- `bazel test //distribution/...` and `bazel run //distribution:checks` pass; `python3 .opp/style/check.py --committed` reports nothing.
- `distribution/pyproject.toml` has version `3.2.0.3+2`.

## Verification

- Before the fix, on this Mac: build `//distribution/macos:dmg`, run the issue #51 reproduction against the app 5 times per quit path, and note the crashes (exit 139 or a crash report).
- After the fix: run the same reproduction 10 times per path, all exit 0. Run the exit-code script for 3, 5 and 4, and the `log_open` plus unflushed-stdout script.
- `bazel test //distribution/...`, `bazel run //distribution:checks`, `python3 .opp/style/check.py --committed`.
- The stub check of `run_smoke_test.sh --gui` for exit codes 139, 0 and 1.
- Linux: CI's `build_app.yaml` GUI smoke tests on the pull request, plus a manual quit test with a draft `setup-v3.2.0.3+2` release.
