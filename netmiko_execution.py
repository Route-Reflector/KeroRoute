import re
from time import perf_counter
from pathlib import Path
import json
from threading import Lock

from message import print_info, print_success, print_warning, print_error
from output_logging import save_log, save_json
from load_and_validate_yaml import get_validated_commands_list, validate_device_type_for_list, get_commands_list_device_type
from connect_device import connect_to_device, safe_disconnect
from prompt_utils import wait_for_prompt_returned


#######################
###  CONST_SECTION  ### 
#######################
SLEEP_TIME = 1



__all__ = ["handle_execution"]


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
    expect_string = rf"{re.escape(prompt)}\s*$"
    read_timeout = getattr(args, "read_timeout", None)
    
    # console専用の送信オプションだけまとめる
    send_kwargs = {}
    if getattr(args, "via", None) == "console":
        send_kwargs["expect_string"] = expect_string
        if read_timeout is not None:
            send_kwargs["read_timeout"] = read_timeout

    if parser_kind:
        if parser_kind == "genie":
            output = connection.send_command(command, use_genie=True, raise_parsing_error=True, **send_kwargs)
            full_output = output
        
        elif parser_kind == "textfsm":
            template = str(Path(args.textfsm_template))
            output = connection.send_command(command, use_textfsm=True, raise_parsing_error=True,
                                             textfsm_template=template, **send_kwargs)
            full_output = output
    else:
        output = connection.send_command(command, **send_kwargs)
        full_output = f"{prompt} {command}\n{output}\n"

    return full_output


def _execute_commands_list(connection, prompt, exec_commands, args, parser_kind):
    """
    commands-lists.yaml で定義されたコマンド列を順次実行し、結果を連結して返す。

    Parameters
    ----------
    connection : BaseConnection
        `connect_to_device()` で取得した Netmiko 接続（特権モード|base_prompt確定済み）。
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

    expect_string = rf"{re.escape(prompt)}\s*$"
    read_timeout = getattr(args, "read_timeout", None)

    # console専用の送信オプションだけまとめる
    send_kwargs = {}
    if getattr(args, "via", None) == "console":
        send_kwargs["expect_string"] = expect_string
        if read_timeout is not None:
            send_kwargs["read_timeout"] = read_timeout

    # textfsmだけ先に一度だけ作る 
    if parser_kind == "textfsm":
        template = str(Path(args.textfsm_template))

    for command in exec_commands:
        if parser_kind:
            if parser_kind == "genie":
                output = connection.send_command(command, use_genie=True, raise_parsing_error=True, **send_kwargs)
                full_output = output
                full_output_list.append(full_output)
            elif parser_kind == "textfsm":
                output = connection.send_command(command, use_textfsm=True, raise_parsing_error=True,
                                                 textfsm_template=template, **send_kwargs)
                full_output = output
                full_output_list.append(full_output)
        else:
            output = connection.send_command(command, **send_kwargs)
            full_output = f"{prompt} {command}\n{output}\n"
            full_output_list.append(full_output)
        
        # via == consoleのときだけ各コマンド後に同期してバッファを吐かせる(安定化)
        if getattr(args, "via", "") == "console":
            try:
                wait_for_prompt_returned(connection, sleep_time=SLEEP_TIME)
            except Exception:
                # 同期失敗は致命的ではないので握りつぶして次へ
                pass
    
    if parser_kind == "genie":
        return full_output_list
    elif parser_kind == "textfsm":
        return full_output_list
    else:
        return "".join(full_output_list)


def _execute_commands(connection, prompt, args, exec_commands, parser_kind: str | None = None) -> str | list | dict:
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
    str | list | dict
        parser_kind=Noneのときは実行結果テキスト。
        parser_kind指定時は構造化データ

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


def reconnect_with_baudrate(device: dict, hostname: str, new_baudrate: int, *, args) -> str | None:
    """
    指定のボーレートで再接続確認だけ行う。
    成功: None を返す（失敗なし）
    失敗: 失敗した hostname を返す（呼び出し側の集計で使える）
    """
    device_re = dict(device) # 再接続用にコピーを作成 元のdeviceに影響を与えない。
    serial_settings = dict(device_re.get("serial_settings", {}))
    serial_settings["baudrate"] = int(new_baudrate)
    device_re["serial_settings"] = serial_settings

    try:
        reconnect_connection, reconnect_prompt, reconnect_hostname = connect_to_device(
            device_re, hostname, require_enable=True
        )
        safe_disconnect(reconnect_connection)
        if not getattr(args, "no_output", False):
            print_success(f"<NODE: {reconnect_hostname}> 🔁{new_baudrate}bps で再接続確認OKケロ🐸")
        return None
    except Exception as e:
        if not getattr(args, "no_output", False):
            print_error(f"<NODE: {hostname}> 🔁再接続失敗ケロ🐸: {e}")
        return hostname


def handle_execution(device: dict, args, poutput, hostname, *, output_buffers: dict | None = None,
                     parser_kind: str | None = None, lock: Lock | None = None) -> str | None:
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
    # ❶ commands-list の存在チェック（必要なら）
    result_output_string = ""
    exec_commands = None # args.commandのとき未定義になるため必要。

    try:
        if args.commands_list:
            exec_commands = get_validated_commands_list(args)
    except (FileNotFoundError, ValueError) as e:
        if not args.no_output:
            print_error(str(e))
            elapsed = perf_counter() - timer
            print_warning(f"<NODE: {hostname}> ❌中断ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return hostname # 失敗時
    
    # ❷ device_type ミスマッチチェック (接続前に実施)
    if args.commands_list:
        list_device_type = get_commands_list_device_type(args.commands_list)
        node_device_type = device.get("device_type")

        re_suffix = re.compile(r"_(serial|telnet)$")
        base_list_device_type = re_suffix.sub("", list_device_type or "")
        base_node_device_type = re_suffix.sub("", node_device_type or "")

        try:
            validate_device_type_for_list(hostname=hostname,
                                          node_device_type=base_node_device_type,
                                          list_name=args.commands_list,
                                          list_device_type=base_list_device_type)
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

    # ❸ 接続とプロンプト取得
    connection = None 
    require_enable = None

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

    if getattr(args, "connect_only", False):
        safe_disconnect(connection)
        elapsed = perf_counter() - timer
        if not args.no_output:
            print_success(f"<NODE: {hostname}> 🔚接続確認だけ完了ケロ🐸 (elapsed: {elapsed:.2f}s)")
        return None

    # CONSOLE対応
    if getattr(args, "via", None) == "console":
        # 画面残り対策prompt同期
        wait_for_prompt_returned(connection, sleep_time=SLEEP_TIME)

    # ❹ コマンド実行（単発 or リスト）
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

    # ❺ 接続終了
    safe_disconnect(connection)

    # ❻ parser option 使用時の json と ordered 用の処理
    # display_text = 生テキスト or json 文字列
    # 表示用。save_json側でjson.dumpsが入るのでsave_jsonの呼び出し時はresult_output_stringを渡す。
    display_text = result_output_string 
    if parser_kind and isinstance(result_output_string, (list, dict)):
        display_text = json.dumps(result_output_string, ensure_ascii=False, indent=2)

    # ❼ ordered option用の貯める処理。(quiet | no-outputのときは貯めない。)
    if output_buffers is not None and args.group and args.ordered and not args.no_output and not args.quiet:
        if lock is not None:
            with lock:
                output_buffers[hostname] = display_text
        else:
            output_buffers[hostname] = display_text
    
    # ❽ ログ保存（--log指定時のみ）
    if getattr(args, "log", False):
        if not getattr(args, "no_output", False):
            print_info(f"<NODE: {hostname}> 💾ログ保存モードONケロ🐸🔛")
        
        via = getattr(args, "via", "")
        if via in ["ssh", "telnet", "console"]:
            log_save_mode = via
            if via == "ssh":
                log_save_mode = "execute"
        else:
            print_error("ログ保存用のモードが決定できないケロ🐸")
            return hostname

        if parser_kind in ("genie", "textfsm") and isinstance(result_output_string, (list, dict)):
            log_path = save_json(result_output_string, hostname, args, parser_kind=parser_kind, mode=log_save_mode)
        else:
            log_path = save_log(result_output_string, hostname, args, mode=log_save_mode)
        
        if not getattr(args, "no_output", False):
            print_success(f"<NODE: {hostname}> 💾ログ保存完了ケロ🐸⏩⏩⏩ {log_path}")


    # ❾ 結果表示
    if not args.no_output:
        if args.quiet:
            print_info(f"<NODE: {hostname}> 📄OUTPUTは省略するケロ (hidden by --quiet) 🐸")
        else:
            if not (args.group and args.ordered and output_buffers is not None):
                if lock:
                    with lock:
                        print_info(f"<NODE: {hostname}> 📄OUTPUTケロ🐸")
                        poutput(display_text)
                else:
                    print_info(f"<NODE: {hostname}> 📄OUTPUTケロ🐸")
                    poutput(display_text)

    elapsed = perf_counter() - timer

    if not args.no_output:
        print_success(f"<NODE: {hostname}> 🔚実行完了ケロ🐸 (elapsed: {elapsed:.2f}s)")
    return None # 成功時