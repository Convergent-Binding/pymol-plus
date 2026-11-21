# Bazel Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 20 `pymol-open-source-whl` wheels with Bazel instead of CMake, vcpkg, scikit-build-core and cibuildwheel, then delete the old path.

**Architecture:** A Bzlmod workspace at the repository root ports OPP's proven Bazel build onto pymol-plus's upstream layout: BCR modules and pinned archives supply every native library, a Starlark rule generates the shader and build-info headers, `cc_binary` targets produce `_cmd` and `_champ`, and `py_wheel` packages `modules/`, `data/` and the extensions. CI builds one wheel per Python version and platform and hands them to the unchanged release jobs.

**Tech Stack:** Bazel 9.2.0 (bazelisk), rules_cc, rules_python (`py_wheel`, Python toolchains 3.10–3.14), rules_foreign_cc (netCDF), apple_support, GitHub Actions with `bazel-contrib/setup-bazel`, auditwheel.

**Spec:** `docs/features/bazel-build/specification.md`

**Reference:** "OPP" below means `C:\Users\manfred\github_repos\open-protein-platform` at `99b551714`. "Port OPP:x" means copy that file, then apply only the listed changes; its explanatory comments may be shortened but the facts they record (why a flag exists) stay.

**Branch:** `bazel-build`, cut from `integrate-setup` (or `production` once `integrate-setup` has landed there).

## Global Constraints

- `.bazelversion` is `9.2.0`; module versions are OPP's: platforms 1.1.0, apple_support 2.9.0, rules_cc 0.2.22, rules_python 2.3.2, bazel_skylib 1.8.2, freetype 2.14.1, glew 2.3.1, libpng 1.6.58, libxml2 2.15.3, glm 1.0.3, zlib 1.3.1.bcr.8, rules_foreign_cc 0.15.1 overridden to commit `f68b351c4691e747f889dc5e4c2cac3cd3b66ea2`, netCDF-C 4.10.1.
- Python toolchains 3.10, 3.11, 3.12, 3.13, 3.14; 3.10 is `is_default` (the `requires-python` floor).
- Compile definitions, C++17 and macOS 12.0 minimum exactly as the spec lists them.
- No build input from `vcpkg_installed/`, `pre-built/`, Conda or Homebrew.
- Keep the upstream source layout; add BUILD files beside sources, move nothing.
- `MODULE.bazel.lock` is committed.
- Commits carry no AI attribution lines (owner's rule).
- Do not push, open PRs, dispatch workflows, bump the version, tag or publish without the owner's explicit go-ahead in chat.

## Review Focus

1. A wheel that installs but lacks `_cmd`, `_champ`, `pymol/data/shaders` or the `pmg_qt` `.ui` forms (`py_wheel` drops `py_library.data` unless it goes through `py_package`) — pinned by `wheel_layout_test` (Task 6) and the PyPI member diff (Task 7).
2. An extension filename or wheel tag that disagrees with the interpreter (`cp3X`, Linux SOABI with CPU, darwin SOABI without CPU, `.cp3X-win_amd64.pyd`) — `wheel_layout_test` asserts both per selected version; CI installs every cell.
3. NumPy C-API mismatch on Windows from a wrong `_numpyconfig.h` — per-platform header repositories (Task 2) and `tests/` NumPy cases on the Windows wheels (Task 7).
4. A Linux wheel that fails on a clean system because `libgomp.so.1` is not bundled — `auditwheel repair` plus an assertion that the repaired wheel carries `pymol_open_source_whl.libs/libgomp` (Task 7).
5. Shader text that still contains an `#include` (50 include lines exist in `data/shaders`), which makes the driver reject the shader and PyMOL silently disable shaders — `generated_headers_test` (Task 3).

---

### Task 1: Bazel workspace and project metadata

**Files:**
- Create: `.bazelversion`, `.bazelrc`, `MODULE.bazel`, `BUILD.bazel`, `tools/bazel/BUILD.bazel`
- Create: `tools/bazel/pyproject.bzl`, `tools/bazel/pyproject_repo.bzl`, `tools/bazel/py_tags.bzl`, `tools/bazel/workspace_status.sh`, `tools/bazel/workspace_status.bat`
- Modify: `.gitignore` (add `/bazel-*`)
- Test: `tools/bazel/tests/BUILD.bazel`, `tools/bazel/tests/pyproject_metadata_test.py`

**Interfaces:**
- Produces: repository `@pymol_project_metadata` with `//:metadata.bzl` exporting `NAME`, `VERSION`, `REQUIRES_PYTHON`, `DEPENDENCIES`; `//tools/bazel:py_tags.bzl` with `SUPPORTED_PYTHON_VERSIONS`, `python_tag() -> select`, `cpython_soabi_prefix() -> select`; root `exports_files(["pyproject.toml", "README.md", "LICENSE"])`.

- [ ] **Step 1: Write the failing test** `pyproject_metadata_test.py`: parse `pyproject.toml` with `tomllib` and assert each constant equals it — `NAME == project["name"]`, `VERSION == project["version"]`, `REQUIRES_PYTHON == ">=3.10"`, `DEPENDENCIES == ["numpy>=2.2"]`. The constants reach the test through a `genrule`/`write_file` in the test package that renders them to JSON. Set `python_version = "3.12"` on the `py_test` (`tomllib` needs 3.11+).
- [ ] **Step 2: Run it and see it fail**
  Run: `bazel test //tools/bazel/tests:pyproject_metadata_test`
  Expected: FAIL — `@pymol_project_metadata` not defined.
- [ ] **Step 3: Implement the workspace.** `.bazelrc`: port OPP:.bazelrc keeping `--macos_minimum_os=12.0`, `--enable_platform_specific_config`, the three `workspace_status_command` lines, `startup --windows_enable_symlinks`, `build:windows --enable_runfiles`, the three network-retry lines; drop buildbuddy, asan and the `venvs_site_packages` line. `MODULE.bazel`: `module(name = "pymol_plus")`, the `bazel_dep`s for platforms, apple_support, rules_cc, rules_python, bazel_skylib, five `python.toolchain()` calls, the `pyproject` extension. Port OPP:tools/bazel/pyproject.bzl and pyproject_repo.bzl, renaming the repository to `pymol_project_metadata` and making `description` optional (it is commented out in `pyproject.toml`); the inline `license` and `authors` tables must be skipped, not rejected. Port OPP:tools/bazel/py_tags.bzl with `SUPPORTED_PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13", "3.14"]` and messages naming `pymol-open-source-whl`. Port both workspace-status scripts verbatim.
- [ ] **Step 4: Run it and see it pass**
  Run: `bazel test //tools/bazel/tests:pyproject_metadata_test`
  Expected: PASS. `MODULE.bazel.lock` now exists.
- [ ] **Step 5: Commit** — `build: add the Bazel workspace and read wheel metadata from pyproject.toml`

### Task 2: Native third-party dependencies and the cross-platform CI gate

**Files:**
- Modify: `MODULE.bazel`
- Create: `third_party/netcdf/BUILD.bazel`, `third_party/netcdf/BUILD.netcdf.bazel`, `third_party/numpy/BUILD.bazel`, `third_party/numpy/BUILD.numpy.bazel`
- Create: `include/BUILD.bazel`, `contrib/pocketfft/BUILD.bazel`, `contrib/uiuc/plugins/include/BUILD.bazel`
- Create: `.github/workflows/bazel.yaml`

**Interfaces:**
- Produces: `//third_party/numpy:headers` (alias selecting the platform's header repo), `@netcdf_c//:netcdf`, `//include:headers`, `//contrib/pocketfft`, `//contrib/uiuc/plugins/include:headers`; CI workflow `Bazel` running `bazel build //...` and `bazel test //...` on four runners.

- [ ] **Step 1: Add the dependencies.** Copy OPP:MODULE.bazel's BCR native deps (freetype, glew, libpng, libxml2, glm, zlib), rules_foreign_cc with its `archive_override` and `tools` extension (`cmake` 3.29.x binary, `ninja` 1.12.1 binary, `pkgconfig(mode = "system")`), and the `netcdf_c` `http_archive`. Port OPP:third_party/netcdf unchanged. Replace OPP's single `numpy_headers` archive with four `http_archive`s of NumPy 2.2.6 cp312 wheels — `numpy_headers_win_amd64`, `numpy_headers_macos_x86_64`, `numpy_headers_macos_arm64`, `numpy_headers_linux_x86_64` — each with the `sha256` PyPI's JSON API lists (`https://pypi.org/pypi/numpy/2.2.6/json`, `digests.sha256`), all using port of OPP:third_party/numpy/BUILD.numpy.bazel. `third_party/numpy/BUILD.bazel` defines `alias(name = "headers", actual = select({...}, no_match_error = ...))` over `@platforms//os` and `@platforms//cpu`. Port the three in-tree header `cc_library` files from OPP unchanged.
- [ ] **Step 2: Verify locally (Windows)**
  Run: `bazel build @netcdf_c//:netcdf @freetype @glew @glm @libpng//:png @libxml2//:xml2 //third_party/numpy:headers //include:headers //contrib/pocketfft //contrib/uiuc/plugins/include:headers`
  Expected: `Build completed successfully`; `netcdf.lib` produced.
- [ ] **Step 3: Add `.github/workflows/bazel.yaml`.** Triggers: `pull_request` and `workflow_dispatch`. Jobs: `linux` on `ubuntu-22.04` in container `quay.io/pypa/manylinux_2_28_x86_64` (install bazelisk 1.29.0 to `/usr/local/bin/bazel`, `dnf install -y mesa-libGL-devel`), `macos-arm64` on `macos-15`, `macos-x86_64` on `macos-15-intel`, `windows` on `windows-latest`. Each: `actions/checkout@v4`, `bazel-contrib/setup-bazel@0.19.0` with `bazelisk-cache`, `repository-cache` and `disk-cache: ${{ github.job }}`, then `bazel build //...` and `bazel test //... --test_output=errors`.
- [ ] **Step 4: Verify on CI** (after the owner allows a push of the branch)
  Run: `gh workflow run bazel.yaml --ref bazel-build`, then `gh run watch`.
  Expected: all four jobs green.
- [ ] **Step 5: Commit** — `build: fetch PyMOL's native dependencies with Bazel and check them on every platform`

### Task 3: Generated shader and build-info headers

**Files:**
- Modify: `scripts/python/create_generated_files.py` (`create_buildinfo`)
- Create: `scripts/python/BUILD.bazel`, `data/shaders/BUILD.bazel`, `tools/bazel/generate_headers_main.py`, `tools/bazel/shader_gen.bzl`
- Modify: `tools/bazel/BUILD.bazel`
- Test: `tools/bazel/tests/generated_headers_test.py`, `tools/bazel/tests/create_buildinfo_test.py`

**Interfaces:**
- Consumes: `create_shadertext(shaderdir, shaderdir2, outputheader, outputfile)` (unchanged).
- Produces: `create_buildinfo(outputdir, pymoldir=".", git_sha=None, build_date=None)`; target `//tools/bazel:pymol_generated_headers` providing `ShaderText.h`, `ShaderText.cpp`, `PyMOLBuildInfo.h` as `DefaultInfo` files and `CcInfo` with their directory on the include path; `//data/shaders:shader_srcs`.

- [ ] **Step 1: Write the failing tests.** `create_buildinfo_test`: with `subprocess.Popen` patched to raise, `create_buildinfo(tmp, git_sha="abc123", build_date=7)` writes a `PyMOLBuildInfo.h` containing `#define _PyMOL_BUILD_DATE 7` and `#define _PYMOL_BUILD_GIT_SHA "abc123"`. `generated_headers_test` (data: `//tools/bazel:pymol_generated_headers`): every line of `ShaderText.cpp` whose stripped form starts with `#include` is `#include "ShaderText.h"`, and every file name under `data/shaders` except `BUILD.bazel` with suffix `.vs`, `.fs`, `.gs`, `.tsc`, `.tse`, `.shared` appears as a string in `ShaderText.cpp`.
- [ ] **Step 2: Run them and see them fail**
  Run: `bazel test //tools/bazel/tests:create_buildinfo_test //tools/bazel/tests:generated_headers_test`
  Expected: FAIL — `create_buildinfo()` has no `git_sha` parameter; target `pymol_generated_headers` missing.
- [ ] **Step 3: Implement.** `create_buildinfo`: run `git` only when `git_sha is None`, read the clock only when `build_date is None` (OPP:scripts/python/create_generated_files.py shows the shape). `data/shaders/BUILD.bazel`: `filegroup(name = "shader_srcs", srcs = glob(["*"], exclude = ["BUILD.bazel"]))`. `scripts/python/BUILD.bazel`: `py_library(name = "create_generated_files_lib", srcs = ["create_generated_files.py"], imports = ["."])`. Port OPP:tools/bazel/generate_headers_main.py verbatim. Port OPP:tools/bazel/shader_gen.bzl without the GLSL gate: drop the `glsl_gate_config`, `_glsl_gate` and `_glslang` attributes, the second action and the `_validation` output group. Add `py_binary(name = "generate_headers")` and `pymol_generated_headers(name = "pymol_generated_headers", shader_srcs = ["//data/shaders:shader_srcs"])` to `tools/bazel/BUILD.bazel`.
- [ ] **Step 4: Run them and see them pass** — same command; expected PASS.
- [ ] **Step 5: Commit** — `build: generate the shader and build-info headers in a Bazel action`

### Task 4: Shared native settings, molfile plugins and `_champ`

**Files:**
- Create: `tools/bazel/pymol_native.bzl`, `contrib/uiuc/plugins/molfile_plugin/src/BUILD.bazel`, `contrib/champ/BUILD.bazel`
- Test: `tools/bazel/tests/champ_extension_test.py`

**Interfaces:**
- Produces: `PYMOL_DEFINES`, `PYMOL_COPTS`, `PYMOL_PLATFORM_LINKOPTS`, `PYMOL_PY_LINK_DEPS` in `//tools/bazel:pymol_native.bzl`; `//contrib/uiuc/plugins/molfile_plugin/src:molfile_plugins`; `//contrib/champ:_champ.so`.

- [ ] **Step 1: Write the failing test** `champ_extension_test`: load the built `_champ.so` (data dep, path from `rlocation`) with `importlib.machinery.ExtensionFileLoader("_champ", path)` and assert the module has the callables `new` and `insert_model` (`contrib/champ/champ_module.c:1020-1023`).
- [ ] **Step 2: Run it and see it fail** — `bazel test //tools/bazel/tests:champ_extension_test`; expected FAIL, target `//contrib/champ:_champ.so` missing.
- [ ] **Step 3: Implement.** Port OPP:tools/bazel/pymol_native.bzl with these changes: `PYMOL_COMMON_DEFINES` adds `_PYMOL_NO_MSGPACKC` and `_PYMOL_NO_MAIN`; the macOS defines add `PYMOL_CURVE_VALIDATE`; the docstring says it mirrors `CMakeLists.txt` at `d7999632` exactly. Port OPP:contrib/uiuc/plugins/molfile_plugin/src/BUILD.bazel and OPP:contrib/champ/BUILD.bazel unchanged.
- [ ] **Step 4: Run it and see it pass** — same command; expected PASS.
- [ ] **Step 5: Commit** — `build: build the molfile plugins and the _champ extension with Bazel`

### Task 5: `_cmd` extension, Python packages and import smoke test

**Files:**
- Modify: `BUILD.bazel` (root), `MODULE.bazel` (pip hub)
- Create: `tools/bazel/relocate.bzl`, `data/BUILD.bazel`, `modules/pymol/BUILD.bazel`, `modules/chempy/BUILD.bazel`, `modules/pmg_qt/BUILD.bazel`, `modules/pmg_tk/BUILD.bazel`, `modules/pymol2/BUILD.bazel`
- Create: `tools/bazel/requirements.in`, `tools/bazel/requirements_lock.txt`
- Test: `tools/bazel/tests/import_smoke_test.py`

**Interfaces:**
- Consumes: Task 2 header and library targets, Task 3 `//tools/bazel:pymol_generated_headers`, Task 4 settings and targets.
- Produces: `//:_cmd.so`; `relocate_file(src, out)` and `relocate_tree(srcs, strip_prefix, dest_prefix)` in `//tools/bazel:relocate.bzl`; `//data:runtime_data` (all of `data/`, shaders included); `py_library` targets `//modules/<pkg>`; run-staging targets `//modules/pymol:cmd_extension_for_run`, `//modules/pymol:runtime_data_for_run`, `//modules/chempy:champ_extension_for_run`; pip hub `@pymol_pip` with `numpy`.

- [ ] **Step 1: Write the failing test** `import_smoke_test` (deps: the five module libraries, `requirement("numpy")`; data: the three run-staging targets; `imports = ["../../modules"]` or equivalent so `import pymol` resolves to `modules/pymol`): `from pymol import cmd`; `cmd.fragment("ala")`; assert `cmd.count_atoms() == 10`; `import chempy.champ._champ`; assert `re.fullmatch(r"[0-9a-f]{40}", cmd.get_version()[4])`.
- [ ] **Step 2: Run it and see it fail** — `bazel test //tools/bazel/tests:import_smoke_test`; expected FAIL, `//:_cmd.so` missing.
- [ ] **Step 3: Implement.** Root `BUILD.bazel`: one `cc_binary(name = "_cmd.so", linkshared = True, linkstatic = True)` whose `srcs` are `glob(["ov/src/*.cpp", "layer0/*.cpp", ..., "layer5/*.cpp", "layerGraphics/gl/*.cpp"])` plus the matching `*.h` globs plus `//tools/bazel:pymol_generated_headers`; `includes` are CMake's list (`ov/src`, `layer0`–`layer5`, `layerGraphics`, `layerGraphics/gl`, `contrib/uiuc/plugins/molfile_plugin/src`); `deps` are OPP:src/cpp/BUILD.bazel's `_CMD_DEPS` minus `mmtf-c`, `@mmtf_cpp`, `@msgpack_cxx`, with `//third_party/numpy:headers`; `copts`, `cxxopts = ["-std=c++17"]` (Windows: `/std:c++17`, via `select`), `defines`, `linkopts` from Task 4. No `cmd_core`/ctest split (no Catch2 build). The globs must equal CMake's `ALL_SRC` — they do at the base commit. Port OPP:tools/bazel/relocate.bzl verbatim. `data/BUILD.bazel`: `filegroup(name = "runtime_data", srcs = glob(["**/*"], exclude = ["BUILD.bazel", "shaders/**"]) + ["//data/shaders:shader_srcs"])`. Module BUILD files: port OPP:src/python/{pymol,chempy,pmg_qt,pmg_tk,pymol2}/BUILD.bazel, dropping `pymol_app`, the `exports_files` lines and every `open_protein_platform` reference. Pip hub: `requirements.in` holds `numpy==2.2.6; python_version < "3.14"` and `numpy==2.3.3; python_version >= "3.14"`; lock it with `uv pip compile --universal --generate-hashes tools/bazel/requirements.in -o tools/bazel/requirements_lock.txt`; one `pip.parse(hub_name = "pymol_pip", python_version = v, requirements_lock = ...)` per supported version.
- [ ] **Step 4: Run it and see it pass** — same command; expected PASS. Then `bazel test //...` green locally and in the `Bazel` workflow on all four runners. Windows link errors on `gl*` symbols mean `opengl32.lib` is missing from the Windows linkopts; add it there.
- [ ] **Step 5: Commit** — `build: build the _cmd extension with Bazel and import it in a smoke test`

### Task 6: Wheel targets

**Files:**
- Create: `tools/bazel/wheel_staging/BUILD.bazel`, `tools/bazel/wheel/BUILD.bazel`
- Test: `tools/bazel/tests/wheel_layout_test.py`

**Interfaces:**
- Consumes: Task 1 metadata and `py_tags.bzl`, Task 5 targets and `relocate.bzl`.
- Produces: `//tools/bazel/wheel:wheel` (alias selecting the host OS's wheel; analysis error on any other OS), the platform wheels `pymol_wheel_macos`, `pymol_wheel_linux`, `pymol_wheel_windows`.

- [ ] **Step 1: Write the failing test** `wheel_layout_test` (data: `//tools/bazel/wheel:wheel`; `env` carries the expected tag and extension suffix from `python_tag()`/`cpython_soabi_prefix()` selects). Assert: the file name is `pymol_open_source_whl-<VERSION>-cp3X-cp3X-<plat>.whl` with `<plat>` one of `macosx_12_0_arm64`, `macosx_12_0_x86_64`, `linux_x86_64`, `win_amd64` for the host; members include `pymol/__init__.py`, `pymol/_cmd<suffix>`, `chempy/champ/_champ<suffix>`, `pymol/data/shaders/default.vs`, `pmg_qt/forms/colors.ui`; no member starts with `modules/`, `tools/`, `data/` or `contrib/`; `METADATA` has `Name: pymol-open-source-whl`, `Version: <VERSION>`, `Requires-Python: >=3.10`, `Requires-Dist: numpy>=2.2`. Suffixes: macOS `.cpython-3X-darwin.so`, Linux `.cpython-3X-x86_64-linux-gnu.so`, Windows `.cp3X-win_amd64.pyd`.
- [ ] **Step 2: Run it and see it fail** — `bazel test //tools/bazel/tests:wheel_layout_test`; expected FAIL, `//tools/bazel/wheel:wheel` missing.
- [ ] **Step 3: Implement.** Port OPP:tools/bazel/wheel_staging/BUILD.bazel: sources become `//:_cmd.so` and `//contrib/champ:_champ.so`; the macOS staging is used for both CPUs (darwin SOABI carries no CPU). Port OPP:tools/bazel/wheel/BUILD.bazel without the release marker, entry points and classifiers; `py_package` deps are the five `//modules/<pkg>` libraries plus the platform's staged files; `strip_path_prefixes = ["modules", "tools/bazel/wheel_staging"]`; `author = "Martin Urban"`, `author_email` from `pyproject.toml`; `description_file = "//:README.md"`; `extra_distinfo_files = {"//:LICENSE": "LICENSE"}`; macOS `platform = select({"@platforms//cpu:arm64": "macosx_12_0_arm64", "@platforms//cpu:x86_64": "macosx_12_0_x86_64"}, no_match_error = ...)`; Linux `linux_x86_64` only; Windows `win_amd64`. Keep OPP's `alias(name = "wheel")` with its `no_match_error`.
- [ ] **Step 4: Run it and see it pass** — same command for the default 3.10 and with `--@rules_python//python/config_settings:python_version=3.14`; expected PASS both times.
- [ ] **Step 5: Install check (local, Windows)** — build the cp312 wheel, install it into a fresh venv with `py -3.12 -m venv`, run `scripts/test_wheel.py`; expected: both NumPy profiles pass, as `scripts/test_wheel.py` reports.
- [ ] **Step 6: Commit** — `build: package the PyMOL wheel with Bazel`

### Task 7: Release wheels from Bazel in CI

**Files:**
- Modify: `.github/workflows/wheels.yaml` (the three `build-*` jobs; `release-integrity`, `attest`, `publish` stay byte-identical)

**Interfaces:**
- Consumes: `//tools/bazel/wheel:wheel`, `scripts/test_wheel.py`, `scripts/verify_release.py`.
- Produces: artifacts `PyMOL-wheel-<platform>-<python>` (still matched by `release-integrity`'s `PyMOL-wheel-*`) and `wheel-tests-<platform>-<python>`.

- [ ] **Step 1: Rewrite the build jobs.** Matrix `python: ['3.10', '3.11', '3.12', '3.13', '3.14']` in each of: `build-linux` (container `quay.io/pypa/manylinux_2_28_x86_64`, bazelisk, `mesa-libGL-devel`; after `bazel build`, `auditwheel repair --plat manylinux_2_28_x86_64 -w wheelhouse bazel-bin/tools/bazel/wheel/*.whl`, then assert `unzip -l wheelhouse/*.whl | grep -q 'pymol_open_source_whl.libs/libgomp'`; test with `/opt/python/cp3X-cp3X/bin/python`), `build-macos` over `macos-15` and `macos-15-intel`, `build-windows` on `windows-latest`. Every job: `setup-bazel` caches as in Task 2; `bazel build --@rules_python//python/config_settings:python_version=${{ matrix.python }} //tools/bazel/wheel:wheel`; copy the wheel to `wheelhouse/`; create a venv from `actions/setup-python` (or the container's Python), `pip install wheelhouse/*.whl`, run `python scripts/test_wheel.py` with `PYMOL_WHEEL_TEST_REPORTS=build/wheel-test-results`; upload both artifacts. Remove `VCPKG_ROOT`, `VCPKG_COMMIT`, uv and every vcpkg step.
- [ ] **Step 2: Verify on CI** (owner's go-ahead required)
  Run: `gh workflow run wheels.yaml --ref bazel-build`, then `gh run watch`.
  Expected: 20 build jobs green, `release-integrity` green (`verify_release.py` reports full coverage), `attest` and `publish` skipped.
- [ ] **Step 3: Compare with the published wheels.** For each of the four platforms: `pip download pymol-open-source-whl==3.2.0.3 --no-deps --only-binary=:all: --python-version 3.12 --platform <tag> -d old/`, download the matching CI artifact to `new/`, and compare `zipfile.ZipFile(...).namelist()` with `*.dist-info/` members dropped and extension names reduced to their stem. Expected: identical sets. Record the result in the PR description.
- [ ] **Step 4: Commit** — `ci: build the release wheels with Bazel`

### Task 8: Developer entry points and packaging metadata

**Files:**
- Modify: `pymakefile.py`, `pyproject.toml`, `uv.lock`
- Create: `tools/build_backend/pymol_build_backend.py`
- Test: `tools/bazel/tests/build_backend_test.py`

**Interfaces:**
- Produces: pymake tasks `build_wheel(python: str = "<running interpreter>")` and `test(match: str = "", verbose: str = "false")`; PEP 517 backend `pymol_build_backend` whose hooks all raise `RuntimeError` with a message naming `bazel build //tools/bazel/wheel:wheel`.

- [ ] **Step 1: Write the failing test** `build_backend_test`: import the backend module and assert `build_wheel("out")`, `build_sdist("out")`, `get_requires_for_build_wheel()` each raise `RuntimeError` whose message contains `bazel build //tools/bazel/wheel:wheel`.
- [ ] **Step 2: Run it and see it fail** — `bazel test //tools/bazel/tests:build_backend_test`; expected FAIL, module missing.
- [ ] **Step 3: Implement.** Port OPP:tools/build_backend/open_protein_platform_build_backend.py as `pymol_build_backend.py` with the message rewritten for this repository. `pyproject.toml`: `[build-system] requires = []`, `build-backend = "pymol_build_backend"`, `backend-path = ["tools/build_backend"]`; delete `[tool.scikit-build*]` and `[tool.cibuildwheel*]`; remove `build`, `cibuildwheel`, `delvewheel`, `setuptools` from the `dev` group; run `uv lock`. `pymakefile.py`: delete `_VCPKG_COMMIT`, `_vcpkg_executable`, `_vcpkg_triplet`, `_native_build_environment`, `generate`, `setup_dev_env`, `build_wheels`; `build_wheel` runs the Bazel wheel build for `python` (default `f"{sys.version_info.major}.{sys.version_info.minor}"`); `test` builds that wheel, `uv pip install --python <sys.executable> --force-reinstall --no-deps <wheel>`, then runs pytest on `tests` with the existing `match`/`verbose` handling.
- [ ] **Step 4: Verify** — `bazel test //tools/bazel/tests:build_backend_test` PASS; `pymake.bat test` PASS on Windows; `pip wheel . --no-deps -w out` fails with the Bazel message; `uv lock --check` passes.
- [ ] **Step 5: Commit** — `build: drive the developer tasks through Bazel and refuse pip builds`

### Task 9: Remove the CMake build and update the documentation

**Files:**
- Delete: `CMakeLists.txt`, `vcpkg.json`, `pre-built/`, `_custom_build/`, `setup.py.bak`, `.github/workflows/nightly_wheels.yaml` (stale: calls `automations/my_automator.py`, absent from this repository), and `create_shadertext.py` if `git grep -n create_shadertext` shows no user other than itself
- Modify: `README.md` (build section), `AGENTS.md` (repository layout: wheel built with Bazel), `.gitignore` (vcpkg/CMake entries)

- [ ] **Step 1: Delete and edit** as listed. `INSTALL`, `DEVELOPERS` and `testing/` are upstream files; leave them.
- [ ] **Step 2: Verify no build path references the old tools**
  Run: `git grep -nIi -e cmake -e vcpkg -e scikit -e cibuildwheel -e pre-built -- . ":!distribution" ":!docs/features" ":!uv.lock" ":!INSTALL" ":!DEVELOPERS" ":!ChangeLog" ":!contrib"`
  Expected: no output, or only lines that explain the migration.
- [ ] **Step 3: Verify everything still builds** — `bazel test //...` green locally; the `Bazel` and `Build Wheels` workflows green on the branch (owner's go-ahead for each dispatch).
- [ ] **Step 4: Commit** — `build: remove the CMake, vcpkg and cibuildwheel wheel build`

Stop here. Version bump, PR, merge, tag and publication are the owner's decisions.
