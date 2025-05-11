import re
import ipaddress



def sanitize_filename_for_log(text: str) -> str:
    """
    ファイル名に使用できない文字を安全な文字に変換する。
    禁止文字: \\ / : * ? " < > | -> "_" アンダースコア
    スペース: " " -> "-" ハイフン
    """

    text = text.replace(" ", "-")
    return re.sub(r'[\\/:*?"<>|]', '_', text).strip()


def is_valid_ip(ip: str) -> bool:
    """IPv4アドレス形式かを判定する（今後--ip用などに）"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

