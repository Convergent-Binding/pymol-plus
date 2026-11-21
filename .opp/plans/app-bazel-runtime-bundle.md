# App Runtime Bundle with Bazel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `bazel build //distribution/bundle:bundle` assembles a relocatable PyMOL-Open-Source app for the host platform from a python-build-standalone CPython 3.13, the locked app dependencies and the in-repo PyMOL, and `bazel test //distribution/...` runs it headless from a copy in a fresh directory on Windows x64, macOS arm64/x86_64 and Linux x86_64.

**Architecture:** A Starlark rule `app_bundle` transitions its inputs to Python 3.13 and runs one first-party tool, `assemble_bundle.py`, which writes a directory: the runtime from `@python_3_13//:files`, a `site-packages` holding the merged `@app_pip` wheels and the unpacked `//tools/bazel/wheel:wheel`, the app's overlays, a native launcher, `licenses/` and `manifest.json`. Packaging (installer, DMG, .deb/.rpm) is later steps; the cx_Freeze path keeps building releases until step 7.

**Tech Stack:** Bazel 9, rules_python 2.3.2 (`pip.parse`, uv `lock`, hermetic 3.13 runtime), rules_cc, Python 3.13 standard library only for the tools, unittest.

**Spec:** `.opp/plans/features/app-bazel-build.md` (step 1 and its Decisions); the bundle design of https://github.com/kullik01/pymol-open-source-setup/pull/8.

## Parent

`features/app-bazel-build.md`, step 1: Runtime bundle.

## Global Constraints

- Python 3.13; PySide6-Essentials and shiboken6 6.9.3; biopython 1.86; numpy 2.5.4, Pmw 2.1.1, msgpack 1.2.4, rules 3.5, simplejson 4.2.0: the versions of today's `distribution/requirements.txt`, unchanged.
- The bundle needs no host Python, virtual environment, uv, network or `PYTHONPATH`; it runs after being moved to another directory.
- The app's version comes from `distribution/pyproject.toml` only.
- Tools run on Bazel's hermetic Python through parameter files, never a host `python3` or a shell.
- `distribution/edited/` files are copied unchanged into the bundle; editing them is not part of this step.
- Python in this repository uses 2-space indents (ruff `indent-width = 2`).

## Review Focus

- The bundle still points into Bazel's output tree (a symlink, an absolute path in a launcher or `.pth` file): `smoke_test` runs a *copy* in a new temporary directory with `PATH` reduced to the system folders (Task 6).
- HTTPS finds no CA certificates in the standalone runtime on Linux/macOS: `smoke_test.py`'s `check_certificates` runs in the Bazel test (Task 6).
- PySide6's compiled modules cannot find shiboken6 or Qt because the wheels sit in separate trees: Task 2's test imports `PySide6.QtCore` from the merged tree.
- An overlay silently replaces a PyMOL file that changed upstream: Task 3's `edited_base_test` fails when `modules/` moves on.
- Arguments with spaces or non-ASCII characters (`C:\Users\Jörg\My Files\x.pdb`) reach PyMOL unchanged: Task 4's launcher test passes such an argument through.

## Scope

```
MODULE.bazel
MODULE.bazel.lock
.github/workflows/bazel.yaml
distribution/BUILD.bazel
distribution/requirements.in
distribution/requirements_lock.txt
distribution/bundle/**
distribution/launcher/**
distribution/edited/BUILD.bazel
distribution/edited/upstream.sha256
distribution/tests/BUILD.bazel
distribution/tests/smoke_test.py
tools/bazel/wheel_merge.bzl
tools/bazel/merge_wheel_files.py
tools/bazel/BUILD.bazel
tools/bazel/tests/BUILD.bazel
tools/bazel/tests/merge_wheel_files_test.py
```

## Done

`bazel test //distribution/...` passes in the Bazel workflow on all four platforms, running the relocated bundle's headless smoke test.

## Non-goals

- Installers, archives, the `.app` layout, the DMG, the Linux packages and every `build_app.yaml` change (steps 2-4).
- Bundling the MSVC C++/OpenMP runtimes, `libgomp` or `libxcb-cursor` (steps 2 and 4); on the CI runners they are installed, so the headless smoke test passes without them.
- The launcher's icon and Windows version resource (step 2).
- Removing cx_Freeze, the automator, `requirements.txt` or uv (step 7).
- The GUI smoke test (`--gui`), which needs a display; steps 2-4 run it in their CI jobs.

## Interfaces

- `@app_pip`: rules_python hub for Python 3.13 locked from `distribution/requirements_lock.txt`; per package `@app_pip//<name>:extracted_whl_files`.
- `merge_wheel_files(name, wheel_files)` in `//tools/bazel:wheel_merge.bzl`: one tree artifact `<name>/site-packages` holding every given extraction; a path present in two inputs fails the build.
- `//distribution/launcher:launcher`: `cc_binary` named `PyMOL-Open-Source`.
- `app_bundle(name, runtime, site_packages, wheel, overlays, launcher, licenses, extra_licenses, project)` in `//distribution/bundle:app_bundle.bzl`: one tree artifact `<name>/PyMOL-Open-Source`.
- Bundle layout:

  ```
  PyMOL-Open-Source/
    PyMOL-Open-Source[.exe]   launcher
    runtime/                  CPython 3.13; site-packages at runtime/Lib/site-packages (Windows)
                              or runtime/lib/python3.13/site-packages (Linux, macOS)
    licenses/                 README.txt index and one folder per distribution
    manifest.json
  ```

- Launcher contract: it sets `PYMOL_APP_ROOT` to its own directory and runs `<root>/runtime/pythonw.exe` (Windows) or `<root>/runtime/bin/python3` with `-I -m pymol.startup_wrapper` followed by its own arguments unchanged, and exits with the child's exit code; with no runtime it prints `PyMOL-Open-Source: runtime not found: <path>` to stderr and exits 127.

## Tasks

### Task 1: The app's dependency lock and hub

**Files:**
- Create: `distribution/requirements.in`, `distribution/requirements_lock.txt` (generated), `distribution/BUILD.bazel`
- Modify: `MODULE.bazel`, `MODULE.bazel.lock`

**Interfaces:**
- Produces: `@app_pip` (Python 3.13), `//distribution:requirements.update`, `@python_3_13` in scope.

- [ ] **Step 1: Write `distribution/requirements.in`** with exactly the nine "Bundled into the application" pins of `distribution/requirements.txt` except `pymol-open-source-whl` (biopython, msgpack, numpy, Pmw, PySide6-Essentials, rules, shiboken6, simplejson), keeping its comments.
- [ ] **Step 2: Add the lock target** to `distribution/BUILD.bazel`: `lock(name = "requirements", srcs = ["requirements.in"], out = "requirements_lock.txt", python_version = "3.13", args = ["--universal", "--python-version", "3.13"])` and `exports_files(["requirements_lock.txt"])`, as `//tools/bazel:requirements` does.
- [ ] **Step 3: Generate the lock**

Run: `bazel run //distribution:requirements.update`
Expected: `OK: updated ...distribution/requirements_lock.txt`; the file pins the eight packages at the versions above plus their dependencies, with hashes.

- [ ] **Step 4: Register the hub and the runtime** in `MODULE.bazel`: `pip.parse(hub_name = "app_pip", python_version = "3.13", requirements_lock = "//distribution:requirements_lock.txt")`, `use_repo(pip, "app_pip")`, and add `"python_3_13"` to the `use_repo(python, ...)` call.
- [ ] **Step 5: Verify**

Run: `bazel build @app_pip//pyside6_essentials:extracted_whl_files @app_pip//shiboken6:extracted_whl_files @python_3_13//:files`
Expected: build succeeds.

- [ ] **Step 6: Commit** `distribution/requirements.in distribution/requirements_lock.txt distribution/BUILD.bazel MODULE.bazel MODULE.bazel.lock` — "build: lock the app's dependencies for Bazel". Leave out a `MODULE.bazel.lock` hunk that only changes `bzlTransitiveDigest` of `pyproject_repo.bzl` (CRLF checkout).

### Task 2: One site-packages from many wheels

**Files:**
- Create: `tools/bazel/wheel_merge.bzl`, `tools/bazel/merge_wheel_files.py` (ported from open-protein-platform's `tools/bazel/devtools/` files of the same names, keeping their reasoning in the docstrings), `tools/bazel/tests/merge_wheel_files_test.py`
- Modify: `tools/bazel/BUILD.bazel`, `tools/bazel/tests/BUILD.bazel`, `distribution/bundle/BUILD.bazel` (create)

**Interfaces:**
- Consumes: `@app_pip//<pkg>:extracted_whl_files` (Task 1).
- Produces: `merge_wheel_files`; `//distribution/bundle:site_packages` merging all eight packages and their dependencies from the lock.

- [ ] **Step 1: Write the failing test** `merge_wheel_files_test.py`: `test_overlapping_paths_fail` (two input trees with the same relative file → `merge_wheel_files.main([...])` exits non-zero naming the path); `test_trees_merge` (two disjoint trees → both files under `<out>/site-packages/`).
- [ ] **Step 2: Run it**

Run: `bazel test //tools/bazel/tests:merge_wheel_files_test`
Expected: FAIL (module missing).

- [ ] **Step 3: Port the rule and tool**: `merge_wheel_files.main(argv: list[str]) -> int` reading `--out <dir>` and one `--tree <dir>` per input from a parameter file; refuse overlaps (open-protein-platform's version tolerates identical files; keep that and refuse only differing contents).
- [ ] **Step 4: Run the test**: Expected: PASS.
- [ ] **Step 5: Add `//distribution/bundle:site_packages`** and a `py_test` `pyside6_import_test` (Python 3.13, `imports` on the merged tree) asserting `PySide6.QtCore.qVersion().startswith("6.9")` and `import Bio, Pmw, numpy, msgpack, simplejson, rules` succeed.

Run: `bazel test //distribution/bundle:pyside6_import_test`
Expected: PASS.

- [ ] **Step 6: Commit** — "build: merge the app's wheels into one site-packages".

### Task 3: Overlays checked against the in-repo PyMOL

**Files:**
- Create: `distribution/edited/upstream.sha256`, `distribution/edited/BUILD.bazel`, `distribution/bundle/tests/edited_base_test.py`

**Interfaces:**
- Produces: `//distribution/edited:overlays` (filegroup of `edited/**` except BUILD and the hash file) and `//distribution/edited:edited_base_test`.

`upstream.sha256` lists, for each edited copy of an upstream file, the SHA-256 of the `modules/` file it was made from, in `sha256sum` format with the `modules/` path (`pmg_qt/pymol_qt_gui.py`, `pmg_qt/pymol_gl_widget.py`). `edited/pymol/startup_wrapper.py` has no upstream file and is not listed. This replaces `EDITED_FOR_PYMOL_WHL_VERSION`: the wheel version no longer moves independently, the in-repo sources do.

- [ ] **Step 1: Write the failing test** `edited_base_test.py`: `test_listed_files_unchanged` (each listed `modules/` file hashes to its line; on mismatch the message names the file and says to port the `BEGIN EDITED CODE SEGMENT` blocks, then update `upstream.sha256`); `test_every_edited_copy_listed` (every `edited/pmg_qt/*.py` has a line).
- [ ] **Step 2: Run it**: `bazel test //distribution/edited:edited_base_test` — Expected: FAIL (no hash file).
- [ ] **Step 3: Write `upstream.sha256`** from the current `modules/` files. Before writing it, confirm the edited copies were made from these sources: `diff` each pair must show only the marked segments; if it shows more, stop and ask.
- [ ] **Step 4: Run it**: Expected: PASS.
- [ ] **Step 5: Commit** — "build: check the app's overlays against the in-repo PyMOL".

### Task 4: The native launcher

**Files:**
- Create: `distribution/launcher/launcher.c`, `distribution/launcher/BUILD.bazel`, `distribution/launcher/launcher_test.py`, `distribution/launcher/fake_python.c`

**Interfaces:**
- Produces: `//distribution/launcher:launcher` with the Launcher contract above.

On POSIX the launcher `execv`s the runtime (one process). On Windows it is a GUI-subsystem program (`/SUBSYSTEM:WINDOWS`, entry `mainCRTStartup`) that starts `pythonw.exe` with `CreateProcessW`, passing the tail of `GetCommandLineW()` after its own program name verbatim (no re-quoting), inheriting the standard handles (so `-cq` output reaches a pipe), waits and returns the child's exit code. It resolves its own directory from `GetModuleFileNameW` / `realpath(argv[0])` (`_NSGetExecutablePath` on macOS).

- [ ] **Step 1: Write the failing test** `launcher_test.py` (`py_test`, data: the launcher and a test-only `cc_binary` `fake_python` that prints its arguments after `argv[0]` and `PYMOL_APP_ROOT` as one JSON object and exits with `FAKE_EXIT_CODE` or 0): it builds a temporary root with the launcher and `fake_python` copied to `runtime/pythonw.exe` (Windows) or `runtime/bin/python3`. Tests: `test_arguments_pass_through` with `["-cq", "C:/Users/Jörg/My Files/x.pdb"]` → `fake_python` sees `["-I", "-m", "pymol.startup_wrapper", "-cq", "C:/Users/Jörg/My Files/x.pdb"]`; `test_app_root_set` → `PYMOL_APP_ROOT` equals the temporary root; `test_exit_code_forwarded` (`FAKE_EXIT_CODE=3` → launcher exits 3); `test_missing_runtime` → exit 127 and the stderr message.
- [ ] **Step 2: Run it**: `bazel test //distribution/launcher:launcher_test` — Expected: FAIL.
- [ ] **Step 3: Implement `launcher.c`** (C11, one file, `#ifdef _WIN32` for the Windows half; wide-character APIs on Windows).
- [ ] **Step 4: Run it**: Expected: PASS on the host; CI covers the other platforms in Task 6.
- [ ] **Step 5: Commit** — "build: add the app's native launcher".

### Task 5: Assemble the bundle

**Files:**
- Create: `distribution/bundle/app_bundle.bzl`, `distribution/bundle/assemble_bundle.py`, `distribution/bundle/tests/assemble_bundle_test.py`
- Modify: `distribution/bundle/BUILD.bazel`

**Interfaces:**
- Consumes: `@python_3_13//:files`, `//distribution/bundle:site_packages`, `//tools/bazel/wheel:wheel`, `//distribution/edited:overlays`, `//distribution/launcher:launcher`, `distribution/licenses/*`, `distribution/pyproject.toml`.
- Produces: `//distribution/bundle:bundle` (tree artifact `bundle/PyMOL-Open-Source`) and `assemble_bundle.main(argv: list[str]) -> int`.

`app_bundle` applies an incoming transition to `@rules_python//python/config_settings:python_version = "3.13"` on `wheel` and `site_packages`, and passes every input through a parameter file. `assemble_bundle.py`:
1. copies the runtime files to `runtime/`, each relative to its repository root (`File.owner.workspace_root`);
2. copies the merged `site-packages` into the runtime's `site-packages`;
3. unpacks the wheel there (its `.dist-info` included);
4. copies the overlays: `edited/pmg_qt/*.py` → `pmg_qt/`, `edited/pymol/startup_wrapper.py` → `pymol/startup_wrapper.py`, `alternative_design/alt_logo.png` → `pymol/data/pymol/icons/alt_logo.png`, `os_specific/<os>/splash.png` → `pymol/data/pymol/splash.png`;
5. copies the launcher to the root;
6. writes `licenses/` with the rules of `os_specific/setup_build_exe.py`'s `collect_license_files` (moved here unchanged in behaviour: every bundled distribution needs a license file or the build fails; the index names `pymol-open-source-whl`, `PySide6_Essentials`, `Python`);
7. writes `manifest.json`: `{"app_version", "python_version", "git_commit", "pymol_wheel", "requirements_lock_sha256", "target"}`, `git_commit` from the stable workspace status `STABLE_GIT_COMMIT` (as `PyMOLBuildInfo.h`), sorted keys, no timestamp, so equal inputs give equal bytes.

- [ ] **Step 1: Write the failing test** `assemble_bundle_test.py` against small fake inputs (a three-file runtime, a one-package site-packages, a minimal wheel): `test_layout` (launcher, `runtime/`, `licenses/README.txt`, `manifest.json` exist), `test_overlay_replaces_wheel_file`, `test_missing_license_fails` (a distribution without a license → non-zero exit naming it), `test_manifest_is_deterministic` (two runs → identical bytes), `test_no_symlinks` (no symlink anywhere in the output).
- [ ] **Step 2: Run it**: `bazel test //distribution/bundle:assemble_bundle_test` — Expected: FAIL.
- [ ] **Step 3: Implement `assemble_bundle.py` and `app_bundle.bzl`**; declare `//distribution/bundle:bundle`.
- [ ] **Step 4: Run it**: Expected: PASS.
- [ ] **Step 5: Build the real bundle**

Run: `bazel build //distribution/bundle:bundle`
Expected: `bazel-bin/distribution/bundle/bundle/PyMOL-Open-Source/` with the layout above; `runtime/` holds `_cmd.cp313-win_amd64.pyd` (or the platform's name) under `site-packages/pymol/`.

- [ ] **Step 6: Commit** — "build: assemble the app bundle with Bazel".

### Task 6: Relocated smoke test in CI

**Files:**
- Create: `distribution/tests/BUILD.bazel`, `distribution/bundle/tests/run_bundle_smoke_test.py`
- Modify: `distribution/tests/smoke_test.py`, `.github/workflows/bazel.yaml`

**Interfaces:**
- Consumes: `//distribution/bundle:bundle`, `distribution/tests/smoke_test.py`.
- Produces: `//distribution/tests:bundle_smoke_test`.

- [ ] **Step 1: Make `smoke_test.py` find the licenses of either app**: `check_licenses` looks first in `$PYMOL_APP_ROOT/licenses` when the variable is set, otherwise where it looks today, so the cx_Freeze app keeps passing until step 7.
- [ ] **Step 2: Write the test** `run_bundle_smoke_test.py` (`py_test`, `size = "medium"`): copies the bundle to a new temporary directory (resolving symlinks), runs `<copy>/PyMOL-Open-Source -cq <smoke_test.py>` with an environment of only `PATH` (system folders), `HOME`/`USERPROFILE`, `SYSTEMROOT` and `TEMP`/`TMPDIR`, and asserts exit 0 and `SMOKE TEST OK` in the output; on failure prints the output.
- [ ] **Step 3: Run it**

Run: `bazel test //distribution/tests:bundle_smoke_test --test_output=errors`
Expected: PASS, output contains `SMOKE TEST OK (headless, PyMOL 3.2.0..., Python 3.13...)`.

- [ ] **Step 4: Let the Bazel workflow see the app**: remove `'distribution/**'` from `paths-ignore` in `.github/workflows/bazel.yaml` (keep the workflow and text-file entries), and update its header comment.
- [ ] **Step 5: Run everything**: `bazel test //...` — Expected: all targets pass.
- [ ] **Step 6: Commit** — "ci: test the Bazel-built app bundle on every platform".

## Acceptance criteria

- `bazel build //distribution/bundle:bundle` produces the bundle layout of the Interfaces section on Windows x64, macOS arm64, macOS x86_64 and Linux x86_64.
- The bundle copied to a new directory passes `smoke_test.py` headless with no host Python on `PATH`.
- The bundle contains no symlinks and no absolute path into Bazel's output base (`grep -r` for the output base finds nothing).
- `licenses/README.txt` lists every bundled distribution; a distribution without a license text fails the build.
- `manifest.json` names the app version from `distribution/pyproject.toml`, the git commit and the lock's SHA-256, and is byte-identical across two builds of the same commit.
- Changing `modules/pmg_qt/pymol_qt_gui.py` makes `edited_base_test` fail with instructions.
- The release path is unchanged: `build_app.yaml` and the cx_Freeze build are untouched.

## Verification

- `bazel test //distribution/... //tools/bazel/tests:merge_wheel_files_test` on the development machine: all pass.
- The Bazel workflow (`bazel.yaml`) on the pull request: Linux (manylinux_2_28), macOS 15 arm64, macOS 15 Intel and Windows all green, `//distribution/tests:bundle_smoke_test` among the passed tests.
- `git diff --name-only production...` lists only paths of the Scope section.
- `python3 .opp/style/check.py --base origin/production`: no findings.
