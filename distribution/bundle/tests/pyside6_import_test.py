"""The app's packages import from the merged site-packages on Python 3.13.

PySide6's compiled modules load shiboken6 and the Qt libraries relative to
their own directory, which works only when the wheels are real siblings in
one site-packages (//tools/bazel:wheel_merge.bzl).
"""

import importlib
import unittest


_OTHER_PACKAGES = ("Bio", "msgpack", "numpy", "Pmw", "rules", "simplejson")
"""The app's packages besides PySide6 and shiboken6, by import name."""


class AppPackagesImportTest(unittest.TestCase):
  """Imports each package the app bundles from the merged tree."""

  def test_pyside6_loads_qt_6_9(self) -> None:
    """PySide6's QtCore loads, with the Qt 6.9 its pin names."""
    tmp_qt_core = importlib.import_module("PySide6.QtCore")

    tmp_version = tmp_qt_core.qVersion()
    self.assertTrue(tmp_version.startswith("6.9."), tmp_version)

  def test_other_packages_import(self) -> None:
    """The other packages import; numpy is the locked version."""
    for tmp_name in _OTHER_PACKAGES:
      with self.subTest(package=tmp_name):
        importlib.import_module(tmp_name)

    self.assertEqual(importlib.import_module("numpy").__version__, "2.5.4")


if __name__ == "__main__":
  unittest.main()
