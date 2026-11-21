"""Shared compile and link settings for PyMOL's native sources.

Mirrors CMakeLists.txt (as of the Bazel migration's base, integrate-setup
2311f027) exactly: `ALL_COMPILER_DEFS`, `ALL_COMPILER_ARGS` and the
`OS_SPECIFIC_*` lists of its WIN32, APPLE and UNIX branches. Ported from
open-protein-platform's tools/bazel/pymol_native.bzl, which dropped
`_PYMOL_NO_MSGPACKC` and `PYMOL_CURVE_VALIDATE`; both stay here so the Bazel
wheels behave like the CMake ones. Changing either is a separate decision.

//:_cmd.so and the molfile plugin library it depends on both need the same
defines -- a cc_library's `defines` reach its consumers, not the other way
round -- so both load these lists.
"""

PYMOL_COMMON_DEFINES = [
    "_PYMOL_LIBPNG",
    "_PYMOL_FREETYPE",
    "_PYMOL_VMD_PLUGINS",
    "_PYMOL_NO_MSGPACKC",
    "_PYMOL_NO_MAIN",
    "_PYMOL_NUMPY",
]

# CMake's OS_SPECIFIC_COMPILER_DEFS per platform.
PYMOL_PLATFORM_DEFINES = select({
    "@platforms//os:macos": [
        "_HAVE_LIBXML",
        "PYMOL_CURVE_VALIDATE",
        "_PYMOL_OSX",
    ],
    "@platforms//os:windows": [
        "WIN32",
        "PYMOL_OPENMP",
        "_HAVE_LIBXML",
        # The BCR glew sets GLEW_STATIC only in its own `local_defines`, which
        # do not reach consumers. Without it GL/glew.h declares every function
        # __declspec(dllimport) and the link looks for a GLEW DLL's import
        # library (LNK2019 on every __imp___glew* symbol).
        "GLEW_STATIC",
    ],
    "//conditions:default": [  # Linux (CMake's `elseif(UNIX)` branch)
        "_HAVE_LIBXML",
    ],
})

PYMOL_DEFINES = PYMOL_COMMON_DEFINES + PYMOL_PLATFORM_DEFINES

# CMake's ALL_COMPILER_ARGS per platform, for C and C++ alike, as CMake's
# target_compile_options applied them to the whole target. The C++ standard
# is in PYMOL_CXXOPTS.
PYMOL_COPTS = select({
    "@platforms//os:macos": [
        "-Werror=return-type",
        "-Wunused-variable",
        "-Wno-switch",
        "-Wno-narrowing",
        "-Wno-char-subscripts",
        "-O3",
        "-fno-strict-aliasing",
    ],
    "@platforms//os:windows": [
        "/MP",
        "/openmp",
    ],
    "//conditions:default": [  # Linux
        "-fopenmp",
    ],
})

# C++17, as CMake's `cxx_std_17` compile feature. MSVC spells it /std:c++17
# and ignores -std=c++17 with a warning, keeping its C++14 default.
PYMOL_CXXOPTS = select({
    "@platforms//os:windows": ["/std:c++17"],
    "//conditions:default": ["-std=c++17"],
})

# CMake's OS_SPECIFIC_LINKER_OPTIONS and system libraries, plus what each
# platform's convention for Python extensions needs: macOS leaves Py* symbols
# undefined until load time; Linux's linker allows undefined symbols in a
# shared object by default; Windows extensions are DLLs that cannot link with
# unresolved symbols, so they get the Python import library through
# PYMOL_PY_LINK_DEPS instead.
PYMOL_PLATFORM_LINKOPTS = select({
    "@platforms//os:macos": [
        "-framework",
        "OpenGL",
        "-Wl,-undefined,dynamic_lookup",
    ],
    "@platforms//os:windows": [
        "/NODEFAULTLIB:nafxcw.lib",
        "ws2_32.lib",
        "advapi32.lib",
        "opengl32.lib",
    ],
    "//conditions:default": [  # Linux
        "-lGL",
        "-fopenmp",
    ],
})

# The Python import library Windows extensions link against; see
# PYMOL_PLATFORM_LINKOPTS.
PYMOL_PY_LINK_DEPS = select({
    "@platforms//os:windows": ["@rules_python//python/cc:current_py_cc_libs"],
    "//conditions:default": [],
})
