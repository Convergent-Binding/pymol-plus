"""gomp_linux: the OpenMP runtime of the compiler that builds _cmd, as @gomp_linux.

PyMOL's _cmd links libgomp.so.1, which the wheel's auditwheel repair and the
cx_Freeze app bundled; the Bazel-built app bundles it too. It must be the
library of the compiler that built _cmd (in CI the manylinux_2_28 image's
gcc-toolset), so a local repository rule asks that compiler for it:
`gcc -print-file-name=libgomp.so.1` ($CC when set). Off Linux, or without
gcc, the repository's `:libgomp` is empty.
"""

def _gomp_linux_impl(rctx):
    found = None
    if rctx.os.name.startswith("linux"):
        compiler = rctx.getenv("CC") or "gcc"
        result = rctx.execute([compiler, "-print-file-name=libgomp.so.1"])
        candidate = result.stdout.strip()
        if result.return_code == 0 and candidate.startswith("/") and rctx.path(candidate).exists:
            found = candidate
    if found:
        rctx.execute(["cp", "-L", found, "libgomp.so.1"])
        rctx.file("BUILD.bazel", 'filegroup(name = "libgomp", srcs = ["libgomp.so.1"], visibility = ["//visibility:public"])\n')
    else:
        rctx.file("BUILD.bazel", 'filegroup(name = "libgomp", srcs = [], visibility = ["//visibility:public"])\n')

gomp_linux = repository_rule(
    implementation = _gomp_linux_impl,
    environ = ["CC", "PATH"],
    local = True,
)
