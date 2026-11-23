# macOS App Packages with Bazel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bazel builds `PyMOL-Open-Source.app` and its DMG for Apple Silicon and Intel from `//distribution/bundle`, the app runs on macOS 12 as its own process (Dock icon, app menu), and `build_app.yaml`'s two `build-macos` jobs ship the Bazel-built DMGs with every check they run today.

**Architecture:** The macOS launcher loads the bundled `libpython3.13.dylib` itself and runs PyMOL in its own process through CPython's `PyConfig` API, so the process stays the `.app`'s `CFBundleExecutable`; on Linux and Windows the launcher keeps starting the runtime's interpreter. A hermetic rule wraps the app folder into `Contents/` (launcher in `MacOS/`, app folder in `Resources/`, `Info.plist` stamped with the version, `icon.icns`), thinning universal binaries to the target's architecture in Python. Local actions sign it ad hoc with `codesign` and write the DMG with create-dmg fetched by checksum.

**Tech Stack:** Bazel 9, rules_cc, rules_python 2.3.2 (Python 3.13 headers, `pip_whl_osx_version`), Python 3.13 standard library (`plistlib`, a Mach-O reader), Apple's `codesign` and `hdiutil`, create-dmg 1.3.0.

**Spec:** `.opp/plans/features/app-bazel-build.md`, step 3.

## Parent

`features/app-bazel-build.md`, step 3: macOS packages.

## Global Constraints

- macOS minimum 12.0 (`LSMinimumSystemVersion` in `distribution/os_specific/macos/Info.plist`); no binary in the app may need more.
- One DMG per architecture: `PyMOL-Open-Source_v<version>_macOS_AppleSilicon.dmg` and `..._macOS_Intel.dmg`, `<version>` from `distribution/pyproject.toml`.
- The app is `PyMOL-Open-Source.app` without a version in its name; `Info.plist` keeps every key it has, with `CFBundleShortVersionString` and `CFBundleVersion` set to the version; bundle identifier `io.github.kullik01.pymol-open-source`; file types .pdb, .cif, .pse as declared there.
- Signing stays ad hoc (`codesign --sign -`); no notarization.
- create-dmg 1.3.0 from `https://github.com/create-dmg/create-dmg/archive/refs/tags/v1.3.0.tar.gz`, SHA-256 `c50d2bc97c3d6292642bac55f530d247eaf4bf65ee605f26b4caf339383e381c` (today's CI pin), with today's window layout and `dmg/dmg_background.svg`.
- Python and C follow the opp family style; the app's Python also passes its ruff settings.

## Review Focus

- The process name and Dock icon: a launcher that `exec`s `runtime/bin/python3` would make macOS show "Python" with a generic icon, because the running executable is no longer the bundle's; Task 1 embeds the runtime instead, and Task 5's CI step reads the running app's bundle path.
- A dependency wheel built for macOS 13 or 14 (numpy ships `macosx_14_0` wheels for Apple Silicon): Task 2 sets the wheel floor and Task 3's `macos_min_version_test` reads every Mach-O file's minimum.
- PySide6's universal2 binaries double the app's size and must match the DMG's architecture: Task 3 thins them and `macos_arch_test` checks every Mach-O file has exactly the target's architecture.
- Signing over Bazel's read-only outputs: Task 4 signs a writable copy, and `codesign --verify --deep` runs on the DMG's app in CI.
- The DMG's architecture label must come from the built app, as `build_dmg.sh` does with `lipo`, not from the runner's.

## Scope

```
.bazelrc
MODULE.bazel
.github/workflows/build_app.yaml
distribution/BUILD.bazel
distribution/launcher/**
distribution/bundle/**
distribution/macos/**
distribution/tests/BUILD.bazel
distribution/README.md
AGENTS.md
```

## Done

Both `build-macos` jobs in `build_app.yaml` build the DMG with Bazel and pass every check they run today, on a pull request into `bazel-app-packaging`.

## Non-goals

- Notarization, a Developer ID signature, a universal (both-architecture) app.
- Linux, the website and the quick checks (steps 4-6); the automator and cx_Freeze stay for Linux until step 7.
- Embedding the runtime in the Linux or Windows launcher.
- Building or testing on a Mac locally: the development machine runs Windows, so every macOS result comes from CI.

## Interfaces

- `distribution/launcher/launcher.c`, macOS: the app root is `<exe dir>/../Resources` when `<exe dir>/../Resources/runtime` exists (inside the `.app`), else `<exe dir>` (the plain app folder); it sets `PYMOL_APP_ROOT`, `dlopen`s `<root>/runtime/lib/libpython3.13.dylib` and runs, with an isolated `PyConfig` (`home` = `<root>/runtime`, `run_module` = `pymol.startup_wrapper`, `parse_argv` = 0, argv = its own), `Py_InitializeFromConfig` and `Py_RunMain`, returning its exit code; without the library it prints `PyMOL-Open-Source: runtime not found: <path>` and exits 127.
- `distribution/macos/macho.py`: `architectures(path) -> list[str]`, `minimum_macos(path) -> tuple[int, int] | None`, `thin(path, arch) -> bytes` (the slice of a universal file, unchanged for a thin one), `is_macho(path) -> bool`.
- `//distribution/macos:app` (hermetic): tree `PyMOL-Open-Source.app`.
- `//distribution/macos:signed_app` (local, `codesign`): the ad-hoc signed copy.
- `//distribution/macos:dmg` (local, `hdiutil` through create-dmg): the DMG under its release name.
- `@create_dmg` (`http_archive`, the pinned tarball), `@app_project_metadata` (from step 2) for the version.

## Tasks

### Task 1: A macOS launcher that runs PyMOL in its own process

**Files:** Modify `distribution/launcher/launcher.c`, `distribution/launcher/BUILD.bazel`, `distribution/launcher/launcher_test.py`.

- [ ] **Step 1: Write the failing tests** (macOS only, `skipUnless(sys.platform == "darwin")`): `test_app_layout_root` — a launcher in `X.app/Contents/MacOS/` with a fake `Contents/Resources/runtime/lib/libpython3.13.dylib` that does not load reports `runtime not found` naming the `Resources` path and exits 127; `test_flat_layout_root` — the same beside `runtime/`. The existing exec tests run on Linux and Windows only; on macOS the smoke test (Task 5) covers a real run.
- [ ] **Step 2: Run** `bazel test //distribution/launcher:launcher_test` on the macOS CI job — Expected: FAIL.
- [ ] **Step 3: Implement** the macOS branch (`#ifdef __APPLE__`) with `dlopen`/`dlsym` of `PyConfig_InitIsolatedConfig`, `PyConfig_SetString`, `PyConfig_SetBytesArgv`, `Py_InitializeFromConfig`, `PyStatus_Exception`, `Py_ExitStatusException`, `PyConfig_Clear`, `Py_RunMain`, `Py_DecodeLocale`, with the 3.13 headers of `@rules_python//python/cc:current_py_cc_headers` (header only, no link: a missing runtime stays an error message, not a dyld abort). The launcher is built in the app's 3.13 configuration.
- [ ] **Step 4: Run** — Expected: PASS on macOS; Windows and Linux unchanged.
- [ ] **Step 5: Commit** — "build: run PyMOL in the macOS launcher's own process".

### Task 2: macOS wheels for macOS 12

**Files:** Modify `.bazelrc`.

- [ ] **Step 1:** `build:macos --@rules_python//python/config_settings:pip_whl_osx_version=12.0`, with a comment naming `LSMinimumSystemVersion`. *(Dropped after review: in rules_python 2.3.2 the flag feeds environment markers only, and wheel selection already prefers the lowest macOS; `app_checks_test` holds the floor.)*
- [ ] **Step 2: Verify** with Task 3's `macos_min_version_test` (the failing case is numpy's `macosx_14_0_arm64` wheel without the flag).
- [ ] **Step 3: Commit** with Task 3.

### Task 3: The `.app`, thinned, with its checks

**Files:** Create `distribution/macos/macho.py`, `distribution/macos/make_app.py`, `distribution/macos/app.bzl`, `distribution/macos/BUILD.bazel`, `distribution/macos/tests/macho_test.py`, `distribution/macos/tests/make_app_test.py`, `distribution/macos/tests/app_checks_test.py`; modify `distribution/BUILD.bazel` (exports).

- [ ] **Step 1: Write the failing tests.** `macho_test.py` (runs everywhere, on byte fixtures built in the test): `test_thin_extracts_slice`, `test_thin_keeps_thin_file`, `test_minimum_from_build_version`, `test_minimum_from_version_min`, `test_architectures_of_fat_file`. `make_app_test.py`: `test_layout` (`Contents/MacOS/PyMOL-Open-Source`, `Contents/Resources/runtime/...`, `Contents/Resources/icon.icns`, `Contents/Info.plist`), `test_plist_version_stamped_and_keys_kept`, `test_universal_files_thinned`. `app_checks_test.py` (macOS, data: `:app`): `test_every_macho_targets_one_architecture` (the target's), `test_minimum_macos_at_most_12`.
- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement** `macho.py`, then `make_app.py` (`main(argv) -> int`: `--app <folder>`, `--launcher`, `--info-plist`, `--icon`, `--version`, `--arch arm64|x86_64`, `--out <X.app>`) and the `macos_app` rule (3.13 transition, `--arch` from a `select` on the CPU).
- [ ] **Step 4: Run** `bazel test //distribution/macos/...` — Expected: PASS (fixture tests locally, app checks on the macOS jobs).
- [ ] **Step 5: Commit** — "build: wrap the app into PyMOL-Open-Source.app for macOS 12".

### Task 4: Signed app and DMG targets

**Files:** Modify `MODULE.bazel` (`@create_dmg`); create `distribution/macos/sign_and_dmg.bzl`, `distribution/macos/sign_app.py`, `distribution/macos/make_dmg.py`.

- [ ] **Step 1:** `sign_app.py` copies the app to a writable folder, runs `codesign --force --deep --sign -` and `codesign --verify --deep`; `make_dmg.py` names the DMG from the version and the architecture `macho.architectures` reads from `pymol/_cmd`, then runs create-dmg with today's layout (three attempts, as `build_dmg.sh` for "Resource busy"). Both actions carry `local` and `no-cache` and are `target_compatible_with` macOS; `:dmg` is `manual`.
- [ ] **Step 2: Verify** on the macOS jobs: `bazel build //distribution/macos:dmg` writes the release-named DMG.
- [ ] **Step 3: Commit** — "build: sign the macOS app and write its DMG with Bazel".

### Task 5: The macOS CI jobs on Bazel

**Files:** Modify `.github/workflows/build_app.yaml`, `distribution/tests/BUILD.bazel`, `distribution/README.md`, `AGENTS.md`.

- [ ] **Step 1:** `bundle_smoke_test` also runs the signed `.app`'s `Contents/MacOS/PyMOL-Open-Source` on macOS (a second test target, `app_smoke_test`).
- [ ] **Step 2:** `build-macos` drops Setup Python, uv, the virtual environment, the create-dmg download and `codesign` steps; adds `setup-bazel`; runs `bazel build //distribution/macos:dmg` and `bazel test //distribution/...`; copies the DMG to `os_specific/dist`; the GUI smoke test and "Verify DMG" keep every check, with the `_cmd` path at `Contents/Resources/runtime/lib/python3.13/site-packages/pymol/`, and a new check that the running app's process is `Contents/MacOS/PyMOL-Open-Source`.
- [ ] **Step 3:** README and AGENTS.md give the macOS Bazel commands.
- [ ] **Step 4: Verify** with actionlint and on the pull request: both `build-macos` jobs and `release` green.
- [ ] **Step 5: Commit** — "ci: build the macOS DMGs with Bazel".

## Acceptance criteria

- Both macOS jobs build their DMG with Bazel, verify it (`hdiutil verify`, mount, `codesign --verify --deep`, `Info.plist` lint, identifier, file types, `_cmd` architecture) and run the app's headless and GUI smoke tests from it, green.
- Every Mach-O file in each app targets only its DMG's architecture and needs at most macOS 12.0.
- The DMG names carry the version and the architecture of the built app.
- The running app's process is the bundle's own executable, so macOS shows it as PyMOL-Open-Source with its icon (the developer checks the Dock and app menu once by hand; noted in the PR).

## Verification

- Locally (Windows): `bazel test //distribution/macos:macho_test //distribution/macos:make_app_test` and `bazel test //...`; the macOS-only targets are skipped.
- On the pull request into `bazel-app-packaging`: `macOS (macos-15)`, `macOS (macos-15-intel)`, both `build-macos` jobs and `release` green.
- `python3 .opp/style/check.py --base origin/bazel-app-packaging` on the touched paths: no findings; ruff with the app's settings: clean.
