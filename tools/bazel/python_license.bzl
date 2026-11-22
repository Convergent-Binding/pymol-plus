"""python_license: the license text of a rules_python standalone runtime.

rules_python's runtime repositories export only their interpreter, and on
Windows their `:files` leave out LICENSE.txt, the license of CPython and of
the libraries python-build-standalone bundles. An app that ships the runtime
must ship that text, so this repository rule copies it out of the runtime
repository beside the given interpreter label and exports it as
`@<name>//:LICENSE.txt`. Declare one per platform and select between them:
only the repository a build selects is fetched, with its runtime.
"""

_CANDIDATES = [
    "LICENSE.txt",  # Windows
    "lib/python{version}/LICENSE.txt",  # Linux, macOS
]

def _python_license_impl(rctx):
    root = rctx.path(rctx.attr.interpreter).dirname
    for candidate in _CANDIDATES:
        path = root.get_child(candidate.format(version = rctx.attr.python_version))
        if path.exists:
            rctx.file("LICENSE.txt", rctx.read(path))
            rctx.file("BUILD.bazel", 'exports_files(["LICENSE.txt"], visibility = ["//visibility:public"])\n')
            return
    fail("No LICENSE.txt in the Python runtime at {}".format(root))

python_license = repository_rule(
    implementation = _python_license_impl,
    attrs = {
        "interpreter": attr.label(
            mandatory = True,
            doc = "The runtime repository's exported `:python` file.",
        ),
        "python_version": attr.string(mandatory = True, doc = "Such as \"3.13\"."),
    },
)
