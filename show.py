import argparse
import cmd2
from ruamel.yaml import YAML


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
log_help = "指定したログファイルの内容を表示します。"
log_last_help = "最新のログファイルの内容を表示します。"


######################
### PARSER_SECTION ###
######################
show_parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
# "-h" はhelpと競合するから使えない。

# mutually exclusive
target_show = show_parser.add_mutually_exclusive_group(required=True)
target_show.add_argument("--hosts", action="store_true", help=hosts_help)
target_show.add_argument("--host", type=str, default="", help=host_help)
target_show.add_argument("--groups", action="store_true", help=groups_help)
target_show.add_argument("--group", type=str, default="", help=group_help)
target_show.add_argument("--commands-lists", action="store_true", help=commands_lists_help)
target_show.add_argument("--commands-list", nargs=2, metavar=("DEVICE_TYPE", "COMMAND_LIST"), help=commands_list_help)
target_show.add_argument("--logs", action="store_true", help=logs_help)
target_show.add_argument("--log", type=str, default="", help=log_help)
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

