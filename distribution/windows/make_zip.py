"""Writes a folder's contents into a ZIP, the same bytes for the same files.

The action tool of //distribution/windows:portable_zip. The members are the
folder's files in path order, with forward slashes, a fixed time stamp and
DEFLATE compression, so a rebuild of the same app gives the same ZIP.
"""

import argparse
import pathlib
import sys
import zipfile


_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
"""The earliest time a ZIP can record, for every member."""


def write_zip(folder: pathlib.Path, out: pathlib.Path) -> int:
  """Writes the folder's files into a ZIP at its root.

  Args:
    folder: The folder whose contents become the ZIP's top level.
    out: The ZIP file to write.

  Returns:
    The number of files written.
  """
  tmp_files = sorted(
    tmp_path for tmp_path in folder.rglob("*") if tmp_path.is_file()
  )
  with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as tmp_zip:
    for tmp_path in tmp_files:
      tmp_info = zipfile.ZipInfo(
        tmp_path.relative_to(folder).as_posix(), _TIMESTAMP
      )
      tmp_info.compress_type = zipfile.ZIP_DEFLATED
      tmp_info.external_attr = 0o644 << 16
      tmp_zip.writestr(tmp_info, tmp_path.read_bytes())
  return len(tmp_files)


def main(argv: list[str]) -> int:
  """Writes the ZIP.

  Args:
    argv: --folder <folder> and --out <ZIP file>.

  Returns:
    0 on success, 1 when the folder holds no file.
  """
  tmp_parser = argparse.ArgumentParser()
  tmp_parser.add_argument("--folder", required=True)
  tmp_parser.add_argument("--out", required=True)
  tmp_arguments = tmp_parser.parse_args(argv)
  if write_zip(pathlib.Path(tmp_arguments.folder), pathlib.Path(tmp_arguments.out)):
    return 0
  print(f"make_zip: {tmp_arguments.folder} holds no file", file=sys.stderr)
  return 1


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
