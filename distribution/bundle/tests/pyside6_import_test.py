"""The app's packages import from the merged site-packages on Python 3.13.

PySide6's compiled modules load shiboken6 and the Qt libraries relative to
their own directory, which works only when the wheels are real siblings in
one site-packages (//tools/bazel:wheel_merge.bzl).
"""

import unittest


class AppPackagesImportTest(unittest.TestCase):

  def test_pyside6_loads_qt_6_9(self) -> None:
    from PySide6 import QtCore  # pylint: disable=import-outside-toplevel

    self.assertTrue(QtCore.qVersion().startswith("6.9."), QtCore.qVersion())

  def test_other_packages_import(self) -> None:
    import Bio  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import
    import msgpack  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import
    import numpy  # pylint: disable=import-outside-toplevel
    import Pmw  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import
    import rules  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import
    import simplejson  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import

    self.assertEqual(numpy.__version__, "2.5.4")


if __name__ == "__main__":
  unittest.main()
