"""Bazel action driver for the shader-cache and build-info headers _cmd needs.

Calls create_generated_files.py's create_shadertext() and create_buildinfo(),
passing the git SHA and the commit time from Bazel's stable workspace status
(tools/bazel/workspace_status.{sh,bat}) instead of letting create_buildinfo()
run `git` and read the clock, neither of which is a declared action input.
"""

import argparse
import os

from create_generated_files import create_buildinfo, create_shadertext


def _read_stable_status(info_file_path: str) -> dict[str, str]:
  """Returns the key-value pairs of a Bazel workspace-status file."""
  status = {}
  with open(info_file_path, encoding="utf-8") as handle:
    for line in handle:
      key, _, value = line.strip().partition(" ")
      status[key] = value
  return status


def main() -> None:
  """Writes ShaderText.h, ShaderText.cpp and PyMOLBuildInfo.h."""
  parser = argparse.ArgumentParser()
  parser.add_argument("--shader-dir", required=True)
  parser.add_argument("--shader-header-out", required=True)
  parser.add_argument("--shader-cpp-out", required=True)
  parser.add_argument("--build-info-out", required=True)
  parser.add_argument("--info-file", required=True)
  args = parser.parse_args()

  create_shadertext(
      args.shader_dir,
      args.shader_dir,
      args.shader_header_out,
      args.shader_cpp_out,
  )

  status = _read_stable_status(args.info_file)
  build_date = status.get("STABLE_BUILD_DATE", "")
  create_buildinfo(
      os.path.dirname(args.build_info_out),
      git_sha=status.get("STABLE_GIT_SHA", ""),
      build_date=int(build_date) if build_date.isdigit() else 0,
  )


if __name__ == "__main__":
  main()
