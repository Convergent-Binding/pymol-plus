"""Runs pytest on the tests beside this file; extra arguments go to pytest.

    bazel test //tests                                # all tests
    bazel test //tests --test_arg=-k --test_arg=undo  # a selection
"""

import pathlib
import sys

import pytest

if __name__ == "__main__":
  sys.exit(
    pytest.main(
      [
        str(pathlib.Path(__file__).parent),
        # The runfiles tree is read-only; pytest's cache would write into it.
        "-p",
        "no:cacheprovider",
        *sys.argv[1:],
      ]
    )
  )
