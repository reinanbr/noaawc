from pathlib import Path
import ast


def _load_setup_call_kwargs() -> dict[str, ast.AST]:
    setup_py = Path(__file__).resolve().parents[1] / "setup.py"
    content = setup_py.read_text(encoding="utf-8")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setup":
            return {kw.arg: kw.value for kw in node.keywords if kw.arg is not None}

    raise AssertionError("setup() call not found in setup.py")


def test_setup_version_is_031():
    kwargs = _load_setup_call_kwargs()
    version_node = kwargs.get("version")
    assert isinstance(version_node, ast.Constant)
    assert version_node.value == "0.3.1"


def test_setup_does_not_require_basemap():
    kwargs = _load_setup_call_kwargs()
    requires_node = kwargs.get("install_requires")
    assert isinstance(requires_node, ast.List)

    install_requires = []
    for item in requires_node.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            install_requires.append(item.value.lower())

    assert "basemap" not in install_requires
