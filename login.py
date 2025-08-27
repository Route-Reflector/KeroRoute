import re
from pathlib import Path
import cmd2
from cmd2 import Cmd2ArgumentParser
from ruamel.yaml import YAML
from message import print_info, print_success, print_warning, print_error
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich_argparse import RawTextRichHelpFormatter
from netmiko.utilities import check_serial_port


from prompt_utils import get_prompt
from output_logging import save_log
from build_device import build_device_and_hostname
from load_and_validate_yaml import get_validated_commands_list, get_validated_inventory_data
from connect_device import connect_to_device, safe_disconnect
from workers import default_workers



######################
###  HELP_SECTION  ### 
######################
# bright_yellow -> file_name or file_path
ip_help = "対象デバイスのIPアドレスを指定します。"
host_help = "[bright_yellow]inventory.yaml[/bright_yellow]に定義されたホスト名を指定します。"
group_help = "[bright_yellow]inventory.yaml[/bright_yellow]に定義されたグループ名を指定します。グループ内の全ホストにコマンドを実行します。"

command_help = "1つのコマンドを直接指定して実行します。"
command_list_help = ("コマンドリスト名（[bright_yellow]commands-lists.yaml[/bright_yellow]に定義）を指定して実行します。\n" 
                    "device_typeはホストから自動で選択されます。")

username_help = ("--ip 専用。SSH接続に使用するユーザー名を指定します。\n"
                 "--host | --group 指定時は[bright_yellow]inventory.yaml[/bright_yellow]の値を使用します。\n")
password_help = ("--ip 専用。SSH接続に使用するパスワードを指定します。\n"
                 " --host | --group 指定時は[bright_yellow]inventory.yaml[/bright_yellow]の値を使用します。\n")
device_type_help = "Netmikoにおけるデバイスタイプを指定します（例: cisco_ios）。省略時は 'cisco_ios' です。\n"
port_help = "SSH接続に使用するポート番号を指定します（デフォルト: 22）\n"
timeout_help = "SSH接続のタイムアウト秒数を指定します（デフォルト: 10秒）\n"
log_help = ("実行結果をログファイルとして保存します。\n"
            "保存先: logs/execute/\n"
            "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]\n"
            "[bright_yellow]example: 20250504-235734_R0_show-ip-int-brief.log\n[/bright_yellow]")
memo_help = ("ログファイル名に付加する任意のメモ（文字列）を指定します。\n"
             "保存先: logs/execute/\n"
             "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]_[memo]\n"
             "[bright_yellow]example: 20250506-125600_R0_show-ip-int-brief_memo.log\n[/bright_yellow]")
workers_help = ("並列実行するワーカースレッド数を指定します。\n"
                "指定しない場合は [bright_yellow]sys_config.yaml[/bright_yellow] の [bright_yellow]executor.default_workers[/bright_yellow] を参照します。\n"
                "そこにも設定が無いときは、グループ台数と 規定上限([bright_blue]DEFAULT_MAX_WORKERS[/bright_blue]) の小さい方が自動で採用されます。\n\n")
secret_help = ("enable に入るための secret を指定します。(省略時は password を流用します。)\n"
               "--ip 専用。--host | --group 指定時は [green]inventory.yaml[/green] の値を使用します。\n\n")
serial_help = ("使用するシリアルポートを指定します。\n"
               "example: console --serial /dev/ttyUSB0\n")
baudrate_help = ("使用するbaudrateを指定します。\n"
                 "example: console --baudrate 9600")
read_timeout_help = ("send_command の応答待ち時間（秒）。\n"
                     "重いコマンド（例: show tech）用に指定します。\n"
                     "console --host R1 -c 'show tech' --read_timeout 1000"
                     "default: 30")


######################
### PARSER_SECTION ###
######################
netmiko_login_parser = Cmd2ArgumentParser(formatter_class=RawTextRichHelpFormatter, description="[green]login コマンド🐸[/green]")
# "-h" はhelpと競合するから使えない。
netmiko_login_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_login_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_login_parser.add_argument("-d", "--device_type", type=str, default="cisco_ios", help=device_type_help)
netmiko_login_parser.add_argument("-P", "--port", type=int, default=22, help=port_help)
netmiko_login_parser.add_argument("-t", "--timeout", type=int, default=10, help=timeout_help)
netmiko_login_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_login_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_login_parser.add_argument("-w", "--workers", type=int, default=None, metavar="N", help=workers_help)
netmiko_login_parser.add_argument("-s", "--secret", type=str, default="", help=secret_help)
netmiko_login_parser.add_argument("--serial", type=str, default="/dev/ttyUSB0", help=serial_help)
netmiko_login_parser.add_argument("-b", "--baudrate", type=int, default=9600, help=baudrate_help)
netmiko_login_parser.add_argument("-r", "--read_timeout", type=int, default=30, help=read_timeout_help)


# mutually exclusive
target_node = netmiko_login_parser.add_mutually_exclusive_group(required=True)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None, help=ip_help)
target_node.add_argument("--console", action="store_true", help=serial_help)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help)


def _handle_login(args, device, hostname):


    # ✅ 2. 接続とプロンプト取得
    try:
        connection, prompt, hostname = connect_to_device(device, hostname)
        print_success(f"NODE: {hostname} 🔗接続成功ケロ🐸")
    except ConnectionError as e:
        print_error(str(e))
        return

    # --- ログ ---
    log_path, log_file = None, None
    if args.log:
        log_path = save_log("", hostname, args, mode="login")
        if log_path:
            log_file = open(log_path, "a", encoding="utf-8")

    # --- 対話ループ ---
    print_info(f"\n🐸loginモード開始！🐸\n"
               f"・このモードはnetmikoで疑似再現しています。実際の表示とは差分がある可能性があります。\n"
               f"・既知の問題: TAB 補完が効きません。\n"
               f"・空行は無視されます。モードを抜けるには KEROKERO または Ctrl+D/Ctrl+Cを入力してください。\n"
               f"・TAB 補完が必要なら  shellコマンドでsshを呼び出す方が良いかもしれません。🐸\n",
               panel=True)

    cli_prompt = f"🐸KeroRoute [login mode]> {prompt} "
    try:
        while True:
            try:
                cmd = input(cli_prompt)
            except (EOFError, KeyboardInterrupt):
                break
            if cmd.strip() == "":
                continue
            if cmd.strip().upper() == "KEROKERO":
                break

            expect_pattern = rf"{re.escape(hostname)}.*[>#]"   # R1, R1(config), R1(config-if) など全部命中

            output = connection.send_command(cmd, strip_prompt=False, strip_command=False, expect_string=expect_pattern)
            print(output)

            if log_file:
                log_file.write(f"$ {cmd}\n{output}\n")
            
            prompt, hostname = get_prompt(connection)
            cli_prompt = f"🐸KeroRoute [login mode]> {prompt} "

    finally:
        if log_file:
            log_file.close()
        safe_disconnect(connection)
        print_success("🐸 セッション終了！")


@cmd2.with_argparser(netmiko_login_parser)
def do_login(self, args):
    # if args.console:
    #     # ここにconsole側の処理。
    #     try:
    #         serial_port = check_serial_port(args.serial)
    #         print_info(f"✅ 使用可能なポート: {serial_port}")
    #     except ValueError as e:
    #         print_error(str(e))
    #         return
    #     if args.host:
    #         device, hostname = build_device_and_hostname(args, serial_port=args.serial)
    #     elif args.group:
    #         print_error(f"loginコマンドのコンソールのgroupコマンドはまだ実装されてないケロ🐸")
    #         raise NotImplementedError
    if args.ip:
         device, hostname = build_device_and_hostname(args)
         _handle_login(args, device, hostname)
         return

    else:
        if args.host or args.group: 
            try:
                inventory_data = get_validated_inventory_data(host=args.host, group=args.group)
            
            except (FileNotFoundError, ValueError) as e:
                print_error(str(e))
                return

        if args.host:
            device, hostname = build_device_and_hostname(args, inventory_data)
            _handle_login(args, device, hostname)
            return

        elif args.group:
            raise NotImplementedError
            # device_list, hostname_list = _build_device_and_hostname(args, inventory_data)

            # max_workers = default_workers(len(device_list), args)

            # with ThreadPoolExecutor(max_workers=max_workers) as pool:

            #     futures = []
            #     for device, hostname in zip(device_list, hostname_list):
            #         future = pool.submit(_handle_execution, device, args, self.poutput, hostname)
            #         futures.append(future)

            #     for future in as_completed(futures):
            #         future.result()