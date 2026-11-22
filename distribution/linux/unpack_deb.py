"""Extracts one file from a .deb package; the action tool of its genrule.

A .deb is an `ar` archive whose data.tar.xz holds the installed files. The
app takes libxcb-cursor.so.0 from Ubuntu's package this way, as RHEL and
AlmaLinux 8 ship it only in EPEL. Links inside the package are followed, so
the soname link gives the library it points to.
"""

import argparse
import io
import pathlib
import posixpath
import sys
import tarfile


_AR_MAGIC = b"!<arch>\n"
"""The first line of an `ar` archive."""


def _ar_members(data: bytes) -> dict[str, bytes]:
  """Reads an `ar` archive's members.

  Args:
    data: The archive's bytes.

  Returns:
    Each member's bytes by name.

  Raises:
    ValueError: The bytes are not an `ar` archive.
  """
  if not data.startswith(_AR_MAGIC):
    raise ValueError("not an ar archive")
  tmp_members = {}
  tmp_offset = len(_AR_MAGIC)
  while tmp_offset + 60 <= len(data):
    tmp_header = data[tmp_offset : tmp_offset + 60]
    tmp_name = tmp_header[:16].decode("ascii").strip().rstrip("/")
    tmp_size = int(tmp_header[48:58].decode("ascii").strip())
    tmp_start = tmp_offset + 60
    tmp_members[tmp_name] = data[tmp_start : tmp_start + tmp_size]
    tmp_offset = tmp_start + tmp_size + tmp_size % 2
  return tmp_members


def extract(deb: pathlib.Path, member: str) -> bytes:
  """Reads one installed file from a .deb, following links.

  Args:
    deb: The package.
    member: The file's installed path, without the leading slash.

  Returns:
    The file's bytes.

  Raises:
    KeyError: The package has no such file.
    ValueError: The package has no data.tar.xz.
  """
  tmp_members = _ar_members(deb.read_bytes())
  if "data.tar.xz" not in tmp_members:
    raise ValueError(f"{deb} has no data.tar.xz")
  with tarfile.open(
    fileobj=io.BytesIO(tmp_members["data.tar.xz"]), mode="r:xz"
  ) as tmp_tar:
    tmp_names = {
      posixpath.normpath(tmp_info.name.removeprefix("./").lstrip("/")): tmp_info
      for tmp_info in tmp_tar.getmembers()
    }
    tmp_path = posixpath.normpath(member)
    for _ in range(8):
      if tmp_path not in tmp_names:
        raise KeyError(member)
      tmp_info = tmp_names[tmp_path]
      if not tmp_info.issym():
        return tmp_tar.extractfile(tmp_info).read()
      tmp_path = posixpath.normpath(
        posixpath.join(posixpath.dirname(tmp_path), tmp_info.linkname)
      )
  raise KeyError(member)


def main(argv: list[str]) -> int:
  """Extracts the file.

  Args:
    argv: --deb <package>, --member <installed path>, --out <file>.

  Returns:
    0 on success, 1 when the package lacks the file.
  """
  tmp_parser = argparse.ArgumentParser()
  for tmp_name in ("--deb", "--member", "--out"):
    tmp_parser.add_argument(tmp_name, required=True)
  tmp_arguments = tmp_parser.parse_args(argv)
  try:
    tmp_data = extract(pathlib.Path(tmp_arguments.deb), tmp_arguments.member)
  except (KeyError, ValueError) as exception:
    print(
      f"unpack_deb: {tmp_arguments.member} not in {tmp_arguments.deb}: "
      f"{exception}",
      file=sys.stderr,
    )
    return 1
  pathlib.Path(tmp_arguments.out).write_bytes(tmp_data)
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
