"""Generate src/PixeraPy/api_functions.py from the official Pixera API description.

Input is the commented plain-text description that ships with Pixera
(pixera_api_comments_revXXX.txt). Usage:

    python tools/generate_api.py api/pixera_api_comments_rev481.txt

Optionally pass --legacy-json api/pixera_api_rev381.json. The text format prints
struct return values as "null"; the old JSON description still knows the real
struct type, so it is used to restore those return annotations.
"""

import argparse
import json
import keyword
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "src" / "PixeraPy" / "api_functions.py"
DEFAULT_REFERENCE = ROOT / "docs" / "api-reference.md"


@dataclass
class Param:
    type: str
    name: str

    @property
    def optional(self) -> bool:
        return self.type.startswith("optional<")


@dataclass
class Function:
    name: str
    returns: str
    params: List[Param]
    doc: List[str]


@dataclass
class Struct:
    name: str
    fields: List[Param]
    doc: List[str]


@dataclass
class Scope:
    """A namespace or a class."""
    kind: str
    name: str
    path: str
    doc: List[str] = field(default_factory=list)
    functions: List[Function] = field(default_factory=list)
    children: List["Scope"] = field(default_factory=list)
    structs: List[Struct] = field(default_factory=list)


# ---------------------------------------------------------------------------- #
#                                    PARSING                                   #
# ---------------------------------------------------------------------------- #

SCOPE_RE = re.compile(r"^(namespace|class|struct)\s+(\w+)$")
FUNC_RE = re.compile(r"^(\S+)\s+(\w+)\((.*)\)$")
FIELD_RE = re.compile(r"^(\S+)\s+(\w+);$")
REVISION_RE = re.compile(r"revision (\d+) of the API")


def split_params(raw: str) -> List[Param]:
    raw = raw.strip()
    if not raw:
        return []
    params = []
    for part in raw.split(","):
        ptype, pname = part.strip().rsplit(" ", 1)
        params.append(Param(ptype.strip(), pname.strip()))
    return params


def parse_description(text: str):
    revision_match = REVISION_RE.search(text)
    revision = int(revision_match.group(1)) if revision_match else None

    root: Optional[Scope] = None
    stack: List[Scope] = []
    current_struct: Optional[Struct] = None
    comments: List[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip().lstrip("﻿")
        if not line:
            comments = []
            continue
        if line.startswith("//"):
            comments.append(line[2:].strip())
            continue
        if line == "{":
            continue
        if line.startswith("}"):
            if current_struct is not None:
                current_struct = None
            elif stack:
                stack.pop()
            comments = []
            continue

        scope_match = SCOPE_RE.match(line)
        if scope_match:
            kind, name = scope_match.groups()
            if kind == "struct":
                current_struct = Struct(name, [], comments)
                stack[-1].structs.append(current_struct)
            else:
                path = f"{stack[-1].path}.{name}" if stack else name
                scope = Scope(kind, name, path, comments)
                if stack:
                    stack[-1].children.append(scope)
                else:
                    root = scope
                stack.append(scope)
            comments = []
            continue

        if current_struct is not None:
            field_match = FIELD_RE.match(line)
            if field_match:
                current_struct.fields.append(Param(*field_match.groups()))
            continue

        func_match = FUNC_RE.match(line)
        if func_match and stack:
            returns, name, raw_params = func_match.groups()
            stack[-1].functions.append(Function(name, returns, split_params(raw_params), comments))
            comments = []
            continue

        if not stack:
            continue  # preamble such as "This documentation describes revision ..."
        raise ValueError(f"Unrecognised line in API description: {raw_line!r}")

    if root is None:
        raise ValueError("No root namespace found")
    return revision, root


def legacy_return_types(path: Optional[Path]) -> Dict[str, str]:
    """Map 'Pixera.Screens.Screen.getPosition' -> 'ScreenPosValues' from an old JSON description."""
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    result = {}

    def walk(node, prefix):
        for func in node.get("functions", []) + node.get("methods", []):
            returns = func.get("returnValues") or []
            if returns:
                result[f"{prefix}.{func['name']}"] = returns[0]["type"]
        for key in ("namespaces", "classes"):
            for child in node.get(key, []):
                walk(child, f"{prefix}.{child['name']}")

    walk(data, data["name"])
    return result


# ---------------------------------------------------------------------------- #
#                                  GENERATION                                  #
# ---------------------------------------------------------------------------- #

def py_type(api_type: str) -> str:
    if api_type.startswith("optional<") and api_type.endswith(">"):
        return f"Optional[{py_type(api_type[9:-1])}]"
    if api_type.endswith("[]"):
        return f"List[{py_type(api_type[:-2])}]"
    return {
        "string": "str",
        "double": "float",
        "boolean": "bool",
        "null": "None",
    }.get(api_type, api_type)


def py_name(name: str) -> str:
    return f"{name}_" if keyword.iskeyword(name) else name


def docstring(lines: List[str], indent: str) -> List[str]:
    lines = [line.replace('"""', "'''").replace("\\", "\\\\") for line in lines]
    if not lines:
        return []
    if len(lines) == 1:
        return [f'{indent}"""{lines[0]}"""']
    return [f'{indent}"""'] + [f"{indent}{line}".rstrip() for line in lines] + [f'{indent}"""']


class Generator:
    def __init__(self, revision: int, root: Scope, legacy_returns: Dict[str, str]):
        self.revision = revision
        self.root = root
        self.legacy_returns = legacy_returns
        self.out: List[str] = []
        self.structs: List[Struct] = []
        self.flat_functions: Dict[str, str] = {}
        self.flat_classes: Dict[str, str] = {}
        self.collisions: List[str] = []
        self.count = 0
        self._collect_structs(root)

    def _collect_structs(self, scope: Scope):
        self.structs.extend(scope.structs)
        for child in scope.children:
            self._collect_structs(child)

    def return_type(self, qualified: str, func: Function) -> str:
        if func.returns == "null" and qualified in self.legacy_returns:
            legacy = self.legacy_returns[qualified]
            if legacy != "null" and any(s.name == legacy for s in self.structs):
                return legacy
        return func.returns

    def emit_function(self, scope: Scope, func: Function, indent: str):
        qualified = f"{scope.path}.{func.name}"
        params = list(func.params)
        if scope.kind == "class":
            params.insert(0, Param("handle", "handle"))

        signature = []
        # Optional parameters only get a None default when every later parameter is optional too.
        trailing_optional = set()
        for param in reversed(params):
            if not param.optional:
                break
            trailing_optional.add(param.name)
        for param in params:
            annotation = py_type(param.type)
            if param.name in trailing_optional:
                signature.append(f"{py_name(param.name)}: {annotation} = None")
            else:
                signature.append(f"{py_name(param.name)}: {annotation}")

        returns = py_type(self.return_type(qualified, func))
        doc = list(func.doc)
        if doc:
            doc.append("")
        doc.append(f"API: {func.returns} {qualified}({', '.join(f'{p.type} {p.name}' for p in func.params)})")
        doc.append(f"Pixera returns: {returns}")

        names = ", ".join(f'"{p.name}"' for p in params)
        values = ", ".join(py_name(p.name) for p in params)
        optional_names = [f'"{p.name}"' for p in params if p.optional]
        optional = ", ".join(optional_names) + ("," if len(optional_names) == 1 else "")

        self.out.append(f"{indent}@staticmethod")
        # The function only builds the request; the annotation describes that, the docstring the reply.
        self.out.append(f"{indent}def {py_name(func.name)}({', '.join(signature)}) -> list:")
        self.out.extend(docstring(doc, indent + "    "))
        self.out.append(f'{indent}    return _request("{qualified}", [{names}], [{values}], ({optional}))')
        self.out.append("")
        self.count += 1

    def emit_scope(self, scope: Scope, indent: str):
        self.out.append(f"{indent}class {scope.name}:")
        doc = list(scope.doc) or [f"Pixera {scope.kind} {scope.path}"]
        self.out.extend(docstring(doc, indent + "    "))
        self.out.append("")
        for func in scope.functions:
            self.emit_function(scope, func, indent + "    ")
        for child in scope.children:
            self.emit_scope(child, indent + "    ")
        if not scope.functions and not scope.children:
            self.out.append(f"{indent}    pass")
            self.out.append("")

    def register_flat(self, scope: Scope, rel: str):
        """Collect backwards-compatible aliases (API.getScreens, API.Screen, ...)."""
        for func in scope.functions:
            if scope.kind != "namespace":
                continue
            target = f"{rel}.{py_name(func.name)}"
            name = py_name(func.name)
            if name in self.flat_functions:
                self.collisions.append(f"function {name}: kept {self.flat_functions[name]}, skipped {target}")
            else:
                self.flat_functions[name] = target
        for child in scope.children:
            child_rel = f"{rel}.{child.name}"
            if child.kind == "class":
                if child.name in self.flat_classes:
                    self.collisions.append(f"class {child.name}: kept {self.flat_classes[child.name]}, skipped {child_rel}")
                else:
                    self.flat_classes[child.name] = child_rel
            else:
                self.register_flat(child, child_rel)

    def generate(self) -> str:
        top_level = [c.name for c in self.root.children]
        self.out = [
            f"# AUTO-GENERATED by tools/generate_api.py from the Pixera API description (revision {self.revision}).",
            "# Do not edit by hand. Regenerate instead.",
            "",
            "from typing import Any, List, Optional",
            "",
            f"API_REVISION = {self.revision}",
            "",
            "",
            "class uint(int):",
            '    """Unsigned integer as used by the Pixera API."""',
            "",
            "",
            "class handle(int):",
            '    """Handle of a Pixera object (screen, timeline, layer, ...)."""',
            "",
            "",
            "class timelineParamValue:",
            '    """Opaque timeline parameter value."""',
            "",
            "",
        ]
        for struct in self.structs:
            self.out.append(f"class {struct.name}(dict):")
            fields = ", ".join(f"{f.name}: {py_type(f.type)}" for f in struct.fields)
            self.out.extend(docstring(struct.doc + [f"Returned as a dict with the keys: {fields}"], "    "))
            self.out.append("")
            self.out.append("")

        self.out += [
            "def _request(method: str, names: List[str], values: List[Any], optional=()) -> list:",
            '    """Build the [method, param_names, values] triple understood by Pixera.send().',
            "",
            "    Optional parameters that are None are left out of the request.",
            '    """',
            "    kept = [(n, v) for n, v in zip(names, values) if not (v is None and n in optional)]",
            "    return [method, [n for n, _ in kept], [v for _, v in kept]]",
            "",
            "",
            "class API:",
            f'    """All functions of the Pixera API, revision {self.revision}.',
            "",
            "    Namespaces mirror the API: API.Screens.getScreens(), API.Screens.Screen.getName(hdl).",
            "    For compatibility with earlier PixeraPy versions every namespace function and class",
            "    is also available directly on API, e.g. API.getScreens() or API.Screen.getName(hdl).",
            '    """',
            "",
        ]
        for child in self.root.children:
            self.emit_scope(child, "    ")
            if child.kind == "namespace":
                self.register_flat(child, child.name)

        self.out.append("    # ------------------------- flat aliases (compatibility) ------------------------- #")
        for name, target in self.flat_functions.items():
            if name in top_level:
                self.collisions.append(f"function {name}: name taken by a namespace, skipped {target}")
                continue
            self.out.append(f"    {name} = staticmethod({target})")
        for name, target in self.flat_classes.items():
            if name in top_level or name in self.flat_functions:
                self.collisions.append(f"class {name}: name taken, skipped {target}")
                continue
            self.out.append(f"    {name} = {target}")
        self.out.append("")
        return "\n".join(self.out)


def reference_markdown(revision: int, root: Scope) -> str:
    out = [
        f"# Pixera API reference (revision {revision})",
        "",
        "Auto-generated by `tools/generate_api.py` from the official API description. Every entry",
        "lists the Python call and the JSON-RPC method it sends. Class methods take the object",
        "handle as first argument.",
        "",
        "## Contents",
        "",
    ]

    def toc(scope: Scope, depth: int):
        for child in scope.children:
            anchor = child.path.lower().replace(".", "")
            out.append(f"{'  ' * depth}- [{child.path}](#{anchor})")
            toc(child, depth + 1)

    toc(root, 0)
    out.append("")

    def body(scope: Scope):
        for child in scope.children:
            out.append(f"## {child.path}")
            out.append("")
            if child.doc:
                out.extend(child.doc)
                out.append("")
            for struct in child.structs:
                fields = ", ".join(f"`{f.type} {f.name}`" for f in struct.fields)
                out.append(f"**struct {struct.name}**: {fields}")
                out.append("")
            py_path = "API." + child.path.split(".", 1)[1]
            for func in child.functions:
                args = [p.name for p in func.params]
                if child.kind == "class":
                    args.insert(0, "handle")
                sig = ", ".join(f"{p.type} {p.name}" for p in func.params)
                out.append(f"### `{py_path}.{func.name}({', '.join(args)})`")
                out.append("")
                out.append(f"`{func.returns} {child.path}.{func.name}({sig})`")
                out.append("")
                if func.doc:
                    out.append(" ".join(func.doc))
                    out.append("")
            body(child)

    body(root)
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("description", type=Path, help="pixera_api_comments_revXXX.txt")
    parser.add_argument("--legacy-json", type=Path, default=ROOT / "api" / "pixera_api_rev381.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    args = parser.parse_args(argv)

    revision, root = parse_description(args.description.read_text(encoding="utf-8-sig"))
    legacy = legacy_return_types(args.legacy_json if args.legacy_json and args.legacy_json.exists() else None)
    generator = Generator(revision, root, legacy)
    code = generator.generate()
    compile(code, str(args.out), "exec")

    args.out.write_text(code, encoding="utf-8")
    args.reference.parent.mkdir(parents=True, exist_ok=True)
    args.reference.write_text(reference_markdown(revision, root), encoding="utf-8")

    print(f"revision {revision}: {generator.count} functions -> {args.out}")
    for line in generator.collisions:
        print(f"  alias skipped: {line}", file=sys.stderr)


if __name__ == "__main__":
    main()
