"""Compare two Pixera API descriptions and list new, removed and changed functions.

    python tools/api_diff.py api/pixera_api_comments_rev481.txt api/pixera_api_rev381.json

Each side may be a pixera_api_comments_revXXX.txt / pixera_api_plain_revXXX.txt file or an
old pixera_api.json description. Return types are ignored because the text format prints
struct returns as "null".
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_api import parse_description  # noqa: E402


def signatures_from_text(path: Path) -> dict:
    _, root = parse_description(path.read_text(encoding="utf-8-sig"))
    result = {}

    def walk(scope):
        for func in scope.functions:
            params = ", ".join(f"{p.type} {p.name}".replace("boolean", "bool") for p in func.params)
            result[f"{scope.path}.{func.name}"] = params
        for child in scope.children:
            walk(child)

    walk(root)
    return result


def signatures_from_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    result = {}

    def walk(node, prefix):
        for func in node.get("functions", []) + node.get("methods", []):
            params = ", ".join(f"{p['type']} {p['name']}".replace("boolean", "bool") for p in func.get("params", []))
            result[f"{prefix}.{func['name']}"] = params
        for key in ("namespaces", "classes"):
            for child in node.get(key, []):
                walk(child, f"{prefix}.{child['name']}")

    walk(data, data["name"])
    return result


def load(path: Path) -> dict:
    return signatures_from_json(path) if path.suffix == ".json" else signatures_from_text(path)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    new, old = load(Path(sys.argv[1])), load(Path(sys.argv[2]))
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(name for name in set(new) & set(old) if new[name] != old[name])

    print(f"{sys.argv[1]}: {len(new)} functions, {sys.argv[2]}: {len(old)} functions\n")
    print(f"NEW ({len(added)})")
    for name in added:
        print(f"  {name}({new[name]})")
    print(f"\nREMOVED ({len(removed)})")
    for name in removed:
        print(f"  {name}({old[name]})")
    print(f"\nCHANGED ({len(changed)})")
    for name in changed:
        print(f"  {name}\n    new: ({new[name]})\n    old: ({old[name]})")


if __name__ == "__main__":
    main()
