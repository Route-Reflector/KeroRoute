import argparse
from time import perf_counter
import cmd2
from cmd2 import Cmd2ArgumentParser
from message import print_info, print_success, print_warning, print_error
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich_argparse import RawTextRichHelpFormatter

from prompt_utils import get_prompt
from output_logging import _save_log
from build_device import _build_device_and_hostname
from load_and_validate_yaml import get_validated_commands_list, get_validated_inventory_data
from connect_device import connect_to_device
from workers import default_workers
from completers import host_names_completer, group_names_completer, device_types_completer, commands_list_names_completer


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
no_output_help = ("画面表示をしない場合に使用します。画面上のoutputを抑制します。--logオプションと一緒に使用します。")


######################
### PARSER_SECTION ###
######################
# netmiko_execute_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
netmiko_execute_parser = Cmd2ArgumentParser(formatter_class=RawTextRichHelpFormatter, description="[green]execute コマンド🐸[/green]")
# "-h" はhelpと競合するから使えない。
netmiko_execute_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_execute_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_execute_parser.add_argument("-d", "--device_type", type=str, default="cisco_ios", help=device_type_help, completer=device_types_completer)
netmiko_execute_parser.add_argument("-P", "--port", type=int, default=22, help=port_help)
netmiko_execute_parser.add_argument("-t", "--timeout", type=int, default=10, help=timeout_help)
netmiko_execute_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_execute_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_execute_parser.add_argument("-w", "--workers", type=int, default=None, metavar="N", help=workers_help)
netmiko_execute_parser.add_argument("-s", "--secret", type=str, default="", help=secret_help)
netmiko_execute_parser.add_argument("--no-output", action="store_true", help=no_output_help)

# mutually exclusive
target_node = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None, help=ip_help)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help, completer=host_names_completer)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help, completer=group_names_completer)

target_command = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("-c", "--command", type=str, default="", help=command_help)
target_command.add_argument("-L", "--commands-list", type=str, default="", help=command_list_help, completer=commands_list_names_completer)


def _execute_command(connection, prompt, command):
    """
    単一コマンドを Netmiko で実行し、プロンプト＋コマンド＋出力を 1 つの文字列に整形して返す。

    Parameters
    ----------
    connection : BaseConnection
        `connect_to_device()` で取得した Netmiko 接続。
    prompt : str
        コマンド実行時に表示するプロンプト文字列（例: "R1#").
        実装上、enable 前後の差異を吸収するため `find_prompt()` により再取得することがある。
    command : str
        実行するコマンド。

    Returns
    -------
    str
        "{prompt} {command}\\n{device_output}\\n" 形式のテキスト。
    """
    prompt = connection.find_prompt()
    output = connection.send_command(command)
    full_output = f"{prompt} {command}\n{output}\n"

    return full_output

def _execute_commands_list(connection, prompt, exec_commands):
    """
    commands-lists.yaml で定義されたコマンド列を順次実行し、各結果を連結して返す。

    Parameters
    ----------
    connection : BaseConnection
        `connect_to_device()` で取得した Netmiko 接続。
    prompt : str
        実行時に先頭へ付与するプロンプト文字列（例: "R1#").
        実装上、必要に応じて `find_prompt()` で再取得する。
    exec_commands : list[str]
        `get_validated_commands_list()` で取得したコマンドのリスト。

    Returns
    -------
    str
        各コマンドの "{prompt} {command}\\n{output}\\n" を連結したテキスト。
        （各要素は末尾改行を含むため、連結は空文字 join で行う）
    """
    full_output_list = []
    prompt = connection.find_prompt()

    for command in exec_commands:
        output = connection.send_command(command)
        full_output = f"{prompt} {command}\n{output}\n"
        full_output_list.append(full_output)
    
    return "".join(full_output_list)


def _execute_commands(connection, prompt, args, exec_commands):
    """
    単発コマンド（--command）またはコマンドリスト（--commands-list）を実行し、結果を返すラッパー関数。

    Parameters
    ----------
    connection : BaseConnection
        `connect_to_device()` で取得した Netmiko 接続。
    prompt : str
        デバイスのプロンプト（例: "R1#").
    args : argparse.Namespace
        引数オブジェクト（args.command または args.commands_list を持つ）。
    exec_commands : list[str] | None
        コマンドリスト実行時に使用するコマンド配列。単発コマンド時は None。

    Returns
    -------
    str
        実行結果テキスト。

    Raises
    ------
    ValueError
        args.command と args.commands_list のいずれも指定されていない場合。
    """
    if args.command:
        return _execute_command(connection, prompt, args.command)
    elif args.commands_list:
        return _execute_commands_list(connection, prompt, exec_commands)
    else:
        raise ValueError("command または commands_list のいずれかが必要ケロ🐸")


def _handle_execution(device: dict, args, poutput, hostname) -> str | None:
    """
    デバイス接続〜コマンド実行〜ログ保存までをまとめて処理するラッパー関数。

    Args:
        device (dict): 接続情報を含むデバイス辞書
        args: コマンドライン引数
        poutput: cmd2 の出力関数
        hostname (str): ログファイル名などに使うホスト識別子
    
    Returns:
        成功時 None
        失敗時 hostname (str)
    """
    timer = perf_counter() # ⌚ start
    # ✅ 1. commands-list の存在チェック（必要なら）
    result_output_string = ""
    exec_commands = None # args.commandのとき未定義になるため必要。

    if args.no_output and not args.log:
        print_error("--no-outputオプションを使用するには--logが必要です。")
        elapsed = perf_counter() - timer
        print_warning(f"NODE: {hostname} ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return hostname # 失敗時

    try:
        if args.commands_list:
            exec_commands = get_validated_commands_list(args, device)
    except (FileNotFoundError, ValueError) as e:
        print_error(str(e))
        elapsed = perf_counter() - timer
        print_warning(f"NODE: {hostname} ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return hostname # 失敗時

    # ✅ 2. 接続とプロンプト取得
    try:
        connection = connect_to_device(device, hostname)
        prompt, hostname = get_prompt(connection)
        print_success(f"NODE: {hostname} 🔗接続成功ケロ🐸")
    except ConnectionError as e:
        print_error(str(e))
        elapsed = perf_counter() - timer
        print_warning(f"NODE: {hostname} ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return hostname # 失敗時

    # ✅ 3. コマンド実行（単発 or リスト）
    try:
        result_output_string = _execute_commands(connection, prompt, args, exec_commands)
    except (KeyError, ValueError) as e:
        print_error(str(e))
        elapsed = perf_counter() - timer
        print_warning(f"NODE: {hostname} ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        connection.disconnect()
        return hostname # 失敗時

    # ✅ 4. 接続終了
    connection.disconnect()

    # ✅ 5. ログ保存（--log指定時のみ）
    if args.log:
        _save_log(result_output_string, hostname, args)

    # ✅ 6. 結果表示
    if args.no_output:
        print_info(f"NODE: {hostname} 📄OUTPUTは省略するケロ (hidden by --no-output) 🐸")
    else:
        print_info(f"NODE: {hostname} 📄OUTPUTケロ🐸")
        poutput(result_output_string)
    elapsed = perf_counter() - timer
    print_success(f"NODE: {hostname} 🔚実行完了ケロ🐸 (elapsed: {elapsed:.2f}s)")
    return None # 成功時


@cmd2.with_argparser(netmiko_execute_parser)
def do_execute(self, args):
    """
    `execute` サブコマンドのエントリポイント。

    ルーティング
    ------------
    1. `--ip` 指定 → 単一デバイス  
    2. `--host`    → inventory から 1 台  
    3. `--group`   → inventory グループ内の複数台

    Notes
    -----
    - 実処理は `_handle_execution()` に委譲。
    - `cmd2` では ``self.poutput`` が標準出力をラップしているため、
      すべての内部関数にこれを渡してカラー表示や装飾を統一している。
    """

    if args.ip:
        device, hostname = _build_device_and_hostname(args)
        result_failed_hostname = _handle_execution(device, args, self.poutput, hostname)
        if result_failed_hostname:
            print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
        return

    if args.host or args.group: 
        try:
            inventory_data = get_validated_inventory_data(host=args.host, group=args.group)
        
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return
        
    
    if args.host:
        device, hostname = _build_device_and_hostname(args, inventory_data)
        result_failed_hostname = _handle_execution(device, args, self.poutput, hostname)
        if result_failed_hostname:
            print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
        return

    elif args.group:
        device_list, hostname_list = _build_device_and_hostname(args, inventory_data)

        max_workers = default_workers(len(device_list), args)

        result_failed_hostname_list = []

        with ThreadPoolExecutor(max_workers=max_workers) as pool:

            futures = []
            future_to_hostname = {} 
            for device, hostname in zip(device_list, hostname_list):
                future = pool.submit(_handle_execution, device, args, self.poutput, hostname)
                futures.append(future)
                future_to_hostname[future] = hostname

            for future in as_completed(futures):
                hostname = future_to_hostname.get(future, "UNKNOWN")
                try:
                    result_failed_hostname = future.result()
                    if result_failed_hostname:
                        result_failed_hostname_list.append(result_failed_hostname)
                except Exception as e:
                    # _handle_execution で捕まえていない想定外の例外
                    print_error(f"⚠️ 未処理の例外: {hostname}:{e}")

        # 結果をまとめて表示
        if result_failed_hostname_list:
            print_warning(f"❎ 🐸なんかトラブルケロ: {', '.join(sorted(result_failed_hostname_list))}")
        else:
            print_success("✅ すべてのホストで実行完了ケロ🐸")