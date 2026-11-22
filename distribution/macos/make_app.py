"""Wraps the app folder into PyMOL-Open-Source.app; the tool of macos_app.

  PyMOL-Open-Source.app/Contents/
    Info.plist              os_specific/macos/Info.plist, version stamped
    PkgInfo                 APPL????
    MacOS/PyMOL-Open-Source the launcher, which finds the runtime in Resources
    Resources/              the app folder without its launcher, and icon.icns

Universal (arm64 and x86_64) binaries, such as PySide6's, are cut down to
the target's architecture, as `ditto --arch` did for the cx_Freeze app: each
DMG is for one architecture, and the slices keep their code signatures.
"""

import argparse
import pathlib
import plistlib
import shutil
import stat
import sys

import macho


_LAUNCHER = "PyMOL-Open-Source"
"""The launcher's name, the bundle's CFBundleExecutable."""


def _copy(source: pathlib.Path, destination: pathlib.Path, arch: str) -> None:
  """Copies a file, cutting a universal Mach-O file down to one architecture.

  Args:
    source: The file.
    destination: The copy's path; missing folders are created.
    arch: The target's architecture.
  """
  destination.parent.mkdir(parents=True, exist_ok=True)
  if macho.is_macho(source) and len(macho.architectures(source)) > 1:
    destination.write_bytes(macho.thin(source, arch))
  else:
    shutil.copyfile(source, destination)
  destination.chmod(source.stat().st_mode | stat.S_IWUSR)


def make_app(
  app: pathlib.Path,
  info_plist: pathlib.Path,
  icon: pathlib.Path,
  version: str,
  arch: str,
  out: pathlib.Path,
) -> None:
  """Writes the .app.

  Args:
    app: The app folder, with the launcher at its top.
    info_plist: The Info.plist to stamp.
    icon: The app icon (.icns).
    version: The app's version.
    arch: The target's architecture, "arm64" or "x86_64".
    out: The .app folder to write.
  """
  tmp_contents = out / "Contents"
  for tmp_path in sorted(app.rglob("*")):
    if not tmp_path.is_file():
      continue
    tmp_relative = tmp_path.relative_to(app)
    if tmp_relative.as_posix() == _LAUNCHER:
      tmp_launcher = tmp_contents / "MacOS" / _LAUNCHER
      _copy(tmp_path, tmp_launcher, arch)
      # The bundle's executable, whatever mode the input carried.
      tmp_launcher.chmod(tmp_launcher.stat().st_mode | 0o755)
    else:
      _copy(tmp_path, tmp_contents / "Resources" / tmp_relative, arch)
  shutil.copyfile(icon, tmp_contents / "Resources" / icon.name)
  with open(info_plist, "rb") as tmp_handle:
    tmp_plist = plistlib.load(tmp_handle)
  tmp_plist["CFBundleShortVersionString"] = version
  tmp_plist["CFBundleVersion"] = version
  with open(tmp_contents / "Info.plist", "wb") as tmp_handle:
    plistlib.dump(tmp_plist, tmp_handle)
  (tmp_contents / "PkgInfo").write_text("APPL????", encoding="ascii")


def main(argv: list[str]) -> int:
  """Writes the .app from the command line.

  Args:
    argv: --app, --info-plist, --icon, --version, --arch and --out.

  Returns:
    0 on success, 1 when the app folder has no launcher.
  """
  tmp_parser = argparse.ArgumentParser()
  for tmp_name in ("--app", "--info-plist", "--icon", "--version", "--out"):
    tmp_parser.add_argument(tmp_name, required=True)
  tmp_parser.add_argument("--arch", required=True, choices=("arm64", "x86_64"))
  tmp_arguments = tmp_parser.parse_args(argv)
  tmp_app = pathlib.Path(tmp_arguments.app)
  if not (tmp_app / _LAUNCHER).is_file():
    print(f"make_app: {tmp_app} has no {_LAUNCHER}", file=sys.stderr)
    return 1
  make_app(
    tmp_app,
    pathlib.Path(tmp_arguments.info_plist),
    pathlib.Path(tmp_arguments.icon),
    tmp_arguments.version,
    tmp_arguments.arch,
    pathlib.Path(tmp_arguments.out),
  )
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
