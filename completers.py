from ruamel.yaml import YAML
from pathlib import Path
from typing import List, Set
import shlex


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
    inventory_data = _load("inventory.yaml")["all"]["hosts"]
    return _match(list(inventory_data.keys()), text)


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
    inventory_data = _load("inventory.yaml")["all"]["groups"]
    return _match(list(inventory_data.keys()), text)


def device_types_completer(_self, text :str, _line, _begidx, _endidx) -> List[str]:
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
    types: Set[str] = set()

    # 1. inventory.yaml
    inventory_data = _load("inventory.yaml")["all"]["hosts"]
    for host in inventory_data.values():
        types.add(host["device_type"])
    
    # 2. commands-lists.yaml
    commands_yaml = _load("commands-lists.yaml")["commands_lists"]
    types.update(commands_yaml.keys())

    # 3. config-lists.yaml
    config_yaml = _load("config-lists.yaml")["config_lists"]
    types.update(config_yaml.keys())

    # 4. プレフィックス一致で絞り込み
    device_type_list = []
    for device_type in sorted(types):
        if device_type.startswith(text):
            device_type_list.append(device_type)
    return device_type_list


def commands_list_names_completer(_self, text: str, line: str, _begidx, _endidx) -> List[str]:
    """
    line から --device_type の値を拾い、その下のリストを補完する。
    device_type が未入力なら全 device_type を横断した名前を返す。
        _self,                    # Cmd2 のインスタンス（使わないので "_"）
    text: str,                # いま補完中の部分文字列
    line: str,                # 入力行全体：--device_type の有無を調べる
    _begidx, _endidx          # 開始 / 終了インデックス（今回は未使用）
    """
    # ────────────────────────────────────────────────────────────────
    # commands-list 用 completer   ← 5 引数が必要
    # ────────────────────────────────────────────────────────────────

    # 1. shlexで行を分割(example: ["execute", "--device_type", "cisco_ios", ...]）
    try:
        tokens = shlex.split(line)
    except ValueError:
        return []

    # 2. --device_type <value> を 探して <value> を抜き取る
    device_type = None
    for i, tok in enumerate(tokens):
        if tok in ("-d", "--device_type") and i + 1 < len(tokens):
            device_type = tokens[i + 1]
            break
    
    commands_data = _load("commands-lists.yaml").get("commands_lists", {})

    # device_type が確定していれば、その型の下だけを見る
    if device_type and device_type in commands_data:
        names = list(commands_data[device_type].keys())
    else:
        # 未入力ならすべての device_type を横断した一覧
        names = []
        for device_dict in commands_data.values():
            for commands_list_name in device_dict.keys():
                names.append(commands_list_name)

    # プレフィックス一致で絞り込み → ソート済み候補を返す
    return _match(names, text)


def show_commands_list_names_completer(_self, text: str, line: str, begidx, endidx) -> List[str]:
    # show --commands_list 用のcompleter

    # shelxでコマンド全体をパース
    try:
        tokens = shlex.split(line)
    except ValueError:
        return []

    # --commands-list の位置を探して、入力済み引数を取得！
    try:
        idx = tokens.index("--commands-list")
        entered = tokens[idx + 1:]
    except (ValueError, IndexError):
        return []

    if len(entered) == 0:
        return device_types_completer(_self, text, line, begidx, endidx)
    elif len(entered) == 1:
        return commands_list_names_completer(_self, text, line, begidx, endidx)
    else:
        return []


def config_list_names_completer(_self, text: str, line: str, _begidx, _endidx) -> List[str]:
    """
    line から --device_type の値を拾い、その配下の config_list 名を補完する。
    device_type が未入力なら全 device_type を横断した一覧を返す。
        _self     : Cmd2 インスタンス（未使用なので "_"）
        text      : いま補完中の部分文字列
        line      : 入力行全体（--device_type の有無を調べる）
        _begidx   : text の開始位置（未使用）
        _endidx   : text の終了位置（未使用）
    """
    # 1. shlexで行を分割(example: ["configure", "--device_type", "cisco_ios", ...]）
    try:
        tokens = shlex.split(line)
    except ValueError:
        return []
    
    # 2. --device_type <value> を 探して <value> を抜き取る
    device_type = None
    for i, tok in enumerate(tokens):
        if tok in ("-d", "--device_type") and i + 1 < len(tokens):
            device_type = tokens[i + 1]
            break
    
    config_data = _load("config-lists.yaml").get("config_lists", {})

    # device_type が確定していれば、その型の下だけを見る
    if device_type and device_type in config_data:
        names = list(config_data[device_type].keys())
    else:
        # 未入力ならすべての device_type を横断した一覧
        names = []
        for device_dict in config_data.values():
            for config_list_name in device_dict.keys():
                names.append(config_list_name)

    # プレフィックス一致で絞り込み → ソート済み候補を返す
    return _match(names, text)


def show_config_list_names_completer(_self, text, line, begidx, endidx):
    try:
        tokens = shlex.split(line)
    except ValueError:
        return []

    try:
        idx = tokens.index("--config-list")
        entered = tokens[idx + 1:]
    except (ValueError, IndexError):
        return []

    if len(entered) == 0:
        return device_types_completer(_self, text, line, begidx, endidx)
    elif len(entered) == 1:
        return config_list_names_completer(_self, text, line, begidx, endidx)
    else:
        return []


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
