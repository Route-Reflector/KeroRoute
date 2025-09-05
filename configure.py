import cmd2
from cmd2 import Cmd2ArgumentParser
from rich_argparse import RawTextRichHelpFormatter

from message import print_info, print_success, print_warning, print_error
from load_and_validate_yaml import get_validated_inventory_data, get_validated_config_list, CONFIG_LISTS_FILE
from output_logging import save_log
from build_device import build_device_and_hostname
from concurrent.futures import ThreadPoolExecutor, as_completed
from connect_device import connect_to_device, safe_disconnect
from workers import default_workers
from completers import host_names_completer, group_names_completer, config_list_names_completer, device_types_completer
from capability_guard import guard_configure, CapabilityError

######################
###  HELP_SECTION  ### 
######################
ip_help = "対象デバイスのIPアドレスを指定します。"
host_help = "inventory.yamlに定義されたホスト名を指定します。"
group_help = "inventory.yamlに定義されたグループ名を指定します。グループ内の全ホストにコマンドを実行します。"
command_help = "1つのコマンドを直接指定して実行します。"
command_list_help = "コンフィグリスト名（config-lists.yamlに定義）を指定して実行します。"
username_help = "SSH接続に使用するユーザー名を指定します。省略時はinventory.yamlの値を使用します。"
password_help = "SSH接続に使用するパスワードを指定します。省略時はinventory.yamlの値を使用します。"
device_type_help = "Netmikoにおけるデバイスタイプを指定します（例: cisco_ios）。省略時は 'cisco_ios' です。"
port_help = "SSH接続に使用するポート番号を指定します（デフォルト: 22）"
timeout_help = "SSH接続のタイムアウト秒数を指定します（デフォルト: 10秒）"
log_help = ("実行結果をログファイルとして保存します。\n"
           "保存先: logs/configure/\n"
           "保存名: yearmmdd-hhmmss_[hostname]_[config_or_config_list]\n"
           "example: 20250504-235734_R0_show-ip-int-brief.log")
memo_help = ("ログファイル名に付加する任意のメモ（文字列）を指定します。\n"
             "保存先: logs/configure/\n"
             "保存名: yearmmdd-hhmmss_[hostname]_[config_or_config_list]_[memo]\n"
             "example 20250506-125600_R0_show-ip-int-brief_memo.log")
workers_help = ("並列実行するワーカースレッド数を指定します。\n"
                "指定しない場合は sys_config.yaml の executor.default_workers を参照します。\n"
                "そこにも設定が無いときは、グループ台数と 規定上限(DEFAULT_MAX_WORKERS) の小さい方が自動で採用されます。")
secret_help = ("enable に入るための secret を指定します。(省略時は password を流用します。)\n"
               "--host | --group 指定時に --secret オプションを使用すると [bright_yellow]inventory.yaml[/bright_yellow] の値に上書き使用します。\n\n")
quiet_help = ("画面上の出力（nodeのcommandの結果）を抑制します。進捗・エラーは表示されます。このオプションを使う場合は --log が必須です。")
no_output_help = ("画面上の出力を完全に抑制します（進捗・エラーも表示しません）。 --log が未指定の場合のみエラー表示します。")
ordered_help = ("--group指定時にoutputの順番を昇順に並べ変えます。 このoptionを使用しない場合は実行完了順に表示されます。"
                "--group 未指定の場合に --ordered オプションを使用するとエラーになります。")
force_help = "device_type の不一致や未設定エラーを無視して強制実行するケロ🐸"
via_help = ("executeコマンドを実行するprotocolを指定します。\n"
            "[ssh | telnet | console]から1つ選択します。指定しない場合はsshになります。🐸")

######################
### PARSER_SECTION ###
######################
netmiko_configure_parser = Cmd2ArgumentParser(formatter_class=RawTextRichHelpFormatter, description="[green]configure コマンド🐸[/green]")
# "-h" はhelpと競合するから使えない。
netmiko_configure_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_configure_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_configure_parser.add_argument("-d", "--device_type", type=str, default="cisco_ios", help=device_type_help, completer=device_types_completer)
netmiko_configure_parser.add_argument("-P", "--port", type=int, default=None, help=port_help)
netmiko_configure_parser.add_argument("-t", "--timeout", type=int, default=None, help=timeout_help)
netmiko_configure_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_configure_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_configure_parser.add_argument("-w", "--workers", type=int, default=None, metavar="N", help=workers_help)
netmiko_configure_parser.add_argument("-s", "--secret", type=str, default="", help=secret_help)
netmiko_configure_parser.add_argument("-o", "--ordered", action="store_true", help=ordered_help)
netmiko_configure_parser.add_argument("--force", action="store_true", help=force_help)
netmiko_configure_parser.add_argument("--via", "-v", "--by", "-V",  dest="via", 
                                    choices=["ssh", "telnet", "console", "restconf"], default="ssh", help=via_help)

# mutually exclusive
target_node = netmiko_configure_parser.add_mutually_exclusive_group(required=False)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None, help=ip_help)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help, completer=host_names_completer)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help, completer=group_names_completer)

target_command = netmiko_configure_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("-L", "--config-list", type=str, default="", help=command_list_help, completer=config_list_names_completer)

silence_group = netmiko_configure_parser.add_mutually_exclusive_group(required=False)
silence_group.add_argument("--quiet", action="store_true", help=quiet_help)
silence_group.add_argument("--no-output", "--no_output", dest="no_output", action="store_true", help=no_output_help)

def apply_config_list(connection, hostname, args):
    """
    config-lists.yaml で指定された設定コマンド群を投入する。

    Parameters
    ----------
    connection : BaseConnection
        `connect_to_device()` で取得した Netmiko 接続（特権モード/#・base_prompt 確定済み）
    hostname : str
        ログ|メッセージ表示用の識別子（base_prompt 由来のホスト名）
    args : argparse.Namespace
        CLI 引数。`args.config_list` を使用

    Returns
    -------
    str
        端末の返り値（`send_config_set()` の生テキスト）

    Raises
    ------
    KeyError
        config-lists.yaml の構造が想定外／参照キーが見つからない場合
    ValueError
        `args.config_list` が未指定など、投入条件を満たさない場合

    Notes
    -----
    - `send_config_set(configure_commands, strip_prompt=False, strip_command=False)` を使用
    - パースや変換は行わず、得られた出力をそのまま返す🐸
    """
    if not args.config_list:
        raise ValueError("config_listが必要ケロ🐸")

    try:
        configure_commands = get_validated_config_list(args)

    except (FileNotFoundError, ValueError) as e:
        raise KeyError(f"[{hostname}] '{CONFIG_LISTS_FILE}' の構造がおかしいケロ🐸 詳細: {e}")



    result_output_string = connection.send_config_set(configure_commands, strip_prompt=False, strip_command=False)

    return result_output_string



def _handle_configure(device: dict, args, poutput, hostname) -> str | None:
    """
    デバイス接続 → 設定投入 → ログ保存 → 出力表示 までを一括で行う実行ラッパー。

    フロー
    ------
    1) `connect_to_device(device, hostname)` で接続を確立
       - 成功時、特権モード(#) へ昇格済み
       - `set_base_prompt()` 済み
       - `(connection, prompt, hostname)` を受け取る（hostname は base_prompt 由来）
    2) `apply_config_list()` で設定コマンドを投入
    3) 必要に応じてログ保存（`--log` 指定時）
    4) 出力表示（`--no-output` / `--quiet` に応じて抑制）

    Parameters
    ----------
    device : dict
        接続パラメータ辞書（inventory もしくは CLI から構築）
    args : argparse.Namespace
        CLI 引数（log, memo, config_list などを含む）
    poutput : Callable[[str], None]
        cmd2 の出力関数（着色や装飾を統一するために使用）
    hostname : str
        接続前の識別子（IP または inventory の hostname）。接続後は base_prompt 由来に更新される

    Returns
    -------
    None | str
        成功時は None。失敗時は識別子（hostname）を返す（上位で失敗ノードとして集計する用）

    Raises
    ------
    （内部で捕捉して `print_error` 済みのため、外側には投げない設計）

    Notes
    -----
    - 例外時／終了時の切断は `safe_disconnect()` を使用して元例外を潰さない
    - 画面表示は `--no-output` | `--quiet` の指定に従う🐸
    """
    result_output_string = ""

    # ✅ 1. 接続とプロンプト取得（接続＝特権化＆base_prompt確定＆prompt取得まで完了）
    try:
        connection, prompt, hostname = connect_to_device(device, hostname)
    except ConnectionError as e:
        print_error(str(e))
        return hostname # 接続失敗時にhostnameをreturn
    
    print_success(f"NODE: {hostname} 🔗接続成功ケロ🐸")
    
    
    # ✅ 2. 設定変更（config-list）
    try:
        result_output_string = apply_config_list(connection, hostname, args)
    except (KeyError, ValueError) as e:
        print_error(str(e))
        safe_disconnect(connection)
        return hostname # 設定投入失敗時にhostnameをreturn

    # ✅ 3. 接続終了
    safe_disconnect(connection)

    # ✅ 4. ログ保存（--log指定時のみ）
    if args.log:
        save_log(result_output_string, hostname, args, mode="configure")

    # ✅ 5. 結果表示
    print_info(f"NODE: {hostname} 📄OUTPUTケロ🐸")
    poutput(result_output_string)
    print_success(f"NODE: {hostname} 🔚実行完了ケロ🐸")
    return None # 成功時にNoneを返す。


@cmd2.with_argparser(netmiko_configure_parser)
def do_configure(self, args):
    """
    `configure` サブコマンドのエントリポイント。

    ルーティング
    ------------
    - `--ip`    : 単一デバイス（CLI 引数で接続情報を指定）
    - `--host`  : inventory.yaml の 1 ホスト
    - `--group` : inventory.yaml のグループ内すべてのホスト（並列実行）

    実装メモ
    -------
    - 実処理は `_handle_configure()` に委譲
    - 接続確立は `connect_to_device()` を使用
        - 成功時点で特権モード/# かつ base_prompt 確定済み
        - `(connection, prompt, hostname)` を受け取り、hostname は base_prompt 由来へ更新
    - ログ保存は `--log` 指定時のみ実施（ファイル名は hostname を組み込む）
    - 画面表示は `--no-output` | `--quiet` に従って抑制

    エラーハンドリング
    ------------------
    - 接続|enable 失敗、設定投入失敗は `_handle_configure()` 内で捕捉・表示
    - グループ実行時は失敗ノードを集計して最後に要約表示する🐸
    """
    # via を確認し、未実装は即終了（UX優先）
    via = getattr(args, "via", "ssh") # ssh, telnet, console, restconfのいずれか 指定なしの場合はssh
    if via in ["restconf", "telnet", "console"]:
        print_error(f"via {via}はまだ実装されてないケロ🐸")
        return
    
    if via == "telnet" and args.port == 22:
        print_warning("via=telnet なのに --port 22 が指定されてるケロ🐸 通常は 23 だよ")
        return

    no_target = not (args.ip or args.host or args.group)
    if no_target and via != "console":
        print_error("ssh|telnetでは --ip か --host か --group の指定が必要ケロ🐸")
        return

    # connect_onlyは出てこないため、

    # if not args.connect_only and not (args.command or args.commands_list):
    #     print_error("コマンド未指定ケロ🐸（-c か -L か --connect-only のいずれかが必要）")
    #     return
    
    # if args.connect_only and args.post_reconnect_baudrate:
    #     print_error("--connect-only と --post-reconnect-baudrate は同時に使えないケロ🐸")
    #     return

    # Capability_Guard executorと差分あり。
    try:
        guard_configure(args)  # ← 不許可オプションがあればここで止める
    except CapabilityError as e:
        print_error(str(e))
        return

    # Capability_Guard
    if args.ordered and not args.group:
        print_error("--ordered は --group 指定時のみ使用できるケロ🐸")
        return

    if args.quiet and not args.log:
        print_error("--quietオプションを使用するには--logが必要ケロ🐸")
        return
    
    elif args.no_output and not args.log:
        print_error("--no-outputオプションを使用するには--logが必要ケロ🐸 (画面出力ゼロだと結果が消えるよ)")
        return

    # Parser_Guard: configureでは未使用
    # parser_kind = None

    if args.ip:
        device, hostname = build_device_and_hostname(args)
        result_failed_hostname = _handle_configure(device,  args, self.poutput, hostname)
        if result_failed_hostname:
            print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
        return
    
    elif args.host or args.group:
        try:
            inventory_data = get_validated_inventory_data(host=args.host, group=args.group)
        
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return
    
    if args.host:
        device, hostname = build_device_and_hostname(args, inventory_data)
        result_failed_hostname = _handle_configure(device, args, self.poutput, hostname)
        if result_failed_hostname:
            print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
        return

    elif args.group:
        device_list, hostname_list = build_device_and_hostname(args, inventory_data)

        max_workers = default_workers(len(device_list), args)

        result_failed_hostname_list = []

        with ThreadPoolExecutor(max_workers=max_workers) as pool:

            futures = []
            for device, hostname in zip(device_list, hostname_list):
                future = pool.submit(_handle_configure, device, args, self.poutput, hostname)
                futures.append(future)

            for future in as_completed(futures):
                try:
                    result_failed_hostname = future.result() # None or "R0"
                    if result_failed_hostname: # 失敗したら文字列が帰る🐸
                        result_failed_hostname_list.append(result_failed_hostname)
                except Exception as e:
                    # _handle_configure で捕まえていない想定外の例外
                    print_error(f"⚠️ 未処理の例外: {hostname}:{e}")

        # 結果をまとめて表示
        if result_failed_hostname_list:
            print_warning(f"❎ 🐸なんかトラブルケロ: {', '.join(sorted(result_failed_hostname_list))}")
        else:
            print_success("✅ すべてのホストで設定完了ケロ🐸")

