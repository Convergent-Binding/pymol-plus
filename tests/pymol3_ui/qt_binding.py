# SPDX-License-Identifier: BSD-3-Clause
"""The Qt binding for the pymol3 GUI tests, or a skip without one.

Where the binding is part of the test setup, as under Bazel, the variable
``PYMOL3_TESTS_REQUIRE_QT`` is ``1`` and a binding that fails to load fails
the tests instead of skipping them unnoticed.
"""

import importlib
import os
import types

import pytest

REQUIRE_QT_VARIABLE = "PYMOL3_TESTS_REQUIRE_QT"
"""The environment variable that turns a missing Qt binding into a failure."""


def qt_required() -> bool:
  """Tells whether a missing Qt binding fails the tests.

  Returns:
    True when ``PYMOL3_TESTS_REQUIRE_QT`` is ``1``, False otherwise.
  """
  return os.environ.get(REQUIRE_QT_VARIABLE) == "1"


def import_qt() -> types.ModuleType:
  """Imports ``pymol.Qt``, the Qt binding PyMOL found.

  Returns:
    The ``pymol.Qt`` module.

  Raises:
    ImportError: No binding loads and ``PYMOL3_TESTS_REQUIRE_QT`` is ``1``;
      without it the calling test or module is skipped instead.
  """
  if qt_required():
    return importlib.import_module("pymol.Qt")
  return pytest.importorskip("pymol.Qt", exc_type=ImportError)
