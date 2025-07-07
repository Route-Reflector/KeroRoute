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
    "2つの引数（DEVICE_TYPE と COMMAND_LIST）を指定してください。\n"
    "例: show --commands-list cisco_ios jizen_command\n"
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

show_parser.add_argument("-m", "--mode", type=str, default="execute", help=mode_help)
show_parser.add_argument("-d", "--date", type=str, default="", help=date_help)
show_parser.add_argument("--style", type=str, default="unified", choices=["unified", "side-by-side", "html"], help=style_help)
show_parser.add_argument("--keep-html", action="store_true", help=keep_html_help)


# mutually exclusive
target_show = show_parser.add_mutually_exclusive_group(required=True)
target_show.add_argument("--hosts", action="store_true", help=hosts_help)
target_show.add_argument("--host", type=str, default="", help=host_help)
target_show.add_argument("--groups", action="store_true", help=groups_help)
target_show.add_argument("--group", type=str, default="", help=group_help)
target_show.add_argument("--commands-lists", action="store_true", help=commands_lists_help)
target_show.add_argument("--commands-list", nargs=2, metavar=("DEVICE_TYPE", "COMMAND_LIST"), help=commands_list_help)
target_show.add_argument("--logs", action="store_true", help=logs_help)
target_show.add_argument("--log", type=str, default="execute", help=log_help)
target_show.add_argument("--log-last", action="store_true", help=log_last_help)
target_show.add_argument("--diff", nargs=2, metavar=("OLD_LOG", "NEW_LOG"), help=diff_help)


def _show_hosts(poutput):

    yaml = YAML()

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
    
    console = Console()
    console.print(table)
    

def _show_host(poutput, node):
    
    yaml = YAML()
    with open("inventory.yaml", "r") as host_list:
        host_list_data = yaml.load(host_list) 
        node_list = host_list_data["all"]["hosts"]


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

        console = Console()
        console.print(table)


def _show_groups(poutput):
    
    yaml = YAML()
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
    
    console = Console()
    console.print(table)


def _show_group(poutput, group):

    yaml = YAML()
    with open("inventory.yaml", "r") as inventory:
        inventory_data = yaml.load(inventory) 
        groups_list = inventory_data["all"]["groups"]

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
        
        console = Console()
        console.print(panel)
        console.print(table)


def _show_commands_lists(poutput):
    yaml = YAML()
    with open("commands-lists.yaml", "r") as yaml_commands_lists:
        commands_lists = yaml.load(yaml_commands_lists)

    table_theme = get_table_theme()
    
    table = Table(title="🐸 SHOW_COMMANDS_LISTS 🐸", **table_theme)

    header = ["DEVICE_TYPE", "NAME", "DESCRIPTION", "TAGS"]

    for _ in header:
        table.add_column(_)

    command_lists_info = commands_lists["commands_lists"]

    for device_type in command_lists_info:
        for command_list in command_lists_info[device_type]:
            command_list_info = command_lists_info[device_type][command_list]

            table_output =[
                f"{device_type}",
                f"{command_list}",
                f'{command_list_info["description"]}',
                f'{", ".join(command_list_info["tags"])}'
                ]
            table.add_row(*table_output)

    console = Console() 
    console.print(table)


def _show_commands_list(poutput, device_type, commands_list):
    yaml = YAML()
    with open("commands-lists.yaml", "r") as yaml_commands_lists:
        commands_lists = yaml.load(yaml_commands_lists)
        command_list_info = commands_lists["commands_lists"][device_type][commands_list]

    table_theme = get_table_theme()
    table = Table(title="🐸 SHOW_COMMANDS_LIST 🐸", **table_theme)
    header = ["COMMAND LIST", "DESCRIPTION", "DEVICE_TYPE", "LINES", "TAGS"]
    row_data = [f"{commands_list}", f'{command_list_info["description"]}', f"{device_type}",  f'{len(command_list_info["commands_list"])} line(s)', f'{", ".join(command_list_info["tags"])}']

    for _ in header:
        table.add_column(_)

    table.add_row(*row_data)

    panel_body = Text()
    lines = [f"{i}. {line}" for i, line in enumerate(command_list_info["commands_list"], start=1)] 
    panel_body.append("\n".join(lines))
    panel_theme = get_panel_theme()
    panel = Panel(panel_body, title="🐸 COMMANDS 🐸", **panel_theme)

    console = Console()
    console.print(table)
    console.print("\n")
    console.print(panel)



def _show_logs(poutput, args):

    console = Console()
    today_str = datetime.now().strftime("%Y%m%d")

    if args.mode == "execute":
        log_mode_dir = Path("logs") / args.mode
    else: # 将来的に別のモードが必要になったときに実装予定。
        raise NotImplementedError(f"モード '{args.mode}' はまだ未対応ケロ🐸")

    today_dir = log_mode_dir / today_str

# 2週間以上前のログはログは表示しない機能。
# 先月のログは一つにまとめる機能。do_archiveとか？
# KeroRoute全体の設定ファイルが必要かも。ログの表示件数とか。

    if args.logs:
        if args.mode == "execute":
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


def _show_log(poutput, args):
    if args.log:
        if args.mode == "execute":
            mode_dir = Path("logs") / args.mode  # e.g., logs/execute/
            target_dir = args.log[:8] # logファイルの最初の8文字を取得。
            log_path = mode_dir / target_dir / args.log       # e.g., logs/execute/20250508/filename.log

            if not log_path.exists():
                print_error(poutput, f"{log_path} が存在しないケロ🐸")
                return

            with open(log_path, "r") as f:
                content = f.read()
                # console = Console(force_terminal=True)
                # console.pager(content) # richのpagerがうまく機能しない。
            
            try:
                subprocess.run(["less", "-R"], input=content.encode(), check=True)
            except Exception as e:
                print_error(poutput, "less での表示に失敗したケロ🐸")
                print_error(poutput, str(e))

        else:
            print_error(poutput, f"未対応のモードケロ🐸: {args.mode}")
            # 将来的に実装


def _show_diff(poutput, args):

    style = args.style

    mode_dir = Path("logs") /args.mode
    log1_path = mode_dir / args.diff[0][:8] / args.diff[0]
    log2_path = mode_dir / args.diff[1][:8] / args.diff[1]
    
    if not log1_path.exists():
        print_error(poutput, f"{log1_path} が存在しないケロ🐸")
        return
    if not log2_path.exists():
        print_error(poutput, f"{log2_path} が存在しないケロ🐸")
        return

    with open(log1_path, "r") as log_1, open(log2_path, "r") as log_2:
        text_1= log_1.readlines()
        text_2= log_2.readlines()



    if args.mode == "execute":
        if style == "unified":
            diff_lines = difflib.unified_diff(text_1, text_2,
                                                fromfile=args.diff[0],
                                                tofile=args.diff[1],
                                                lineterm="")
            console = Console()
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
                print_success(poutput, f"🦊 HTML差分ファイルをFirefoxで開いたケロ！: {html_path}")
            except webbrowser.Error:
                print_warning(poutput, "🚨 Firefoxが見つからなかったケロ！手動で開いてケロ🐸")            
        
            if not args.keep_html:
                # 数秒待ってから削除（確実にブラウザが開いたあと）
                time.sleep(3)
                html_path.unlink()
                print_info(poutput, "🧹 一時HTMLファイルは削除したケロ🐸")
            else:
                print_info(poutput, f"💾 一時HTMLファイルを保持したケロ🐸: {html_path}")


        elif style == "side-by-side":
            diff_command = "colordiff" if shutil.which("colordiff") else "diff"
            subprocess.run([diff_command, "-y", str(log1_path), str(log2_path)])

    else:
        print_error(poutput, f"未対応のモードケロ🐸: {args.mode}")



@cmd2.with_argparser(show_parser)
def do_show(self, args):
    if args.diff:
        _show_diff(self.poutput, args)
    elif args.hosts:
        _show_hosts(self.poutput)
    elif args.host:
        _show_host(self.poutput, args.host)
    elif args.groups:
        _show_groups(self.poutput)
    elif args.group:
        _show_group(self.poutput, args.group)
    elif args.commands_lists:
        _show_commands_lists(self.poutput)
    elif args.commands_list:
        device_type, commands_list = args.commands_list
        _show_commands_list(self.poutput, device_type, commands_list)
    elif args.logs:
        _show_logs(self.poutput, args)
    elif args.log:
        _show_log(self.poutput, args)


