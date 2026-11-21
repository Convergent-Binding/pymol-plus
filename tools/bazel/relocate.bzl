"""Relocate files to explicit wheel-relative paths.

py_wheel's `strip_path_prefixes` remaps Bazel source paths into wheel paths
by stripping a common leading segment -- that's enough for the Python package
roots (modules/<pkg>/... -> <pkg>/...), but not where the destination bears no
prefix relationship to the source: _cmd.so and _champ.so (built at the
repository root and in contrib/champ/) land in pymol/ and chempy/champ/, and
data/ lands nested under pymol/data/.
These two rules produce relocated-file outputs for py_library `data`
attributes to pick up.
"""

def _relocate_file_impl(ctx):
    out = ctx.actions.declare_file(ctx.attr.out)
    ctx.actions.symlink(output = out, target_file = ctx.file.src)
    return [DefaultInfo(files = depset([out]))]

relocate_file = rule(
    implementation = _relocate_file_impl,
    attrs = {
        "src": attr.label(allow_single_file = True, mandatory = True),
        "out": attr.string(mandatory = True),
    },
)

def _relocate_tree_impl(ctx):
    strip_prefix = ctx.attr.strip_prefix.rstrip("/") + "/"
    outs = []
    for src in ctx.files.srcs:
        rel = src.short_path
        if not rel.startswith(strip_prefix):
            fail("%s does not start with strip_prefix %s" % (rel, strip_prefix))
        rel = rel[len(strip_prefix):]
        out = ctx.actions.declare_file(ctx.attr.dest_prefix + "/" + rel)
        ctx.actions.symlink(output = out, target_file = src)
        outs.append(out)
    return [DefaultInfo(files = depset(outs))]

relocate_tree = rule(
    implementation = _relocate_tree_impl,
    attrs = {
        "srcs": attr.label_list(allow_files = True, mandatory = True),
        "strip_prefix": attr.string(mandatory = True),
        "dest_prefix": attr.string(mandatory = True),
    },
)
