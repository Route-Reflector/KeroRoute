import pytest
from pathlib import Path
import textwrap
import importlib


@pytest.fixture(autouse=True)
def project_root(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))


def _write(p: Path, content: str) -> Path:
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def test_get_commands_list_device_type_ok(tmp_path, monkeypatch):
    yaml_path = _write(tmp_path / "commands-lists.yaml", """
    commands_lists:
      cisco-precheck:
        device_type: cisco_ios
        description: precheck
        tags: [before, cisco_ios]
        commands_list:
          - show version
    """)
    import load_and_validate_yaml as lvy
    importlib.reload(lvy)  # ← 先にリロード（任意）
    monkeypatch.setattr(lvy, "COMMANDS_LISTS_FILE", str(yaml_path))  # ← パッチは最後！
    dt = lvy.get_commands_list_device_type("cisco-precheck")
    assert dt == "cisco_ios"


def test_get_commands_list_device_type_none_when_missing_key(tmp_path, monkeypatch):
    yaml_path = _write(tmp_path / "commands-lists.yaml", """
    commands_lists:
      palo-precheck:
        # device_type を未設定
        description: precheck
        tags: [before, paloalto]
        commands_list:
          - show system info
    """)
    import load_and_validate_yaml as lvy
    importlib.reload(lvy)
    monkeypatch.setattr(lvy, "COMMANDS_LISTS_FILE", str(yaml_path))
    assert lvy.get_commands_list_device_type("palo-precheck") is None


def test_get_commands_list_device_type_error_when_no_root_key(tmp_path, monkeypatch):
    yaml_path = _write(tmp_path / "commands-lists.yaml", """
    not_commands_lists:
      x: y
    """)
    import load_and_validate_yaml as lvy
    importlib.reload(lvy)
    monkeypatch.setattr(lvy, "COMMANDS_LISTS_FILE", str(yaml_path))
    with pytest.raises(ValueError):
        lvy.get_commands_list_device_type("any")


def test_get_commands_list_device_type_error_when_file_missing(tmp_path, monkeypatch):
    missing = tmp_path / "nope.yaml"
    import load_and_validate_yaml as lvy
    importlib.reload(lvy)
    monkeypatch.setattr(lvy, "COMMANDS_LISTS_FILE", str(missing))
    with pytest.raises(FileNotFoundError):
        lvy.get_commands_list_device_type("any")
