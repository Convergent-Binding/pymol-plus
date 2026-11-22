"""Copies files from several extracted wheels into one site-packages tree.

The action tool of //tools/bazel:wheel_merge.bzl, ported from
open-protein-platform. rules_python's pip.parse extracts every wheel into a
repository of its own, while PySide6's compiled modules find shiboken6 and
the Qt libraries relative to their own directory, as in a normal pip install
into one site-packages; see wheel_merge.bzl for the full reasoning.

Real copies, never symlinks: the dynamic loaders resolve own-directory-relative
paths (rpath, @loader_path, DLL search directories) from a file's real path,
so only real siblings under one real directory find each other.
"""

import argparse
import os
import shutil
import sys


def _is_bytecode(relative: str) -> bool:
  """Tells whether a path is compiled bytecode, which no wheel ships.

  A test importing from an extracted wheel or from the merged tree makes
  Python write __pycache__ there, with that run's absolute paths in it.

  Args:
    relative: A path relative to site-packages, with "/" separators.

  Returns:
    Whether it lies in __pycache__ or is a .pyc file.
  """
  return "__pycache__" in relative.split("/") or relative.endswith(".pyc")


def main(argv: list[str]) -> int:
  """Copies each (source, destination) pair into --out.

  Args:
    argv: `--out <dir>` followed by alternating source paths and paths
      relative to the output directory; `@file` reads them from a file.

  Returns:
    0 on success; 1 if two sources claim the same destination path.
  """
  tmp_parser = argparse.ArgumentParser(fromfile_prefix_chars="@")
  tmp_parser.add_argument("--out", required=True)
  tmp_parser.add_argument(
    "pairs",
    nargs="+",
    help="alternating source paths and paths relative to --out",
  )
  tmp_arguments = tmp_parser.parse_args(argv)
  if len(tmp_arguments.pairs) % 2 != 0:
    tmp_parser.error(
      "expected an even number of source and destination arguments"
    )

  tmp_seen = {}
  for tmp_source, tmp_relative in zip(
    tmp_arguments.pairs[0::2], tmp_arguments.pairs[1::2], strict=True
  ):
    if _is_bytecode(tmp_relative):
      continue
    if tmp_relative in tmp_seen:
      print(
        f"merge_wheel_files: two wheels both provide '{tmp_relative}' "
        f"({tmp_seen[tmp_relative]} and {tmp_source}); the merged wheels "
        "must ship complementary paths, and a version bump likely broke that.",
        file=sys.stderr,
      )
      return 1
    tmp_seen[tmp_relative] = tmp_source
    tmp_destination = os.path.join(tmp_arguments.out, tmp_relative)
    os.makedirs(os.path.dirname(tmp_destination), exist_ok=True)
    shutil.copy2(tmp_source, tmp_destination)
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
