"""create_buildinfo() takes its git SHA and date from the caller when given.

The Bazel action that writes PyMOLBuildInfo.h passes both, because neither a
`git` call nor the wall clock is a declared, cacheable action input. The
function must then not start `git` at all.
"""

import pathlib
import tempfile
import unittest
from unittest import mock

import create_generated_files


class CreateBuildinfoTest(unittest.TestCase):
  """PyMOLBuildInfo.h carries the given SHA and date without running git."""

  def test_given_sha_and_date_are_written_without_git(self) -> None:
    with tempfile.TemporaryDirectory() as out, mock.patch.object(
        create_generated_files, "Popen", side_effect=AssertionError("git ran")
    ):
      create_generated_files.create_buildinfo(
          out, git_sha="abc123", build_date=7
      )
      header = (pathlib.Path(out) / "PyMOLBuildInfo.h").read_text()
    self.assertIn("#define _PyMOL_BUILD_DATE 7", header)
    self.assertIn('#define _PYMOL_BUILD_GIT_SHA "abc123"', header)


if __name__ == "__main__":
  unittest.main()
