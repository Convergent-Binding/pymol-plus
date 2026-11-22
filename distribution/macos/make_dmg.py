"""Writes the DMG of the signed app with create-dmg; the tool of macos_dmg.

The window layout is the one build_dmg.sh used. The DMG's architecture label
must match the app's own: it is checked against PyMOL's _cmd extension, as
build_dmg.sh did with lipo. create-dmg copies a source folder into a disk
image and then writes there, so it gets a writable copy of the app, alone in
a staging folder: Bazel leaves the signed app read-only. Permissions are not
part of the code signature. create-dmg sometimes fails on CI runners with
"Resource busy"; only that failure is tried again, up to three times.
"""

import argparse
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import time

import macho


_LABELS = {"AppleSilicon": "arm64", "Intel": "x86_64"}
"""The DMG name's architecture labels and the architecture each means."""

_ATTEMPTS = 3
"""How often create-dmg is tried."""


def cmd_architectures(app: pathlib.Path) -> list[str]:
  """Reads the architectures of PyMOL's _cmd extension in the app.

  Args:
    app: The .app.

  Returns:
    The architectures of the one _cmd file.

  Raises:
    FileNotFoundError: The app holds no _cmd extension, or more than one.
  """
  tmp_found = sorted(
    (app / "Contents" / "Resources" / "runtime" / "lib").glob(
      "python3.*/site-packages/pymol/_cmd.*.so"
    )
  )
  if len(tmp_found) != 1:
    raise FileNotFoundError(
      f"expected one pymol/_cmd.*.so in {app}, found {tmp_found}"
    )
  return macho.architectures(tmp_found[0])


def stage_app(app: pathlib.Path, staging: pathlib.Path) -> pathlib.Path:
  """Copies the app, writable, into a staging folder of its own.

  Args:
    app: The signed .app.
    staging: The folder to create; it holds only the copy.

  Returns:
    The copy's path.
  """
  tmp_copy = staging / app.name
  shutil.copytree(app, tmp_copy, symlinks=True)
  for tmp_path in [tmp_copy, *tmp_copy.rglob("*")]:
    if not tmp_path.is_symlink():
      tmp_path.chmod(tmp_path.stat().st_mode | stat.S_IWUSR)
  return tmp_copy


def main(argv: list[str]) -> int:
  """Writes the DMG.

  Args:
    argv: --app <signed .app>, --create-dmg <script>, --background <.svg>,
      --label AppleSilicon|Intel, --out <.dmg>.

  Returns:
    0 when the DMG is written, 1 otherwise.
  """
  tmp_parser = argparse.ArgumentParser()
  for tmp_name in ("--app", "--create-dmg", "--background", "--out"):
    tmp_parser.add_argument(tmp_name, required=True)
  tmp_parser.add_argument("--label", required=True, choices=tuple(_LABELS))
  tmp_arguments = tmp_parser.parse_args(argv)
  tmp_app = pathlib.Path(tmp_arguments.app)
  tmp_out = pathlib.Path(tmp_arguments.out).resolve()
  tmp_architectures = cmd_architectures(tmp_app)
  if tmp_architectures != [_LABELS[tmp_arguments.label]]:
    print(
      f"make_dmg: PyMOL's _cmd is built for {tmp_architectures}, "
      f"not for the {tmp_arguments.label} DMG",
      file=sys.stderr,
    )
    return 1
  tmp_volume = tmp_out.stem
  tmp_staging = pathlib.Path(tempfile.mkdtemp(prefix="pymol-dmg-"))
  try:
    return _write_dmg(
      stage_app(tmp_app, tmp_staging / "source"),
      tmp_arguments,
      tmp_volume,
      tmp_out,
    )
  finally:
    shutil.rmtree(tmp_staging, ignore_errors=True)


def _write_dmg(
  app: pathlib.Path,
  arguments: argparse.Namespace,
  volume: str,
  out: pathlib.Path,
) -> int:
  """Runs create-dmg on the staged app's folder.

  Args:
    app: The staged, writable .app.
    arguments: The command line, for the create-dmg script and background.
    volume: The disk image's volume name.
    out: The DMG to write.

  Returns:
    0 when the DMG is written, 1 otherwise.
  """
  tmp_app = app
  tmp_arguments = arguments
  tmp_volume = volume
  tmp_out = out
  tmp_command = [
    "bash",
    tmp_arguments.create_dmg,
    "--volname",
    tmp_volume,
    "--background",
    tmp_arguments.background,
    "--window-pos",
    "200",
    "120",
    "--window-size",
    "660",
    "400",
    "--icon-size",
    "100",
    "--icon",
    tmp_app.name,
    "160",
    "185",
    "--app-drop-link",
    "500",
    "185",
    str(tmp_out),
    str(tmp_app.parent),
  ]
  for tmp_attempt in range(1, _ATTEMPTS + 1):
    subprocess.run(
      ["hdiutil", "detach", f"/Volumes/{tmp_volume}"],
      capture_output=True,
      check=False,
    )
    tmp_out.unlink(missing_ok=True)
    for tmp_partial in tmp_out.parent.glob("rw.*.dmg"):
      tmp_partial.unlink()
    tmp_result = subprocess.run(
      tmp_command,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      text=True,
      check=False,
    )
    print(tmp_result.stdout, end="")
    if tmp_result.returncode == 0:
      return 0
    print(f"make_dmg: create-dmg attempt {tmp_attempt} failed", file=sys.stderr)
    if "Resource busy" not in tmp_result.stdout:
      return 1
    if tmp_attempt < _ATTEMPTS:
      time.sleep(10)
  return 1


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
