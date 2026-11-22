# Linux App Packages with Bazel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bazel builds the Linux `.tar.gz`, `.deb` and `.rpm` from `//distribution/bundle` inside the `manylinux_2_28` container, the app needs nothing a supported distribution lacks (glibc at most 2.28, every library bundled or declared), and `build-gnu-linux` ships these files to the eight-distribution package tests unchanged.

**Architecture:** The bundle gains the two shared libraries cx_Freeze copied in: `libgomp.so.1` (OpenMP, for `_cmd`), taken from the compiler that built `_cmd`, and `libxcb-cursor.so.0` (Qt's X11 cursor support, missing from RHEL/AlmaLinux 8), from a pinned Ubuntu 20.04 package. A standard-library ELF reader checks every binary's needed libraries and glibc versions. rules_pkg writes the three packages with today's contents, names, dependencies and scripts.

**Tech Stack:** Bazel 9, rules_pkg 1.3.0 (`pkg_files`, `pkg_mklink`, `pkg_tar`, `pkg_deb`, `pkg_rpm`), rpmbuild in the build container, Python 3.13 standard library (ELF and `ar` readers), the `quay.io/pypa/manylinux_2_28_x86_64` image the wheel and `bazel.yaml` already use.

**Spec:** `.opp/plans/features/app-bazel-build.md`, step 4.

## Parent

`features/app-bazel-build.md`, step 4: Linux packages.

## Global Constraints

- Every binary in the app needs at most glibc 2.28 (RHEL/AlmaLinux 8).
- File names stay `PyMOL-Open-Source_v<version>.tar.gz`, `PyMOL-Open-Source_v<version>_amd64.deb` and `PyMOL-Open-Source_v<version>_x86_64.rpm`. The tarball extracts into `PyMOL-Open-Source-<version>/`.
- The packages install into `/opt/PyMOL-Open-Source-<version>`, with `/usr/bin/PyMOL-Open-Source` a link to its launcher, plus the desktop entry (install path filled in), the 256×256 icon, the AppStream metainfo (`@VERSION@`, and `@DATE@` the commit date) and the MIME types. These are the destinations of `os_specific/linux/build_packages.sh`.
- The package metadata stays as `build_packages.sh` sets it:
  - deb name `pymol-open-source`, rpm name `PyMOL-Open-Source`;
  - license `BSD-3-Clause AND LGPL-3.0-only AND HPND`;
  - maintainer, vendor, URL, category, description;
  - the deb `Depends` list and the rpm soname `Requires` list, verbatim;
  - `remove_empty_old_folders.sh` as deb `postinst` and rpm `%posttrans`;
  - no rpm build-id links; the package owns its `/opt` folder.
- The package tests (`tests/test_linux_package.sh` on eight distributions, installing over the latest release) run unchanged.
- Python and C follow the opp family style; the app's Python also passes its ruff settings.

## Review Focus

- A library `_cmd`, Qt or the runtime needs that neither ships in the app nor is a declared dependency. A full desktop has it, a minimal install does not, and the package test containers find only what is declared. `linux_libraries_test` (Task 2) resolves every `DT_NEEDED` entry against the bundle and the declared sonames.
- A glibc symbol newer than 2.28, from a library taken from a newer system. `linux_libraries_test` reads every binary's `GLIBC_` versions.
- The launcher reached through `/usr/bin/PyMOL-Open-Source`, a link: it must find the runtime in `/opt`. Its `/proc/self/exe` resolves links, and the package tests start PyMOL through that path.
- Bytecode under the read-only `/opt`: Python could not write a cache and would recompile everything at every start. Task 1 sends it to `~/.cache/PyMOL-Open-Source`, as macOS does.
- `rpmbuild` and the `+` in the version (`3.2.0.3+1`): today's rpm carries that version, and the update test installs the new rpm over it.

## Scope

```
MODULE.bazel
.github/workflows/build_app.yaml
distribution/BUILD.bazel
distribution/launcher/**
distribution/bundle/**
distribution/linux/**
distribution/edited/pymol/startup_wrapper.py
distribution/tests/smoke_test.py
distribution/README.md
AGENTS.md
```

## Done

`build-gnu-linux` builds the three packages with Bazel in the `manylinux_2_28` container, and `test-gnu-linux-packages` passes on all eight distributions, update test included, on a pull request into `bazel-app-packaging`.

## Non-goals

- New package formats (Flatpak, AppImage, Snap) or architectures (aarch64).
- Signing the packages or a package repository.
- The website and the quick checks (steps 5 and 6); removing cx_Freeze, the automator and uv (step 7).

## Interfaces

- `distribution/linux/elf.py`: `needed_libraries(path) -> list[str]` (`DT_NEEDED`), `glibc_versions(path) -> set[tuple[int, int]]`, `is_elf(path) -> bool`.
- `distribution/linux/unpack_deb.py`: `main(argv) -> int` with `--deb`, `--member <path in data.tar>` and `--out <file>`. It reads the `ar` archive and its `data.tar.xz`.
- `@gomp_linux` (local repository rule): `libgomp.so.1` of the compiler on `PATH` (`gcc -print-file-name=libgomp.so.1`), empty off Linux.
- `@libxcb_cursor_deb` (`http_file`): Ubuntu 20.04's `libxcb-cursor0` `.deb`, pinned by SHA-256 at implementation time from `archive.ubuntu.com`. It is about 10 kB; fetching it is part of this approved plan.
- `app_bundle`'s existing `runtime_files`/`runtime_from_site_packages`, plus a new `site_packages_files` (`label_keyed_string_dict`: file → path in site-packages), on Linux only:
  - `libgomp.so.1` → `runtime/lib/`;
  - `libxcb-cursor.so.0` → `PySide6/Qt/lib/`, where Qt's xcb plugin finds it through its `$ORIGIN` RUNPATH.
- `//distribution/linux:tarball`, `:deb`, `:rpm`, `:packages` (filegroup); the `:rpm` target needs `rpmbuild`.

## Tasks

### Task 1: Linux launcher and startup settings

**Files:** Modify `distribution/launcher/launcher.c`, `distribution/launcher/launcher_test.py`, `distribution/edited/pymol/startup_wrapper.py`, `distribution/tests/smoke_test.py`.

- [ ] **Step 1: Write the failing tests.**
  - `launcher_test.py::test_arguments_pass_through` expects, on Linux, `["-I", "-X", "pycache_prefix=<home>/.cache/PyMOL-Open-Source/pycache", "-m", "pymol.startup_wrapper", ...]`. `XDG_CACHE_HOME` takes precedence over `~/.cache` when set; Windows is unchanged.
  - `smoke_test.py::check_linux_settings` asserts that `sys.pycache_prefix` ends in `PyMOL-Open-Source/pycache` and that `libgomp.so.1` is loaded from the app's `runtime/lib`.
- [ ] **Step 2: Run** `bazel test //distribution/launcher:launcher_test` on Linux (the `GNU/Linux` job of `bazel.yaml`). Expected: FAIL.
- [ ] **Step 3: Implement.**
  - The Linux launcher adds `-X pycache_prefix=…`.
  - `startup_wrapper.py` (Linux only) loads `<sys.prefix>/lib/libgomp.so.1` with `ctypes.CDLL(..., mode=RTLD_GLOBAL)` before `import pymol`, so `_cmd`'s `libgomp.so.1` resolves to the app's copy.
- [ ] **Step 4: Run.** Expected: PASS on Linux; Windows and macOS unchanged.
- [ ] **Step 5: Commit** — "app: Linux bytecode cache outside /opt, the app's own libgomp".

### Task 2: Bundle libgomp and libxcb-cursor, and check every library

**Files:** Modify `MODULE.bazel`, `distribution/bundle/**` (the `app_bundle` attribute, `assemble_bundle.py` and its test), `distribution/BUILD.bazel`. Create `distribution/linux/BUILD.bazel`, `elf.py`, `unpack_deb.py`, `gomp_repo.bzl`, and the tests `tests/elf_test.py`, `tests/unpack_deb_test.py`, `tests/linux_libraries_test.py`.

- [ ] **Step 1: Write the failing tests.**
  - `elf_test.py`, on fixture ELF files built in the test: `test_needed_libraries`, `test_glibc_versions`, `test_not_elf`.
  - `unpack_deb_test.py`, on a fixture `.deb` built with `ar` and `tar.xz` in the test: `test_member_extracted`, `test_missing_member_fails`.
  - `assemble_bundle_test.py::test_site_packages_files`.
  - `linux_libraries_test.py` (Linux, data: the bundle). It has two tests:
    - `test_every_needed_library_is_bundled_or_declared`: each `DT_NEEDED` entry is in the bundle, in the declared rpm sonames, or in glibc's own libraries (`libc.so.6`, `libm.so.6`, `libdl.so.2`, `libpthread.so.0`, `librt.so.1`, `ld-linux-x86-64.so.2`, `libutil.so.1`, `libresolv.so.2`). `libstdc++.so.6` and `libgcc_s.so.1` count too: every supported distribution installs them with its base system.
    - `test_glibc_at_most_2_28`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** the readers, the repository rule, the pinned `http_file`, the new attribute, and the Linux `select`s in `//distribution/bundle`.
- [ ] **Step 4: Run** `bazel test //distribution/...` (the fixture tests locally, the bundle checks in the Linux CI job). Expected: PASS.
- [ ] **Step 5: Commit** — "build: bundle libgomp and libxcb-cursor and check every Linux library".

### Task 3: The packages with rules_pkg

**Files:** Modify `MODULE.bazel` (`bazel_dep(name = "rules_pkg", version = "1.3.0")`), `distribution/BUILD.bazel` (exports). Create `distribution/linux/packages.bzl` (the version and metadata constants), `distribution/linux/fill_template.py` (desktop entry and metainfo), and `distribution/linux/tests/packages_test.py`.

- [ ] **Step 1: Write the failing test** `packages_test.py`.
  - Linux; data: the tarball and the deb. The rpm is checked in CI with `rpm -qpl`/`-qpR`.
  - `test_tarball_top_folder`, `test_deb_control` (name, version, `Depends` verbatim, `postinst`), `test_deb_files` (every destination of the Global Constraints, the `/usr/bin` link target).
  - `test_desktop_entry_names_install_dir`, `test_metainfo_version_and_date`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** with `pkg_files` (modes: directories 0755, the launcher and the runtime's executables 0755), `pkg_mklink`, `pkg_tar` (`package_dir`), `pkg_deb`, and `pkg_rpm`:
  - `defines = {"_build_id_links": "none"}`;
  - `posttrans_scriptlet_file`;
  - `requires` = the sonames with `()(64bit)`.
- [ ] **Step 4: Run** the test, then `bazel build //distribution/linux:packages` in the container. Expected: PASS; three release-named files.
- [ ] **Step 5: Commit** — "build: write the Linux packages with rules_pkg".

### Task 4: The Linux CI jobs on Bazel

**Files:** Modify `.github/workflows/build_app.yaml`, `distribution/README.md`, `AGENTS.md`.

- [ ] **Step 1: Move `build-gnu-linux` into the container.**
  - It runs in `quay.io/pypa/manylinux_2_28_x86_64`, with the safe-directory, bazelisk and `mesa-libGL-devel` steps of `bazel.yaml`, plus `dnf install rpm-build`.
  - It runs `bazel build //distribution/linux:packages` and `bazel test //distribution/...`, then lists the rpm's files and requirements (`rpm -qpl`, `rpm -qpR`).
  - It copies the packages to `os_specific/dist` and runs the headless smoke test from the extracted tarball.
  - It drops Python, uv, fpm and the host `libxcb-cursor0`.
- [ ] **Step 2: Move the previous-release download to a new job.** The step needs `gh`, which the container lacks, so a new job `previous-linux-release` (ubuntu-latest) runs it; `test-gnu-linux-packages` needs both jobs and stays unchanged otherwise.
- [ ] **Step 3: Docs.** README and AGENTS.md give the Linux Bazel commands. The automator remains only as the cx_Freeze reference until step 7.
- [ ] **Step 4: Verify** with actionlint and on the pull request: `build-gnu-linux`, all eight `test-gnu-linux-packages` jobs and `release` green.
- [ ] **Step 5: Commit** — "ci: build the Linux packages with Bazel".

## Acceptance criteria

- All eight distribution tests install the Bazel-built package over the latest release and pass the headless and GUI smoke tests.
- Every library any app binary needs is bundled or declared, and no binary needs glibc newer than 2.28.
- The three files carry the release names, and the packages install to today's destinations with today's metadata, dependencies and scripts.
- The installed app keeps its bytecode in `~/.cache/PyMOL-Open-Source`, not under `/opt`.

## Verification

- Locally (Windows): `elf_test`, `unpack_deb_test`, `assemble_bundle_test` and `bazel test //...`; the Linux-only targets are skipped.
- On the pull request into `bazel-app-packaging`: `GNU/Linux (x86_64)`, `build-gnu-linux`, the eight `test-gnu-linux-packages` jobs and `release` green.
- `python3 .opp/style/check.py --base origin/bazel-app-packaging` on the touched paths: no findings; ruff with the app's settings: clean.
