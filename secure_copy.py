import argparse
import cmd2
import sys
from netmiko import SCPConn
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from message import print_info, print_success, print_warning, print_error
from utils import sanitize_filename_for_log, load_sys_config, ensure_enable_mode
from executor import _build_device_and_hostname, _load_and_validate_inventory, _connect_to_device, _get_prompt, _save_log, _default_workers


######################
###  HELP_SECTION  ### 
######################
ip_help = "対象デバイスのIPアドレスを指定します。"
host_help = "inventory.yamlに定義されたホスト名を指定します。"
group_help = "inventory.yamlに定義されたグループ名を指定します。グループ内の全ホストにコマンドを実行します。"

put_help = "1つのコマンドを直接指定して実行します。"
get_help = "コマンドリスト名（commands-lists.yamlに定義）を指定して実行します。" \
                    "device_typeはホストから自動で選択されます。"

username_help = "SSH接続に使用するユーザー名を指定します。--ip専用。--host|--group指定時はinventory.yamlの値を使用します。"
password_help = "SSH接続に使用するパスワードを指定します。--ip専用。--host|--group指定時はinventory.yamlの値を使用します。"
device_type_help = "Netmikoにおけるデバイスタイプを指定します（例: cisco_ios）。省略時は 'cisco_ios' です。"
port_help = "SSH接続に使用するポート番号を指定します（デフォルト: 22）"
timeout_help = "SSH接続のタイムアウト秒数を指定します（デフォルト: 10秒）"
log_help = ("実行結果をログファイルとして保存します。\n"
           "保存先: logs/execute/\n"
           "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]\n"
           "example: 20250504-235734_R0_show-ip-int-brief.log")
memo_help = ("ログファイル名に付加する任意のメモ（文字列）を指定します。\n"
             "保存先: logs/execute/\n"
             "保存名: yearmmdd-hhmmss_[hostname]_[commands_or_commands_list]_[memo]\n"
             "example 20250506-125600_R0_show-ip-int-brief_memo.log")
workers_help = ("並列実行するワーカースレッド数を指定します。\n"
                "指定しない場合は sys_config.yaml の executor.default_workers を参照します。\n"
                "そこにも設定が無いときは、グループ台数と 規定上限(DEFAULT_MAX_WORKERS) の小さい方が自動で採用されます。")
secret_help = ("enable に入るための secret を指定します。(省略時は password を流用します。)\n"
               "--ip専用。--host|--group指定時はinventory.yamlの値を使用します。")

src_help = ("転送元のパスを指定します。")
dest_help = ("転送先のパスを指定します。")

######################
### PARSER_SECTION ###
######################
netmiko_scp_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
# "-h" はhelpと競合するから使えない。
netmiko_scp_parser.add_argument("-u", "--username", type=str, default="", help=username_help)
netmiko_scp_parser.add_argument("-p", "--password", type=str, default="", help=password_help)
netmiko_scp_parser.add_argument("-d", "--device_type", type=str, default="cisco_ios", help=device_type_help)
netmiko_scp_parser.add_argument("-P", "--port", type=int, default=22, help=port_help)
netmiko_scp_parser.add_argument("-t", "--timeout", type=int, default=10, help=timeout_help)
netmiko_scp_parser.add_argument("-l", "--log", action="store_true", help=log_help)
netmiko_scp_parser.add_argument("-m", "--memo", type=str, default="", help=memo_help)
netmiko_scp_parser.add_argument("-w", "--workers", type=int, default=None, metavar="N", help=workers_help)
netmiko_scp_parser.add_argument("-s", "--secret", type=str, default="", help=secret_help)

netmiko_scp_parser.add_argument("--src", type=str, required=True, help=src_help)
netmiko_scp_parser.add_argument("--dest", type=str, required=True, help=dest_help)

# mutually exclusive
target_node = netmiko_scp_parser.add_mutually_exclusive_group(required=True)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None, help=ip_help)
target_node.add_argument("--host", type=str, nargs="?", default=None, help=host_help)
target_node.add_argument("--group", type=str, nargs="?", default=None, help=group_help)

target_command = netmiko_scp_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("--put", action="store_true", help=put_help)
target_command.add_argument("--get", action="store_true", help=get_help)


def progress(filename, size, sent):
    if isinstance(filename, bytes):
        filename = filename.decode()
    pct = sent / size * 100 if size else 100
    print(f"\r📤 {Path(filename).name}: {pct:6.2f}% ({sent}/{size} B)",
          end="", file=sys.stderr, flush=True)
    if sent >= size:
        print(file=sys.stderr, flush=True)   # 完了時に改行


def _handle_scp(device, args, poutput, hostname):
    # ファイルの存在を確認
    if args.put:
        src_path = Path(args.src)
        if not src_path.is_file():
            print_error(f"ローカルファイルが存在しないケロ🐸💥: {args.src}")
            return
    elif args.get:
        dest_path = Path(args.dest)
        if not dest_path.parent.exists():
            print_error(f"ダウンロード先が存在しないケロ🐸💥: {dest_path.parent}")
            return

    # ① SSH接続を確立
    # ✅ 2. 接続とプロンプト取得
    try:
        connection = _connect_to_device(device, hostname)
        print_success(f"NODE: {hostname} 🔗接続成功ケロ🐸")
        prompt, hostname = _get_prompt(connection)
    except ConnectionError as e:
        print_error(str(e))
        return

    # ② SCPConnをラップ
    scp = SCPConn(connection, progress=progress)

    # ③ 転送！
    if args.put:
        scp.scp_put_file(args.src, args.dest)   # put（アップロード）
        result_output_string = f"PUT {args.src} >>>>>>> {args.dest}"

    elif args.get:
        scp.scp_get_file(args.src, args.dest) # get（ダウンロード）
        result_output_string = f"GET {args.dest} <<<<<<< {args.src}"


    # ④ 忘れずにクローズ！
    scp.close()
    # ✅ 4. 接続終了
    connection.disconnect()

    # ✅ 5. ログ保存（--log指定時のみ）
    if args.log:
        _save_log(result_output_string, hostname, args, mode="scp")

    # ✅ 6. 結果表示
    print_info(f"NODE: {hostname} 📄OUTPUTケロ🐸")
    poutput(result_output_string)
    print_success(f"NODE: {hostname} 🔚実行完了ケロ🐸")
    return



@cmd2.with_argparser(netmiko_scp_parser)
def do_scp(self, args):
    """
    `execute` サブコマンドのエントリポイント。

    ルーティング
    ------------
    1. `--ip` 指定 → 単一デバイス  
    2. `--host`    → inventory から 1 台  
    3. `--group`   → inventory グループ内の複数台（※並列化は今後）

    Notes
    -----
    - 実処理は `_handle_execution()` に委譲。
    - `cmd2` では ``self.poutput`` が標準出力をラップしているため、
      すべての内部関数にこれを渡してカラー表示や装飾を統一している。
    """

    if args.ip:
        device, hostname = _build_device_and_hostname(args)
        _handle_scp(device, args, self.poutput, hostname)
        return

    if args.host or args.group: 
        try:
            inventory_data = _load_and_validate_inventory(host=args.host, group=args.group)
        
        except (FileNotFoundError, ValueError) as e:
            print_error(str(e))
            return
        
    
    if args.host:
        device, hostname = _build_device_and_hostname(args, inventory_data)
        _handle_scp(device, args, self.poutput, hostname)
        return

    elif args.group:
        device_list, hostname_list = _build_device_and_hostname(args, inventory_data)

        max_workers = _default_workers(len(device_list), args)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:

            futures = []
            for device, hostname in zip(device_list, hostname_list):
                future = pool.submit(_handle_scp, device, args, self.poutput, hostname)
                futures.append(future)

            for future in as_completed(futures):
                future.result()
