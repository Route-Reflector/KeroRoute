from pathlib import Path
import threading
import cmd2
from cmd2 import Cmd2ArgumentParser
from rich_argparse import RawTextRichHelpFormatter
from concurrent.futures import ThreadPoolExecutor, as_completed
from netmiko.utilities import check_serial_port

from message import print_info, print_success, print_warning, print_error
from build_device import build_device_and_hostname
from load_and_validate_yaml import get_validated_inventory_data
from workers import default_workers
from completers import host_names_completer, group_names_completer, device_types_completer, commands_list_names_completer
from capability_guard import guard_execute, CapabilityError
from netmiko_execution import handle_execution


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

username_help = ("SSH|TELNET|CONSOLE 接続に使用するユーザー名を指定します。\n"
                 "--host | --group 指定時に --username オプションを使用すると[bright_yellow]inventory.yaml[/bright_yellow]の値に上書き使用します。\n")
password_help = ("SSH|TELNET|CONSOLE 接続に使用するパスワードを指定します。\n"
                 "--host | --group 指定時に --password オプションを使用すると[bright_yellow]inventory.yaml[/bright_yellow]の値に上書き使用します。\n")
device_type_help = ("Netmikoにおけるデバイスタイプを指定します（例: cisco_ios）。省略時は 'cisco_ios' です。\n"
                    "--via console | --via telnet指定時には自動的に'_serial','_telnet'を付与します。\n"
                    "内部的に自動で処理されるため_serial, _telnetを `inventory.yaml` や `commands-lists.yaml` に付与する必要はありません。")
port_help = "SSH接続に使用するポート番号を指定します（デフォルト: 22）\n"
timeout_help = "SSH接続のタイムアウト秒数を指定します（デフォルト: 10秒）\n"
log_help = ("実行結果をログファイルとして保存します。\n"
            "保存先: logs/[mode]/\n"
            "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]\n"
            "[bright_yellow]example: 20250504-235734_R0_show-ip-int-brief.log[/bright_yellow]\n"
            "[mode]には'execute, configure, console, telnet'等の値が入ります。")
memo_help = ("ログファイル名に付加する任意のメモ（文字列）を指定します。\n"
             "保存先: logs/[mode]/\n"
             "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]_[memo]\n"
             "[bright_yellow]example: 20250506-125600_R0_show-ip-int-brief_memo.log[/bright_yellow]\n"
             "[mode]には'execute, configure, console, telnet'等の値が入ります。")
workers_help = ("並列実行するワーカースレッド数を指定します。\n"
                "指定しない場合は [bright_yellow]sys_config.yaml[/bright_yellow] の [bright_yellow]executor.default_workers[/bright_yellow] を参照します。\n"
                "そこにも設定が無いときは、グループ台数と 規定上限([bright_blue]DEFAULT_MAX_WORKERS[/bright_blue]) の小さい方が自動で採用されます。\n\n")
secret_help = ("enable に入るための secret を指定します。(省略時は password を流用します。)\n"
               "--host | --group 指定時に --secret オプションを使用すると [bright_yellow]inventory.yaml[/bright_yellow] の値に上書き使用します。\n\n")
quiet_help = ("画面上の出力（nodeのcommandの結果）を抑制します。進捗・エラーは表示されます。このオプションを使う場合は --log が必須です。")
no_output_help = ("画面上の出力を完全に抑制します（進捗・エラーも表示しません）。 --log が未指定の場合のみエラー表示します。")
ordered_help = ("--group指定時にoutputの順番を昇順に並べ変えます。 このoptionを使用しない場合は実行完了順に表示されます。"
                "--group 未指定の場合に --ordered オプションを使用するとエラーになります。")
parser_help = ("コマンドの結果をparseします。textfsmかgenieを指定します。")
textfsm_template_help = ("--parser optionで textfsm を指定する際に template ファイルを渡すためのオプションです。\n"
                         "--parser optionで textfsm を指定する際は必須です。(genieのときは必要ありません。)")
force_help = "device_type の不一致や未設定エラーを無視して強制実行するケロ🐸"
via_help = ("executeコマンドを実行するprotocolを指定します。\n"
            "[ssh | telnet | console | restconf]から1つ選択します。指定しない場合はsshになります。🐸")
serial_help = ("使用するシリアルポートを指定します。\n"
               "example: console --serial /dev/ttyUSB0\n")
baudrate_help = ("使用するbaudrateを指定します。\n"
                 "example: console --baudrate 9600")
read_timeout_help = ("send_command の応答待ち時間（秒）。\n"
                     "重いコマンド（例: show tech）用に指定します。\n"
                     "console --host R1 -c 'show tech' --read_timeout 1000\n"
                     "default: 60 (seconds)")
connect_only_help = "コマンドを実行せず、接続確認だけ行うケロ🐸（enable まで）"
post_reconnect_baudrate_help = "実行後にこのボーレートで再接続確認だけ行うケロ🐸"


######################
### PARSER_SECTION ###
######################
netmiko_execute_parser = Cmd2ArgumentParser(formatter_class=RawTextRichHelpFormatter,
                                            description="[green]execute コマンド🐸[/green]")
# "-h" はhelpと競合するから使えない。
netmiko_execute_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_execute_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_execute_parser.add_argument("-d", "--device_type", type=str, default="cisco_ios", help=device_type_help,
                                    completer=device_types_completer)
netmiko_execute_parser.add_argument("-P", "--port", type=int, default=None, help=port_help)
netmiko_execute_parser.add_argument("-t", "--timeout", type=int, default=None, help=timeout_help)
netmiko_execute_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_execute_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_execute_parser.add_argument("-w", "--workers", type=int, default=None, metavar="N", help=workers_help)
netmiko_execute_parser.add_argument("-s", "--secret", type=str, default="", help=secret_help)
netmiko_execute_parser.add_argument("-o", "--ordered", action="store_true", help=ordered_help)
netmiko_execute_parser.add_argument("--parser", "--parse", dest="parser", 
                                    choices=["textfsm", "genie", "text-fsm"], help=parser_help)
netmiko_execute_parser.add_argument("--textfsm-template", type=str,  help=textfsm_template_help)
netmiko_execute_parser.add_argument("--force", action="store_true", help=force_help)
netmiko_execute_parser.add_argument("--via", "-v", "--by", "-V",  dest="via", 
                                    choices=["ssh", "telnet", "console", "restconf"], default="ssh", help=via_help)
netmiko_execute_parser.add_argument("-S", "--serial", nargs="+", default=["/dev/ttyUSB0"], help=serial_help)
netmiko_execute_parser.add_argument("-b", "--baudrate", type=int, default=None, help=baudrate_help)
netmiko_execute_parser.add_argument("-r", "--read_timeout", "--read-timeout", dest="read_timeout", type=int, default=60, help=read_timeout_help)
netmiko_execute_parser.add_argument("--post-reconnect-baudrate", type=int, help=post_reconnect_baudrate_help)


# mutually exclusive
target_node = netmiko_execute_parser.add_mutually_exclusive_group(required=False)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None, help=ip_help)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help, completer=host_names_completer)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help, completer=group_names_completer)

target_command = netmiko_execute_parser.add_mutually_exclusive_group(required=False)
target_command.add_argument("-c", "--command", type=str, default="", help=command_help)
target_command.add_argument("-L", "--commands-list", type=str, default="",
                            help=command_list_help, completer=commands_list_names_completer)
target_command.add_argument("--connect-only", action="store_true", help=connect_only_help)

silence_group = netmiko_execute_parser.add_mutually_exclusive_group(required=False)
silence_group.add_argument("--quiet", action="store_true", help=quiet_help)
silence_group.add_argument("--no-output", "--no_output", dest="no_output", action="store_true", help=no_output_help)


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
    - 実処理は `handle_execution()` に委譲。
    - `cmd2` では ``self.poutput`` が標準出力をラップしているため、
      すべての内部関数にこれを渡してカラー表示や装飾を統一している。
    """
    # via を確認し、未実装は即終了（UX優先）
    via = getattr(args, "via", "ssh") # ssh, telnet, console, restconfのいずれか 指定なしの場合はssh
    if via == "restconf":
        print_error(f"via {via}はまだ実装されてないケロ🐸")
        return
    
    if via == "telnet" and args.port == 22:
        print_warning("via=telnet なのに --port 22 が指定されてるケロ🐸 通常は 23 だよ")
        return

    no_target = not (args.ip or args.host or args.group)
    if no_target and via != "console":
        print_error("ssh|telnetでは --ip か --host か --group の指定が必要ケロ🐸")
        return

    if not args.connect_only and not (args.command or args.commands_list):
        print_error("コマンド未指定ケロ🐸（-c か -L か --connect-only のいずれかが必要）")
        return
    
    if args.connect_only and args.post_reconnect_baudrate:
        print_error("--connect-only と --post-reconnect-baudrate は同時に使えないケロ🐸")
        return

    # Capability_Guard
    try:
        guard_execute(args)
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

    # Parser_Guard
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
    if via == "console":
        try:
            # args.serial は list になっている（nargs='+'）
            serial_list = args.serial if isinstance(args.serial, list) else [args.serial]
 
            # print連打を避けるための簡易キャッシュ（複数ポート対応）
            if not hasattr(self, "_printed_serial_ports"):
                self._printed_serial_ports = set()
 
            checked_ports = []
            for sp in serial_list:
                real = check_serial_port(sp)  # ここで存在/権限チェック。失敗なら except へ
                if not args.no_output and real not in self._printed_serial_ports:
                    print_info(f"✅ 使用可能なポート: {real}")
                    self._printed_serial_ports.add(real)
                checked_ports.append(real)
 
            # group ならリストのまま、単体なら先頭だけ（従来互換）
            if args.group:
                serial_port = checked_ports
            else:
                serial_port = checked_ports[0]
                # 単発ターゲットなのに複数シリアル指定があれば親切に警告しておく
                if not args.no_output and len(checked_ports) > 1:
                    print_warning("複数の --serial が指定されたけど単一ターゲットなので先頭の1本だけ使うケロ🐸")
        except ValueError as e:
            if not args.no_output:
                print_error(str(e))
                print_warning(f"❌中断ケロ🐸")
            return
    else:
        serial_port = None

    # ❷ inventory_data を先に初期化しておく (host/groupが無い経路用)
    inventory_data = None
    
    #########################
    ### command_execution ###
    #########################
    if via in ("ssh", "telnet", "console"):

        if args.ip:
            if via == "console":
                device, hostname = build_device_and_hostname(args, serial_port=serial_port)
            else:
                device, hostname = build_device_and_hostname(args)
                
            result_failed_hostname = handle_execution(device, args, self.poutput, hostname, parser_kind=parser_kind)
            if result_failed_hostname and not args.no_output:
                print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
            return

        try:
            if args.host:
                inventory_data = get_validated_inventory_data(host=args.host)
            elif args.group:
                inventory_data = get_validated_inventory_data(group=args.group)    
        except (FileNotFoundError, ValueError) as e:
            if not args.no_output:
                print_error(str(e))
                # 👉 ssh/telnet で inventory の IP が空/不正なときは console を案内
                if via in ("ssh", "telnet") and ("inventory の ip が" in str(e) or "--ip で指定した値が" in str(e)):
                    print_info("👉 コンソール接続なら --via console を使ってね🐸")
                print_warning(f"❌中断ケロ🐸")
            return
        
        if args.host:
            if via == "console":
                device, hostname = build_device_and_hostname(args, inventory_data, serial_port=serial_port)
            else:
                device, hostname = build_device_and_hostname(args, inventory_data)

            result_failed_hostname = handle_execution(device, args, self.poutput, hostname, parser_kind=parser_kind)
            if result_failed_hostname and not args.no_output:
                print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
            return

        elif args.group:
            if via == "console":
                # === via=console: build_device 側が“バッチ配列”を返す ===
                batches = build_device_and_hostname(args, inventory_data, serial_port=serial_port)
                # example: [(device_list, hostname_list), (device_list, hostname_list), ...]

                result_failed_hostname_list = []
                for batch_idx, (device_list, hostname_list) in enumerate(batches, start=1):
                    max_workers = default_workers(len(device_list), args)

                    ordered_output_buffers = {} # --ordered 用
                    lock = threading.Lock()
                    futures = []
                    future_to_hostname = {}
                    ordered_output_enabled = args.ordered and not args.quiet and not args.no_output

                    with ThreadPoolExecutor(max_workers=max_workers) as pool:
                        for device, hostname in zip(device_list, hostname_list):
                            if ordered_output_enabled:
                                future = pool.submit(handle_execution, device, args, self.poutput, hostname,
                                                     output_buffers=ordered_output_buffers,
                                                     parser_kind=parser_kind, lock=lock)
                            else:
                                future = pool.submit(handle_execution, device, args, self.poutput, hostname,
                                                     parser_kind=parser_kind, lock=lock)
                            
                            futures.append(future)
                            future_to_hostname[future] = hostname
                        
                        for future in as_completed(futures):
                            hostname = future_to_hostname.get(future, "UNKNOWN")
                            try:
                                result_failed_hostname = future.result()
                                if result_failed_hostname:
                                    result_failed_hostname_list.append(result_failed_hostname)
                            except Exception as e:
                                if not args.no_output:
                                    print_error(f"⚠️ 未処理の例外: {hostname}:{e}")

                    # --ordered の表示（このバッチ分）
                    if ordered_output_enabled:
                        for h in sorted(ordered_output_buffers.keys(), key=lambda x: (x is None, x or "")):
                            print_info(f"NODE: {h} 📄OUTPUTケロ🐸")
                            self.poutput(ordered_output_buffers[h])
                    
                    # バッチ間の差し替え案内
                    if batch_idx < len(batches) and not args.no_output:
                        print_success(f"✅ バッチ {batch_idx}/{len(batches)} 完了ケロ🐸")
                        print_info("🔌 次のバッチに向けてケーブルを差し替えてね（同じ順番でOK）")
                        try:
                            input("準備できたら Enter を押して 続行ケロ🐸")
                        except KeyboardInterrupt:
                            print_warning("⛔ 中断ケロ🐸")
                            return
                    
                # 全体まとめ
                if result_failed_hostname_list and not args.no_output:
                    print_warning(f"❎ 一部失敗ケロ: {', '.join(sorted(result_failed_hostname_list))}")
                else:
                    if not args.no_output:
                        print_success("🎉 すべてのバッチが完了したケロ🐸")

            else:
                # via != consoleの場合
                try: 
                    device_list, hostname_list = build_device_and_hostname(args, inventory_data)
                except ValueError as e:
                    if not args.no_output:
                        print_error(str(e))
                        print_warning("⛔ 中断ケロ🐸")
                    return

                max_workers = default_workers(len(device_list), args)

                result_failed_hostname_list = []

                # ✅ --ordered 用の本文バッファ（hostname -> str）
                ordered_output_buffers = {}  # {hostname: collected_output}
                lock = threading.Lock()

                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = []
                    future_to_hostname = {} 
                    ordered_output_enabled =  args.ordered and not args.quiet and not args.no_output

                    for device, hostname in zip(device_list, hostname_list):
                        # --orderedがあって--quietと--no_outputがないこと。
                        if ordered_output_enabled:
                            # 順番を並び替えるために貯める。Lockを渡す。
                            future = pool.submit(handle_execution, device, args, self.poutput, hostname,
                                                output_buffers=ordered_output_buffers, parser_kind=parser_kind, lock=lock)
                        else:
                            future = pool.submit(handle_execution, device, args, self.poutput, hostname,
                                                parser_kind=parser_kind, lock=lock)
                        
                        futures.append(future)
                        future_to_hostname[future] = hostname

                    for future in as_completed(futures):
                        hostname = future_to_hostname.get(future, "UNKNOWN")
                        try:
                            result_failed_hostname = future.result()
                            if result_failed_hostname:
                                result_failed_hostname_list.append(result_failed_hostname)
                        except Exception as e:
                            # handle_execution で捕まえていない想定外の例外
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
                
                return # via sshの処理を明示的に閉じる
        
        else:
            # consoleかつip,host,groupを使用しないパターン
            if via == "console":
                device , hostname = build_device_and_hostname(args, inventory_data, serial_port)
                result_failed_hostname = handle_execution(device, args, self.poutput, hostname, parser_kind=parser_kind)
                if result_failed_hostname and not args.no_output:
                    print_error(f"❎ 🐸なんかトラブルケロ@: {result_failed_hostname}")
                return