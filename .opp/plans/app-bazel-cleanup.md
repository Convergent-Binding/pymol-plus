# Cleanup after the Bazel App Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nothing of the cx_Freeze build is left:
- no automator, no `requirements.txt`, no `.python-version`;
- no uv settings in the app's jobs, no fpm or create-dmg scripts.

The documentation, the third-party notices and Dependabot describe the app Bazel builds, so `bazel-app-packaging` is ready for its pull request into `production`.

**Architecture:** This step removes files and words only; no build target changes:
- The Bazel targets of steps 1-4 and 6 already build, test and package every app artifact.
- `freeze-core` stays in `build_requirements.in`, because `//distribution/windows:msvc_runtime` unpacks the Microsoft C++ runtime with it.
- The website jobs keep their own Python and MkDocs (step 5 is skipped); only their Python version, read from `.python-version` today, is written into the job.

**Tech Stack:** git, Bazel 9 (for verification only), GitHub Actions.

**Spec:** `.opp/plans/features/app-bazel-build.md`, step 7.

## Parent

`features/app-bazel-build.md`, step 7: Cleanup.

## Global Constraints

- **Nothing a Bazel target, a test or a workflow uses is removed.** Every deleted file is first shown to be referenced only by other deleted files, or by text this step rewrites.
- **The app's contents and release files stay byte-for-byte what step 6 built,** except the updated `licenses/THIRD-PARTY-NOTICES.txt` and the new `licenses/GCC-exception-3.1.txt`.
- **The website build keeps working unchanged,** on Python 3.13 as now.
- **The notices name every component of the Bazel app that has no license file of its own,** under its actual license.

## Review Focus

- **A deleted file still in use.** Candidates: a script a workflow calls, an asset a BUILD file exports, or the website job's `.python-version`. Task 1 lists each file's references before deleting it, and CI runs every app job.
- **Wrong license notices.** The Bazel app gets OpenSSL, SQLite, Tcl/Tk, libffi, bzip2 and xz from python-build-standalone on every platform, not from cx_Freeze. libgomp (Linux) is GCC's runtime library, under the GPL with the GCC Runtime Library Exception, whose text the app must carry. The Microsoft C++ runtime's license sits in `licenses/vc_redist`. Task 2 checks each entry against the built bundle.
- **Dependabot after the cleanup.** Its pip entry for `/distribution` reads `requirements.in`, `build_requirements.in` and `checks_requirements.in` with their uv locks. The `pymol-open-source-whl` exclusion refers to a package the app no longer pins.

## Scope

```
distribution/automator.sh
distribution/win_automator.bat
distribution/automations/**
distribution/os_specific/setup_build_exe.py
distribution/os_specific/linux/build_packages.sh
distribution/os_specific/macos/build_dmg.sh
distribution/os_specific/macos/dmg/bg.png
distribution/os_specific/macos/dmg/bg.svg
distribution/tests/check_macos_min_version.sh
distribution/requirements.txt
distribution/.python-version
distribution/build_requirements.in
distribution/licenses/**
distribution/edited/pymol/startup_wrapper.py
distribution/tests/smoke_test.py
distribution/README.md
AGENTS.md
.github/workflows/build_app.yaml
.github/dependabot.yml
```

Comments elsewhere that still say how the cx_Freeze app did something stay. They explain why the Bazel build does the same.

## Done

On a pull request into `bazel-app-packaging`, every check is green:
- the app's Windows, macOS and Linux jobs, the eight-distribution package tests and `release`;
- `checks`, `website` and the Bazel check on all four platforms.

None of the cx_Freeze path's files is left. `git grep` finds no instructions to use automator, uv, `requirements.txt` or `.python-version` for the app.

## Non-goals

- The website's build (step 5, skipped) beyond its Python version line.
- Renaming `os_specific/` or moving its remaining assets (icons, splash screens, desktop and AppStream files, Inno Setup script, DMG background).
- Changing URLs that name `pymol-open-source-setup`.
- Committing `MODULE.bazel.lock`, whose digests change with Windows line endings.

## Interfaces

No code interfaces change. Gone are `./automator.sh`, `win_automator.bat`, `os_specific/linux/build_packages.sh`, `os_specific/macos/build_dmg.sh` and `tests/check_macos_min_version.sh`. The Bazel commands in AGENTS.md replace them.

## Tasks

### Task 1: Remove the cx_Freeze build

- [ ] Confirm, for each file below, that only other deleted files, or the docs Task 3 rewrites, refer to it (`git grep -n -F <name>`). Then delete:
  - `automator.sh`, `win_automator.bat` and `automations/`;
  - `os_specific/setup_build_exe.py`, `os_specific/linux/build_packages.sh` and `os_specific/macos/build_dmg.sh`;
  - `tests/check_macos_min_version.sh`, which only `build_dmg.sh` ran; `//distribution/macos:app_checks_test` checks the minimum macOS;
  - `os_specific/macos/dmg/bg.png` and `bg.svg`, if nothing but the cx_Freeze path used them (the DMG uses `dmg_background.svg`);
  - `requirements.txt` and `.python-version`.
- [ ] `build_app.yaml`:
  - drop the workflow-level `UV_PYTHON_PREFERENCE` and its comment;
  - in the `website` job, `python-version: '3.13'` replaces `python-version-file: 'distribution/.python-version'`.
- [ ] `build_requirements.in`: the freeze-core comment no longer points at `requirements.txt`.
- [ ] `dependabot.yml`: drop the `pymol-open-source-whl` exclusion and its comment, as the app bundles the wheel built in this repository. The ignore rules for PySide6, shiboken6 and biopython stay.
- [ ] `bazel test //distribution/...` and `bazel run //distribution:checks` pass (Windows).

### Task 2: Third-party notices for the Bazel app

- [ ] Build `//distribution/bundle` and list what the runtime brings: OpenSSL, SQLite, Tcl/Tk, libffi, bzip2, xz and others in `runtime/`. Compare with python-build-standalone's license file in `licenses/Python/`.
- [ ] `licenses/THIRD-PARTY-NOTICES.txt`:
  - drop the cx_Freeze entry and "bundled by cx_Freeze/freeze-core";
  - name python-build-standalone as the source of OpenSSL and the runtime's native libraries on every platform;
  - point the Microsoft C++ runtime at `licenses/vc_redist`;
  - add libgomp (Linux), under GPL-3.0 with the GCC Runtime Library Exception, and libxcb-cursor (Linux, MIT);
  - keep Qt, Mesa llvmpipe and numpy's libraries.
- [ ] Add `licenses/GCC-exception-3.1.txt`, the exception's verbatim text from https://www.gnu.org/licenses/gcc-exception-3.1.txt. `license_texts` picks it up by its glob.
- [ ] `bazel test //distribution/...` passes. The bundle's `licenses/` holds both files.

### Task 3: Documentation and wording

- [ ] `distribution/README.md`:
  - the contents table, without `automations/`, and with `os_specific/` as the per-platform assets and the `linux`/`macos`/`windows`/`bundle`/`launcher`/`checks` Bazel packages listed;
  - the prerequisites, without uv;
  - no "no longer used" paragraph;
  - the Dependabot note on PyMOL updates: `//distribution/edited:edited_base_test` fails until `edited/` is ported, replacing `EDITED_FOR_PYMOL_WHL_VERSION`;
  - "the bundled app" for "the frozen app".
- [ ] AGENTS.md: the `edited/` rule names `edited_base_test` and `edited/upstream.sha256` instead of `EDITED_FOR_PYMOL_WHL_VERSION`.
- [ ] `tests/smoke_test.py` and `edited/pymol/startup_wrapper.py`: docstrings say "bundled app" and "the runtime's OpenSSL" where they describe today's app as frozen or cx_Freeze's. Behaviour stays unchanged.
- [ ] `git grep -n -i "automator\|cx_freeze\|frozen\|uvx\|python-version"` finds only history notes, Bazel's `--python-version` arguments and the wheel's own jobs.

## Acceptance criteria

- The cx_Freeze path's files are deleted, and no workflow, BUILD file or test refers to them.
- The app jobs in `build_app.yaml` set no uv settings and run only Bazel and the tests' own scripts. The website job builds on Python 3.13.
- `licenses/THIRD-PARTY-NOTICES.txt` describes the Bazel app's components; `licenses/GCC-exception-3.1.txt` is shipped.
- README, `distribution/README.md` and AGENTS.md describe only Bazel commands for the app.
- CI is green on the pull request, release jobs and package tests included.

## Verification

- `bazel test //distribution/...` and `bazel run //distribution:checks` (Windows, locally).
- `python3 .opp/style/check.py --base origin/bazel-app-packaging`.
- `git grep` as in Task 3.
- CI on the pull request: `build_app.yaml` (all app jobs, `website`, `checks`, `release`) and `bazel.yaml` on four platforms.
