"""Unpacks the Microsoft C++ runtime DLLs and license from vc_redist.x64.exe.

The action tool of //distribution/windows:msvc_runtime. It runs freeze-core's
own unpacker, the code cx_Freeze used to bundle the runtime, on the pinned
Redistributable, and writes the DLLs into one folder and the license
(LICENSE.RTF and its text, LICENSE.txt) into another.
"""

import argparse
import pathlib
import shutil
import sys
import tempfile

from freeze_core import winmsvcr_repack


def main(argv: list[str]) -> int:
  """Unpacks the runtime.

  Args:
    argv: --exe <vc_redist.x64.exe>, --dlls <folder> and --license <folder>.

  Returns:
    0 on success, 1 when the installer held no DLL or no license.
  """
  tmp_parser = argparse.ArgumentParser()
  tmp_parser.add_argument("--exe", required=True)
  tmp_parser.add_argument("--dlls", required=True)
  tmp_parser.add_argument("--license", required=True)
  tmp_arguments = tmp_parser.parse_args(argv)
  with tempfile.TemporaryDirectory() as tmp_folder:
    tmp_unpacked = list(
      winmsvcr_repack.unpack_exe(
        pathlib.Path(tmp_arguments.exe), pathlib.Path(tmp_folder)
      )
    )
    tmp_dlls = [
      tmp_file for tmp_file in tmp_unpacked if tmp_file.suffix == ".dll"
    ]
    tmp_licenses = [
      tmp_file
      for tmp_file in tmp_unpacked
      if tmp_file.name in ("LICENSE.RTF", "LICENSE.txt")
    ]
    if not tmp_dlls:
      print("unpack_vc_redist: no DLL in the installer", file=sys.stderr)
      return 1
    if len(tmp_licenses) != 2:
      print("unpack_vc_redist: no license in the installer", file=sys.stderr)
      return 1
    for tmp_files, tmp_target in (
      (tmp_dlls, tmp_arguments.dlls),
      (tmp_licenses, tmp_arguments.license),
    ):
      pathlib.Path(tmp_target).mkdir(parents=True, exist_ok=True)
      for tmp_file in tmp_files:
        shutil.copyfile(tmp_file, pathlib.Path(tmp_target, tmp_file.name))
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
