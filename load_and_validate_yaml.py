from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError, MarkedYAMLError 
from pathlib import Path


#####################
### CONST_SECTION ###
#####################
SYS_CONFIG_FILE = "sys_config.yaml"
INVENTORY_YAML_FILE = "inventory.yaml"
COMMANDS_LISTS_FILE = "commands-lists.yaml"
CONFIG_LISTS_FILE = "config-lists.yaml"


def _load_yaml_file_safe(file_path: Path, file_label: str) -> dict:
    _yaml = YAML(typ="safe")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = _yaml.load(f)
    except MarkedYAMLError as e:
        mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
        loc = f" (line {mark.line+1}, column {mark.column+1})" if mark else ""
        problem = getattr(e, "problem", None) or getattr(e, "context", None) or str(e)
        raise ValueError(f"{file_label} のYAML構文エラーだケロ🐸{loc}\n{problem}") from e
    except YAMLError as e:  # その他のYAMLエラー
        raise ValueError(f"{file_label} のYAML読込エラーだケロ🐸\n{e}") from e
    
    if data is None:
        raise ValueError(f"{file_label} が空だケロ🐸")
    if not isinstance(data, dict):
        raise ValueError(f"{file_label} のトップレベルはマップじゃないケロ🐸")

    return data


def load_sys_config():
    """
    sys_config.yaml を 読み込んで dict を返す。
    キャッシュはしない(呼び出し側で保持する。)
    """
    config_path = Path(SYS_CONFIG_FILE)
    if not config_path.exists():
        raise FileNotFoundError(f"'{SYS_CONFIG_FILE}' が見つからないケロ🐸")
    
    sys_config_data = _load_yaml_file_safe(config_path, SYS_CONFIG_FILE)
    return sys_config_data


def get_validated_inventory_data(host: str = None, group: str =None) -> dict:
    """
    inventory.yaml を読み込み、指定されたホストまたはグループの存在を検証する。

    Parameters
    ----------
    host : str, optional
        inventory.yaml 内のホスト名。指定されている場合は存在を検証する。
    group : str, optional
        inventory.yaml 内のグループ名。指定されている場合は存在を検証する。

    Returns
    -------
    dict
        パース済みの inventory データ。

    Raises
    ------
    FileNotFoundError
        inventory.yaml が見つからない場合。
    ValueError
        指定された host または group が inventory.yaml に存在しない場合。
    """
    inventory_path = Path(INVENTORY_YAML_FILE)
    if not inventory_path.exists():
        raise FileNotFoundError(f"'{INVENTORY_YAML_FILE}' が存在しないケロ🐸")

    inventory_data = _load_yaml_file_safe(inventory_path, INVENTORY_YAML_FILE)

    all_node = inventory_data.get("all")
    if not isinstance(all_node, dict):
        raise ValueError("inventory.yamlの 'all' が無いか形式が不正ケロ🐸")

    hosts = all_node.get("hosts", {})
    groups = all_node.get("groups", {})
    if not isinstance(hosts, dict) or not isinstance(groups, dict):
        raise ValueError("inventory.yaml の 'all.hosts' または 'all.groups' の形式が不正ケロ🐸")

    if host and host not in hosts:
        raise ValueError(f"ホスト '{host}' はinventory.yamlに存在しないケロ🐸")

    elif group and group not in groups:
        raise ValueError(f"グループ '{group}' はinventory.yamlに存在しないケロ🐸")
    
    return inventory_data


def get_validated_commands_list(args) -> list[str]:
    """
    commands-lists.yaml（フラット構造）に基づいて、
    指定されたコマンドリストの存在を検証し、リスト本体を返す。

    Args:
        args: argparse.Namespace - コマンドライン引数（args.commands_list を参照）

    Returns:
        list[str]: 実行するコマンドの配列

    Raises:
        FileNotFoundError: commands-lists.yaml が存在しない場合
        ValueError: commands_list が未指定/未定義、またはcommands_listが空の場合

    Example:
        commands_lists: # TOP LEVEL
          cisco-precheck: # key only. commands-list-name 
            device_type: cisco_ios
            description: precheck_commands_before_config_change
            tags: [before, cisco_ios] 
            commands_list: 
             - command
             - command
             - command       
    """
    # ✅ commands-listが指定されていない場合はError
    if not getattr(args, "commands_list", None):
        raise ValueError("-L or --commands-listが指定されていないケロ🐸")

    # ✅ ファイル存在チェック
    commands_lists_path = Path(COMMANDS_LISTS_FILE)
    if not commands_lists_path.exists():
        raise FileNotFoundError(f"'{COMMANDS_LISTS_FILE}' が見つからないケロ🐸")

    # ✅ YAML読み込み
    commands_lists_data = _load_yaml_file_safe(commands_lists_path, COMMANDS_LISTS_FILE)

    if "commands_lists" not in commands_lists_data:
        raise ValueError(f"commands_lists は '{COMMANDS_LISTS_FILE}' に存在しないケロ🐸")

    # ルートキー検証
    commands_lists_root = commands_lists_data.get("commands_lists")

    if  not isinstance(commands_lists_root, dict):
        raise ValueError(f"'{COMMANDS_LISTS_FILE}' の形式が不正ケロ🐸")

    commands_list_name = args.commands_list
    commands_list_definition = commands_lists_root.get(commands_list_name)

    # ✅ リスト名の存在チェック（フラット構造：トップレベルのキーが list_name）
    if commands_list_name not in commands_lists_root:
        raise ValueError(f"コマンドリスト: '{commands_list_name}' は '{COMMANDS_LISTS_FILE}' に存在しないケロ🐸")
    
    if not isinstance(commands_list_definition, dict):
        raise ValueError(f"コマンドリスト: '{commands_list_name}' の 内容の形式が不正ケロ🐸")

    execution_commands = commands_list_definition.get("commands_list")

    if not execution_commands:
        raise ValueError(f"コマンドリスト: '{commands_list_name}' の 'commands_list' が空ケロ🐸")

    if not isinstance(execution_commands, list):
        raise ValueError(f"コマンドリスト: '{commands_list_name}' の 'commands_list' の形式が不正ケロ🐸")
    
    # 文字列か検証
    for ec in execution_commands:
        if not isinstance(ec, str):
            raise ValueError(f"コマンドリスト: '{commands_list_name}' の 'commands_list' に文字列以外が混入してるケロ🐸")

    # 前後空白除去 and 空行除去
    execution_commands = [command.strip() for command in execution_commands if command.strip()]

    if not execution_commands:
        raise ValueError(f"コマンドリスト: '{commands_list_name}' の 'commands_list' が空（空行/空白のみ）ケロ🐸")

    return execution_commands


def get_validated_config_list(args) -> list[str]:
    """
    config-lists.yaml（フラット構造）に基づいて、
    指定されたコンフィグリストの存在と形式を検証し、リスト本体（list[str]）を返す。

    Args:
        args (argparse.Namespace): コマンドライン引数（args.config_list を使用）

    Returns:
        list[str]: 実行するコンフィグ行の配列

    Raises:
        FileNotFoundError: config-lists.yaml が存在しない場合
        ValueError: ルートキー 'config_lists' が無い／形式不正、指定リストが未定義、
                    もしくは 'config_list' が空または文字列リストでない場合

    Example:
        config_lists:  # TOP LEVEL
          cisco-loopback-change:  # <- config-list name
            device_type: cisco_ios
            description: loopback 0 configuration
            tags: [configure, cisco_ios]
            config_list:
              - interface Loopback0
              - description example
              - ip address 10.0.0.1 255.255.255.255
              - no shutdown
    """

    # ✅ config-listが指定されている場合は先に存在チェック

    if not getattr(args, "config_list", None):
        raise ValueError("-L or --config-list が指定されていないケロ🐸")

    config_lists_path = Path(CONFIG_LISTS_FILE)
    if not config_lists_path.exists():
        raise FileNotFoundError(f"'{CONFIG_LISTS_FILE}' が見つからないケロ🐸")

    config_lists_data = _load_yaml_file_safe(config_lists_path, CONFIG_LISTS_FILE)
    if "config_lists" not in config_lists_data:
        raise ValueError(f"config_lists は {CONFIG_LISTS_FILE} に存在しないケロ🐸")
    
    config_lists_root =  config_lists_data.get("config_lists")

    if not isinstance(config_lists_root, dict):
        raise ValueError(f"{CONFIG_LISTS_FILE} の形式が不正ケロ🐸")
    
    config_list_name = args.config_list
    
    if config_list_name not in config_lists_root:
        raise ValueError(f"コンフィグリスト '{config_list_name}' は '{CONFIG_LISTS_FILE}' に存在しないケロ🐸")
    
    config_list_definition = config_lists_root.get(config_list_name)

    configure_commands = config_list_definition.get("config_list")
    
    if not configure_commands:
        raise ValueError(f"コンフィグリスト: '{config_list_name}' の 'config_list' が空ケロ🐸")
    if not isinstance(configure_commands, list):
        raise ValueError(f"コンフィグリスト: '{config_list_name}' の 'config_list' は文字列のリストじゃないケロ🐸")

    # 文字列か検証
    for cc in configure_commands:
        if not isinstance(cc, str):
            raise ValueError(f"コンフィグリスト: '{config_list_name}' の 'config_list' に文字列以外が混入してるケロ🐸")

    # 前後空白除去 and 空行除去
    configure_commands = [command.strip() for command in configure_commands if command.strip()]

    if not configure_commands:
        raise ValueError(f"コンフィグリスト: '{config_list_name}' の 'config_list' が空（空行/空白のみ）ケロ🐸")

    return configure_commands


def validate_device_type_for_list(hostname: str, node_device_type: str | None,
                                  list_name:str, list_device_type: str | None) -> bool:
    """
    対象ホストの device_type とリスト側の device_type が一致するか検証する。
    - ここではメッセージ表示は行わず、ValueError を投げるだけ。
    - 上位（executor.py / configure.py）で try/except して表示やスキップ/続行を決める。
    """
    # List側が未設定
    if not list_device_type:
        raise ValueError(f"LIST: {list_name} に device_type が未設定ケロ🐸")
    
    # host側が未設定
      # 簡単な入力対策(大文字小文字 -> 小文字に統一, 前後スペース削除)
    if not node_device_type:
        raise ValueError(f"NODE: {hostname} に device_type が未設定ケロ🐸")
    
    node_dt_ls = node_device_type.lower().strip()
    list_dt_ls = list_device_type.lower().strip()

    if node_dt_ls != list_dt_ls:
        raise ValueError(
            f"NODE: {hostname} , LIST: {list_name} ❌ device_type 不一致ケロ🐸 "
            f"(NODE: {node_device_type} / LIST: {list_device_type})"
        )
    return True


def get_commands_list_device_type(list_name: str) -> str | None:
    """
    commands-lists.yaml から指定リストの device_type を返す。
    見つからない・未設定なら None を返す。
    """
    # ✅ ファイル存在チェック
    commands_lists_path = Path(COMMANDS_LISTS_FILE)
    if not commands_lists_path.exists():
        raise FileNotFoundError(f"{COMMANDS_LISTS_FILE}が見つからないケロ🐸")

    # ✅ YAML読み込み
    commands_lists_data = _load_yaml_file_safe(commands_lists_path, COMMANDS_LISTS_FILE)
    
    if "commands_lists" not in commands_lists_data:
        raise ValueError(f"commands_lists は {COMMANDS_LISTS_FILE} に存在しないケロ🐸")

    commands_lists_root = commands_lists_data.get("commands_lists")
    
    if not isinstance(commands_lists_root, dict):
        raise ValueError(f"{COMMANDS_LISTS_FILE} の形式が不正ケロ🐸")
    
    commands_list_definition = commands_lists_root.get(list_name)

    if not isinstance(commands_list_definition, dict):
        return None
        
    commands_lists_device_type = commands_list_definition.get("device_type")
    
    if not isinstance(commands_lists_device_type, str):
        return None
    
    commands_lists_device_type = commands_lists_device_type.strip()

    if not commands_lists_device_type:
        return None
    
    return commands_lists_device_type 
