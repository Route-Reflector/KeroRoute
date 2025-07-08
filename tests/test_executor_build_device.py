import pytest
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from types import SimpleNamespace
from executor import _build_device_from_ip
from executor import _build_device_from_host
from executor import _build_device_from_group


def test_build_device_from_ip():
    args = SimpleNamespace(
        device_type="cisco_ios",
        ip="192.0.2.1",
        username="admin",
        password="password",
        port=22,
        timeout=10
    )

    device, hostname = _build_device_from_ip(args)

    assert isinstance(device, dict)
    assert device["ip"] == "192.0.2.1"
    assert hostname == "192.0.2.1"


def test_build_device_from_host():


    args = SimpleNamespace(
        host="R1"
    )

    # モックのinventory_data（最低限でOK）
    inventory_data = {
        "all": {
            "hosts": {
                "R1": {
                    "hostname": "R1",
                    "ip": "192.0.2.1",
                    "device_type": "cisco_ios",
                    "username": "admin",
                    "password": "password",
                    "port": 22,
                    "timeout": 10
                }
            }
        }
    }

    device, hostname = _build_device_from_host(args, inventory_data)
    assert isinstance(device, dict)
    assert device["ip"] == "192.0.2.1"
    assert device["device_type"] == "cisco_ios"
    assert hostname == "R1"


def test_build_device_from_group():


    args = SimpleNamespace( group = "cisco_ios")

    inventory_data = {
        "all": {
            "hosts": {
                "R1": {
                    "hostname": "R1",
                    "ip": "192.168.10.10",
                    "username": "cisco",
                    "password": "cisco",
                    "device_type": "cisco_ios",
                    "port": 22,
                    "timeout": 10,
                    "ttl": 64,
                    "tags": ["core", "lab"],
                    "description": "東京オフィスのルータ"
                },
                "R2": {
                    "hostname": "R2",
                    "ip": "192.168.10.11",
                    "username": "cisco",
                    "password": "cisco",
                    "device_type": "cisco_ios",
                    "port": 22,
                    "timeout": 10,
                    "ttl": 64,
                    "tags": ["branch"],
                    "description": "大阪支店のルータ"
                },
                "R3": {
                    "hostname": "R3",
                    "ip": "192.168.10.12",
                    "username": "cisco",
                    "password": "cisco",
                    "device_type": "cisco_ios",
                    "port": 22,
                    "timeout": 10,
                    "ttl": 64,
                    "tags": ["backup"],
                    "description": "災害対策用のバックアップルータ"
                },
                "R4": {
                    "hostname": "R4",
                    "ip": "192.168.10.13",
                    "username": "cisco",
                    "password": "cisco",
                    "device_type": "cisco_ios",
                    "port": 22,
                    "timeout": 10,
                    "ttl": 64,
                    "tags": ["test"],
                    "description": "テスト環境のルータ"
                },
            },
            "groups": {
                "cisco_ios": {
                    "description": "Cisco IOSデバイスをまとめた標準グループ",
                    "tags": ["ios", "production"],
                    "hosts": ["R1", "R2", "R3", "R4"]
                },
                "lab_devices": {
                    "description": "ラボ・検証用機器グループ",
                    "tags": ["lab", "testing"],
                    "hosts": ["R1"]
                }
            }
        }
    }


    device_list, hostname_for_log_list = _build_device_from_group(args, inventory_data)

    assert isinstance(device_list, list)
    assert isinstance(hostname_for_log_list, list)

    assert len(device_list) == 4
    assert len(hostname_for_log_list) == 4

    """R2"""
    assert device_list[1]["ip"] == "192.168.10.11"
    assert device_list[1]["device_type"] == "cisco_ios"

    assert hostname_for_log_list[0] == "R1"
    assert hostname_for_log_list[3] == "R4"

