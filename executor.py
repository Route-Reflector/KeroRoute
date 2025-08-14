import argparse
from time import perf_counter
from pathlib import Path
import json
import cmd2
from cmd2 import Cmd2ArgumentParser
from message import print_info, print_success, print_warning, print_error
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich_argparse import RawTextRichHelpFormatter

from output_logging import save_log, save_json
from build_device import _build_device_and_hostname
from load_and_validate_yaml import get_validated_commands_list, get_validated_inventory_data
from connect_device import connect_to_device, safe_disconnect
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
quiet_help = ("画面上の出力（nodeのcommandの結果）を抑制します。進捗・エラーは表示されます。このオプションを使う場合は --log が必須です。")
no_output_help = ("画面上の出力を完全に抑制します（進捗・エラーも表示しません）。 --log が未指定の場合は実行を中止します。")
ordered_help = ("--group指定時にoutputの順番を昇順に並べ変えます。 このoptionを使用しない場合は実行完了順に表示されます。--group 未指定の場合は実行を中止します。")
parser_help = ("コマンドの結果をparseします。textfsmかgenieを指定します。")
textfsm_template_help = ("--parser optionで textfsm を指定する際に template ファイルを渡すためのオプションです。\n"
                         "--parser optionで textfsm を指定する際は必須です。(genieのときは必要ありません。)")

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
netmiko_execute_parser.add_argument("-o", "--ordered", action="store_true", help=ordered_help)
netmiko_execute_parser.add_argument("--parser", "--parse",dest="parser",  choices=["textfsm", "genie", "text-fsm"], help=parser_help)
netmiko_execute_parser.add_argument("--textfsm-template", type=str,  help=textfsm_template_help)


# mutually exclusive
target_node = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None, help=ip_help)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help, completer=host_names_completer)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help, completer=group_names_completer)

target_command = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("-c", "--command", type=str, default="", help=command_help)
target_command.add_argument("-L", "--commands-list", type=str, default="", help=command_list_help, completer=commands_list_names_completer)

silence_group = netmiko_execute_parser.add_mutually_exclusive_group(required=False)
silence_group.add_argument("--quiet", action="store_true", help=quiet_help)
silence_group.add_argument("--no-output", action="store_true", help=no_output_help)


def _execute_command(connection, prompt, command, args, parser_kind):
    """
    単一コマンドを Netmiko で実行し、プロンプト＋コマンド＋出力を 1 つの文字列に整形して返す。

    Parameters
    ----------
    connection : BaseConnection
        `connect_to_device()` で取得した Netmiko 接続（特権モード|base_prompt確定済み）。
    prompt : str
        呼び出し元で取得済みの固定プロンプト文字列（例: "R1#"). 再取得は行わない。
    command : str
        実行するコマンド。
    args : argparse.Namespace
        実行オプション（parser_kind 等を含む）。
    parser_kind : str | None
        "genie" / "textfsm" のときは構造化データを返す。None のときはテキストを返す。

    Returns
    -------
    str | list | dict
        parser_kind=None のときは "{prompt} {command}\\n{device_output}\\n" 形式のテキスト。
        parser_kind が指定されている場合は構造化データ（list/dict）。
    """
    if parser_kind:
        if parser_kind == "genie":
            output = connection.send_command(command, use_genie=True, raise_parsing_error=True)
            full_output = output
        elif parser_kind == "textfsm":
            template = str(Path(args.textfsm_template))
            output = connection.send_command(command, use_textfsm=True, raise_parsing_error=True,
                                             textfsm_template=template)
            full_output = output
    else:
        output = connection.send_command(command)
        full_output = f"{prompt} {command}\n{output}\n"

    return full_output

def _execute_commands_list(connection, prompt, exec_commands, args, parser_kind):
    """
    commands-lists.yaml で定義されたコマンド列を順次実行し、結果を連結して返す。

    Parameters
    ----------
    connection : BaseConnection
        `connect_to_device()` で取得した Netmiko 接続（特権モード／base_prompt確定済み）。
    prompt : str
        呼び出し元で取得済みの固定プロンプト文字列（例: "R1#"). 再取得は行わない。
    exec_commands : list[str]
        `get_validated_commands_list()` で取得したコマンドのリスト。
    args : argparse.Namespace
        実行オプション（parser_kind 等を含む）。
    parser_kind : str | None
        "genie" / "textfsm" のときは各コマンドの構造化データ（list）を返す。None のときはテキスト連結。

    Returns
    -------
    str | list
        parser_kind=None のときは各要素 "{prompt} {command}\\n{output}\\n" を連結したテキスト。
        parser_kind が指定されている場合は各コマンド結果の配列（list）。
    """
    full_output_list = []

    # textfsmだけ先に一度だけ作る 
    if parser_kind == "textfsm":
        template = str(Path(args.textfsm_template))

    for command in exec_commands:
        if parser_kind:
            if parser_kind == "genie":
                output = connection.send_command(command, use_genie=True, raise_parsing_error=True)
                full_output = output
                full_output_list.append(full_output)
            elif parser_kind == "textfsm":
                output = connection.send_command(command, use_textfsm=True, raise_parsing_error=True,
                                                 textfsm_template=template)
                full_output = output
                full_output_list.append(full_output)
        else:
            output = connection.send_command(command)
            full_output = f"{prompt} {command}\n{output}\n"
            full_output_list.append(full_output)
    
    if parser_kind == "genie":
        return full_output_list
    elif parser_kind == "textfsm":
        return full_output_list
    else:
        return "".join(full_output_list)


def _execute_commands(connection, prompt, args, exec_commands, parser_kind: str | None = None):
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
        return _execute_command(connection, prompt, args.command, args=args, parser_kind=parser_kind)
    elif args.commands_list:
        return _execute_commands_list(connection, prompt, exec_commands, args=args, parser_kind=parser_kind)
    else:
        raise ValueError("command または commands_list のいずれかが必要ケロ🐸")


def _handle_execution(device: dict, args, poutput, hostname, *, output_buffers: dict | None = None, parser_kind: str | None = None) -> str | None:
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

    try:
        if args.commands_list:
            exec_commands = get_validated_commands_list(args, device)
    except (FileNotFoundError, ValueError) as e:
        if not args.no_output:
            print_error(str(e))
            elapsed = perf_counter() - timer
            print_warning(f"<NODE: {hostname}> ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return hostname # 失敗時

    # ✅ 2. 接続とプロンプト取得
    try:
        connection, prompt, hostname = connect_to_device(device, hostname)
    except ConnectionError as e:
        if not args.no_output:
            print_error(str(e))
            elapsed = perf_counter() - timer
            print_warning(f"<NODE: {hostname}> ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return hostname # 失敗時
    
    if not args.no_output:
        print_success(f"<NODE: {hostname}> 🔗接続成功ケロ🐸")

    # ✅ 3. コマンド実行（単発 or リスト）
    try:
        result_output_string = _execute_commands(connection, prompt, args, exec_commands, parser_kind)
    except Exception as e:
        if not args.no_output:
            if args.parser == "genie":
                print_error(f"<NODE: {hostname}> 🧩Genieパース失敗ケロ🐸: {e}")
            elif args.parser == "textfsm":
                print_error(f"<NODE: {hostname}> 🧩textfsmパース失敗ケロ🐸: {e}")
            else:   
                print_error(f"<NODE: {hostname}> ⚠️実行エラーケロ🐸: {e}")
            elapsed = perf_counter() - timer
            print_warning(f"<NODE: {hostname}> ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        safe_disconnect(connection)
        return hostname # 失敗時

    # ✅ 4. 接続終了
    safe_disconnect(connection)

    # display_text = 生テキスト or json 文字列
    # 表示用。save_json側でjson.dumpsが入るのでsave_jsonの呼び出し時はresult_output_stringを渡す。
    display_text = result_output_string 
    if parser_kind and isinstance(result_output_string, (list, dict)):
        display_text = json.dumps(result_output_string, ensure_ascii=False, indent=2)

    # ordered option用の貯める処理。(quiet | no-outputのときは貯めない。)
    if output_buffers is not None and args.group and args.ordered and not args.no_output and not args.quiet:
        output_buffers[hostname] = display_text
    
    # ✅ 5. ログ保存（--log指定時のみ）
    if getattr(args, "log", False):
        if not getattr(args, "no_output", False):
            print_info(f"<NODE: {hostname}> 💾ログ保存モードONケロ🐸🔛")
        if parser_kind in ("genie", "textfsm") and isinstance(result_output_string, (list, dict)):
            log_path = save_json(result_output_string, hostname, args, parser_kind=parser_kind, mode="execute")
        else:
            log_path = save_log(result_output_string, hostname, args)
        if not getattr(args, "no_output", False):
            print_success(f"<NODE: {hostname}> 💾ログ保存完了ケロ🐸⏩⏩⏩ {log_path}")


    # ✅ 6. 結果表示
    if not args.no_output:
        if args.quiet:
            print_info(f"<NODE: {hostname}> 📄OUTPUTは省略するケロ (hidden by --quiet) 🐸")
        else:
            if not (args.group and args.ordered and output_buffers is not None):
                print_info(f"<NODE: {hostname}> 📄OUTPUTケロ🐸")
                poutput(display_text)
    elapsed = perf_counter() - timer
    if not args.no_output:
        print_success(f"<NODE: {hostname}> 🔚実行完了ケロ🐸 (elapsed: {elapsed:.2f}s)")
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
    if args.ordered and not args.group:
        print_error("--ordered は --group 指定時のみ使用できるケロ🐸")
        return

    if args.quiet and not args.log:
        print_error("--quietオプションを使用するには--logが必要ケロ🐸")
        return
    elif args.no_output and not args.log:
        # 現仕様：完全サイレント。黙って終了（将来 notify 実装時に or を足すだけでOK）
        return

    parser_kind = None
    if args.parser:
        # 表記ゆれ正規化（互換用）
        if args.parser == "text-fsm":
            print_warning("`text-fsm` は非推奨ケロ🐸 → `textfsm` を使ってね")
            args.parser = "textfsm"
        parser_kind = args.parser

    if args.parser == "textfsm":
        if not args.textfsm_template:
            print_error("--parser textfsm を使うには --textfsm-template <PATH> が必要ケロ🐸")
            return
        if not Path(args.textfsm_template).is_file():
            print_error(f"指定のtemplateが見つからないケロ🐸: {args.textfsm_template}")
            return


    if args.ip:
        device, hostname = _build_device_and_hostname(args)
        result_failed_hostname = _handle_execution(device, args, self.poutput, hostname, parser_kind=parser_kind)
        if result_failed_hostname and not args.no_output:
            print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
        return

    if args.host or args.group: 
        try:
            inventory_data = get_validated_inventory_data(host=args.host, group=args.group)
        
        except (FileNotFoundError, ValueError) as e:
            if not args.no_output:
                print_error(str(e))
            return
        
    
    if args.host:
        device, hostname = _build_device_and_hostname(args, inventory_data)
        result_failed_hostname = _handle_execution(device, args, self.poutput, hostname, parser_kind=parser_kind)
        if result_failed_hostname and not args.no_output:
            print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
        return

    elif args.group:
        device_list, hostname_list = _build_device_and_hostname(args, inventory_data)

        max_workers = default_workers(len(device_list), args)

        result_failed_hostname_list = []

        # ✅ --ordered 用の本文バッファ（hostname -> str）
        ordered_output_buffers = {}  # {hostname: collected_output}

        with ThreadPoolExecutor(max_workers=max_workers) as pool:

            futures = []
            future_to_hostname = {} 

            ordered_output_enabled =  args.ordered and not args.quiet and not args.no_output

            for device, hostname in zip(device_list, hostname_list):
                # --orderedがあって--quietと--no_outputがないこと。
                if ordered_output_enabled:
                    # 順番を並び替えるために貯める。
                    future = pool.submit(_handle_execution, device, args, self.poutput, hostname, output_buffers=ordered_output_buffers, parser_kind=parser_kind)
                else:
                    future = pool.submit(_handle_execution, device, args, self.poutput, hostname, parser_kind=parser_kind)
                
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
                    if not args.no_output:
                        print_error(f"⚠️ 未処理の例外: {hostname}:{e}")
        
        # --orderedの場合は、ここで実行結果をまとめて表示する。
        if ordered_output_enabled:
            for h in sorted(ordered_output_buffers.keys(), key=lambda x: (x is None, x or "")):
                print_info(f"NODE: {h} 📄OUTPUTケロ🐸")
                self.poutput(ordered_output_buffers[h])

        # 結果をまとめて表示
        if result_failed_hostname_list and not args.no_output:
            print_warning(f"❎ 🐸なんかトラブルケロ: {', '.join(sorted(result_failed_hostname_list))}")
        else:
            if not args.no_output:
                print_success("✅ すべてのホストで実行完了ケロ🐸")