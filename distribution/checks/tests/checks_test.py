"""checks finds its tools and runs them on a tree, finding each kind of problem.

The fixture trees are built here. Most have no git, so the checker takes
its file walk; one is a git checkout, for `git ls-files`.
"""

import contextlib
import io
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import checks


_RUFF_SETTINGS = (
  "[tool.ruff]\n"
  "indent-width = 2\n"
  'extend-exclude = ["edited"]\n'
  "[tool.ruff.lint]\n"
  'extend-select = ["I"]\n'
  "[tool.ruff.lint.isort]\n"
  "lines-after-imports = 2\n"
)
"""The app's ruff settings (distribution/pyproject.toml): edited/ excluded."""


class ShellScriptsTest(unittest.TestCase):
  """Selects the files pre-commit's shellcheck hook selected."""

  def setUp(self) -> None:
    """Creates the temporary folder."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)

  def tearDown(self) -> None:
    """Removes the temporary folder."""
    self._dir.cleanup()

  def _file(self, name: str, text: str) -> str:
    """Writes a file.

    Args:
      name: Its path in the folder.
      text: Its content.

    Returns:
      The path, as given.
    """
    (self.root / name).write_text(text, encoding="utf-8", newline="\n")
    return name

  def test_extensions_and_shebangs(self) -> None:
    """.sh, .bash and sh or bash shebangs count; zsh and Python do not."""
    tmp_paths = [
      self._file("a.sh", "echo a\n"),
      self._file("b.bash", "echo b\n"),
      self._file("c", "#!/bin/sh\necho c\n"),
      self._file("d", "#!/usr/bin/env bash\necho d\n"),
      self._file("e.zsh", "#!/bin/zsh\necho e\n"),
      self._file("f", "#!/bin/zsh\necho f\n"),
      self._file("g.py", "#!/usr/bin/env python3\n"),
      self._file("h.txt", "text\n"),
    ]

    tmp_scripts = checks.shell_scripts(self.root, tmp_paths)

    self.assertEqual(tmp_scripts, ["a.sh", "b.bash", "c", "d"])


class ToolsTest(unittest.TestCase):
  """Finds each tool in the runfiles."""

  def test_each_tool_runs(self) -> None:
    """ruff, shellcheck and actionlint answer --version."""
    for tmp_name in ("ruff", "shellcheck", "actionlint"):
      with self.subTest(tool=tmp_name):
        tmp_result = subprocess.run(
          [str(checks.tool(tmp_name)), "--version"],
          capture_output=True,
          check=False,
        )

        self.assertEqual(tmp_result.returncode, 0, tmp_result.stderr)


class MainTest(unittest.TestCase):
  """Runs the three checks on fixture trees."""

  def setUp(self) -> None:
    """Writes a tree with one problem for each tool."""
    self._dir = tempfile.TemporaryDirectory()
    self.root = pathlib.Path(self._dir.name)
    (self.root / "distribution" / "edited").mkdir(parents=True)
    (self.root / ".github" / "workflows").mkdir(parents=True)
    self._write("distribution/pyproject.toml", _RUFF_SETTINGS)
    self._write("distribution/edited/upstream.py", "import os\n")
    self._write("distribution/tool.py", "import os\n")
    self._write("distribution/run.sh", '#!/bin/sh\necho $1\n')
    self._write(
      ".github/workflows/ci.yaml",
      "on: push\n"
      "jobs:\n"
      "  test:\n"
      "    runs-on: ubuntu-latest\n"
      "    steps:\n"
      "      - run: echo $HOME\n",
    )

  def tearDown(self) -> None:
    """Removes the temporary folder."""
    self._dir.cleanup()

  def _write(self, name: str, text: str) -> None:
    """Writes a file of the tree.

    Args:
      name: Its path from the root.
      text: Its content.
    """
    (self.root / name).write_text(text, encoding="utf-8", newline="\n")

  def _main(self) -> tuple[int, str]:
    """Runs the checks on the tree.

    Returns:
      The exit status and what the checks printed.
    """
    tmp_output = io.StringIO()
    with contextlib.redirect_stdout(tmp_output):
      tmp_status = checks.main(["--root", str(self.root)])
    return tmp_status, tmp_output.getvalue()

  def test_each_problem_found(self) -> None:
    """Each tool fails and names its file; edited/ stays unchecked."""
    tmp_status, tmp_output = self._main()

    self.assertEqual(tmp_status, 1)
    self.assertIn("tool.py", tmp_output)
    self.assertIn("run.sh", tmp_output)
    self.assertIn("ci.yaml", tmp_output)
    self.assertNotIn("upstream.py", tmp_output)

  def _fix_problems(self) -> None:
    """Rewrites the tree's three problem files without their problems."""
    self._write("distribution/tool.py", "import os\n\n\nprint(os.sep)\n")
    self._write("distribution/run.sh", '#!/bin/sh\necho "$1"\n')
    self._write(
      ".github/workflows/ci.yaml",
      "on: push\n"
      "jobs:\n"
      "  test:\n"
      "    runs-on: ubuntu-latest\n"
      "    steps:\n"
      '      - run: echo "$HOME"\n',
    )

  def _git(self, *arguments: str) -> None:
    """Runs git in the tree.

    Args:
      *arguments: git's arguments.
    """
    subprocess.run(
      [
        "git",
        "-c",
        "user.name=checks",
        "-c",
        "user.email=checks@example.invalid",
        "-c",
        "commit.gpgsign=false",
        *arguments,
      ],
      cwd=self.root,
      capture_output=True,
      check=True,
    )

  def test_clean_tree_passes(self) -> None:
    """Without the problems every check passes."""
    self._fix_problems()

    tmp_status, tmp_output = self._main()

    self.assertEqual(tmp_status, 0, tmp_output)

  @unittest.skipUnless(shutil.which("git"), "needs git")
  def test_git_checkout_from_a_subfolder(self) -> None:
    """Started below the top, it checks the tracked files that still exist.

    Untracked files and tracked ones deleted from the disk stay unchecked.
    """
    self._fix_problems()
    self._write("distribution/gone.py", "import os\n")
    self._write("distribution/gone", '#!/bin/sh\necho "$1"\n')
    self._git("init", "-q")
    self._git("add", "-A")
    self._git("commit", "-q", "-m", "fixture")
    (self.root / "distribution" / "gone.py").unlink()
    (self.root / "distribution" / "gone").unlink()
    self._write("distribution/untracked.py", "import os\n")
    self._write("distribution/untracked.sh", "echo $1\n")

    tmp_output = io.StringIO()
    with contextlib.redirect_stdout(tmp_output):
      tmp_status = checks.main(["--root", str(self.root / "distribution")])

    self.assertEqual(tmp_status, 0, tmp_output.getvalue())
    self.assertIn("ruff: 2 files", tmp_output.getvalue())
    self.assertIn("shellcheck: 1 files", tmp_output.getvalue())
    self.assertIn("actionlint: 1 files", tmp_output.getvalue())

  def test_nothing_to_check_fails(self) -> None:
    """A tree with no files for the tools fails instead of passing."""
    with tempfile.TemporaryDirectory() as tmp_empty:
      tmp_output = io.StringIO()
      with contextlib.redirect_stdout(tmp_output):
        tmp_status = checks.main(["--root", tmp_empty])

    self.assertEqual(tmp_status, 1)
    self.assertIn("no files to check", tmp_output.getvalue())

  def test_fix_applies_ruff_fixes(self) -> None:
    """--fix removes the unused import."""
    tmp_output = io.StringIO()
    with contextlib.redirect_stdout(tmp_output):
      checks.main(["--root", str(self.root), "--fix"])

    self.assertNotIn(
      "import os",
      (self.root / "distribution" / "tool.py").read_text(encoding="utf-8"),
    )


if __name__ == "__main__":
  unittest.main()
