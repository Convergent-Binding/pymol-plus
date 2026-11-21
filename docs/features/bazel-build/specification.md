# Bazel build for the PyMOL wheel

Status: Proposed, awaiting owner approval.
Base: `integrate-setup` at `d7999632`.
Reference implementation: `open-protein-platform` (OPP) at `99b551714`, whose
`MODULE.bazel`, `.bazelrc`, `tools/bazel/`, `third_party/`, `src/cpp/BUILD.bazel`
and `contrib/*/BUILD.bazel` build the same PyMOL native sources with Bazel 9.2.0
on macOS, Linux and Windows.

## Intent

Replace the wheel build of `pymol-open-source-whl` — CMake, scikit-build-core,
vcpkg, the checked-in `pre-built/` libraries and headers, and cibuildwheel —
with a Bazel build that fetches every native dependency itself, pinned by
checksum, and produces the same wheels. Once the Bazel wheels pass the existing
release gates, the CMake path is deleted.

## Behaviour that stays the same

- Distribution `pymol-open-source-whl`, version from `pyproject.toml`,
  `Requires-Python: >=3.10`, `Requires-Dist: numpy>=2.2`.
- Wheel matrix: CPython 3.10, 3.11, 3.12, 3.13, 3.14 on each of `win_amd64`,
  `macosx_12_0_x86_64`, `macosx_12_0_arm64`, `manylinux_2_28_x86_64`:
  20 wheels, which `scripts/verify_release.py` accepts unchanged. The macOS
  x86_64 wheels stay because `distribution/requirements.txt` pins this wheel and
  the app supports Intel Macs.
- Wheel contents: the packages `chempy`, `pmg_qt`, `pmg_tk`, `pymol`, `pymol2`
  from `modules/`, the whole `data/` tree as `pymol/data/` (shaders included),
  `pymol/_cmd` and `chempy/champ/_champ` extensions. Member names equal those of
  the published 3.2.0.3 wheel for the same tag, apart from `*.dist-info/`.
- Native compile definitions equal `CMakeLists.txt`'s per platform:
  all: `_PYMOL_LIBPNG _PYMOL_FREETYPE _PYMOL_VMD_PLUGINS _PYMOL_NO_MSGPACKC
  _PYMOL_NO_MAIN _PYMOL_NUMPY`; Windows: `WIN32 PYMOL_OPENMP _HAVE_LIBXML`
  (plus `GLEW_STATIC`, which the BCR glew needs); macOS: `_HAVE_LIBXML
  PYMOL_CURVE_VALIDATE _PYMOL_OSX`; Linux: `_HAVE_LIBXML`. C++17 everywhere.
- Release pipeline after the wheels exist is unchanged: `twine check`,
  `verify_release.py` (with `--tag` on tags), build-provenance attestation,
  PyPI trusted publishing, and the triggers of `wheels.yaml`.
- Every wheel is installed into a clean environment and passes
  `scripts/test_wheel.py` with the minimum and the latest NumPy 2.

## Interfaces

- `bazel build //tools/bazel/wheel:wheel --@rules_python//python/config_settings:python_version=3.X`
  builds the host platform's wheel for CPython 3.X into
  `bazel-bin/tools/bazel/wheel/`.
- `bazel test //...` runs the Bazel-side checks (metadata, generated headers,
  native import smoke test, wheel layout).
- `pymake build_wheel` and `pymake test` keep working, now driving Bazel.
- `pip install .` fails at once with a message saying the wheel is built with
  Bazel, instead of building a wheel without extensions.

## Non-goals

- Moving sources into OPP's `src/cpp`, `src/python` layout. The upstream layout
  (`layer*/`, `ov/src/`, `modules/`) stays so merges from
  `schrodinger/pymol-open-source` stay clean.
- OPP's functional deltas: enabling msgpack (BCIF/MMTF export), dropping
  `PYMOL_CURVE_VALIDATE`, the glslang GLSL gate, the Catch2 `layerCTest` build,
  clang-format targets, AddressSanitizer, BuildBuddy remote cache, rules_python
  coverage patches. Each is a separate later change.
- New platforms (Linux aarch64, Windows x86) or dropping Python 3.10.
- Publishing an sdist (`wheels.yaml` publishes wheels only today).
- The `distribution/` app build, which installs the wheel from PyPI.
- Version bump, tag and publication: the owner's decisions.

## Edge cases and failure behaviour

- An unsupported OS, CPU or Python version fails at analysis with a message
  (`select(..., no_match_error=...)`), never with a mislabelled wheel.
- NumPy headers come from the NumPy wheel of the target platform:
  `_numpyconfig.h` differs between platforms (`NPY_SIZEOF_LONG` is 4 on
  Windows), so OPP's single macOS-arm64 header set is not reused.
- The build reads nothing from `vcpkg_installed/`, `pre-built/`, Conda or
  Homebrew. Only the compiler toolchain and the system OpenGL (OpenGL.framework,
  `opengl32`, Mesa `libGL` in the manylinux image) come from the host.
- The Linux wheel is retagged by `auditwheel repair`, which also bundles
  `libgomp`; the Bazel target itself emits `linux_x86_64`.
- Shader sources are flattened at build time; no `#include` reaches the driver.

## Acceptance criteria

1. `wheels.yaml`, dispatched on the migration branch, builds all 20 wheels with
   Bazel; each passes `scripts/test_wheel.py` (both NumPy profiles) and the
   `release-integrity` job passes.
2. For CPython 3.12 on each of the four platforms, the member names of the Bazel
   wheel equal those of the PyPI 3.2.0.3 wheel, `*.dist-info/` excluded.
3. `bazel test //...` passes on a Windows workstation and on the four CI runners.
4. After cutover no build path references CMake, vcpkg, scikit-build or
   cibuildwheel, `pre-built/` is gone, and `pip install .` fails with the
   Bazel message.

## Decisions taken as defaults (confirm or change)

1. Keep the full 20-wheel matrix, macOS x86_64 included.
2. Port with CMake parity first; OPP's deltas come later.
3. NumPy headers pinned to 2.2.6, the runtime floor's series.
4. No remote cache; `setup-bazel`'s disk and repository caches only.
5. `pymake` stays the developer entry point.
6. CMake, vcpkg and `pre-built/` are deleted in this branch after criterion 1
   holds, not kept side by side.
