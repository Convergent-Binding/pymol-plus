"""Wheel tags and SOABI fragments derived from the selected Python version.

Writing `cp312` or `cpython-312` by hand in the wheel and staging targets
would have to be repeated for every Python version, and getting one wrong does
not fail the build: it produces a wheel whose tag or extension filename
disagrees with the interpreter it was compiled for, which pip installs and
which then fails at `import pymol._cmd` (open-protein-platform hit exactly this,
three times, before deriving them here).

Deriving both from `@rules_python//python/config_settings:is_python_*` means
the tag follows whatever `--@rules_python//python/config_settings:python_version`
the invocation selected, so a matrix build cannot mislabel a cell.

SUPPORTED_PYTHON_VERSIONS is the single list to edit when a version is added or
dropped; it must stay in step with MODULE.bazel's `python.toolchain()` calls and
pyproject.toml's `requires-python`.
"""

SUPPORTED_PYTHON_VERSIONS = [
    "3.10",
    "3.11",
    "3.12",
    "3.13",
    "3.14",
]

_NO_MATCH = (
    "No supported Python version selected. pymol-open-source-whl builds wheels for " +
    ", ".join(SUPPORTED_PYTHON_VERSIONS) +
    "; pass --@rules_python//python/config_settings:python_version=<version>, " +
    "or add the version to SUPPORTED_PYTHON_VERSIONS in tools/bazel/py_tags.bzl " +
    "and register a toolchain for it in MODULE.bazel."
)

def _setting(version):
    return "@rules_python//python/config_settings:is_python_" + version

def _nodot(version):
    return version.replace(".", "")

def python_tag():
    """The wheel's python_tag/abi tag, e.g. "cp312"."""
    return select(
        {_setting(v): "cp" + _nodot(v) for v in SUPPORTED_PYTHON_VERSIONS},
        no_match_error = _NO_MATCH,
    )

def cpython_soabi_prefix():
    """The interpreter half of an extension module's SOABI, e.g. "cpython-312".

    The remainder of the SOABI is platform-specific and belongs at the call
    site: "-darwin" on macOS (no architecture in it), "-<cpu>-linux-gnu" on
    Linux (architecture included, which is why the Linux staging targets also
    select() on @platforms//cpu).
    """
    return select(
        {_setting(v): "cpython-" + _nodot(v) for v in SUPPORTED_PYTHON_VERSIONS},
        no_match_error = _NO_MATCH,
    )
