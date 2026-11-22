# Build the ready-to-run apps with Bazel

**Goal:** Every app artifact (Windows installer and portable ZIP, macOS DMGs, Linux .tar.gz/.deb/.rpm) is built and tested by Bazel from the same commit as the PyMOL wheel, without cx_Freeze, uv or the automator. The website keeps its own build until its overhaul (step 5, skipped).

**Architecture:** The app becomes a relocatable bundle of a python-build-standalone CPython 3.13 runtime (the same one rules_python already downloads for its toolchains), a `site-packages` merged from the locked app dependencies and the in-repo Bazel-built PyMOL wheel, the app's overlays, a small native launcher and a provenance manifest. That is the design of kullik01/pymol-open-source-setup#8, with Bazel in place of uv and cx_Freeze. rules_pkg packages the bundle per platform; steps that need the operating system's own tools (Inno Setup, hdiutil, codesign, rpmbuild) run as local, unsandboxed Bazel actions with pinned inputs.

**Tech Stack:** Bazel 9 (bzlmod), rules_python 2.3.2 (python-build-standalone 3.13 runtimes, `pip.parse`, the uv `lock` rule), rules_pkg (`pkg_files`, `pkg_zip`, `pkg_tar`, `pkg_deb`, `pkg_rpm`), rules_cc (launcher), Inno Setup 7, create-dmg 1.3.0, MkDocs Material.

**Spec:** This plan, the decisions recorded under Decisions below, and the standalone-runtime design of https://github.com/kullik01/pymol-open-source-setup/pull/8 (`scripts/python/windows_bundle.py`, `docs/features/uv-standalone-bundle/windows-x86_64-poc.md` on its branch `new-distribution`).

## Decisions

Settled with the developer before planning:

- The app bundles the PyMOL that Bazel builds from the same commit (`//tools/bazel/wheel:wheel`), not `pymol-open-source-whl` from PyPI. `EDITED_FOR_PYMOL_WHL_VERSION` gives way to a per-file check against the in-repo sources.
- No cx_Freeze: the app runs on a bundled python-build-standalone runtime, as in pymol-open-source-setup#8.
- Python, dependencies and downloadable tools are pinned and fetched by Bazel; steps that need operating-system tools run as local Bazel actions (`tags = ["local", "no-cache"]`). A fully hermetic build is not a goal.
- The Linux packages are built with rules_pkg (`pkg_tar`, `pkg_deb`, `pkg_rpm`); fpm and Ruby go.
- This feature plan lists every step; each step gets its own Superpowers plan in `.opp/plans/<branch>.md` when it starts. Step 1's plan is `.opp/plans/app-bazel-runtime-bundle.md`.

## Global Constraints

Quoted from AGENTS.md and the current build; every step holds them:

- App: PySide6 stays at 6.9 (6.10+ drops macOS 12 and RHEL/AlmaLinux 8); Python 3.13; biopython 1.86.
- App package and AppStream license: `BSD-3-Clause AND LGPL-3.0-only AND HPND`.
- Windows installs per user into `AppData\Roaming\PyMOL-Open-Source`; the installer's AppId, file types (.pdb, .cif, .pse), shortcuts and update-over-previous-release behaviour stay as tested in `build_app.yaml`.
- macOS minimum is 12.0 (`LSMinimumSystemVersion` in `distribution/os_specific/macos/Info.plist`); one DMG per architecture (AppleSilicon, Intel).
- Linux binaries need at most glibc 2.28 (RHEL/AlmaLinux 8); the packages install into `/opt/PyMOL-Open-Source-<version>`.
- The app's version lives only in `distribution/pyproject.toml`; a tag `setup-v<version>` builds a draft release; the website is published only when a release is published.
- New dependency versions only when they are at least 14 days old.
- Release file names stay as they are (`tests/check_release_assets.sh` matches them against the website's download links).

## Non-goals

- Code signing or notarization beyond today's ad-hoc macOS signature.
- New platforms or architectures (Windows arm64, Linux aarch64), Flatpak, AppImage or Snap.
- Changing what the app contains: its dependencies, Qt binding, Python version, overlays or user-visible behaviour.
- A fully hermetic, remotely cacheable packaging build.
- Moving the wheel's release flow (`wheels.yaml`, `release-stage/` branches); the app keeps its own `setup-v*` tags.

## Steps

Each step is one branch and one pull request into the feature branch `bazel-app-packaging`, which is cut from `production`; the step's pull request is merged there once its CI is green. When steps 1-4, 6 and 7 are in, one pull request takes `bazel-app-packaging` into `production`, and the developer merges that one. Until step 7 the cx_Freeze path keeps building the releases, so `bazel-app-packaging` stays releasable after every step.

1. **Runtime bundle** (`app-bazel-runtime-bundle`): the app's locked dependency hub `@app_pip`, the merged `site-packages`, the in-repo PyMOL with the overlays, the native launcher, the manifest and licenses, assembled as `//distribution/bundle:bundle` for the host platform; a relocated headless smoke test runs in `bazel test //...` on Windows x64, macOS arm64/x86_64 and Linux x86_64. Done when the Bazel workflow passes it on all four platforms. Plan: `.opp/plans/app-bazel-runtime-bundle.md`.
2. **Windows packages** (`app-bazel-windows`): the MSVC C++ and OpenMP runtimes in the bundle (found through the Visual Studio redistributable folder by a repository rule), the launcher's icon and version resource, `pkg_zip` for the portable ZIP, Inno Setup 7 fetched by checksum and run by a local action for the installer, `tests/check_msvc_runtime.py` as a Bazel test. `build-windows` in `build_app.yaml` switches to Bazel and keeps every install, update, uninstall and portable test. Done when that job is green with the Bazel-built files.
3. **macOS packages** (`app-bazel-macos`): the `.app` layout (`Contents/MacOS` launcher, `Contents/Resources` bundle, `Info.plist` stamped with the version), the macOS wheel-selection floor for `@app_pip` (`pip_whl_osx_version=12.0`), architecture thinning only if still needed, ad-hoc `codesign`, create-dmg fetched by checksum, `check_macos_min_version.sh` and the architecture check as tests. `build-macos` switches to Bazel for both runners.
4. **Linux packages** (`app-bazel-linux`): the app built in the `manylinux_2_28` container like the wheel, `libxcb-cursor.so.0` and `libgomp` in the bundle, the glibc ≤ 2.28 check as a Bazel test, `pkg_tar`/`pkg_deb`/`pkg_rpm` with today's dependencies, install path, desktop file, icon, AppStream and MIME files and post-install script. `build-gnu-linux` switches to Bazel; `test-gnu-linux-packages` on the eight distributions stays unchanged.
5. **Website** (`app-bazel-website`): **skipped** (developer, 2026-11-22). The website needs a complete overhaul, which is not part of this feature, so `build_app.yaml`'s `website` job and `docs.yaml` keep building it as they do now. The step as first planned: `@docs_pip` from `docs/website/requirements.txt`, `bazel build //distribution/docs/website:site` (MkDocs strict), `check_release_assets.sh` as a test against the step 2-4 package names. `build_app.yaml`'s `website` job and `docs.yaml` switch to Bazel.
6. **Quick checks** (`app-bazel-checks`): ruff, ShellCheck and actionlint from pinned wheels as `bazel run //distribution:checks` on the checkout (the developer's choice over a cached `bazel test`); desktop-file-validate and appstreamcli stay a CI step (system packages). `.pre-commit-config.yaml` and Dependabot's `pre-commit` entry go.
7. **Cleanup** (`app-bazel-cleanup`): remove cx_Freeze (`os_specific/setup_build_exe.py`, `automations/`, `automator.sh`, `win_automator.bat`, `requirements.txt`, `.python-version`, the uv steps and `UV_PYTHON_PREFERENCE` of the app's build jobs; the website jobs keep theirs while step 5 is skipped); `build_app.yaml` runs only Bazel targets; Dependabot's pip entry points at `distribution/requirements.in`; README, `distribution/README.md` and AGENTS.md describe only Bazel commands.

## Review Focus

Failure modes no single step's tests cover, most likely first; each step's plan pins the ones it owns:

- The bundled OpenSSL finds no CA certificates on Linux and macOS, so fetching from the PDB fails; `startup_wrapper.py` must still set `SSL_CERT_FILE` (step 1, smoke test `check_certificates`).
- A dependency wheel needs a newer macOS than 12.0 or a newer glibc than 2.28 because Bazel selected another wheel than uv did (steps 3 and 4, both checks as tests).
- `_cmd` needs a runtime the wheel repair used to add (Windows `msvcp140.dll`/`vcomp140.dll`, Linux `libgomp`), and the runners have it installed, so only a clean machine fails (steps 2 and 4: bundle checks, not just the smoke test).
- The relocated bundle still refers to the Bazel output tree, so it works in CI and not after installation (step 1: smoke test from a copy in a fresh directory; steps 2-4: the installed-package tests).
- An upgrade from the last cx_Freeze release leaves old files behind or loses file associations (step 2's update test, step 4's `test_linux_package.sh` with the previous release).
