from ruamel.yaml import YAML
from pathlib import Path
from message import print_error


def load_sys_config():
    """
    sys_config.yaml を 読み込んで dict を返す。
    キャッシュはしない(呼び出し側で保持する。)
    """
    config_path = Path("sys_config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("sys_config.yaml が見つからないケロ🐸")

    yaml = YAML()
    with config_path.open("r") as f:
        sys_config_data = yaml.load(f)

    return sys_config_data


def get_validated_inventory_data(host=None, group=None):
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

    inventory_path = Path("inventory.yaml")
    if not inventory_path.exists():
        raise FileNotFoundError("inventory.yamlが存在しないケロ🐸")

    yaml = YAML()
    with open(inventory_path, "r") as inventory:
        inventory_data = yaml.load(inventory)

    if host and host not in inventory_data["all"]["hosts"]:
            msg = f"ホスト '{host}' はinventory.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)

    elif group and group not in inventory_data["all"]["groups"]:
            msg = f"グループ '{group}' はinventory.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)
    
    return inventory_data


def get_validated_commands_list(args, device):
    """
    commands-lists.yaml に基づいて、指定されたコマンドリストの存在を検証する。

    Args:
        args: argparse.Namespace - コマンドライン引数
        device: dict - 接続対象のデバイス情報（device_type含む）

    Returns:
        commands_lists_data

    Raises:
        FileNotFoundError: commands-lists.yaml が存在しない場合
        ValueError: device_type または commands_list が未定義の場合
    """

    # ✅ commands-listが指定されている場合は先に存在チェック

    if not args.commands_list:
        msg = "-L or --commands_list が指定されていないケロ🐸"
        print_error(msg)
        raise ValueError(msg)

    if args.commands_list:
        commands_lists_path = Path("commands-lists.yaml")
        if not commands_lists_path.exists():
            msg = "commands-lists.yaml が見つからないケロ🐸"
            print_error(msg)
            raise FileNotFoundError(msg)

        yaml = YAML()
        with commands_lists_path.open("r") as f:
            commands_lists_data = yaml.load(f)

        device_type = device["device_type"]

        if device_type not in commands_lists_data["commands_lists"]:
            msg = f"デバイスタイプ '{device_type}' はcommands-lists.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)

        if args.commands_list not in commands_lists_data["commands_lists"][device_type]:
            msg = f"コマンドリスト '{args.commands_list}' はcommands-lists.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)
    
    exec_commands = commands_lists_data["commands_lists"][device["device_type"]][f"{args.commands_list}"]["commands_list"]
    return exec_commands



def get_validate_config_list(args, device):
    """
    config-lists.yaml に基づいて、指定されたコンフィグリストの存在を検証する。

    Args:
        args: argparse.Namespace - コマンドライン引数
        device: dict - 接続対象のデバイス情報（device_type含む）

    Returns:
        config_lists_data

    Raises:
        FileNotFoundError: config-lists.yaml が存在しない場合
        ValueError: device_type または config_list が未定義の場合
    """

    # ✅ config-listが指定されている場合は先に存在チェック

    if not args.config_list:
        msg = "-L or --config_list が指定されていないケロ🐸"
        print_error(msg)
        raise ValueError(msg)

    if args.config_list:
        config_lists_path = Path("config-lists.yaml")
        if not config_lists_path.exists():
            msg = "config-lists.yaml が見つからないケロ🐸"
            print_error(msg)
            raise FileNotFoundError(msg)

        yaml = YAML()
        with config_lists_path.open("r") as f:
            config_lists_data = yaml.load(f)

        device_type = device["device_type"]

        if device_type not in config_lists_data["config_lists"]:
            msg = f"デバイスタイプ '{device_type}' はconfig-lists.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)

        if args.config_list not in config_lists_data["config_lists"][device_type]:
            msg = f"コマンドリスト '{args.config_list}' はconfig-lists.yamlに存在しないケロ🐸"
            print_error(msg)
            raise ValueError(msg)
    
    return config_lists_data