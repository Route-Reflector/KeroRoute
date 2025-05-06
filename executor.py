import argparse
import os
from datetime import datetime
from netmiko import ConnectHandler
import cmd2
from ruamel.yaml import YAML
from message import print_info, print_success, print_warning, print_error, ask


######################
###  HELP_SECTION  ### 
######################
ip_help = ""
host_help = ""
group_help = ""

command_help = ""
command_list_help = ""

username_help = ""
password_help = ""
device_type_help = ""
port_help = ""
timeout_help = ""
log_help = ""
memo_help = ""


######################
### PARSER_SECTION ###
######################
netmiko_execute_parser = argparse.ArgumentParser()
# "-h" はhelpと競合するから使えない。
netmiko_execute_parser.add_argument("-u", "--username", type=str, default="")
netmiko_execute_parser.add_argument("-p", "--password", type=str, default="")
netmiko_execute_parser.add_argument("-d", "--device_type", type=str, default="cisco_ios")
netmiko_execute_parser.add_argument("-P", "--port", type=int, default=22)
netmiko_execute_parser.add_argument("-t", "--timeout", type=int, default=10)
netmiko_execute_parser.add_argument("-l", "--log", action="store_true")
netmiko_execute_parser.add_argument("-m", "--memo", type=str, default="")

# mutually exclusive
target_node = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_node.add_argument("-i", "--ip", type=str, nargs="?", default=None)
target_node.add_argument("--host", type=str, nargs="?", default=None)
target_node.add_argument("--group", type=str, nargs="?", default=None)

target_command = netmiko_execute_parser.add_mutually_exclusive_group(required=True)
target_command.add_argument("-c", "--command", type=str, default="")
target_command.add_argument("-L", "--command-list", type=str, default="")


def _connect_to_device(device: dict, hostname_for_log:str):

    try:   
        connection = ConnectHandler(**device)
        # TODO: 将来的にはdevice_typeでCisco以外の他機種にも対応。
        node_prompt = connection.find_prompt()
        hostname = node_prompt.strip("#>")
        return connection, node_prompt, hostname

    except Exception as e:
        raise ConnectionError(f"[{hostname_for_log}]に接続できないケロ。🐸 \n {e}")


def _execute_commands_on_device(connection, node_prompt, hostname_for_log, args, poutput) -> str:
    
    if args.command:
        output = connection.send_command(args.command)
        full_output = f"{node_prompt} {args.command}\n{output}"

        return full_output

    elif args.command_list:
        yaml = YAML()
        with open("command-list.yaml", "r") as file_command_list:
            command_list_data = yaml.load(file_command_list)

            if args.device_type not in command_list_data["command_list"]:
                print_error(poutput, f"デバイスタイプ '{args.device_type}' はcommand-list.yamlに存在しないケロ🐸")
                return
            if args.command_list not in command_list_data["command_list"][f"{args.device_type}"]:
                print_error(poutput, f"コマンドリスト '{args.command_list}' はcommand-list.yamlに存在しないケロ🐸")
                return

            try:
                exec_commands = command_list_data["command_list"][f"{args.device_type}"][f"{args.command_list}"]["commands"]
            except Exception as e:
                raise KeyError(f"[{hostname_for_log}] command-list.yamlの構造がおかしいケロ🐸")

            full_output_list = []

            for command in exec_commands:
                output = connection.send_command(command)
                full_output = f"{node_prompt} {command}\n{output}"
                full_output_list.append(full_output)
            
            return "\n".join(full_output_list)


def _execute_on_device(device: dict, args, poutput, hostname_for_log) -> None:

    try:
        connection, node_prompt, real_hostname = _connect_to_device(device, hostname_for_log)
    except ConnectionError as e:
        print_error(poutput, str(e))
        return

    try:
        full_output_or_full_output_list = _execute_commands_on_device(connection, node_prompt, hostname_for_log, args, poutput)
    except KeyError as e:
        print_error(poutput, str(e))
        return

    connection.disconnect()

    if args.memo and not args.log:
        print_warning(poutput, "--memo は --log が指定されているときだけ有効ケロ🐸")
    
    if args.log == True:
        os.makedirs("logs/execute/", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if args.command:
            sanitized_command = args.command.replace(" ", "-")
        elif args.command_list:
            sanitized_command = args.command_list.replace(" ", "-")

        if args.memo == "":
            file_name = f"logs/execute/{timestamp}_{real_hostname}_{sanitized_command}.log"
        else:
            file_name = f"logs/execute/{timestamp}_{real_hostname}_{sanitized_command}_{args.memo}.log"

        with open(file_name, "w") as log_file:
            log_file.write(full_output_or_full_output_list)
            print_info(poutput, "💾ログ保存モードONケロ🐸🔛")
            print_success(poutput, "🔗接続成功ケロ🐸")
            poutput(full_output_or_full_output_list)
            print_success(poutput, f"💾ログ保存完了ケロ🐸⏩⏩⏩ {file_name}")

    else:
        print_success(poutput, "🔗接続成功ケロ🐸")
        poutput(full_output_or_full_output_list)


def _load_and_validate_inventory(args, poutput):
    
    yaml = YAML()
    with open("inventory.yaml", "r") as inventory:
        inventory_data = yaml.load(inventory)

    if args.host:
        if args.host not in inventory_data["all"]["hosts"]:
            print_error(poutput, f"ホスト '{args.host}' はinventory.yamlに存在しないケロ🐸")
            return None
    elif args.group:
        # if args.group not in inventory_data["all"]["children"]:
        if args.group not in inventory_data["all"]["groups"]:
            print_error(poutput, f"グループ '{args.group}' はinventory.yamlに存在しないケロ🐸")
            return None
    
    return inventory_data
    

def _build_device_and_hostname(args, inventory_data=None):

    if args.ip:
        device = {
            "device_type": args.device_type,
            "ip": args.ip,
            "username": args.username,
            "password": args.password,
            "port": args.port,
            "timeout": args.timeout
        }

        hostname_for_log = args.ip
        return device, hostname_for_log
    
    elif args.host:
        node_info = inventory_data["all"]["hosts"][args.host]
        
        device = {
        "device_type": node_info["device_type"],
        "ip": node_info["ip"],
        "username": node_info["username"],
        "password": node_info["password"],
        "port": node_info["port"],
        "timeout": node_info["timeout"] 
        }

        hostname_for_log = node_info["hostname"]
        return device, hostname_for_log 

    elif args.group:
        # group_info = inventory_data["all"]["children"][f"{args.group}"]["hosts"]
        group_info = inventory_data["all"]["groups"][f"{args.group}"]["hosts"]
        
        device_list = []
        hostname_for_log_list = []

        for node in group_info:
            node_info = inventory_data["all"]["hosts"][f"{node}"]
            device = {
                "device_type": node_info["device_type"],
                "ip": node_info["ip"],
                "username": node_info["username"],
                "password": node_info["password"],
                "port": node_info["port"],
                "timeout": node_info["timeout"] 
                } 
            hostname_for_log = node_info["hostname"]
            
            device_list.append(device)
            hostname_for_log_list.append(hostname_for_log)
        
        return device_list, hostname_for_log_list


@cmd2.with_argparser(netmiko_execute_parser)
def do_execute(self, args):

    if args.ip:
        device, hostname_for_log = _build_device_and_hostname(args)
        _execute_on_device(device, args, self.poutput, hostname_for_log)
    

    elif args.host:
        inventory_data = _load_and_validate_inventory(args, self.poutput)
        if inventory_data is None:
            return
              
        device, hostname_for_log = _build_device_and_hostname(args, inventory_data)
        _execute_on_device(device, args, self.poutput, hostname_for_log)


    elif args.group:
        # TODO: 将来的には並列処理を実装。
        inventory_data = _load_and_validate_inventory(args, self.poutput)            
        if inventory_data is None:
            return

        device_list, hostname_for_log_list = _build_device_and_hostname(args, inventory_data)
        for device, hostname_for_log in zip(device_list, hostname_for_log_list):
            _execute_on_device(device, args, self.poutput, hostname_for_log)