"""Starts the Linux app: the app's own libgomp first, then PyMOL.

The launcher runs `python -m pymol_app_start` on Linux. PyMOL's _cmd links
libgomp.so.1 (OpenMP), which a minimal system lacks and the packages do not
declare, so the app ships it in the runtime's lib folder. It has to be loaded
before the pymol package is imported, as importing the package loads _cmd:
`-m pymol.startup_wrapper` imports the package before the wrapper's own code
runs. Loaded first and globally, it is the copy _cmd's dependency resolves to,
and the only OpenMP runtime in the process.
"""

import ctypes
import os
import runpy
import sys


def load_bundled_openmp() -> None:
  """Loads the runtime's libgomp.so.1 globally, if the app ships one."""
  tmp_library = os.path.join(sys.prefix, "lib", "libgomp.so.1")
  if os.path.isfile(tmp_library):
    ctypes.CDLL(tmp_library, mode=ctypes.RTLD_GLOBAL)


if __name__ == "__main__":
  load_bundled_openmp()
  runpy.run_module(
    "pymol.startup_wrapper", run_name="__main__", alter_sys=True
  )
