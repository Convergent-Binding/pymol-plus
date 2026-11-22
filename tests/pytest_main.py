"""Runs pytest on the tests beside this file; extra arguments go to pytest.

    bazel test //tests                                # all tests
    bazel test //tests --test_arg=-k --test_arg=undo  # a selection
"""

import pathlib
import sys

import pytest

if __name__ == "__main__":
  tmp_tests = str(pathlib.Path(__file__).parent)
  sys.exit(
    pytest.main(
      [
        tmp_tests,
        # pytest lists every folder from its root down to the tests; the
        # repository's root on Windows, the execroot, holds other tests'
        # temporary files, which can vanish while it lists them.
        f"--rootdir={tmp_tests}",
        # The runfiles tree is read-only; pytest's cache would write into it.
        "-p",
        "no:cacheprovider",
        *sys.argv[1:],
      ]
    )
  )
