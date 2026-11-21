"""Read the `[project]` table of pyproject.toml so wheel metadata has one source.

`py_wheel` would otherwise restate the version, summary, author,
`requires-python` and dependencies that pyproject.toml already declares. Two
copies of the same field do not stay equal: open-protein-platform, where this reader comes from, had shipped
a `requires-python = ">=3.11"` that was false, and a `dependencies =
["numpy==1.26.4"]` that contradicted its own `[build-system]`.

Starlark has no TOML parser, and adding a complete one would be a poor trade for
the handful of fields actually needed. The design that keeps a partial parser
safe is: **parse leniently, fail loudly on demand.** A value written in TOML this
reader does not understand is recorded as None rather than skipped or guessed
at, and `require()` turns that into a build failure -- but only for the keys
something actually asks for. So an unrelated key cannot break the build, while a
needed one can never be silently wrong. That distinction is not academic: the
first version failed outright on `authors`, a list of inline tables that nothing
here reads.

A parser that silently returns the wrong version is worse than no parser, since
the wrong value would be baked into a published artifact.

What it understands:
  * the `[project]` table only -- every other table is skipped
  * `key = "value"` string entries
  * `key = ["a", "b"]` list entries, single-line or spread over lines
  * `#` comments, on their own line or trailing

Everything else -- numbers, booleans, inline tables such as
`license = {file = "LICENSE"}`, lists of them such as `authors`, multi-line
strings -- parses to None and fails only if required.

Verified by //tools/bazel/tests:pyproject_metadata_test, which parses the
same file with Python's real `tomllib` and asserts the constants this
reader produced agree. That test is the reason this hand-rolled reader is safe to rely on: if
it ever mis-parses, the comparison against a real TOML parser fails.
"""

def _strip_comment(line):
    """Remove a trailing comment, respecting quoted strings."""
    out = []
    in_string = False
    for ch in line.elems():
        if ch == '"':
            in_string = not in_string
        if ch == "#" and not in_string:
            break
        out.append(ch)
    return "".join(out)

def _try_unquote(token):
    """Return the unquoted string, or None if this is not a quoted string."""
    token = token.strip()
    if token.endswith(","):
        token = token[:-1].strip()
    if len(token) < 2 or not token.startswith('"') or not token.endswith('"'):
        return None
    return token[1:-1]

def parse_project_table(content, path = "pyproject.toml"):
    """Parse the `[project]` table into a dict of str -> str, list[str] or None.

    Keys whose values use TOML this reader does not support -- numbers,
    booleans, inline tables such as `license = {file = "LICENSE"}`, or lists of
    them such as `authors` -- are recorded with a value of None rather than
    skipped or guessed at. Parsing stays lenient so an unrelated key cannot
    break the build; `require()` is what turns an unusable value into a loud
    failure, and only for the keys actually asked for.

    Args:
      content: the file's text.
      path: the file's path, used only in error messages.

    Returns:
      A dict mapping keys of the `[project]` table to strings, string lists, or
      None where the value's syntax is unsupported.
    """
    values = {}
    in_project = False
    pending_key = None
    pending_list = []
    pending_ok = True

    for raw in content.split("\n"):
        line = _strip_comment(raw).strip()
        if not line:
            continue

        if pending_key != None:
            if line.startswith("]"):
                values[pending_key] = pending_list if pending_ok else None
                pending_key = None
                pending_list = []
                pending_ok = True
            elif pending_ok:
                item = _try_unquote(line)
                if item == None:
                    pending_ok = False
                else:
                    pending_list.append(item)
            continue

        if line.startswith("["):
            in_project = line == "[project]"
            continue

        if not in_project or "=" not in line:
            continue

        key, _, rest = line.partition("=")
        key = key.strip()
        rest = rest.strip()

        if rest.startswith("["):
            inner = rest[1:]
            if inner.rstrip().endswith("]"):
                inner = inner.rstrip()[:-1]
                items = [_try_unquote(t) for t in inner.split(",") if t.strip()]
                values[key] = None if None in items else items
            else:
                pending_key = key
                pending_ok = True
                pending_list = []
                for t in inner.split(","):
                    if not t.strip():
                        continue
                    item = _try_unquote(t)
                    if item == None:
                        pending_ok = False
                    else:
                        pending_list.append(item)
        elif rest.startswith('"'):
            values[key] = _try_unquote(rest)
        else:
            values[key] = None

    if pending_key != None:
        fail("{}: unterminated list for `{}`".format(path, pending_key))

    return values

def require(values, key, path = "pyproject.toml"):
    """Fetch a key that must be present and readable, or fail usefully."""
    if key not in values or values[key] == None:
        fail(
            "{}: no `{}` found in the [project] table. ".format(path, key) +
            "//tools/bazel:pyproject.bzl reads a restricted subset of TOML; if this key " +
            "exists but uses a form it does not understand (a number, a boolean, an " +
            "inline table or a multi-line string), extend the parser rather than " +
            "reintroducing a hardcoded copy of the value.",
        )
    return values[key]
