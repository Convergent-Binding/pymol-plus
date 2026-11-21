"""`pip install .` fails at once and says the wheel is built with Bazel.

Without a [build-system] table pip would fall back to setuptools and build
pyproject.toml's metadata into a pure-Python wheel without _cmd, which installs
and then fails at `import pymol._cmd`. The in-tree backend refuses every hook
pip calls instead.
"""

import unittest

import pymol_build_backend

_COMMAND = "bazel build //tools/bazel/wheel:wheel"


class BuildBackendTest(unittest.TestCase):
  """Every PEP 517 and PEP 660 hook raises with the Bazel command."""

  def test_every_hook_refuses_with_the_bazel_command(self) -> None:
    hooks = {
        "build_wheel": ("out",),
        "build_sdist": ("out",),
        "build_editable": ("out",),
        "get_requires_for_build_wheel": (),
        "get_requires_for_build_sdist": (),
        "get_requires_for_build_editable": (),
        "prepare_metadata_for_build_wheel": ("out",),
        "prepare_metadata_for_build_editable": ("out",),
    }
    for name, args in hooks.items():
      with self.subTest(hook=name):
        with self.assertRaises(RuntimeError) as raised:
          getattr(pymol_build_backend, name)(*args)
        self.assertIn(_COMMAND, str(raised.exception))


if __name__ == "__main__":
  unittest.main()
