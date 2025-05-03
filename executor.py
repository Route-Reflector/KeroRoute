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


def _execute_on_device(device: dict, coomand: str, args, poutput) -> None:
    try:   

        connection = ConnectHandler(**device)
        # 将来的にはdevice_typeでCisco以外の他機種にも対応。
        hostname = connection.find_prompt().strip("#>")
        output = connection.send_command(args.command)
        connection.disconnect()


        if args.memo and not args.log:
            print_warning(poutput, "--memo は --log が指定されているときだけ有効ケロ🐸")
        

        if args.log == True:
            os.makedirs("logs/execute/", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

            sanitized_command = args.command.replace(" ", "-")
            
            if args.memo == "":
                file_name = f"logs/execute/{timestamp}_{hostname}_{sanitized_command}.log"

            else:
                file_name = f"logs/execute/{timestamp}_{hostname}_{sanitized_command}_{args.memo}.log"

            with open(file_name, "w") as log_file:
                log_file.write(output + "\n")
                print_info(poutput, "💾ログ保存モードONケロ🐸🔛")
                print_success(poutput, "🔗接続成功ケロ🐸")
                poutput(output)
                print_success(poutput, f"💾ログ保存完了ケロ🐸⏩⏩⏩ {file_name}")
        
        else:
            print_success(poutput, "🔗接続成功ケロ🐸")
            poutput(output)


    except Exception as e:
        print_error(poutput, f"エラー？接続できないケロ。🐸 \n {e}")


@cmd2.with_argparser(netmiko_execute_parser)
def do_execute(self, args):

    if args.ip:
        device = {
            "device_type": args.device_type,
            "ip": args.ip,
            "username": args.username,
            "password": args.password,
            "port": args.port,
            "timeout": args.timeout
        }

        if args.command:
            _execute_on_device(device, args.command, args, self.poutput)
        elif args.command_list:
            # _execute_on_device(device, args.command-list, args)
            pass    
    elif args.host:
        # with open でinventory fileを読み取る。
        with open("inventory.yaml", "r") as inventory:
           yaml = YAML()
           inventory_data = yaml.load(inventory)
           node_info = inventory_data["all"]["hosts"][args.host]
           device = {
            "device_type": node_info["device_type"],
            "ip": node_info["ip"],
            "username": node_info["username"],
            "password": node_info["password"],
            "port": node_info["port"],
            "timeout": node_info["timeout"] 
           } 

        if args.command:
            _execute_on_device(device, args.command, args, self.poutput)
        elif args.command_list:
            # _execute_on_device(device, args.command-list, args)
            pass    


    elif args.group:
        pass
        # with open でinventory fileを読み取る。
        # していされたグループの情報を取得
        # そのグループののーどのじょうほうを取得。
        # for loopが必要。
        # 将来的には並列処理を実装。
    else:
        pass




