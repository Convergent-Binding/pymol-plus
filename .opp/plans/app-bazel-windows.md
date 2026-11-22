# Windows App Packages with Bazel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bazel builds the Windows portable ZIP and the Inno Setup installer from `//distribution/bundle`, the bundle starts on a PC without the VC++ Redistributable, and `build_app.yaml`'s `build-windows` job ships these Bazel-built files with every install, update, uninstall and portable test it runs today.

**Architecture:** The bundle gains the Microsoft C++ and OpenMP runtimes from the same `vc_redist.x64.exe` cx_Freeze used, now pinned by URL and SHA-256 and unpacked at build time with freeze-core's own code. The launcher gains a statically linked CRT, the app icon and a version resource, generated as a `.res` file by a small Python tool. `pkg_zip` (rules_pkg) writes the portable ZIP; a local Bazel action runs Inno Setup 7's ISCC on the unchanged `setup.iss`.

**Tech Stack:** Bazel 9, rules_pkg 1.3.0, rules_python 2.3.2 (a `@app_build_pip` hub), freeze-core 0.8.1 with cabarchive and lief (today's pins), Inno Setup 7.1.1, MSVC.

**Spec:** `.opp/plans/features/app-bazel-build.md`, step 2.

## Parent

`features/app-bazel-build.md`, step 2: Windows packages.

## Global Constraints

- The installer's AppId `{192F52C3-D86D-4735-9929-C7DF593CB534}`, per-user install into `AppData\Roaming\PyMOL-Open-Source` with the app in `bin\`, the shortcuts, the file types (.pdb, .cif, .pse) and the removal of an all-users installation stay as `setup.iss` defines them.
- Release file names stay `PyMOL-Open-Source_v<version>_x64_setup.exe` and `PyMOL-Open-Source_v<version>_x64_portable.zip`, with `<version>` from `distribution/pyproject.toml`.
- The portable ZIP holds the app folder's contents at its root, as today.
- The VC++ runtime comes from `https://download.visualstudio.microsoft.com/download/pr/e9604e21-4b79-4096-a4b3-1b63d4b55b4d/CC0FF0EB1DC3F5188AE6300FAEF32BF5BEEBA4BDD6E8E445A9184072096B713B/VC_redist.x64.exe` (SHA-256 `cc0ff0eb1dc3f5188ae6300faef32bf5beeba4bdd6e8e445a9184072096b713b`, published 2026-11-07), its license text goes into `licenses/vc_redist/`.
- New dependencies at least 14 days old; build tools at today's `requirements.txt` pins.
- Python and C follow the opp family style (`.opp/style/check.py`); the app's Python also passes its ruff settings.

## Review Focus

- `_cmd` imports `MSVCP140.dll` and `VCOMP140.DLL`, which a clean PC finds only next to `pythonw.exe`; PySide6's own copies are on the search path only after PySide6 is imported, so a headless start fails there: Task 2's `msvc_runtime_test` checks every binary's runtime imports against the bundle, independent of what the runner has installed.
- The launcher sits outside `runtime\` and imported `VCRUNTIME140.dll`: Task 1's test asserts its import table holds no C++ runtime DLL.
- The software-OpenGL fallback (`opengl32sw.dll` copied to `opengl32.dll`) must sit next to the process that loads OpenGL, which is now `runtime\pythonw.exe`, not the launcher: Task 2 puts it in `runtime\` and Task 5 updates the website's note and the CI GUI test.
- An update from the last cx_Freeze release keeps old files: `setup.iss` deletes `{app}\bin` before installing; the CI update test (Task 5) runs over the latest published release.
- The taskbar shows Python's icon and a second group, because the window belongs to `pythonw.exe`: Task 3 gives the process and the shortcuts one AppUserModelID.

## Scope

```
MODULE.bazel
MODULE.bazel.lock
.github/workflows/build_app.yaml
distribution/BUILD.bazel
distribution/build_requirements.in
distribution/build_requirements_lock.txt
distribution/bundle/**
distribution/launcher/**
distribution/windows/**
distribution/edited/pymol/startup_wrapper.py
distribution/os_specific/windows/inno_setup/setup.iss
distribution/tests/smoke_test.py
distribution/tests/check_msvc_runtime.py
distribution/tests/BUILD.bazel
distribution/docs/website/docs/**
distribution/README.md
AGENTS.md
```

## Done

`build-windows` in `build_app.yaml` builds the ZIP and the installer with Bazel and passes every test it runs today, on a pull request into `bazel-app-packaging`.

## Non-goals

- macOS, Linux, the website build and the quick checks (steps 3-6).
- Removing the automator, cx_Freeze or `requirements.txt` (step 7); only the Windows job stops using them.
- Code signing; a native launcher that embeds Python instead of starting `pythonw.exe`.
- Fetching Inno Setup with Bazel: its installer documents no portable mode, so ISCC comes from an Inno Setup 7 installation, as today.

## Interfaces

- `@vc_redist//file` (`http_file`), unpacked by `//distribution/windows:msvc_runtime` into a tree `msvc_runtime/` with the runtime DLLs and `LICENSE.RTF`, `LICENSE.txt`.
- `app_bundle` gains `runtime_files` (`label_keyed_string_dict`: file or tree → folder in `runtime/`) and `license_trees` (`label_keyed_string_dict`: tree → folder in `licenses/`); `//distribution/bundle` sets both on Windows only.
- `//distribution/launcher:make_resources` writes `launcher.res` from `os_specific/windows/logo.ico` and the app version; the launcher links it.
- `@app_project_metadata//:metadata.bzl` exports the app's `VERSION` (`pyproject_metadata` repository rule on `//distribution:pyproject.toml`).
- `@inno_setup//:ISCC.exe`: a local repository rule finding Inno Setup 7 (the three install folders `build_inno_setup.py` searches, then `PATH`); without it, a target whose action fails with the install instructions.
- `//distribution/windows:portable_zip` and `//distribution/windows:installer` (tag `manual`), named as the Global Constraints say.

## Tasks

### Task 1: A launcher that starts on a clean PC

**Files:** Modify `distribution/launcher/BUILD.bazel`, `launcher_test.py`; create `distribution/launcher/make_resources.py`, `distribution/launcher/make_resources_test.py`.

- [ ] **Step 1: Write the failing tests.** `launcher_test.py::test_no_cpp_runtime_import` (Windows): the launcher's PE import table (read with a stdlib parser shared with Task 2's test) names none of `vcruntime140*`, `msvcp140*`, `vcomp140`. `make_resources_test.py`: `test_icon_group_lists_every_image` (the `.res` holds one RT_ICON per image of a two-image `.ico` and an RT_GROUP_ICON naming them), `test_version_strings` (RT_VERSION holds `ProductName PyMOL-Open-Source` and `ProductVersion` = the given version), `test_resources_are_dword_aligned`.
- [ ] **Step 2: Run them.** `bazel test //distribution/launcher/...` — Expected: FAIL.
- [ ] **Step 3: Implement.** `features = ["static_link_msvcrt"]` on Windows. `make_resources.main(argv) -> int` with `--icon`, `--version`, `--out`, writing the 32-bit RES format (empty first entry, RT_ICON, RT_GROUP_ICON id 1, RT_VERSION with a `StringFileInfo` `040904B0` and `VarFileInfo`). The launcher links the `.res` through `additional_linker_inputs` and `linkopts`.
- [ ] **Step 4: Run them.** Expected: PASS; Explorer shows the icon (manual check, noted in the PR).
- [ ] **Step 5: Commit** — "build: link the launcher's C runtime statically and give it the app icon".

### Task 2: The C++ and OpenMP runtimes in the bundle

**Files:** Modify `MODULE.bazel`, `distribution/bundle/**`, `distribution/tests/smoke_test.py`; create `distribution/build_requirements.in` (freeze-core 0.8.1, cabarchive 0.2.5, lief 1.0.0, striprtf 0.0.35) and its lock, `distribution/windows/BUILD.bazel`, `distribution/windows/unpack_vc_redist.py`, `distribution/bundle/tests/msvc_runtime_test.py`.

- [ ] **Step 1: Write the failing test** `msvc_runtime_test.py` (Windows, data: the bundle): for every `.exe`, `.dll`, `.pyd` in the bundle, each imported runtime DLL (the pattern of `check_msvc_runtime.py`) exists in `runtime/` or beside the importer; `licenses/vc_redist/LICENSE.txt` exists; `runtime/opengl32sw.dll` exists.
- [ ] **Step 2: Run it.** Expected: FAIL naming `msvcp140.dll` and `vcomp140.dll` for `_cmd`.
- [ ] **Step 3: Implement.** `unpack_vc_redist.py` calls `freeze_core.winmsvcr_repack.unpack_exe` on the pinned file and copies the DLLs and both license files into its tree output. `app_bundle` copies `runtime_files` and `license_trees`; `//distribution/bundle` adds the runtime tree and `PySide6/opengl32sw.dll` to `runtime/` and the license files to `licenses/vc_redist/` on Windows. `smoke_test.py` checks `licenses/vc_redist` for the Bazel-built app on Windows; `check_msvc_runtime.py` is removed (the Bazel test replaces it; the cx_Freeze job is gone after Task 5).
- [ ] **Step 4: Run it**, and `bazel test //distribution/...` — Expected: PASS.
- [ ] **Step 5: Commit** — "build: bundle the Microsoft C++ and OpenMP runtimes".

### Task 3: One taskbar identity

**Files:** Modify `distribution/edited/pymol/startup_wrapper.py`, `distribution/os_specific/windows/inno_setup/setup.iss`.

- [ ] **Step 1:** `startup_wrapper.py` calls `SetCurrentProcessExplicitAppUserModelID("io.github.kullik01.pymol-open-source")` through `ctypes` on Windows before PyMOL starts (the macOS bundle identifier, so one name everywhere). Both `[Icons]` entries get `AppUserModelID: "io.github.kullik01.pymol-open-source"`.
- [ ] **Step 2:** `smoke_test.py` asserts on Windows that `GetCurrentProcessExplicitAppUserModelID` returns it.
- [ ] **Step 3: Run** `bazel test //distribution/tests:bundle_smoke_test` — Expected: PASS.
- [ ] **Step 4: Commit** — "app: give the Windows process and its shortcuts one AppUserModelID".

### Task 4: Portable ZIP and installer targets

**Files:** Modify `MODULE.bazel` (rules_pkg 1.3.0, `@app_project_metadata`, `@inno_setup`, `@vc_redist`), `distribution/os_specific/windows/inno_setup/setup.iss` (the `#error` messages name the Bazel target); create the rules in `distribution/windows/BUILD.bazel`, `distribution/windows/inno_setup.bzl`, `distribution/windows/tests/portable_zip_test.py`.

- [ ] **Step 1: Write the failing test** `portable_zip_test.py`: the ZIP is named for the version, holds `PyMOL-Open-Source.exe`, `runtime/pythonw.exe` and `manifest.json` at its root, and no `.pyc`.
- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Implement** `pkg_zip` over the bundle tree; the `inno_setup_installer` rule runs `ISCC /DMyAppVersion=<VERSION> /DAppSourceDir=<bundle> /O<out dir> setup.iss` (`tags = ["local", "manual"]`).
- [ ] **Step 4: Run** the test and `bazel build //distribution/windows:installer` — Expected: PASS; the installer exists with the release name.
- [ ] **Step 5: Commit** — "build: package the Windows app as ZIP and installer with Bazel".

### Task 5: The Windows CI job on Bazel

**Files:** Modify `.github/workflows/build_app.yaml`, `distribution/docs/website/docs/**` (the OpenGL note), `distribution/README.md`, `AGENTS.md`.

- [ ] **Step 1:** `build-windows` drops Setup Python, uv, the virtual environment and the C++ runtime cache; adds `setup-bazel` (as `bazel.yaml`); keeps the pinned Inno Setup install; runs `bazel build //distribution/windows:portable_zip //distribution/windows:installer` and `bazel test //distribution/...`, copies the two files (paths from `bazel cquery --output=files`) and the bundle to where the later steps read them, and keeps the smoke, GUI (with `opengl32.dll` in `runtime\`), installer, update, uninstall and portable steps unchanged in what they check. `build_app.yaml`'s `changes` filter also counts `MODULE.bazel` and the Bazel files the app uses.
- [ ] **Step 2:** The website's OpenGL troubleshooting note names `bin\runtime\` for `opengl32.dll`; README and AGENTS.md give the Windows Bazel commands.
- [ ] **Step 3: Verify** with actionlint and on the pull request: `build-windows` and `release` green.
- [ ] **Step 4: Commit** — "ci: build the Windows packages with Bazel".

## Acceptance criteria

- `msvc_runtime_test` passes: every C++/OpenMP runtime DLL any bundle binary imports ships with the bundle; the launcher imports none.
- `build-windows` installs the Bazel-built installer over the latest published release, runs the installed app's smoke test, uninstalls it cleanly, and tests the portable ZIP, all green.
- The ZIP and the installer carry the release names; `check_release_assets.sh` in the `release` job passes.
- `licenses/vc_redist/` holds the runtime's license, as the cx_Freeze app's `share/licenses/vc_redist/` did.
- The installed launcher shows the PyMOL icon in Explorer and the shortcuts and the running window share one taskbar group (manual check by the developer, recorded in the PR).

## Verification

- `bazel test //...` on Windows: all pass.
- The pull request into `bazel-app-packaging`: `Windows (x64)`, `build-windows` and `release` green.
- `python3 .opp/style/check.py --base origin/bazel-app-packaging` on the touched paths: no findings; ruff with the app's settings: clean.
