import argparse
import cmd2
from ruamel.yaml import YAML

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.tree import Tree
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

import difflib

import shutil
import subprocess

import webbrowser
import time

from message import print_info, print_success, print_warning, print_error
from utils import get_table_theme, get_panel_theme
from completers import host_names_completer, group_names_completer, commands_list_names_completer, config_list_names_completer, log_filename_completer
from load_and_validate_yaml import COMMANDS_LISTS_FILE, CONFIG_LISTS_FILE


#######################
###  CONST_SECTION  ### 
#######################
MODE = ["execute", "console", "configure", "scp"]
# choice ["fold", "ellipsis", "crop"] fold: 改行して全文を表示, ellipsis: "..."で切って1行に収める。, crop: はみ出た部分をバッサリ切る。
TABLE_OVERFLOW_MODE = "fold"


######################
###  HELP_SECTION  ### 
######################
hosts_help = "すべてのホストの一覧を表示します。"
host_help = "指定したホスト（hostname）の詳細情報を表示します。"

groups_help = "すべてのグループの一覧を表示します。"
group_help = "指定したグループのメンバー情報と詳細を表示します。"

commands_lists_help = "すべてのコマンドリストの一覧を表示します。"
commands_list_help = (
    "コマンドリストの内容を表示します。\n"
    "引数 COMMAND_LIST を指定してください。\n"
    "例: show --commands-list cisco_precheck\n"
)

config_lists_help = "すべてのコンフィグリストの一覧を表示します。"
config_list_help = (
    "コンフィグリストの内容を表示します。\n"
    "example: show --config-list cisco-R1-loopback100-setup"
)

logs_help = "保存されているすべてのログファイルの一覧を表示します。"
log_help = "--logで表示するログファイルを指定します。(例: 20250508/filename.log)"
log_last_help = "最新のログファイルの内容を表示します。"

mode_help = "show --log(s)で指定するモードです。execute以外のディレクトリを指定する際に使用します。"
date_help = "show --logs で指定する日付です。YYYY-MM-DDで記載します。"

diff_help= "--diff で比較する2つのログファイルを指定するケロ🐸"
style_help = "差分表示のスタイルを選べるケロ🐸\n" \
                  "unified（標準）, side-by-side, html から選べるケロ"
keep_html_help = "HTMLファイルを削除せずに残すケロ🐸"


######################
### PARSER_SECTION ###
######################
show_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
# "-h" はhelpと競合するから使えない。

show_parser.add_argument("-m", "--mode", type=str, default="execute", choices=["execute", "console", "configure","scp"], help=mode_help)
show_parser.add_argument("-d", "--date", type=str, default="", help=date_help)
show_parser.add_argument("--style", type=str, default="unified", choices=["unified", "side-by-side", "html"], help=style_help)
show_parser.add_argument("--keep-html", action="store_true", help=keep_html_help)


# mutually exclusive
target_show = show_parser.add_mutually_exclusive_group(required=True)
target_show.add_argument("--hosts", action="store_true", help=hosts_help)
target_show.add_argument("--host", type=str, default="", help=host_help, completer=host_names_completer)
target_show.add_argument("--groups", action="store_true", help=groups_help)
target_show.add_argument("--group", type=str, default="", help=group_help, completer=group_names_completer)
target_show.add_argument("--commands-lists", action="store_true", help=commands_lists_help)
target_show.add_argument("--commands-list", type=str, default="", help=commands_list_help, completer=commands_list_names_completer)
target_show.add_argument("--logs", action="store_true", help=logs_help)
target_show.add_argument("--log", type=str, default="", help=log_help, completer=log_filename_completer)
target_show.add_argument("--log-last", action="store_true", help=log_last_help)
target_show.add_argument("--diff", nargs=2, metavar=("OLD_LOG", "NEW_LOG"), help=diff_help, completer=log_filename_completer)
target_show.add_argument("--config-lists", action="store_true", help=config_lists_help)
target_show.add_argument("--config-list", type=str, default="", help=config_list_help, completer=config_list_names_completer)


yaml = YAML()
console = Console()


def _show_hosts():

    with open("inventory.yaml", "r") as host_list:
        host_list_data = yaml.load(host_list) 
        node_list = host_list_data["all"]["hosts"]
    
    table_theme = get_table_theme()

    table = Table(title="🐸 SHOW_HOSTS 🐸", **table_theme)

    header = ["HOSTNAME", "IP", "TYPE", "DESCRIPTION", "TAGS"]

    for _ in header:
        table.add_column(_)
    
    for node in node_list:
        table_output = [
            f'{node_list[node]["hostname"]}', 
            f'{node_list[node]["ip"]}',
            f'{node_list[node]["device_type"]}',
            f'{node_list[node]["description"]}',
            f'{", ".join(node_list[node]["tags"])}'
        ]
        table.add_row(*table_output)
    
    console.print(table)
    

def _show_host(node):
    
    with open("inventory.yaml", "r") as host_list:
        host_list_data = yaml.load(host_list) 
        node_list = host_list_data["all"]["hosts"]

    if node not in node_list:
        raise ValueError(f"'{node}' は inventory.yaml に居ないケロ🐸")

    table_theme = get_table_theme()
    table = Table(title="🐸 SHOW_HOST 🐸", **table_theme)

    header = ["Hostname", "IP Address", "Device Type", "Description", "Username", "Password", "Tags", "Port", "Timeout", "TTL"]
    for _ in header:
        table.add_column(_)

    table_output = (
        f'{node_list[node]["hostname"]}',
        f'{node_list[node]["ip"]}',
        f'{node_list[node]["device_type"]}',
        f'{node_list[node]["description"]}',
        f'{node_list[node]["username"]}',
        f'{node_list[node]["password"]}',
        f'{", ".join(node_list[node]["tags"])}',
        f'{node_list[node]["port"]}',
        f'{node_list[node]["timeout"]}',
        f'{node_list[node]["ttl"]}'
        )
    table.add_row(*table_output)

    console.print(table)


def _show_groups():
    
    with open("inventory.yaml", "r") as inventory:
        inventory_data = yaml.load(inventory) 
        groups_list = inventory_data["all"]["groups"]
    
    table_theme = get_table_theme()
    table = Table(title="🐸 SHOW_GROUPS 🐸", **table_theme)

    header = ["GROUP", "DESCRIPTION", "TAGS"]
    for _ in header:
        table.add_column(_)

    for group in groups_list:
        group_desc = groups_list[group]["description"]
        group_tags = ", ".join(groups_list[group]["tags"])
        table.add_row(group, group_desc, group_tags)
    
    console.print(table)


def _show_group(group):

    with open("inventory.yaml", "r") as inventory:
        inventory_data = yaml.load(inventory) 
        groups_list = inventory_data["all"]["groups"]

    if group not in groups_list:
        raise ValueError(f"'{group}' は inventory.yaml に居ないケロ🐸")

    table_theme = get_table_theme()
    panel_theme = get_panel_theme()

    panel_body = Text()
    panel_body.append(f'Group: {group}\n')
    panel_body.append(f'Description: {groups_list[group]["description"]}\n')
    panel_body.append(f'Tags: {", ".join(groups_list[group]["tags"])}\n')
    panel_body.append(f'Members: {len(groups_list[group]["hosts"])} host(s)')

    panel = Panel(panel_body, title="🐸 GROUP INFO 🐸", **panel_theme)

    table = Table(title="🐸 SHOW_GROUP 🐸", **table_theme)
    header = ["Hostname", "Ip", "Type", "Description", "Tags"]
    for _ in header:
        table.add_column(_)

    group_hosts = groups_list[group]["hosts"]

    for host in group_hosts:
        host_info = inventory_data["all"]["hosts"][host]

        table_output = (
            f'{host_info["hostname"]}',
            f'{host_info["ip"]}',
            f'{host_info["device_type"]}',
            f'{host_info["description"]}',
            f'{", ".join(host_info["tags"])}'
            )
        table.add_row(*table_output)
    
    console.print(panel)
    console.print(table)


def _show_commands_lists():
    if not Path(COMMANDS_LISTS_FILE).exists():
        raise FileNotFoundError(f"'{COMMANDS_LISTS_FILE}' が無いケロ🐸")

    with open(COMMANDS_LISTS_FILE, "r", encoding="utf-8") as yaml_commands_lists:
        commands_lists_data = yaml.load(yaml_commands_lists)

    table_theme = get_table_theme()
    
    table = Table(title="🐸 SHOW_COMMANDS_LISTS 🐸", **table_theme)

    header = ["DEVICE_TYPE", "NAME", "DESCRIPTION", "TAGS"]

    for h in header:
        table.add_column(h, overflow=TABLE_OVERFLOW_MODE) # 折り返して行全体を表示
        # table.add_column(h) # 省略表示

    commands_lists = commands_lists_data.get("commands_lists", {})
    if not isinstance(commands_lists, dict):
        console = Console()
        raise ValueError(f"commands-listsの形式が不正ケロ")

    for commands_list_name, commands_list_entry in commands_lists.items():
        device_type  = commands_list_entry.get("device_type", "")
        description  = commands_list_entry.get("description", "")
        tags_list  = commands_list_entry.get("tags", [])
        tags = ", ".join(map(str, tags_list)) if isinstance(tags_list, list) else str(tags_list)

        table_output =[
            f"{device_type}",
            f"{commands_list_name}",
            f'{description}',
            f'{tags}'
            ]
        table.add_row(*table_output)

    console.print(table)


def _show_commands_list(commands_list_name: str):
    # commands_list_name: 引数（キー文字列）
    # commands_lists_entry: 1エントリ(dict)
    # commands_list: 実際のコマンド配列(list[str])
    if not Path(COMMANDS_LISTS_FILE).exists():
        raise FileNotFoundError(f"'{COMMANDS_LISTS_FILE}' が無いケロ🐸")

    with open(COMMANDS_LISTS_FILE, "r", encoding="utf-8") as yaml_commands_lists:
        commands_lists_data = yaml.load(yaml_commands_lists)

    commands_lists_root = commands_lists_data.get("commands_lists", {})

    # 形式チェック
    if not isinstance(commands_lists_root, dict):
        raise ValueError(f"'{COMMANDS_LISTS_FILE}' の形式が不正ケロ🐸")
    
    commands_lists_entry = commands_lists_root.get(f"{commands_list_name}")

    if not isinstance(commands_lists_entry, dict):
        raise ValueError(f"'{commands_list_name}' は '{COMMANDS_LISTS_FILE}' に存在しないケロ🐸")
    
    commands_list = commands_lists_entry.get("commands_list", [])

    if not commands_list:
        raise ValueError(f"'{commands_list_name}' の 'commands-list' が空ケロ🐸")

    # エントリ取得
    description = commands_lists_entry.get("description", "")
    device_type = commands_lists_entry.get("device_type", "")
    lines_text = f'{len(commands_list)} line(s)'
    tags_list = commands_lists_entry.get("tags", [])
    tags = ", ".join(map(str, tags_list)) if isinstance(tags_list, list) else str(tags_list)

    table_output = [commands_list_name, description, device_type, lines_text, tags]

    # ヘッダー情報テーブル
    table_theme = get_table_theme()
    table = Table(title="🐸 SHOW_COMMANDS_LIST 🐸", **table_theme)

    header = ["COMMAND_LIST", "DESCRIPTION", "DEVICE_TYPE", "LINES", "TAGS"]

    for h in header:
        table.add_column(h, overflow=TABLE_OVERFLOW_MODE)

    table.add_row(*table_output)

    # コマンド本体(番号つき)
    panel_body = Text()
    numbered_lines = [f"{i}. {line}" for i, line in enumerate(commands_list, start=1)] 
    panel_body.append("\n".join(numbered_lines))
    panel_theme = get_panel_theme()
    panel = Panel(panel_body, title="🐸 COMMANDS 🐸", **panel_theme)

    console.print(table)
    console.print("\n")
    console.print(panel)


def _show_config_lists():

    if not Path(CONFIG_LISTS_FILE).exists():
        raise FileNotFoundError(f"'{CONFIG_LISTS_FILE}' が無いケロ🐸")

    with open(CONFIG_LISTS_FILE, "r", encoding="utf-8") as yaml_config_lists:
        config_lists_data = yaml.load(yaml_config_lists)

    table_theme = get_table_theme()
    table = Table(title="🐸 SHOW_CONFIG_LISTS 🐸", **table_theme)

    header = ["DEVICE_TYPE", "NAME", "DESCRIPTION", "TAGS"]
    for h in header:
        table.add_column(h, overflow=TABLE_OVERFLOW_MODE)

    config_lists = config_lists_data.get("config_lists", {})
    if not isinstance(config_lists, dict):
        raise ValueError(f"'{CONFIG_LISTS_FILE}' の形式が不正ケロ")

    for config_list_name, config_list_entry in config_lists.items():
        device_type = config_list_entry.get("device_type", "")
        description = config_list_entry.get("description", "")
        tags_list = config_list_entry.get("tags", [])
        tags = ", ".join(map(str, tags_list)) if isinstance(tags_list, list) else str(tags_list)

        table_output = [
            f"{device_type}",
            f"{config_list_name}",
            f"{description}",
            f'{tags}'
                ]
        table.add_row(*table_output)

    console.print(table)


def _show_config_list(config_list_name :str):

    if not Path(CONFIG_LISTS_FILE).exists():
        raise FileNotFoundError(f"'{CONFIG_LISTS_FILE}' が無いケロ🐸")

    with open(CONFIG_LISTS_FILE, "r", encoding="utf-8") as yaml_config_lists:
        config_lists_data = yaml.load(yaml_config_lists)

    # 形式チェック 
    config_lists_root = config_lists_data.get("config_lists", {})

    if not isinstance(config_lists_root, dict):
        raise ValueError(f"'{CONFIG_LISTS_FILE}' の形式が不正ケロ🐸")
    
    config_lists_entry = config_lists_root.get(config_list_name)
    if not isinstance(config_lists_entry, dict):
        raise ValueError(f"'{config_list_name}' は '{CONFIG_LISTS_FILE}' に存在しないケロ🐸")

    config_list = config_lists_entry.get("config_list", [])

    if not config_list:
        raise ValueError(f"'{config_list_name}' の 'config-list' が空ケロ🐸")

    # エントリ取得
    description = config_lists_entry.get("description", "")
    device_type = config_lists_entry.get("device_type", "")
    lines_text = f'{len(config_list)} line(s)'
    tags_list = config_lists_entry.get("tags", [])
    tags = ", ".join(map(str, tags_list)) if isinstance(tags_list, list) else str(tags_list)

    table_output = [config_list_name, description, device_type, lines_text, tags]

    # ヘッダー情報テーブル
    table_theme = get_table_theme()
    table = Table(title="🐸 SHOW_CONFIG_LIST 🐸", **table_theme)

    header = ["CONFIG LIST", "DESCRIPTION", "DEVICE_TYPE", "LINES", "TAGS"]
    for h in header:
        table.add_column(h, overflow=TABLE_OVERFLOW_MODE)

    table.add_row(*table_output)

    # config-list の中身
    panel_body = Text()
    numbered_lines = [f"{i}. {line}" for i, line in enumerate(config_list, start=1)] 
    panel_body.append("\n".join(numbered_lines))
    panel_theme = get_panel_theme()
    panel = Panel(panel_body, title="🐸 CONFIGS 🐸", **panel_theme)

    console.print(table)
    console.print("\n")
    console.print(panel)


def _show_logs(args):

    today_str = datetime.now().strftime("%Y%m%d")

    if args.mode in ("execute", "console", "configure", "scp"):
        log_mode_dir = Path("logs") / args.mode
    else: # 将来的に別のモードが必要になったときに実装予定。
        raise NotImplementedError(f"モード '{args.mode}' はまだ未対応ケロ🐸")

    today_dir = log_mode_dir / today_str

# 2週間以上前のログはログは表示しない機能。
# 先月のログは一つにまとめる機能。do_archiveとか？
# KeroRoute全体の設定ファイルが必要かも。ログの表示件数とか。

    if args.logs:
        if args.mode in ("execute", "console", "configure", "scp"):
            if args.date:
                date_str = args.date
                date_dir = log_mode_dir / date_str
                log_dir_list = list(log_mode_dir.glob("*"))
                is_exists_directory = False
                # 特定の日付だけログを表示
                for dir in log_dir_list:
                    if dir.name == date_str:
                        is_exists_directory = True
                        # 一致するならTree表示。
                        num_logs = len(list(date_dir.glob("*.log")))
                        date_tree = Tree(str(date_dir))
                        for log_file in sorted(date_dir.glob("*.log")):
                            date_tree.add(log_file.name)
                        console.print(f"📂 {date_dir}/ :{num_logs}件のログファイルがあるケロ🐸\n")
                        console.print(date_tree)
                        console.print("\n")
                        return

                if not is_exists_directory:
                    console.print(f"📂 {args.date} に対応するログディレクトリは存在しないケロ🐸")

            else:
                # 今日のログをTree表示。その他の日はフアイル数でTree or Summary
                num_logs_today = len(list(today_dir.glob("*.log")))
                today_tree = Tree(str(today_dir))
                for log_file in sorted(today_dir.glob("*.log")):
                    today_tree.add(log_file.name)
                console.print(f"📂 {today_dir}/ :{num_logs_today}件のログファイルがあるケロ🐸\n")
                console.print(today_tree)            
                console.print("\n")            

                # 他の日付はファイル数でTree表示。
                for date_dir in sorted(log_mode_dir.glob("*")):
                    if date_dir == today_dir:
                        continue
                    
                    num_logs = len(list(date_dir.glob("*.log")))
                    if num_logs == 0:
                        console.print(f"📂 {date_dir.name}/ : ログファイルは存在しないケロ🐸\n")
                    elif num_logs <= 5: # magic_number
                        tree = Tree(f"{log_mode_dir}/{date_dir.name}")
                        for log_file in sorted(date_dir.glob("*.log")):
                            tree.add(log_file.name)
                        console.print(f"📂 {log_mode_dir}/{date_dir.name}/ :{num_logs}件のログファイルがあるケロ🐸\n")
                        console.print(tree)
                        console.print("\n")
                    else:
                        console.print(f"📂 {log_mode_dir}/{date_dir.name}/ :{num_logs}件のログファイルがあるケロ🐸\n")
                        console.print("ファイル数が多いから省略するケロ🐸\n")


def _show_log(args):
    if args.log:
        if args.mode in ("execute", "console", "configure", "scp"):
            mode_dir = Path("logs") / args.mode  # e.g., logs/execute/
            target_dir = args.log[:8] # logファイルの最初の8文字を取得。
            log_path = mode_dir / target_dir / args.log       # e.g., logs/execute/20250508/filename.log

            if not log_path.exists():
                print_error(f"{log_path} が存在しないケロ🐸")
                return

            with open(log_path, "r") as f:
                content = f.read()
           
            # Linuxのコマンドでlessを使用している  
            try:
                subprocess.run(["less", "-R"], input=content.encode(), check=True)
            except Exception as e:
                print_error(f"less での表示に失敗したケロ🐸 {e}")

        else:
            print_error(f"未対応のモードケロ🐸: {args.mode}")


def _show_diff(args):

    style = args.style

    if args.mode not in ("execute", "console", "configure", "scp"):
        print_error(f"未対応のモードケロ🐸: {args.mode}")
        return

    mode_dir = Path("logs") /args.mode
    log1_path = mode_dir / args.diff[0][:8] / args.diff[0]
    log2_path = mode_dir / args.diff[1][:8] / args.diff[1]
    
    if not log1_path.exists():
        print_error(f"{log1_path} が存在しないケロ🐸")
        return
    if not log2_path.exists():
        print_error(f"{log2_path} が存在しないケロ🐸")
        return

    with open(log1_path, "r") as log_1, open(log2_path, "r") as log_2:
        text_1= log_1.readlines()
        text_2= log_2.readlines()


    if args.mode in ("execute", "console", "configure", "scp"):
        if style == "unified":
            diff_lines = list(difflib.unified_diff(text_1, text_2,
                                                fromfile=args.diff[0],
                                                tofile=args.diff[1],
                                                lineterm=""))
            if diff_lines:
                console.print("\n".join(diff_lines))
            else:
                console.print("🎉 差分は見つからなかったケロ🐸")

        elif style == "html":
            # HTML差分ファイルを生成して保存
            tmp_dir = Path("tmp")
            tmp_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

            html_diff = difflib.HtmlDiff().make_file(text_1, text_2, fromdesc=args.diff[0], todesc=args.diff[1])
            html_path = tmp_dir / f"diff_result_{timestamp}.html"

            with open(html_path, "w") as f:
                f.write(html_diff)

            try:
                webbrowser.get("firefox").open(f"file://{html_path.resolve()}")
                print_success(f"🦊 HTML差分ファイルをFirefoxで開いたケロ！: {html_path}")
            except webbrowser.Error:
                print_warning("🚨 Firefoxが見つからなかったケロ！手動で開いてケロ🐸")            
        
            if not args.keep_html:
                # 数秒待ってから削除（確実にブラウザが開いたあと）
                time.sleep(3)
                html_path.unlink()
                print_info("🧹 一時HTMLファイルは削除したケロ🐸")
            else:
                print_info(f"💾 一時HTMLファイルを保持したケロ🐸: {html_path}")


        elif style == "side-by-side":
            diff_command = "colordiff" if shutil.which("colordiff") else "diff"
            subprocess.run([diff_command, "-y", str(log1_path), str(log2_path)])

    else:
        print_error(f"未対応のモードケロ🐸: {args.mode}")


def _find_latest_log_path(mode: str) -> Path | None:

    mode_dir = Path("logs") / mode
    candidates_dirs = sorted(mode_dir.glob("*")) # 日付dirを取得してソート
    if not candidates_dirs:
        return None
    
    latest_date_dir = candidates_dirs[-1] # ソート済みのリストの最後の要素が最新
    
    # 最新の日付ディレクトリ内のログファイルを取得
    log_files = sorted(latest_date_dir.glob("*.log")) # ここもソート
    
    if not log_files:
        return None
        
    return log_files[-1] # 最新のログファイルを返す


def _show_log_last(args):
    """--log-last, 最新のログ1件を less -R で表示する。"""
    # :NOTE windows対応のときに影響あり。
    mode = "execute"
    if args.mode:
        mode = args.mode
    if mode not in MODE:
        print_error(f"未対応のモードケロ🐸: {mode}")
        return
    
    latest_log = _find_latest_log_path(mode)

    if latest_log is None:
        print_info("📭 表示できるログが見つからないケロ🐸")
        return
    
    print_info(f"🕒 最新ログを表示するケロ🐸 → {latest_log}")
    try:
        content = latest_log.read_text()
        subprocess.run(["less", "-R"], input=content.encode(), check=True)
    except Exception as e:
        print_error(f"lessの表示に失敗したケロ🐸: {e}")



@cmd2.with_argparser(show_parser)
def do_show(self, args):
    if args.diff:
        _show_diff(args)
    elif args.hosts:
        _show_hosts()
    elif args.host:
        _show_host(args.host)
    elif args.groups:
        _show_groups()
    elif args.group:
        _show_group(args.group)
    elif args.commands_lists:
        _show_commands_lists()
    elif args.commands_list:
        _show_commands_list(args.commands_list)
    elif args.config_lists:
        _show_config_lists()
    elif args.config_list:
        _show_config_list(args.config_list)
    elif args.log_last:
        _show_log_last(args)
    elif args.logs:
        _show_logs(args)
    elif args.log:
        _show_log(args)
