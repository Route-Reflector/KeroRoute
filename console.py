import cmd2
from cmd2 import Cmd2ArgumentParser

from netmiko.utilities import check_serial_port

from rich.console import Console
from rich_argparse import RawTextRichHelpFormatter

import re
from time import perf_counter

from message import print_error, print_info, print_warning, print_success
from load_and_validate_yaml import get_validated_inventory_data, get_validated_commands_list, get_commands_list_device_type, validate_device_type_for_list
from output_logging import save_log
from prompt_utils import wait_for_prompt_returned
from build_device import build_device_and_hostname_for_console
from connect_device import connect_to_device_for_console, safe_disconnect
from completers import host_names_completer, group_names_completer, device_types_completer, commands_list_names_completer



#######################
###  CONST_SECTION  ### 
#######################
SLEEP_TIME = 1


######################
###  HELP_SECTION  ### 
######################
serial_help = ("使用するシリアルポートを指定します。\n"
               "example: console --serial /dev/ttyUSB0\n")
baudrate_help = ("使用するbaudrateを指定します。\n"
                 "example: console --baudrate 9600")
username_help = "console接続に使用するユーザー名を指定します。"
password_help = "console接続に使用するパスワードを指定します。"
device_type_help = "Netmikoにおけるデバイスタイプを指定します（例: cisco_ios）。省略時は 'cisco_ios_serial' です。"
host_help = ("inventory.yamlに定義されたホスト名を指定します。\n"
             "--host 指定時は他オプション（username, password, device_type, baudrate）は無視されます。")
group_help = "[bright_yellow]inventory.yaml[/bright_yellow]に定義されたグループ名を指定します。グループ内の全ホストにコマンドを実行します。"
read_timeout_help = ("send_command の応答待ち時間（秒）。\n"
                     "重いコマンド（例: show tech）用に指定します。\n"
                     "console --host R1 -c 'show tech' --read_timeout 1000"
                     "default: 60 (seconds)")
log_help = ("実行結果をログファイルとして保存します。\n"
           "保存先: logs/console/\n"
           "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]\n"
           "example: 20250504-235734_R0_show-ip-int-brief.log")
memo_help = ("ログファイル名に付加する任意のメモ（文字列）を指定します。\n"
             "保存先: logs/console/\n"
             "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]_[memo]\n")
command_help = "1つのコマンドを直接指定して実行します。"
command_list_help = "コマンドリスト名（commands-lists.yamlに定義）を指定して実行します。"
secret_help = ("enable に入るための secret を指定します。(省略時は password を流用します。)\n")
force_help = "device_type の不一致や未設定エラーを無視して強制実行するケロ🐸"


######################
### PARSER_SECTION ###
######################
# netmiko_console_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
netmiko_console_parser = Cmd2ArgumentParser(formatter_class=RawTextRichHelpFormatter, description="[green]execute コマンド🐸[/green]")
# "-h" はhelpと競合するから使えない。
netmiko_console_parser.add_argument("-s", "--serial", type=str, default="/dev/ttyUSB0", help=serial_help)
netmiko_console_parser.add_argument("-b", "--baudrate", type=int, default=None, help=baudrate_help)
netmiko_console_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_console_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_console_parser.add_argument("-d", "--device_type", type=str, default="", help=device_type_help, completer=device_types_completer)
netmiko_console_parser.add_argument("-r", "--read_timeout", type=int, default=60, help=read_timeout_help)
netmiko_console_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_console_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_console_parser.add_argument("-S", "--secret", type=str, default="", help=secret_help)
netmiko_console_parser.add_argument("--force", action="store_true", help=force_help)

# mutually exclusive
target_node = netmiko_console_parser.add_mutually_exclusive_group(required=True)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help, completer=host_names_completer)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help, completer=group_names_completer)

# mutually exclusive
target_command = netmiko_console_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("-c", "--command", type=str, default="", help=command_help)
target_command.add_argument("-L", "--commands-list", type=str, default="", help=command_list_help, completer=commands_list_names_completer)


console = Console()


@cmd2.with_argparser(netmiko_console_parser)
def do_console(self, args):
    """
    Netmiko を用いてシリアルコンソール接続を行い、コマンドを実行します。

    概要:
        - 指定されたシリアルポート（--serial）とボーレート（--baudrate）で接続
        - inventory.yaml からのホスト情報読み取りにも対応（--host）
        - enable モードへの昇格を自動で試行（失敗時は警告）
        - 単一コマンド（--command）またはコマンドリスト（--commands-list）の実行
        - 実行結果をログファイルに保存するオプション（--log）

    注意:
        - 応答の遅いコマンドに備え、--read_timeout オプションで待機時間を調整可能
        - prompt 検出のために wait を挟むことで、確実な同期を行っています

    Args:
        args (argparse.Namespace): コマンドライン引数

    Raise:
        ValueError: inventory 取得失敗、enable モード移行失敗、YAML 読み取り失敗など
    """
    timer = perf_counter() # ⌚ start

    # ❶ シリアルポートのチェック
    try:
        serial_port = check_serial_port(args.serial)
        print_info(f"✅ 使用可能なポート: {serial_port}")
    except ValueError as e:
        print_error(str(e))
        elapsed = perf_counter() - timer
        print_warning(f"❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return

    # ❷ commands-listは接続前に検証
    # ※ 接続前なので try/except で安全に中断する
    exec_commands = None
    if args.commands_list:
        try:
            exec_commands = get_validated_commands_list(args)
        except (NotImplementedError, FileNotFoundError, ValueError) as e:
            print_error(str(e))
            elapsed = perf_counter() - timer
            print_warning(f"❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
            return


    # ❸ inventoryの取得(--host or --group)
    inventory_data = None

    try:
        if args.host:
            inventory_data = get_validated_inventory_data(host=args.host)
        elif args.group:
            raise NotImplementedError
            inventory_data = get_validated_inventory_data(host=args.group)
        # TODO: group対応は将来実装予定
    except (FileNotFoundError, ValueError) as e:
        print_error(str(e))
        elapsed = perf_counter() - timer
        print_warning(f"❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return

    # ❹ device 構築
    device , hostname = build_device_and_hostname_for_console(args, inventory_data, serial_port)

    # ✅ 2. device_type ミスマッチチェック (接続前に実施)
    if args.commands_list:
        list_device_type = get_commands_list_device_type(args.commands_list)
        node_device_type = device.get("device_type")

        # console の device_type は *_serial になりがちなので、末尾だけ安全に外して比較
        node_device_type_base = re.sub(r"_serial$", "", node_device_type)

        try:
            validate_device_type_for_list(hostname=hostname,
                                          node_device_type=node_device_type_base,
                                          list_name=args.commands_list,
                                          list_device_type=list_device_type)
        except ValueError as e:
            if getattr(args, "force", False):
                if not args.no_output:
                    print_warning(f"{e} (--force指定のため続行ケロ🐸)")
            else:
                if not args.no_output:
                    print_error(str(e))
                    elapsed = perf_counter() - timer
                    print_warning(f"<NODE: {hostname}> ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
                return hostname # このホストはスキップ

    
    # ❺ 接続 (enableまで)
    connection = None 
    try:
        connection, prompt, hostname = connect_to_device_for_console(device, hostname, require_enable=True)
    except ConnectionError as e:
        print_error(str(e))
        elapsed = perf_counter() - timer
        print_warning(f"<NODE: {hostname}> ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return
    
    print_success(f"<NODE: {hostname}> 🔗接続成功ケロ🐸")

    try:
        # prompt 同期 必要に応じて 必要か？
        wait_for_prompt_returned(connection, sleep_time=SLEEP_TIME)
        
        # 実行時点のベースプロンプトから期待プロンプトを生成
        expect_prompt = re.escape(prompt)

        # ❻ 実行
        if args.command:
            output = connection.send_command(args.command, expect_string=expect_prompt, read_timeout=args.read_timeout)
            full_output = f"{prompt} {args.command}\n{output}\n"
            result_output_string = full_output


        elif args.commands_list:

            full_output_list = []

            for command in exec_commands:
                output = connection.send_command(command, expect_string=expect_prompt, read_timeout=args.read_timeout)
                full_output = f"{prompt} {command}\n{output}\n"
                full_output_list.append(full_output)
            
            result_output_string =  "\n".join(full_output_list)

        # ❼ ログの保存
        if args.log:
            save_log(result_output_string, hostname, args, mode="console")

        # ❽ 画面表示
        self.poutput(result_output_string)
        wait_for_prompt_returned(connection, sleep_time=SLEEP_TIME)

        elapsed = perf_counter() - timer
        print_success(f"<NODE: {hostname}> 🔚実行完了ケロ🐸 (elapsed: {elapsed:.2f}s)")
            
    # 安全に切断
    finally:
        safe_disconnect(connection)