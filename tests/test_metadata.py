from pathlib import Path


def test_setup_version_is_030():
    setup_py = Path(__file__).resolve().parents[1] / "setup.py"
    content = setup_py.read_text(encoding="utf-8")
    assert "version='0.3.0'" in content
