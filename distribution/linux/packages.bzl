"""linux_template: a desktop entry or metainfo filled in for the packages.

Runs //distribution/linux:fill_template with Bazel's stable status, which
gives @DATE@ the date of the built commit.
"""

def _linux_template_impl(ctx):
    out = ctx.actions.declare_file(ctx.attr.out)
    args = ctx.actions.args()
    args.add("--template", ctx.file.template)
    args.add("--out", out)
    args.add("--status-file", ctx.info_file)
    for old, new in ctx.attr.replacements.items():
        args.add("--replace", "{}={}".format(old, new))
    ctx.actions.run(
        outputs = [out],
        inputs = [ctx.file.template, ctx.info_file],
        executable = ctx.executable._tool,
        arguments = [args],
        mnemonic = "LinuxTemplate",
        progress_message = "Filling in %{output}",
    )
    return [DefaultInfo(files = depset([out]))]

linux_template = rule(
    implementation = _linux_template_impl,
    attrs = {
        "out": attr.string(mandatory = True, doc = "The output file's name."),
        "replacements": attr.string_dict(
            doc = "Texts to replace; @DATE@ is always the commit date.",
        ),
        "template": attr.label(allow_single_file = True, mandatory = True),
        "_tool": attr.label(
            default = Label("//distribution/linux:fill_template"),
            executable = True,
            cfg = "exec",
        ),
    },
)
