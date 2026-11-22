"""Runs Inno Setup's compiler on setup.iss for the app folder.

The action tool of //distribution/windows:installer. ISCC runs from its own
install folder, where it loads its compiler DLLs and the files setup.iss
names with `compiler:`. It resolves the script's relative paths against the
script's folder, so the app and output folders are handed to it as absolute
paths. Inside Bazel's output tree the app's deepest files pass Windows'
classic 260-character path limit, so ISCC compiles a copy of the app at a
short temporary path.
"""

import argparse
import contextlib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator


def long_path(path: pathlib.Path) -> pathlib.Path:
  """Makes a path usable beyond 260 characters on Windows.

  Args:
    path: A path.

  Returns:
    On Windows the absolute path with the `\\\\?\\` prefix, which lifts the
    limit for the file functions Python calls; elsewhere the path unchanged.
  """
  if sys.platform != "win32":
    return path
  tmp_text = os.path.abspath(path)
  if tmp_text.startswith("\\\\?\\"):
    return pathlib.Path(tmp_text)
  return pathlib.Path("\\\\?\\" + tmp_text)


@contextlib.contextmanager
def short_copy(app: pathlib.Path) -> Iterator[pathlib.Path]:
  """Copies the app folder to a short temporary path.

  Args:
    app: The app folder.

  Yields:
    The copy's path, without the long-path prefix, for ISCC. The copy is
    removed afterwards.
  """
  tmp_folder = pathlib.Path(tempfile.mkdtemp(prefix="pymol-app-"))
  tmp_copy = tmp_folder / "app"
  try:
    shutil.copytree(long_path(app), long_path(tmp_copy))
    yield tmp_copy
  finally:
    shutil.rmtree(long_path(tmp_folder), ignore_errors=True)


def main(argv: list[str]) -> int:
  """Compiles the installer.

  Args:
    argv: --iscc <absolute path of ISCC.exe>, --script <setup.iss>,
      --app <app folder>, --version <app version>, --out <installer file>.

  Returns:
    ISCC's exit status, or 1 when it wrote no installer of the expected name.
  """
  tmp_parser = argparse.ArgumentParser()
  for tmp_name in ("--iscc", "--script", "--app", "--version", "--out"):
    tmp_parser.add_argument(tmp_name, required=True)
  tmp_arguments = tmp_parser.parse_args(argv)
  tmp_out = pathlib.Path(tmp_arguments.out).resolve()
  with short_copy(pathlib.Path(tmp_arguments.app)) as tmp_app:
    tmp_result = subprocess.run(
      [
        tmp_arguments.iscc,
        "/Q",
        f"/DMyAppVersion={tmp_arguments.version}",
        f"/DAppSourceDir={tmp_app}",
        f"/O{tmp_out.parent}",
        f"/F{tmp_out.stem}",
        str(pathlib.Path(tmp_arguments.script).resolve()),
      ],
      check=False,
    )
  if tmp_result.returncode != 0:
    return tmp_result.returncode
  if not tmp_out.is_file():
    print(f"run_iscc: ISCC wrote no {tmp_out.name}", file=sys.stderr)
    return 1
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
