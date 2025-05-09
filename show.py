import argparse
import cmd2
from ruamel.yaml import YAML

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.tree import Tree
from rich.table import Table

import subprocess

from message import print_info, print_success, print_warning, print_error, ask


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


######################
### PARSER_SECTION ###
######################
show_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
# "-h" はhelpと競合するから使えない。

show_parser.add_argument("-m", "--mode", type=str, default="execute", help=mode_help)
show_parser.add_argument("-d", "--date", type=str, default="", help=date_help)

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


def _show_hosts(poutput):

    yaml = YAML()

    with open("inventory.yaml", "r") as host_list:
        host_list_data = yaml.load(host_list) 
        node_list = host_list_data["all"]["hosts"]

    header = (
        f'{"HOSTNAME":<15} | '
        f'{"IP":<15} | '
        f'{"TYPE":<15} | '
        f'{"DESCRIPTION":<30} | '
        f'{"TAGS":<20}'
        )
    
    poutput(header)
    poutput("-" * len(header))

    for node in node_list:
        table_output = (
            f'{node_list[node]["hostname"]:<15} | '
            f'{node_list[node]["ip"]:<15} | '
            f'{node_list[node]["device_type"]:<15} | '
            f'{node_list[node]["description"]:<30} | '
            f'{", ".join(node_list[node]["tags"]):<20}'
            )
        poutput(table_output)


def _show_host(poutput, node):
    
    yaml = YAML()
    with open("inventory.yaml", "r") as host_list:
        host_list_data = yaml.load(host_list) 
        node_list = host_list_data["all"]["hosts"]



        table_output = (
            f'{"IP Address: ":<15}{node_list[node]["ip"]:<15}\n'
            f'{"Device Type: ":<15}{node_list[node]["device_type"]:<15}\n'
            f'{"Description: ":<30}{node_list[node]["description"]:<30}\n'
            f'{"Username: ":<30}{node_list[node]["username"]:<30}\n'
            f'{"Password: ":<30}{node_list[node]["password"]:<30}\n'
            f'{"Tags: ":<20}{", ".join(node_list[node]["tags"]):<20}\n'
            f'{"Port: ":<20}{node_list[node]["port"]:<20}\n'
            f'{"Timeout: ":<20}{node_list[node]["timeout"]:<20}\n'
            f'{"TTL: ":<20}{node_list[node]["ttl"]:<20}\n'
            )

        poutput(f'{"Host: ":<15}{node_list[node]["hostname"]:<15}')
        poutput("-" * 50)
        poutput(table_output)



def _show_groups(poutput):
    
    yaml = YAML()
    with open("inventory.yaml", "r") as inventory:
        inventory_data = yaml.load(inventory) 
        groups_list = inventory_data["all"]["groups"]

    header = (
        f'{"GROUP":<15} | '
        f'{"DESCRIPTION":<40} | '
        f'{"TAGS":<20}'
    )
    poutput(header)
    poutput("-" * len(header))

    for group in groups_list:
        group_desc = groups_list[group]["description"]
        group_tags = ", ".join(groups_list[group]["tags"])
        poutput(f'{group:<15} | {group_desc:<40} | {group_tags:<20}')


def _show_group(poutput, group):

    yaml = YAML()
    with open("inventory.yaml", "r") as inventory:
        inventory_data = yaml.load(inventory) 
        groups_list = inventory_data["all"]["groups"]

        poutput(f'{"Group: ":<15}{group:<15}')
        poutput(f'{"Description: ":<15}{groups_list[group]["description"]:<15}')
        poutput(f'{"Tags: ":<15}{", ".join(groups_list[group]["tags"]):<15}')
        poutput(f'{"Members: ":<15}{f"{len(groups_list[group]['hosts'])} host(s)":<15}')


        header = (
            f'{"HOSTNAME":<15} | '
            f'{"IP":<15} | '
            f'{"TYPE":<15} | '
            f'{"DESCRIPTION":<30} | '
            f'{"TAGS":<20}'
        )
    
        poutput(header)
        poutput("-" * len(header))


        group_hosts = groups_list[group]["hosts"]

        for host in group_hosts:
            host_info = inventory_data["all"]["hosts"][host]

            table_output = (
                f'{host_info["hostname"]:<15} | '
                f'{host_info["ip"]:<15} | '
                f'{host_info["device_type"]:<15} | '
                f'{host_info["description"]:<30} | '
                f'{", ".join(host_info["tags"]):<20}'
                )
            poutput(table_output)


def _show_commands_lists(poutput):
    yaml = YAML()
    with open("commands-lists.yaml", "r") as yaml_commands_lists:
        commands_lists = yaml.load(yaml_commands_lists)

    header = (
        f'{"DEVICE_TYPE":<15} | '
        f'{"NAME":<15} | '
        f'{"DESCRIPTION":<40} | '
        f'{"TAGS":<20}'
    )

    poutput(header)
    poutput("-" * len(header))

    command_lists_info = commands_lists["commands_lists"]

    for device_type in command_lists_info:
        for command_list in command_lists_info[device_type]:
            command_list_info = command_lists_info[device_type][command_list]

            table_output = (
                f'{device_type:<15} | '
                f'{command_list:<15} | '
                f'{command_list_info["description"]:<30} | '
                f'{", ".join(command_list_info["tags"]):<20}'
                )
            poutput(table_output)



def _show_commands_list(poutput, device_type, commands_list):
    yaml = YAML()
    with open("commands-lists.yaml", "r") as yaml_commands_lists:
        commands_lists = yaml.load(yaml_commands_lists)

        command_list_info = commands_lists["commands_lists"][device_type][commands_list]

        poutput(f'{"Command List: ":<15}{commands_list:<15}')
        poutput(f'{"Description: ":<15}{command_list_info["description"]:<15}')
        poutput(f'{"Device_Type: ":<15}{device_type:<15}')
        poutput(f'{"Tags: ":<15}{", ".join(command_list_info["tags"]):<15}')
        poutput(f'{"Lines: ":<15}{f"{len(command_list_info['commands_list'])} line(s)":<15}\n')

        poutput(f'{"COMMANDS: ":<15}')
        for i, line in enumerate(command_list_info["commands_list"]):
            poutput(f"{i}. {line}")


def _show_logs(poutput, args):

    console = Console()
    today_str = datetime.now().strftime("%Y%m%d")

    if args.mode == "execute":
        log_mode_dir = Path("logs") / args.mode
    elif True: # 将来的に別のモードが必要になったときに実装予定。
        pass

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

                if is_exists_directory == False:
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
                        console.print(f"ファイル数が多いから省略するケロ🐸\n")


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


@cmd2.with_argparser(show_parser)
def do_show(self, args):
    if args.hosts:
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

