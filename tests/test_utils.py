# tests/test_utils.py

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from utils import sanitize_filename_for_log, is_valid_ip

def test_sanitize_filename_for_log():
    assert sanitize_filename_for_log("test log.txt") == "test-log.txt"
    assert sanitize_filename_for_log("foo/bar:baz") == "foo_bar_baz"
    assert sanitize_filename_for_log('a?b*c"d<e>f|g') == 'a_b_c_d_e_f_g'
    assert sanitize_filename_for_log("show ip int brief") == "show-ip-int-brief"

def test_is_valid_ip():
    assert is_valid_ip("192.168.1.1") is True
    assert is_valid_ip("8.8.8.8") is True
    assert is_valid_ip("10.0.0.256") is False  # 256は不正
    assert is_valid_ip("999.999.999.999") is False
    assert is_valid_ip("abcd") is False
    assert is_valid_ip("this.is.not.an.ip") is False


def test_is_valid_ip_ipv6():
    # 正常なIPv6アドレス（圧縮あり）
    assert is_valid_ip("2001:0db8:85a3::8a2e:0370:7334") is True
    # 正常なIPv6アドレス（全展開）
    assert is_valid_ip("2001:0db8:0000:0000:0000:0000:0000:0001") is True
    # 短縮形式
    assert is_valid_ip("::1") is True
    assert is_valid_ip("fe80::") is True
    # IPv6 + Zone ID（リンクローカル）
    assert is_valid_ip("fe80::1%eth0") is True

    # 異常系（無効なIPv6）
    assert is_valid_ip("2001::85a3::8a2e") is False  # コロンが多すぎる
    assert is_valid_ip("abcd:1234") is False  # セグメント不足
    assert is_valid_ip("fe80:::1") is False  # コロンの使い方が異常
    assert is_valid_ip("::gggg") is False  # 無効な文字

