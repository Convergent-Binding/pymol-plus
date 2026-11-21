"""A PEP 517 backend that refuses to build, with an explanation.

pymol-open-source-whl's wheels are built by Bazel. Deleting pyproject.toml's
[build-system] table would be worse than this: pip would fall back to
setuptools and build the [project] metadata into a pure-Python wheel with no
compiled extensions, which installs cleanly and then fails at
`import pymol._cmd`. So `pip install .` fails at once and says why.

The hooks below are the PEP 517 and PEP 660 surface pip probes; every one
raises.
"""

_MESSAGE = """\
pymol-open-source-whl is not built with pip.

Its wheels contain compiled extensions (pymol._cmd, chempy.champ._champ) that
Bazel builds, together with the runtime data tree and the right platform, ABI
and Python tags. A pip-driven build could only produce a wheel without them,
which would install and then fail at `import pymol._cmd`.

Build a wheel for this platform with Bazel instead:

    bazel build //tools/bazel/wheel:wheel

Select the Python version with, for example:

    --@rules_python//python/config_settings:python_version=3.13

The built wheel installs with pip in the normal way:

    pip install bazel-bin/tools/bazel/wheel/pymol_open_source_whl-*.whl

See "Build wheel file" in README.md.\
"""


def _refuse(*_args, **_kwargs):
  raise RuntimeError(_MESSAGE)


# PEP 517 mandatory hooks.
build_wheel = _refuse
build_sdist = _refuse

# PEP 517 optional hooks, so pip's probing fails here with the message above.
get_requires_for_build_wheel = _refuse
get_requires_for_build_sdist = _refuse
prepare_metadata_for_build_wheel = _refuse

# PEP 660 (editable installs), so `pip install -e .` fails the same way.
build_editable = _refuse
get_requires_for_build_editable = _refuse
prepare_metadata_for_build_editable = _refuse
