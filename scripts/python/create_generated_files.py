import glob
import io as cStringIO
import os
import pathlib
import time
from collections import defaultdict
from subprocess import PIPE, Popen


def create_all(generated_dir, pymoldir="."):
  """
  Generate various stuff
  """
  create_shadertext(
    os.path.join(pymoldir, "data", "shaders"),
    generated_dir,
    os.path.join(generated_dir, "ShaderText.h"),
    os.path.join(generated_dir, "ShaderText.cpp"),
  )
  create_buildinfo(generated_dir, pymoldir)


class openw(object):
  """
  File-like object for writing files. File is actually only
  written if the content changed.
  """

  def __init__(self, filename):
    if os.path.exists(filename):
      self.out = cStringIO.StringIO()
      self.filename = filename
    else:
      os.makedirs(os.path.dirname(filename), exist_ok=True)
      self.out = open(filename, "w")
      self.filename = None

  def close(self):
    if self.out.closed:
      return
    if self.filename:
      with open(self.filename) as handle:
        oldcontents = handle.read()
      newcontents = self.out.getvalue()
      if oldcontents != newcontents:
        self.out = open(self.filename, "w")
        self.out.write(newcontents)
    self.out.close()

  def __getattr__(self, name):
    return getattr(self.out, name)

  def __enter__(self):
    return self

  def __exit__(self, *a, **k):
    self.close()

  def __del__(self):
    self.close()


def create_shadertext(shaderdir, shaderdir2, outputheader, outputfile):
  outputheader = openw(outputheader)
  outputfile = openw(outputfile)

  include_deps = defaultdict(set)
  ifdef_deps = defaultdict(set)

  # get all *.gs *.vs *.fs *.shared from the two input directories
  shaderfiles = set()
  for sdir in [shaderdir, shaderdir2]:
    for ext in ["gs", "vs", "fs", "shared", "tsc", "tse"]:
      shaderfiles.update(
        map(os.path.basename, sorted(glob.glob(os.path.join(sdir, "*." + ext))))
      )

  varname = "_shader_cache_raw"
  outputheader.write("extern const char * %s[];\n" % varname)
  outputfile.write("const char * %s[] = {\n" % varname)

  for filename in sorted(shaderfiles):
    shaderfile = os.path.join(shaderdir, filename)
    if not os.path.exists(shaderfile):
      shaderfile = os.path.join(shaderdir2, filename)

    with open(shaderfile, "r") as handle:
      contents = handle.read()

    if True:
      outputfile.write('"%s", ""\n' % (filename))

      for line in contents.splitlines():
        line = line.strip()

        # skip blank lines and obvious comments
        if not line or line.startswith("//") and not "*/" in line:
          continue

        # write line, quoted, escaped and with a line feed
        outputfile.write(
          '"%s\\n"\n' % line.replace("\\", "\\\\").replace('"', r"\"")
        )

        # include and ifdef dependencies
        if line.startswith("#include"):
          include_deps[line.split()[1]].add(filename)
        elif line.startswith("#ifdef") or line.startswith("#ifndef"):
          ifdef_deps[line.split()[1]].add(filename)

      outputfile.write(",\n")

  outputfile.write("0};\n")

  # include and ifdef dependencies
  for varname, deps in [("_include_deps", include_deps), ("_ifdef_deps", ifdef_deps)]:
    outputheader.write("extern const char * %s[];\n" % varname)
    outputfile.write("const char * %s[] = {\n" % varname)
    for name, itemdeps in deps.items():
      outputfile.write('"%s", "%s", 0,\n' % (name, '", "'.join(sorted(itemdeps))))
    outputfile.write("0};\n")

  outputheader.close()
  outputfile.close()


def create_buildinfo(outputdir, pymoldir=".", git_sha=None, build_date=None):
  """Writes PyMOLBuildInfo.h with the build's git SHA and date.

  Args:
    outputdir: Directory the header is written to.
    pymoldir: Checkout whose `git rev-parse HEAD` is used when no SHA is given.
    git_sha: The SHA to embed. A Bazel action passes it, because neither the
      `git` binary nor the checkout's .git directory is a declared input.
    build_date: The Unix time to embed. A Bazel action passes it, because a
      wall-clock read inside an action makes its output uncacheable.
  """
  sha = git_sha
  if sha is None:
    try:
      sha = (
        Popen(["git", "rev-parse", "HEAD"], cwd=pymoldir, stdout=PIPE)
        .stdout.read()
        .strip()
        .decode()
      )
    except OSError:
      sha = ""
  date = build_date if build_date is not None else time.time()

  with openw(os.path.join(outputdir, "PyMOLBuildInfo.h")) as out:
    print(
      """
#define _PyMOL_BUILD_DATE %d
#define _PYMOL_BUILD_GIT_SHA "%s"
  """
      % (date, sha),
      file=out,
      )


if __name__ == '__main__':
  FILE_ROOT_PATH = pathlib.Path(__file__).parent
  PROJECT_ROOT_PATH = FILE_ROOT_PATH.parent.parent
  #PYMOL_PATH = pathlib.Path(PROJECT_ROOT_PATH / "vendor/pymol-open-source/")
  PYMOL_INTERNAL_BUILD_PATH = pathlib.Path(PROJECT_ROOT_PATH / "build")
  if not PYMOL_INTERNAL_BUILD_PATH.exists():
    PYMOL_INTERNAL_BUILD_PATH.mkdir()
  generated_dir = os.path.join(PYMOL_INTERNAL_BUILD_PATH, "generated")
  create_all(generated_dir, str(PROJECT_ROOT_PATH))
