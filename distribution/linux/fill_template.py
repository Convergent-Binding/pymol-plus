"""Fills a desktop entry or AppStream metainfo template for the packages.

The action tool of linux_template: it replaces given text, and @DATE@ with
the date of the built commit (Bazel's stable status STABLE_BUILD_DATE, a
Unix time), so rebuilds of a version keep their release date, as
build_packages.sh did with `git log -1 --format=%cs`.
"""

import argparse
import datetime
import pathlib
import sys


def commit_date(status_file: pathlib.Path) -> str:
  """Reads the built commit's date from Bazel's stable status file.

  Args:
    status_file: The status file, one "KEY value" line per entry.

  Returns:
    The date as YYYY-MM-DD in UTC; 1970-01-01 when the status names none.
  """
  for tmp_line in status_file.read_text(encoding="utf-8").splitlines():
    tmp_key, _, tmp_value = tmp_line.partition(" ")
    if tmp_key == "STABLE_BUILD_DATE" and tmp_value.strip().isdigit():
      tmp_time = datetime.datetime.fromtimestamp(
        int(tmp_value.strip()), datetime.UTC
      )
      return tmp_time.date().isoformat()
  return "1970-01-01"


def main(argv: list[str]) -> int:
  """Writes the filled template.

  Args:
    argv: --template, --out, --status-file, and --replace OLD=NEW pairs.

  Returns:
    0 on success, 1 when a text to replace is not in the template.
  """
  tmp_parser = argparse.ArgumentParser()
  for tmp_name in ("--template", "--out", "--status-file"):
    tmp_parser.add_argument(tmp_name, required=True)
  tmp_parser.add_argument("--replace", action="append", default=[])
  tmp_arguments = tmp_parser.parse_args(argv)
  tmp_text = pathlib.Path(tmp_arguments.template).read_text(encoding="utf-8")
  tmp_pairs = [tmp_pair.split("=", 1) for tmp_pair in tmp_arguments.replace]
  tmp_pairs.append(
    ["@DATE@", commit_date(pathlib.Path(tmp_arguments.status_file))]
  )
  for tmp_old, tmp_new in tmp_pairs:
    if tmp_old != "@DATE@" and tmp_old not in tmp_text:
      print(f"fill_template: {tmp_old} not in the template", file=sys.stderr)
      return 1
    tmp_text = tmp_text.replace(tmp_old, tmp_new)
  pathlib.Path(tmp_arguments.out).write_text(tmp_text, encoding="utf-8")
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
