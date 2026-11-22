"""Runs the app's quick checks: ruff, ShellCheck and actionlint.

    bazel run //distribution:checks            # check
    bazel run //distribution:checks -- --fix   # also apply ruff's fixes

The tools come from pinned wheels (distribution/checks_requirements.in) and
run on the checkout: ruff on the Python files in distribution/, with its
pyproject.toml settings; ShellCheck on the shell scripts there; actionlint
on the repository's workflows, with ShellCheck on its PATH, so that it
also checks their run: scripts. All three run; the exit status is 1 if any
of them failed.
"""

import argparse
import os
import pathlib
import subprocess
import sys

from python.runfiles import runfiles


_APP = "distribution"
"""The app's folder, whose files ruff and ShellCheck check."""

_WORKFLOWS = ".github/workflows/"
"""The folder of the workflows actionlint checks."""

_SHELL_EXTENSIONS = (".sh", ".bash", ".ksh")
"""Shell script extensions; zsh is not one, as ShellCheck cannot read it."""

_SHELLS = frozenset({"sh", "bash", "dash", "ksh"})
"""Shebang interpreters of scripts ShellCheck reads."""


def shell_scripts(root: pathlib.Path, paths: list[str]) -> list[str]:
  """Selects the shell scripts among files, as pre-commit's hook did.

  Args:
    root: The folder the paths are relative to.
    paths: The files.

  Returns:
    The paths with a shell extension, or without one and with a sh, bash,
    dash or ksh shebang, sorted.
  """
  tmp_scripts = []
  for tmp_path in paths:
    tmp_suffix = pathlib.PurePosixPath(tmp_path).suffix
    if tmp_suffix in _SHELL_EXTENSIONS or (
      not tmp_suffix and _shell_shebang(root / tmp_path)
    ):
      tmp_scripts.append(tmp_path)
  return sorted(tmp_scripts)


def _shell_shebang(path: pathlib.Path) -> bool:
  """Tells whether a file starts with a sh, bash, dash or ksh shebang.

  Args:
    path: The file.

  Returns:
    Whether its interpreter, or the one env runs, is such a shell.
  """
  with open(path, "rb") as tmp_handle:
    tmp_line = tmp_handle.readline(200)
  if not tmp_line.startswith(b"#!"):
    return False
  tmp_words = tmp_line[2:].decode("utf-8", "replace").split()
  if tmp_words and tmp_words[0].endswith("/env"):
    tmp_words = tmp_words[1:]
  return bool(tmp_words) and tmp_words[0].rsplit("/", 1)[-1] in _SHELLS


def tool(name: str) -> pathlib.Path:
  """Finds one of the tools in the runfiles.

  Args:
    name: ruff, shellcheck or actionlint.

  Returns:
    The program's path.

  Raises:
    LookupError: No runfile is that program.
  """
  tmp_runfiles = runfiles.Create()
  for tmp_path in os.environ.get("CHECKS_TOOLS", "").split():
    tmp_file = pathlib.PurePosixPath(tmp_path)
    if tmp_file.parent.name == "bin" and tmp_file.stem == name:
      return pathlib.Path(tmp_runfiles.Rlocation(tmp_path))
  raise LookupError(f"{name} is not among the checks' runfiles")


def _tracked_files(root: pathlib.Path) -> list[str]:
  """Lists the files of the checkout, as paths relative to its root.

  Args:
    root: The checkout.

  Returns:
    git's tracked files; every file outside .git if git is missing or the
    folder is no checkout.
  """
  try:
    tmp_result = subprocess.run(
      ["git", "ls-files", "-z"],
      cwd=root,
      capture_output=True,
      check=True,
    )
    return [
      tmp_path.decode("utf-8")
      for tmp_path in tmp_result.stdout.split(b"\0")
      if tmp_path
    ]
  except (OSError, subprocess.CalledProcessError):
    return sorted(
      tmp_path.relative_to(root).as_posix()
      for tmp_path in root.rglob("*")
      if tmp_path.is_file() and ".git" not in tmp_path.relative_to(root).parts
    )


def _run(
  title: str,
  command: list[str],
  files: list[str],
  cwd: pathlib.Path,
  env: dict[str, str] | None = None,
) -> bool:
  """Runs one tool on files and prints what it reports.

  Args:
    title: The tool's name, for the summary line.
    command: The program and its options, before the files.
    files: The files to check, relative to cwd.
    cwd: The folder to run in.
    env: The environment; the current one if None.

  Returns:
    Whether the tool passed.
  """
  if not files:
    print(f"{title}: no files to check")
    return True
  tmp_result = subprocess.run(
    [*command, *files],
    cwd=cwd,
    env=env,
    capture_output=True,
    text=True,
    check=False,
  )
  tmp_output = (tmp_result.stdout + tmp_result.stderr).strip()
  if tmp_output:
    print(tmp_output)
  tmp_passed = tmp_result.returncode == 0
  print(
    f"{title}: {len(files)} files, {'passed' if tmp_passed else 'FAILED'}"
  )
  return tmp_passed


def main(argv: list[str]) -> int:
  """Runs ruff, ShellCheck and actionlint on the checkout.

  Args:
    argv: The command-line arguments, without the program name.

  Returns:
    0 if all three passed, else 1.
  """
  tmp_parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
  tmp_parser.add_argument(
    "--fix", action="store_true", help="apply ruff's fixes"
  )
  tmp_parser.add_argument(
    "--root",
    default=os.environ.get("BUILD_WORKSPACE_DIRECTORY", "."),
    help="the checkout (default: the workspace bazel run started in)",
  )
  tmp_arguments = tmp_parser.parse_args(argv)
  tmp_root = pathlib.Path(tmp_arguments.root).resolve()
  tmp_files = _tracked_files(tmp_root)
  tmp_app_files = [
    tmp_path.removeprefix(_APP + "/")
    for tmp_path in tmp_files
    if tmp_path.startswith(_APP + "/")
  ]
  tmp_app = tmp_root / _APP
  tmp_shellcheck = tool("shellcheck")
  tmp_env = dict(os.environ)
  tmp_env["PATH"] = os.pathsep.join(
    [str(tmp_shellcheck.parent), tmp_env.get("PATH", "")]
  )
  tmp_results = [
    _run(
      "ruff",
      [str(tool("ruff")), "check", "--force-exclude"]
      + (["--fix"] if tmp_arguments.fix else []),
      [tmp_path for tmp_path in tmp_app_files if tmp_path.endswith(".py")],
      tmp_app,
    ),
    _run(
      "shellcheck",
      [str(tmp_shellcheck)],
      shell_scripts(tmp_app, tmp_app_files),
      tmp_app,
    ),
    _run(
      "actionlint",
      [str(tool("actionlint"))],
      [
        tmp_path
        for tmp_path in tmp_files
        if tmp_path.startswith(_WORKFLOWS)
        and tmp_path.endswith((".yaml", ".yml"))
      ],
      tmp_root,
      tmp_env,
    ),
  ]
  return 0 if all(tmp_results) else 1


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
