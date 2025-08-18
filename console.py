import argparse
import cmd2
import re
from rich.console import Console

from netmiko.utilities import check_serial_port

from message import print_error, print_info, print_warning, print_success
from load_and_validate_yaml import get_validated_inventory_data, get_validated_commands_list
from output_logging import save_log
from prompt_utils import wait_for_prompt_returned
from build_device import build_device_and_hostname_for_console
from completers import commands_list_names_completer
from connect_device import connect_to_device_for_console, safe_disconnect



#######################
###  CONST_SECTION  ### 
#######################
DELAY_FACTOR = 3
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
read_timeout_help = ("send_command の応答待ち時間（秒）。\n"
                     "重いコマンド（例: show tech）用に指定します。\n"
                     "console --host R1 -c 'show tech' --read_timeout 1000"
                     "default: 30")
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


######################
### PARSER_SECTION ###
######################
netmiko_console_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
# "-h" はhelpと競合するから使えない。
netmiko_console_parser.add_argument("-s", "--serial", type=str, default="/dev/ttyUSB0", help=serial_help)
netmiko_console_parser.add_argument("-b", "--baudrate", type=int, default=None, help=baudrate_help)
netmiko_console_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_console_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_console_parser.add_argument("-d", "--device_type", type=str, default="", help=device_type_help)
netmiko_console_parser.add_argument("-r", "--read_timeout", type=int, default=30, help=read_timeout_help)
netmiko_console_parser.add_argument("-H", "--host", type=str, default="", help=host_help)
netmiko_console_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_console_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_console_parser.add_argument("-S", "--secret", type=str, default="", help=secret_help)


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
    # ❶ シリアルポートのチェック
    try:
        serial_port = check_serial_port(args.serial)
        print_info(f"✅ 使用可能なポート: {serial_port}")
    except ValueError as e:
        print_error(str(e))
        return

    # ❷ commands-listは接続前に検証
    # ※ 接続前なので try/except で安全に中断する
    exec_commands = None
    if args.commands_list:
        try:
            exec_commands = get_validated_commands_list(args)
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return


    # ❸ inventoryの取得(--host or --group)
    inventory_data = None

    try:
        if args.host:
            inventory_data = get_validated_inventory_data(host=args.host)
        elif args.group:
            inventory_data = get_validated_inventory_data(host=args.group)
    except (FileNotFoundError, ValueError) as e:
        print_error(str(e))
        return

    # ❹ device 構築
    device , hostname = build_device_and_hostname_for_console(args, inventory_data, serial_port)
    
    # ❺ 接続 (enableまで)
    connection = None 
    try:
        connection, prompt, hostname = connect_to_device_for_console(device, hostname, require_enable=True)
    except ConnectionError as e:
        print_error(str(e))
        return
    
    print_success(f"<NODE: {hostname}> 🔗接続成功ケロ🐸")

    try:
        # prompt 同期 必要に応じて 必要か？
        wait_for_prompt_returned(connection, sleep_time=SLEEP_TIME)
        
        # 実行時点のベースプロンプトから期待プロンプトを生成
        expect_prompt = re.escape(prompt)

        # ❻ 実行
        if args.command:
            output = connection.send_command(args.command, delay_factor=DELAY_FACTOR, expect_string=expect_prompt, read_timeout=args.read_timeout)
            full_output = f"{prompt} {args.command}\n{output}\n"
            result_output_string = full_output


        elif args.commands_list:

            full_output_list = []

            for command in exec_commands:
                output = connection.send_command(command, delay_factor=DELAY_FACTOR, expect_string=expect_prompt, read_timeout=args.read_timeout)
                full_output = f"{prompt} {command}\n{output}\n"
                full_output_list.append(full_output)
            
            result_output_string =  "\n".join(full_output_list)

        # ❼ ログの保存
        if args.log:
            save_log(result_output_string, hostname, args, mode="console")

        # ❽ 画面表示
        self.poutput(result_output_string)
        wait_for_prompt_returned(connection, sleep_time=SLEEP_TIME)
            
    # 安全に切断
    finally:
        safe_disconnect(connection)