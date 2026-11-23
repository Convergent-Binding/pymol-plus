"""The app_bundle rule: the PyMOL-Open-Source app folder for the target platform.

It builds its inputs for the app's Python version (an incoming transition),
so the in-repo PyMOL wheel, the merged site-packages and the runtime agree,
and runs //distribution/bundle:assemble_bundle on Bazel's hermetic Python
through a parameter file. The output is one tree artifact,
`<name>/PyMOL-Open-Source`; see assemble_bundle.py for its layout.
"""

_PYTHON_VERSION = "@rules_python//python/config_settings:python_version"

def _app_python_transition_impl(_settings, attr):
    return {_PYTHON_VERSION: attr.python_version}

_app_python_transition = transition(
    implementation = _app_python_transition_impl,
    inputs = [],
    outputs = [_PYTHON_VERSION],
)

def _app_bundle_impl(ctx):
    out = ctx.actions.declare_directory(ctx.label.name + "/PyMOL-Open-Source")
    runtime_files = ctx.files.runtime
    if not runtime_files:
        fail("app_bundle '{}': the runtime has no files.".format(ctx.label))
    runtime_root = runtime_files[0].owner.workspace_root
    if not runtime_root:
        fail("app_bundle '{}': the runtime must come from an external repository.".format(ctx.label))

    args = ctx.actions.args()
    args.add("--out", out.path)
    args.add("--runtime-root", runtime_root)
    args.add_all(runtime_files, before_each = "--runtime-file")
    args.add("--site-packages", ctx.file.site_packages.path)
    args.add("--wheel", ctx.file.wheel)
    for target, destination in ctx.attr.overlays.items():
        for f in target.files.to_list():
            args.add("--overlay", "{}={}".format(f.path, destination))
    args.add("--launcher", ctx.executable.launcher)
    for target, destination in ctx.attr.bundle_files.items():
        for f in target.files.to_list():
            args.add("--bundle-file", "{}={}".format(f.path, destination))
    for f in ctx.files.runtime_trees:
        args.add("--runtime-tree", f.path)
    for source, destination in ctx.attr.runtime_from_site_packages.items():
        args.add("--runtime-from-site-packages", "{}={}".format(source, destination))
    for target, name in ctx.attr.license_trees.items():
        for f in target.files.to_list():
            args.add("--license-tree", "{}={}".format(f.path, name))
    for f in ctx.files.licenses:
        args.add("--license", "{}={}".format(f.path, f.basename))
    args.add("--project-license", ctx.file.project_license)
    args.add("--python-license", ctx.file.python_license)
    args.add_all(ctx.attr.distributions, before_each = "--distribution")
    args.add("--pyproject", ctx.file.pyproject)
    args.add("--lock", ctx.file.lock)
    args.add("--status-file", ctx.info_file)
    args.add("--target", ctx.attr.target)
    args.add("--python-version", ctx.attr.python_version)
    args.use_param_file("@%s", use_always = True)
    args.set_param_file_format("multiline")

    ctx.actions.run(
        outputs = [out],
        inputs = depset(
            runtime_files + ctx.files.overlays + ctx.files.licenses +
            ctx.files.runtime_trees + ctx.files.license_trees +
            ctx.files.bundle_files + [
                ctx.file.site_packages,
                ctx.file.wheel,
                ctx.executable.launcher,
                ctx.file.project_license,
                ctx.file.python_license,
                ctx.file.pyproject,
                ctx.file.lock,
                ctx.info_file,
            ],
        ),
        executable = ctx.executable._assembler,
        arguments = [args],
        mnemonic = "AppBundle",
        progress_message = "Assembling the app in %{output}",
    )
    return [DefaultInfo(files = depset([out]))]

app_bundle = rule(
    implementation = _app_bundle_impl,
    cfg = _app_python_transition,
    attrs = {
        "bundle_files": attr.label_keyed_string_dict(
            allow_files = True,
            doc = "Files copied into the app folder at the paths given, " +
                  "such as the Linux libraries the system may lack.",
        ),
        "distributions": attr.string_list(
            mandatory = True,
            doc = "The bundled distributions whose licenses go into licenses/.",
        ),
        "launcher": attr.label(
            mandatory = True,
            executable = True,
            cfg = "target",
        ),
        "license_trees": attr.label_keyed_string_dict(
            allow_files = True,
            doc = "Folders copied into licenses/, each into the folder named.",
        ),
        "licenses": attr.label_list(
            allow_files = True,
            doc = "Texts copied into licenses/ under their own names; " +
                  "LGPL-3.0.txt and GPL-3.0.txt also cover Qt for Python.",
        ),
        "lock": attr.label(allow_single_file = True, mandatory = True),
        "overlays": attr.label_keyed_string_dict(
            allow_files = True,
            doc = "Files that replace or join files of site-packages, with " +
                  "their path in site-packages.",
        ),
        "project_license": attr.label(allow_single_file = True, mandatory = True),
        "pyproject": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "distribution/pyproject.toml, the app's version.",
        ),
        "python_license": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "The runtime's LICENSE.txt (//tools/bazel:python_license.bzl).",
        ),
        "python_version": attr.string(mandatory = True),
        "runtime": attr.label(
            mandatory = True,
            allow_files = True,
            doc = "The python-build-standalone files, such as @python_3_13//:files.",
        ),
        "runtime_from_site_packages": attr.string_dict(
            doc = "Files of the app's site-packages also copied into runtime/, " +
                  "as site-packages path to runtime/ path.",
        ),
        "runtime_trees": attr.label_list(
            allow_files = True,
            doc = "Folders whose files go into runtime/, beside the interpreter.",
        ),
        "site_packages": attr.label(
            mandatory = True,
            allow_single_file = True,
            doc = "A merge_wheel_files target.",
        ),
        "target": attr.string(
            mandatory = True,
            doc = "The platform named in manifest.json, such as windows-x86_64.",
        ),
        "wheel": attr.label(mandatory = True, allow_single_file = [".whl"]),
        "_assembler": attr.label(
            default = Label("//distribution/bundle:assemble_bundle"),
            executable = True,
            cfg = "exec",
        ),
    },
)
