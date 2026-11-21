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


def main(argv: list[str]) -> int:
  """Copies each (source, destination) pair into --out.

  Args:
    argv: `--out <dir>` followed by alternating source paths and paths
      relative to the output directory; `@file` reads them from a file.

  Returns:
    0 on success; 1 if two sources claim the same destination path.
  """
  parser = argparse.ArgumentParser(fromfile_prefix_chars="@")
  parser.add_argument("--out", required=True)
  parser.add_argument(
      "pairs",
      nargs="+",
      help="alternating source paths and paths relative to --out",
  )
  args = parser.parse_args(argv)
  if len(args.pairs) % 2 != 0:
    parser.error("expected an even number of source and destination arguments")

  seen = {}
  for source, relative in zip(args.pairs[0::2], args.pairs[1::2], strict=True):
    if relative in seen:
      print(
          f"merge_wheel_files: two wheels both provide '{relative}' "
          f"({seen[relative]} and {source}); the merged wheels must ship "
          "complementary paths, and a version bump likely broke that.",
          file=sys.stderr,
      )
      return 1
    seen[relative] = source
    destination = os.path.join(args.out, relative)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    shutil.copy2(source, destination)
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
