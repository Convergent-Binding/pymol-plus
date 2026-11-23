"""Signs a copy of PyMOL-Open-Source.app ad hoc; the tool of macos_signed_app.

Bazel's outputs are read-only, so the app is copied to the action's output
folder and made writable first. An ad-hoc signature (`codesign --sign -`)
keeps Gatekeeper from calling the downloaded app damaged.
"""

import argparse
import pathlib
import shutil
import stat
import subprocess
import sys


def _make_writable(folder: pathlib.Path) -> None:
  """Gives the owner write access to every file and folder below a folder.

  Args:
    folder: The folder.
  """
  for tmp_path in [folder, *folder.rglob("*")]:
    tmp_path.chmod(tmp_path.stat().st_mode | stat.S_IWUSR)


def main(argv: list[str]) -> int:
  """Copies, signs and verifies the app.

  Args:
    argv: --app <unsigned .app> and --out <signed .app>.

  Returns:
    codesign's exit status: 0 when the app is signed and verified.
  """
  tmp_parser = argparse.ArgumentParser()
  tmp_parser.add_argument("--app", required=True)
  tmp_parser.add_argument("--out", required=True)
  tmp_arguments = tmp_parser.parse_args(argv)
  tmp_out = pathlib.Path(tmp_arguments.out)
  shutil.copytree(tmp_arguments.app, tmp_out, symlinks=True, dirs_exist_ok=True)
  _make_writable(tmp_out)
  for tmp_command in (
    ["codesign", "--force", "--deep", "--sign", "-", str(tmp_out)],
    ["codesign", "--verify", "--deep", "--strict", str(tmp_out)],
  ):
    tmp_result = subprocess.run(tmp_command, check=False)
    if tmp_result.returncode != 0:
      print(f"sign_app: {' '.join(tmp_command)} failed", file=sys.stderr)
      return tmp_result.returncode
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
