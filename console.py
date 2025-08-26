import cmd2
from cmd2 import Cmd2ArgumentParser

from netmiko.utilities import check_serial_port

from rich_argparse import RawTextRichHelpFormatter

from pathlib import Path
import json
import re
from time import perf_counter

from message import print_error, print_info, print_warning, print_success
from load_and_validate_yaml import get_validated_inventory_data, get_validated_commands_list, get_commands_list_device_type, validate_device_type_for_list
from output_logging import save_log, save_json
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
device_type_help = "Netmikoにおけるデバイスタイプを指定します（例: cisco_ios）。"
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
quiet_help = ("画面上の出力（nodeのcommandの結果）を抑制します。進捗・エラーは表示されます。このオプションを使う場合は --log が必須です。")
no_output_help = ("画面上の出力を完全に抑制します（進捗・エラーも表示しません）。 --log が未指定の場合は実行を中止します。")
ordered_help = ("--group指定時にoutputの順番を昇順に並べ変えます。 このoptionを使用しない場合は実行完了順に表示されます。--group 未指定の場合は実行を中止します。")
parser_help = ("コマンドの結果をparseします。textfsmかgenieを指定します。")
textfsm_template_help = ("--parser optionで textfsm を指定する際に template ファイルを渡すためのオプションです。\n"
                         "--parser optionで textfsm を指定する際は必須です。(genieのときは必要ありません。)")
# post_reconnect_baudrate_help = "実行後にこのボーレートで再接続確認だけ行うケロ🐸"
connect_only_help = "コマンドを実行せず、接続確認だけ行うケロ🐸（enable まで）"


######################
### PARSER_SECTION ###
######################
# netmiko_console_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
netmiko_console_parser = Cmd2ArgumentParser(formatter_class=RawTextRichHelpFormatter, description="[green]console コマンド🐸[/green]")
# "-h" はhelpと競合するから使えない。
netmiko_console_parser.add_argument("-s", "--serial", type=str, default="/dev/ttyUSB0", help=serial_help)
netmiko_console_parser.add_argument("-b", "--baudrate", type=int, default=None, help=baudrate_help)
netmiko_console_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_console_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_console_parser.add_argument("-d", "--device_type", type=str, default="", help=device_type_help, completer=device_types_completer)
netmiko_console_parser.add_argument("-r", "--read_timeout", "--read-timeout", dest="read_timeout", type=int, default=60, help=read_timeout_help)
netmiko_console_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_console_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_console_parser.add_argument("-S", "--secret", type=str, default="", help=secret_help)
netmiko_console_parser.add_argument("-o", "--ordered", action="store_true", help=ordered_help)
netmiko_console_parser.add_argument("--parser", "--parse",dest="parser",  choices=["textfsm", "genie", "text-fsm"], help=parser_help)
netmiko_console_parser.add_argument("--textfsm-template", type=str,  help=textfsm_template_help)
netmiko_console_parser.add_argument("--force", action="store_true", help=force_help)
# netmiko_console_parser.add_argument("--post-reconnect-baudrate", type=int, help=post_reconnect_baudrate_help)


# mutually exclusive
target_node = netmiko_console_parser.add_mutually_exclusive_group(required=False)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help, completer=host_names_completer)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help, completer=group_names_completer)

# mutually exclusive
target_command = netmiko_console_parser.add_mutually_exclusive_group(required=False)
target_command.add_argument("-c", "--command", type=str, default="", help=command_help)
target_command.add_argument("-L", "--commands-list", type=str, default="", help=command_list_help, completer=commands_list_names_completer)
target_command.add_argument("--connect-only", action="store_true", help=connect_only_help)

# mutually exclusive
silence_group = netmiko_console_parser.add_mutually_exclusive_group(required=False)
silence_group.add_argument("--quiet", action="store_true", help=quiet_help)
silence_group.add_argument("--no-output", "--no_output", dest="no_output", action="store_true", help=no_output_help)


def _execute_console_command(connection, prompt, command, *, args, parser_kind, expect_string: str | None):
    if parser_kind:
        if parser_kind == "genie":
            output = connection.send_command(command, use_genie=True, raise_parsing_error=True, read_timeout=args.read_timeout, expect_string=expect_string)
            full_output = output
        elif parser_kind == "textfsm":
            template = str(Path(args.textfsm_template))
            output = connection.send_command(command, use_textfsm=True, raise_parsing_error=True,
                                             textfsm_template=template, read_timeout=args.read_timeout, expect_string=expect_string)
            full_output = output
    else:
        output = connection.send_command(command, expect_string=expect_string, read_timeout=args.read_timeout)
        full_output = f"{prompt} {command}\n{output}\n"

    return full_output


def _execute_console_commands_list(connection, prompt, exec_commands, *, args, parser_kind, expect_string: str | None):
    # :TODO commands_listの送信はsend_config_setを使うほうが安定するかも。
    full_output_list = []

    # textfsmだけ先に一度だけ作る 
    if parser_kind == "textfsm":
        template = str(Path(args.textfsm_template))

    for command in exec_commands:
        if parser_kind:
            if parser_kind == "genie":
                output = connection.send_command(command, use_genie=True, raise_parsing_error=True, read_timeout=args.read_timeout, expect_string=expect_string)
                full_output = output
                full_output_list.append(full_output)
            elif parser_kind == "textfsm":
                output = connection.send_command(command, use_textfsm=True, raise_parsing_error=True,
                                                 textfsm_template=template, read_timeout=args.read_timeout, expect_string=expect_string)
                full_output = output
                full_output_list.append(full_output)
        else:
            output = connection.send_command(command, read_timeout=args.read_timeout, expect_string=expect_string)
            full_output = f"{prompt} {command}\n{output}\n"
            full_output_list.append(full_output)
    
    if parser_kind == "genie":
        return full_output_list
    elif parser_kind == "textfsm":
        return full_output_list
    else:
        return "".join(full_output_list)


def _execute_console_commands(connection, prompt, args, exec_commands, parser_kind: str | None = None, *, expect_string: str | None = None):
    if args.command:
        return _execute_console_command(connection, prompt, args.command, args=args, parser_kind=parser_kind, expect_string=expect_string)
    elif args.commands_list:
        return _execute_console_commands_list(connection, prompt, exec_commands, args=args, parser_kind=parser_kind, expect_string=expect_string)
    else:
        raise ValueError("command または commands_list のいずれかが必要ケロ🐸")


# def reconnect_with_baudrate(device: dict, hostname: str, new_baudrate: int, *, args) -> str | None:
#     """
#     指定のボーレートで再接続確認だけ行う。
#     成功: None を返す（失敗なし）
#     失敗: 失敗した hostname を返す（呼び出し側の集計で使える）
#     """
#     device_re = dict(device) # 再接続用にコピーを作成 元のdeviceに影響を与えない。
#     serial_settings = dict(device_re.get("serial_settings", {}))
#     serial_settings["baudrate"] = int(new_baudrate)
#     device_re["serial_settings"] = serial_settings

#     try:
#         reconnect_connection, reconnect_prompt, reconnect_hostname = connect_to_device_for_console(
#             device_re, hostname, require_enable=True
#         )
#         safe_disconnect(reconnect_connection)
#         if not getattr(args, "no_output", False):
#             print_success(f"<NODE: {reconnect_hostname}> 🔁{new_baudrate}bps で再接続確認OKケロ🐸")
#         return None
#     except Exception as e:
#         if not getattr(args, "no_output", False):
#             print_error(f"<NODE: {hostname}> 🔁再接続失敗ケロ🐸: {e}")
#         return hostname


def _handle_console_execution(device: dict, args, poutput, hostname: str, *, output_buffers: dict | None = None, parser_kind: str | None = None) -> str | None:
    timer = perf_counter() # ⌚ start

    # ❶ commands-listは接続前に検証
    # ※ 接続前なので try/except で安全に中断する
    result_output_string = ""
    exec_commands = None # args.commandのとき未定義になるため必要。
    if args.commands_list:
        try:
            exec_commands = get_validated_commands_list(args)
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            elapsed = perf_counter() - timer
            print_warning(f"❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
            return hostname
    
    # ❷ device_type ミスマッチチェック (接続前に実施)
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

    
    # ❸ 接続 (enableまで)
    connection = None 
    require_enable = None
    try:
        require_enable = not getattr(args, "connect_only", False) # connect-onlyならenable昇格しない
        connection, prompt, hostname = connect_to_device_for_console(device, hostname, require_enable=require_enable)
    except ConnectionError as e:
        if not args.no_output:
            print_error(str(e))
            elapsed = perf_counter() - timer
            print_warning(f"<NODE: {hostname}> ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
            return hostname
        
    if not args.no_output:
        print_success(f"<NODE: {hostname}> 🔗接続成功ケロ🐸")

    if getattr(args, "connect_only", False):
        safe_disconnect(connection)
        elapsed = perf_counter() - timer
        if not args.no_output:
            print_success(f"<NODE: {hostname}> 🔚接続確認だけ完了ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return None

    # ❹ コマンド実行（単発 or リスト）
    # prompt 同期 必要に応じて 必要か？
    wait_for_prompt_returned(connection, sleep_time=SLEEP_TIME)
    # 実行時点のベースプロンプトから期待プロンプトを生成
    expect_string = re.escape(prompt)

    try:
        result_output_string = _execute_console_commands(connection, prompt, args, exec_commands, parser_kind, expect_string=expect_string)
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


    # ❺ 安全に切断
    safe_disconnect(connection)

    # if getattr(args, "post_reconnect_baudrate", None):
    #     failed = reconnect_with_baudrate(device, hostname, args.post_reconnect_baudrate, args=args)
    #     if failed:
    #         return failed

    # ❻ parser option 使用時の json と ordered 用の処理
    # display_text = 生テキスト or json 文字列
    # 表示用。save_json側でjson.dumpsが入るのでsave_jsonの呼び出し時はresult_output_stringを渡す。
    display_text = result_output_string 
    if parser_kind and isinstance(result_output_string, (list, dict)):
        display_text = json.dumps(result_output_string, ensure_ascii=False, indent=2)

    # ordered option用の貯める処理。(quiet | no-outputのときは貯めない。)
    if output_buffers is not None and args.group and args.ordered and not args.no_output and not args.quiet:
        output_buffers[hostname] = display_text
    
    # ❼ ログ保存（--log指定時のみ）
    if getattr(args, "log", False):
        if not getattr(args, "no_output", False):
            print_info(f"<NODE: {hostname}> 💾ログ保存モードONケロ🐸🔛")
        if parser_kind in ("genie", "textfsm") and isinstance(result_output_string, (list, dict)):
            log_path = save_json(result_output_string, hostname, args, parser_kind=parser_kind, mode="console")
        else:
            log_path = save_log(result_output_string, hostname, args, mode="console")
        if not getattr(args, "no_output", False):
            print_success(f"<NODE: {hostname}> 💾ログ保存完了ケロ🐸⏩⏩⏩ {log_path}")

    # ❽ 画面表示
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
    if not args.connect_only and not (args.command or args.commands_list):
        print_error("コマンド未指定ケロ🐸（-c か -L か --connect-only のいずれかが必要）")
        return
    
    # if args.connect_only and args.post_reconnect_baudrate:
    #     print_error("--connect-only と --post-reconnect-baudrate は同時に使えないケロ🐸")
    #     return

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




    # ❶ シリアルポートのチェック
    try:
        serial_port = check_serial_port(args.serial)
        if not args.no_output:
            print_info(f"✅ 使用可能なポート: {serial_port}")
    except ValueError as e:
        if not args.no_output:
            print_error(str(e))
            print_warning(f"❌中断ケロ🐸")
            return

    # ❸ inventoryの取得(--host or --group)
    inventory_data = None

    try:
        if args.host:
            inventory_data = get_validated_inventory_data(host=args.host)
        elif args.group:
            raise NotImplementedError
            inventory_data = get_validated_inventory_data(group=args.group)
        # TODO: group対応は将来実装予定
    except (NotImplementedError, FileNotFoundError, ValueError) as e:
        if not args.no_output:
            print_error(str(e))
            print_warning(f"❌中断ケロ🐸")
            return

    if args.host:
        device , hostname = build_device_and_hostname_for_console(args, inventory_data, serial_port)
        result_failed_hostname = _handle_console_execution(device, args, self.poutput, hostname, parser_kind=parser_kind)
        if result_failed_hostname and not args.no_output:
            print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
        return
    elif args.group:
        device , hostname = build_device_and_hostname_for_console(args, inventory_data, serial_port)
        # TODO: group実装時につくる
    # max_workers = default_workers(len(device_list), args)

    #     result_failed_hostname_list = []

    #     # ✅ --ordered 用の本文バッファ（hostname -> str）
    #     ordered_output_buffers = {}  # {hostname: collected_output}

    #     with ThreadPoolExecutor(max_workers=max_workers) as pool:

    #         futures = []
    #         future_to_hostname = {} 

    #         ordered_output_enabled =  args.ordered and not args.quiet and not args.no_output

    #         for device, hostname in zip(device_list, hostname_list):
    #             # --orderedがあって--quietと--no_outputがないこと。
    #             if ordered_output_enabled:
    #                 # 順番を並び替えるために貯める。
    #                 future = pool.submit(_handle_execution, device, args, self.poutput, hostname, output_buffers=ordered_output_buffers, parser_kind=parser_kind)
    #             else:
    #                 future = pool.submit(_handle_execution, device, args, self.poutput, hostname, parser_kind=parser_kind)
                
    #             futures.append(future)
    #             future_to_hostname[future] = hostname

    #         for future in as_completed(futures):
    #             hostname = future_to_hostname.get(future, "UNKNOWN")
    #             try:
    #                 result_failed_hostname = future.result()
    #                 if result_failed_hostname:
    #                     result_failed_hostname_list.append(result_failed_hostname)
    #             except Exception as e:
    #                 # _handle_execution で捕まえていない想定外の例外
    #                 if not args.no_output:
    #                     print_error(f"⚠️ 未処理の例外: {hostname}:{e}")
        
    #     # --orderedの場合は、ここで実行結果をまとめて表示する。
    #     if ordered_output_enabled:
    #         for h in sorted(ordered_output_buffers.keys(), key=lambda x: (x is None, x or "")):
    #             print_info(f"NODE: {h} 📄OUTPUTケロ🐸")
    #             self.poutput(ordered_output_buffers[h])

    #     # 結果をまとめて表示
    #     if result_failed_hostname_list and not args.no_output:
    #         print_warning(f"❎ 🐸なんかトラブルケロ: {', '.join(sorted(result_failed_hostname_list))}")
    #     else:
    #         if not args.no_output:
    #             print_success("✅ すべてのホストで実行完了ケロ🐸")

        pass
    else:
        # hostやgroupを使用しないとき用
        device , hostname = build_device_and_hostname_for_console(args, inventory_data, serial_port)
        result_failed_hostname = _handle_console_execution(device, args, self.poutput, hostname, parser_kind=parser_kind)
        if result_failed_hostname and not args.no_output:
            print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
        return





 


