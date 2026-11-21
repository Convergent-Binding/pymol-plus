"""Merges several pip.parse wheel extractions into one site-packages tree.

Ported from open-protein-platform (tools/bazel/devtools/wheel_merge.bzl).

rules_python's pip.parse extracts every requirement into a repository of its
own. Some packages find a sibling package's files relative to their own
directory: PySide6's compiled modules locate shiboken6 and the Qt libraries
through an rpath (`@loader_path`, `$ORIGIN`) or a DLL search directory, which
holds only in a normal single-site-packages install. Runfiles symlinks do not
help, because the loaders resolve those paths from a file's real path, deep
in Bazel's repository cache. So this rule copies (never symlinks) every
input wheel's files into one tree artifact, `<name>/site-packages`, laid out
as pip would install them, dist-info directories included.

The files still come from pip.parse's hash-pinned, per-platform fetches
(each wheel's public `:extracted_whl_files` filegroup), so the lock file stays
the single source of versions and hashes; this rule only lays the files out.
"""

_SITE_PACKAGES_MARKER = "/site-packages/"

_PYTHON_VERSION = "@rules_python//python/config_settings:python_version"

def _python_version_transition_impl(settings, attr):
    # A hub locked for one Python version (such as @app_pip, 3.13 only) has
    # no wheels for the repository's default 3.10, so `bazel build //...`
    # must not build its merge in the default configuration.
    if not attr.python_version:
        return {_PYTHON_VERSION: settings[_PYTHON_VERSION]}
    return {_PYTHON_VERSION: attr.python_version}

_python_version_transition = transition(
    implementation = _python_version_transition_impl,
    inputs = [_PYTHON_VERSION],
    outputs = [_PYTHON_VERSION],
)

def _merge_wheel_files_impl(ctx):
    out_dir = ctx.actions.declare_directory(ctx.label.name + "/site-packages")

    pairs = []
    for f in ctx.files.wheel_files:
        idx = f.short_path.find(_SITE_PACKAGES_MARKER)
        if idx == -1:
            # `:extracted_whl_files` also holds the repository's bookkeeping
            # files (MODULE.bazel and the like); every wheel file installs
            # under site-packages.
            continue
        pairs.extend([f.path, f.short_path[idx + len(_SITE_PACKAGES_MARKER):]])

    if not pairs:
        fail("merge_wheel_files '{}': wheel_files produced no files; check the labels.".format(ctx.label))

    args = ctx.actions.args()
    args.add("--out", out_dir.path)
    args.add_all(pairs)
    args.use_param_file("@%s", use_always = True)
    args.set_param_file_format("multiline")

    ctx.actions.run(
        outputs = [out_dir],
        inputs = ctx.files.wheel_files,
        executable = ctx.executable._merger,
        arguments = [args],
        mnemonic = "MergeWheelFiles",
        progress_message = "Merging wheel files into %{output}",
    )

    return [DefaultInfo(files = depset([out_dir]))]

merge_wheel_files = rule(
    implementation = _merge_wheel_files_impl,
    cfg = _python_version_transition,
    attrs = {
        "python_version": attr.string(
            doc = "The Python version the wheels are resolved for, such as " +
                  "\"3.13\"; empty keeps the invocation's version.",
        ),
        "wheel_files": attr.label_list(
            mandatory = True,
            allow_files = True,
            doc = "Wheels' `:extracted_whl_files` filegroups, such as " +
                  "`@app_pip//pyside6_essentials:extracted_whl_files`. Two " +
                  "wheels that ship the same path fail the build.",
        ),
        "_merger": attr.label(
            default = Label("//tools/bazel:merge_wheel_files"),
            executable = True,
            cfg = "exec",
        ),
    },
)
