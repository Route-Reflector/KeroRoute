from ruamel.yaml import YAML
from pathlib import Path

#####################
### CONST_SECTION ###
#####################
SYS_CONFIG_FILE = ""
INVENTORY_YAML_FILE = ""
COMMANDS_LISTS_FILE = "commands-lists.yaml"
CONFIG_LISTS_FILE = "config-lists.yaml"

yaml = YAML()

def load_sys_config():
    """
    sys_config.yaml を 読み込んで dict を返す。
    キャッシュはしない(呼び出し側で保持する。)
    """
    config_path = Path("sys_config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("sys_config.yaml が見つからないケロ🐸")

    with open(config_path, "r", encoding="utf-8") as f:
        sys_config_data = yaml.load(f)

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
    # Errorはraiseするが表示はexecuterやconfigure側で対応。

    inventory_path = Path("inventory.yaml")
    if not inventory_path.exists():
        raise FileNotFoundError("inventory.yamlが存在しないケロ🐸")

    with open(inventory_path, "r", encoding="utf-8") as inventory:
        inventory_data = yaml.load(inventory)

    if host and host not in inventory_data["all"]["hosts"]:
            msg = f"ホスト '{host}' はinventory.yamlに存在しないケロ🐸"
            raise ValueError(msg)

    elif group and group not in inventory_data["all"]["groups"]:
            msg = f"グループ '{group}' はinventory.yamlに存在しないケロ🐸"
            raise ValueError(msg)
    
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
        raise FileNotFoundError(f"{COMMANDS_LISTS_FILE}が見つからないケロ🐸")

    # ✅ YAML読み込み
    with open(commands_lists_path, "r", encoding="utf-8") as f:
        commands_lists_data = yaml.load(f)

    # ✅ ルートキー検証
    if "commands_lists" not in commands_lists_data:
        raise ValueError(f"commands_lists は {COMMANDS_LISTS_FILE} に存在しないケロ🐸")

    if  not isinstance(commands_lists_data["commands_lists"], dict):
        raise ValueError(f"{COMMANDS_LISTS_FILE} の形式が不正ケロ🐸")

    commands_list_name = args.commands_list
    commands_lists_dict = commands_lists_data["commands_lists"]

    # ✅ リスト名の存在チェック（フラット構造：トップレベルのキーが list_name）
    if commands_list_name not in commands_lists_dict:
        raise ValueError(f"コマンドリスト: '{commands_list_name}'は{COMMANDS_LISTS_FILE}に存在しないケロ🐸")

    exec_commands = commands_lists_dict[commands_list_name].get("commands_list")

    if not exec_commands:
        raise ValueError(f"コマンドリスト: '{commands_list_name}'の'commands_list'が空ケロ🐸")

    if not isinstance(exec_commands, list):
        raise ValueError(f"コマンドリスト: '{commands_list_name}'の'commands_list'の形式が不正ケロ🐸")

    return exec_commands


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

    with open(config_lists_path, "r", encoding="utf-8") as f:
        config_lists_data = yaml.load(f)

    if "config_lists" not in config_lists_data:
        raise ValueError(f"config_lists は {CONFIG_LISTS_FILE} に存在しないケロ🐸")

    if not isinstance(config_lists_data["config_lists"], dict):
        raise ValueError(f"{CONFIG_LISTS_FILE} の形式が不正ケロ🐸")

    
    config_lists =  config_lists_data["config_lists"]
    config_list_name = args.config_list

    if config_list_name not in config_lists:
        raise ValueError(f"コンフィグリスト '{config_list_name}' は '{CONFIG_LISTS_FILE}' に存在しないケロ🐸")
    
    exec_commands = config_lists.get(config_list_name).get("config_list")
    
    if not exec_commands:
        raise ValueError(f"コンフィグリスト: '{config_list_name}' の 'config_list' が空ケロ🐸")
    if not isinstance(exec_commands, list):
        raise ValueError(f"コンフィグリスト: '{config_list_name}' の 'config_list' は文字列のリストじゃないケロ🐸")

    return exec_commands


def validate_device_type_for_list(hostname: str, node_device_type: str | None, list_name:str, list_device_type: str | None) -> bool:
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
    with open(commands_lists_path, "r", encoding="utf-8") as f:
        commands_lists_data = yaml.load(f)

    # ✅ ルートキー検証
    if "commands_lists" not in commands_lists_data:
        raise ValueError(f"commands_lists は {COMMANDS_LISTS_FILE} に存在しないケロ🐸")

    if  not isinstance(commands_lists_data["commands_lists"], dict):
        raise ValueError(f"{COMMANDS_LISTS_FILE} の形式が不正ケロ🐸")

    
    commands_lists_device_type = commands_lists_data.get("commands_lists", {}).get(list_name, {}).get("device_type")
    return commands_lists_device_type 
