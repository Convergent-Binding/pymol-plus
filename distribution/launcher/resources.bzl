"""launcher_resources: the Windows launcher's icon and version as a .res file.

Runs //distribution/launcher:make_resources on Bazel's hermetic Python; the
MSVC linker links the output into the launcher.
"""

def _launcher_resources_impl(ctx):
    out = ctx.actions.declare_file(ctx.label.name + ".res")
    args = ctx.actions.args()
    args.add("--icon", ctx.file.icon)
    args.add("--pyproject", ctx.file.pyproject)
    args.add("--out", out)
    ctx.actions.run(
        outputs = [out],
        inputs = [ctx.file.icon, ctx.file.pyproject],
        executable = ctx.executable._tool,
        arguments = [args],
        mnemonic = "LauncherResources",
        progress_message = "Writing the launcher's resources %{output}",
    )
    return [DefaultInfo(files = depset([out]))]

launcher_resources = rule(
    implementation = _launcher_resources_impl,
    attrs = {
        "icon": attr.label(allow_single_file = [".ico"], mandatory = True),
        "pyproject": attr.label(
            allow_single_file = True,
            mandatory = True,
            doc = "distribution/pyproject.toml, the app's version.",
        ),
        "_tool": attr.label(
            default = Label("//distribution/launcher:make_resources"),
            executable = True,
            cfg = "exec",
        ),
    },
)
