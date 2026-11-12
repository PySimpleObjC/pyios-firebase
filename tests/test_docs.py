"""Every public function and method documents each parameter in an ``Args:``
section, and documents no parameter it does not have.

Constructor parameters are documented in the class docstring. Private modules
(``_name.py``) and names are skipped, and so is the Apple sign-in delegate,
whose methods UIKit calls.
"""

import ast
import pathlib
import re

import pytest

PACKAGE = pathlib.Path(__file__).parent.parent / "src" / "pyios_firebase"
# Objective-C bridges that Firebase or UIKit call, not apps
SKIP_CLASSES = {
    "PyAppleSignInDelegate",
    "PyAppCheckProviderBridge",
    "PyAppCheckProviderFactory",
    "PyInAppMessagingDelegate",
    "PyInAppMessagingDisplay",
    "PyMessagingDelegate",
    "PyNotificationCenterDelegate",
}
LEGACY_MODULES: set[str] = set()
ARG_LINE = re.compile(r"^    \*{0,2}(\w+)(?: \([^)]*\))?:", re.MULTILINE)


def _params(fn: ast.FunctionDef) -> list[str]:
    args = fn.args
    names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    if args.vararg:
        names.append(args.vararg.arg)
    if args.kwarg:
        names.append(args.kwarg.arg)
    return [n for n in names if n not in ("self", "cls") and not n.startswith("_")]


def _documented(doc: str) -> list[str]:
    if "Args:" not in doc:
        return []
    section = doc.split("Args:", 1)[1]
    # the section ends at the next unindented line (Returns:, Raises:, text)
    section = re.split(r"\n(?=\S)", section, maxsplit=1)[0]
    return ARG_LINE.findall(section)


def _public_callables():
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name.startswith("_") and path.name != "__init__.py":
            continue
        if path.name in LEGACY_MODULES:
            continue
        rel = path.relative_to(PACKAGE)
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                yield f"{rel}:{node.name}", node, ast.get_docstring(node) or ""
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                if node.name in SKIP_CLASSES:
                    continue
                for item in node.body:
                    if not isinstance(item, ast.FunctionDef):
                        continue
                    if any(
                        isinstance(d, ast.Attribute) and d.attr == "setter"
                        for d in item.decorator_list
                    ):
                        continue  # documented on the property getter
                    name = f"{rel}:{node.name}.{item.name}"
                    if item.name == "__init__":
                        yield name, item, ast.get_docstring(node) or ""
                    elif not item.name.startswith("_"):
                        yield name, item, ast.get_docstring(item) or ""


CALLABLES = list(_public_callables())


def test_audit_finds_the_public_api():
    assert len(CALLABLES) > 100  # guards against the walk silently finding nothing


@pytest.mark.parametrize(
    ("name", "fn", "doc"), CALLABLES, ids=[c[0] for c in CALLABLES]
)
def test_parameters_are_documented(name, fn, doc):
    params = _params(fn)
    documented = _documented(doc)
    missing = [p for p in params if p not in documented]
    stale = [p for p in documented if p not in params]
    assert not missing, f"{name}: no Args entry for {missing}"
    assert not stale, f"{name}: Args documents parameters it does not have: {stale}"
