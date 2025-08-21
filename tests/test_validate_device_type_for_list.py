import pytest
from pathlib import Path


@pytest.fixture
def project_root(monkeypatch):
    """プロジェクトルートを import パスに追加するfixture"""
    root = Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root))  # sys.path.append より安全
    return root


def test_validate_device_type_for_list_ok(project_root):
    from load_and_validate_yaml import validate_device_type_for_list
    assert validate_device_type_for_list(
        hostname="R1",
        node_device_type="cisco_ios",
        list_name="cisco-precheck",
        list_device_type="cisco_ios",
    ) is True

def test_validate_device_type_for_list_case_insensitive_and_spaces(project_root):
    from load_and_validate_yaml import validate_device_type_for_list
    assert validate_device_type_for_list(
        hostname="R1",
        node_device_type="  CISCO_IOS ", # 大文字
        list_name="cisco-precheck",
        list_device_type=" cisco_ios ",
    ) is True

def test_validate_device_type_for_list_list_missing(project_root):
    from load_and_validate_yaml import validate_device_type_for_list
    with pytest.raises(ValueError) as ei:
        validate_device_type_for_list(
            hostname="R1",
            node_device_type="cisco_ios",
            list_name="cisco-precheck",
            list_device_type=None,
        )
    assert "LIST: cisco-precheck に device_type が未設定" in str(ei.value)

def test_validate_device_type_for_list_node_missing(project_root):
    from load_and_validate_yaml import validate_device_type_for_list
    with pytest.raises(ValueError) as ei:
        validate_device_type_for_list(
            hostname="R1",
            node_device_type=None,
            list_name="cisco-precheck",
            list_device_type="cisco_ios",
        )
    assert "NODE: R1 に device_type が未設定" in str(ei.value)

def test_validate_device_type_for_list_mismatch(project_root):
    from load_and_validate_yaml import validate_device_type_for_list
    with pytest.raises(ValueError) as ei:
        validate_device_type_for_list(
            hostname="R1",
            node_device_type="cisco_ios",
            list_name="palo-precheck",
            list_device_type="paloalto_panos",
        )
    # 文言の要点だけ確認（厳密一致にしすぎない）
    msg = str(ei.value)
    assert "device_type 不一致" in msg and "NODE: R1" in msg and "LIST: palo-precheck" in msg