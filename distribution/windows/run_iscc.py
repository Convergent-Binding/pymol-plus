"""Runs Inno Setup's compiler on setup.iss for the app folder.

The action tool of //distribution/windows:installer. ISCC resolves the
script's relative paths against the script's own folder, so the app folder
and the output folder are handed to it as absolute paths.
"""

import argparse
import pathlib
import subprocess
import sys


def main(argv: list[str]) -> int:
  """Compiles the installer.

  Args:
    argv: --iscc <ISCC.exe>, --script <setup.iss>, --app <app folder>,
      --version <app version>, --out <installer file>.

  Returns:
    ISCC's exit status, or 1 when it wrote no installer of the expected name.
  """
  tmp_parser = argparse.ArgumentParser()
  for tmp_name in ("--iscc", "--script", "--app", "--version", "--out"):
    tmp_parser.add_argument(tmp_name, required=True)
  tmp_arguments = tmp_parser.parse_args(argv)
  tmp_out = pathlib.Path(tmp_arguments.out).resolve()
  tmp_result = subprocess.run(
    [
      tmp_arguments.iscc,
      "/Q",
      f"/DMyAppVersion={tmp_arguments.version}",
      f"/DAppSourceDir={pathlib.Path(tmp_arguments.app).resolve()}",
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
