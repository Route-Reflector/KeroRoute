from ruamel.yaml import YAML
from pathlib import Path
from typing import List, Set
import shlex
import platform

from load_and_validate_yaml import COMMANDS_LISTS_FILE, CONFIG_LISTS_FILE

_yaml = YAML()


def _load(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as file_path:
        return _yaml.load(file_path)


def _match(candidates: List[str], text:str) -> List[str]:
    candidate_list = []
    for candidate in candidates:
        if candidate.startswith(text):
            candidate_list.append(candidate)
    return candidate_list


def host_names_completer(_self, text :str, _line, _begidx, _endidx) -> List[str]:
    """
    cmd2 用タブ補完コールバック。

    Parameters
    ----------
    _self   : Cmd インスタンス。今回は未使用なので先頭に `_`。
    text    : 今まさに補完しようとしている “部分文字列”。
    _line   : 行全体。解析しないので `_`。
    _begidx : text の開始位置（行頭からのインデックス）。
    _endidx : text の終了位置。同じく未使用。

    Returns
    -------
    list[str]
        text をプレフィックスに持つ候補一覧（ソート済み）。
    """
    try:
        inventory_data = _load("inventory.yaml")["all"]["hosts"]
        return _match(list(inventory_data.keys()), text)
    except Exception: # ファイルがない、壊れてる、構造がないとか
        return []


def group_names_completer(_self, text :str, _line, _begidx, _endidx) -> List[str]:
    """
    cmd2 用タブ補完コールバック。

    Parameters
    ----------
    _self   : Cmd インスタンス。今回は未使用なので先頭に `_`。
    text    : 今まさに補完しようとしている “部分文字列”。
    _line   : 行全体。解析しないので `_`。
    _begidx : text の開始位置（行頭からのインデックス）。
    _endidx : text の終了位置。同じく未使用。

    Returns
    -------
    list[str]
        text をプレフィックスに持つ候補一覧（ソート済み）。
    """
    try:
        inventory_data = _load("inventory.yaml")["all"]["groups"]
        return _match(list(inventory_data.keys()), text)
    except Exception: # ファイルがない、壊れてる、構造がないとか
        return []


def device_types_completer(_self, text :str, _line, _begidx, _endidx) -> List[str]:
    """
    cmd2 用タブ補完コールバック（--device_type 用）。

    Sources
    -------
    候補は以下の3種類から収集する:
      1. inventory.yaml の all.hosts[].device_type
      2. commands-lists.yaml の各 commands_list の device_type
      3. config-lists.yaml の各 config_list の device_type

    Parameters
    ----------
    _self   : Cmd インスタンス。未使用なので "_"。
    text    : 今まさに補完しようとしている部分文字列。
    _line   : 行全体。未使用。
    _begidx : text の開始位置（行頭からのインデックス）。未使用。
    _endidx : text の終了位置。未使用。

    Returns
    -------
    list[str]
        text をプレフィックスに持つ device_type 候補一覧（ソート済み）。
    """   
    types: Set[str] = set()

    # 1. inventory.yaml
    try:
        inventory_data = _load("inventory.yaml")["all"]["hosts"]
        for host in inventory_data.values():
            types.add(host["device_type"])
    except Exception:
        pass # 壊れててもかけてても静かに無視
        
    # 2. commands-lists.yaml
    try:
        commands_lists_data = _load(COMMANDS_LISTS_FILE)["commands_lists"]
        for commands_list_name in commands_lists_data.keys():    
            types.add(commands_lists_data[commands_list_name]["device_type"])
    except Exception:
        pass # 壊れててもかけてても静かに無視

    # 3. config-lists.yaml
    try:
        config_lists_data = _load(CONFIG_LISTS_FILE)["config_lists"]
        for config_list_name in config_lists_data.keys():
            types.add(config_lists_data[config_list_name]["device_type"])
    except Exception:
        pass # 壊れててもかけてても静かに無視

    # 4. プレフィックス一致で絞り込み
    device_type_list = []
    for device_type in sorted(types):
        if device_type.startswith(text):
            device_type_list.append(device_type)
    return device_type_list


def commands_list_names_completer(_self, text: str, line: str, _begidx, _endidx) -> List[str]:
    commands_lists_file_path = Path(COMMANDS_LISTS_FILE)
    if not commands_lists_file_path.exists():
        return []
    
    try:
        commands_lists_yaml = _load(commands_lists_file_path).get("commands_lists", {})
        if not isinstance(commands_lists_yaml, dict):
            return []
    except Exception:
        # 壊れているyamlなどは静かに空のリストを返す。
        return []

    names = []
    for commands_list_name in commands_lists_yaml.keys():
            names.append(commands_list_name)

    # プレフィックス一致で絞り込み → ソート済み候補を返す
    return _match(names, text)


def config_list_names_completer(_self, text: str, line: str, _begidx, _endidx) -> List[str]:
    """
    line から  config_list 名を補完する。
        _self     : Cmd2 インスタンス（未使用なので "_"）
        text      : いま補完中の部分文字列
        line      : 入力行全体
        _begidx   : text の開始位置（未使用）
        _endidx   : text の終了位置（未使用）
    """
    config_lists_file_path = Path(CONFIG_LISTS_FILE)
    if not config_lists_file_path.exists():
        return []
    
    try:
        config_lists_yaml = _load(config_lists_file_path).get("config_lists", {})
        if not isinstance(config_lists_yaml, dict):
            return []
    except Exception:
        # 壊れているyamlなどは静かに空のリストを返す。
        return []

    names = []
    for config_list_name in config_lists_yaml.keys():
            names.append(config_list_name)

    # プレフィックス一致で絞り込み → ソート済み候補を返す
    return _match(names, text)   


def log_filename_completer(_self, text, line, begidx, endidx):
    # :TODO ログファイルの数が増えたときに1000個とか表示されてしまうので対策が必要。
    # KeroRouteでは、ログファイル補完の候補リストは下に行くほど新しいものが表示される仕様です🐸📄✨
    # 本当は上を最新にしたかったのですが、仕様上難しそうです。🐸📄✨
    # NOTE: nargs=2 でも2つ目の補完が効いているが、cmd2の挙動によるラッキーな仕様かもしれない🐸
    # 必要なら将来的に「引数位置に応じた補完ロジック」を検討すること。
    try:
        tokens = shlex.split(line)
    except ValueError:
        return []

    # デフォルトは execute
    mode = "execute"

    # --mode があれば抽出
    if "--mode" in tokens:
        try:
            mode = tokens[tokens.index("--mode") + 1]
        except IndexError:
            pass

    log_root = Path("logs") / mode
    all_logs = sorted(log_root.glob("*/*.log"), key=lambda p: str(p.name), reverse=True)

    # 🐸 NOTE: cmd2の補完順が勝手にソートされる問題への対策
    # printを1回でも入れると、resultの順序がそのまま反映される不思議な仕様…
    # 下のprint行をコメントアウトする、しないで昇順と降順が変わってしまう。
    result = []
    for log_path in all_logs:
        if log_path.name.startswith(text):
            # print(f"match: {log_path.name}")
            result.append(log_path.name)
        
    return result
    # return list(reversed(result))


def serial_choices_provider(_arg_tokens=None) -> List[str]:
    """
    choices_provider 用。
    - pyserial があれば list_ports の結果を返す
    - なければ OS ごとの代表的なパターンを glob して存在確認
    - 最終的に候補が空なら OS ごとのフォールバックを返す
    """
    ports: List[str] = []

    # ❶ pyserialがあればそれを使う
    try:
        from serial.tools import list_ports
        for port in list_ports.comports():
            if port and getattr(port, "device", None):
                ports.add(str(port.device))
    except Exception:
        pass

    # ❷ OSごとの代表的なパターンをglob
    if not ports:
        system = platform.system().lower()
        patterns: List[str] = []

        if system == "linux":
            patterns = ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*"]
        elif system == "darwin":
            patterns = ["/dev/tty.usbserial*", "/dev/tty.usbmodem*",
                        "/dev/cu.usbserial*", "/dev/cu.usbmodem*"]
        elif system == "windows":
        # Windows は COM ポートを1〜256まで一括で候補に
            patterns = [f"COM{i}" for i in range(1, 257)]
        
        if patterns and system != "windows":
            for pattern in patterns:
                for pat in Path("/dev").glob(pattern.split("/")[-1]):
                    if pat.exists():
                        ports.append(str(pat))
        elif system == "windows":
            ports.extend(patterns)
    
    # ③ まだ空ならフォールバック
    if not ports:
        system = platform.system().lower()
        if system == "linux":
            ports = ["/dev/ttyUSB0"]
        elif system == "darwin":
            ports = ["/dev/cu.usbserial", "/dev/cu.usbmodem"]
        elif system == "windows":
            ports = ["COM1"]
        else:
            ports = ["/dev/ttyUSB0"]

    return sorted(set(ports))