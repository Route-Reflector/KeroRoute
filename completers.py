from ruamel.yaml import YAML
from pathlib import Path
from typing import List, Set


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


def commands_list_names_completer(device_type: str, text: str) -> List[str]:
    commands_data = _load("commands-lists.yaml")["commands_lists"]
    return _match(list(commands_data.get(device_type, {}).keys()), text)


def config_list_names_completer(device_type: str, text: str) -> List[str]:
    config_data = _load("config-lists.yaml")["config_lists"]
    return _match(list(config_data.get(device_type, {}).keys()), text)
