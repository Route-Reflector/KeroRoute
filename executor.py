import argparse
import os
from datetime import datetime
from netmiko import ConnectHandler
import cmd2

from message import print_info, print_success, print_warning, print_error, ask



######################
### PARSER_SECTION ###
######################
netmiko_execute_parser = argparse.ArgumentParser()
# "-h" はhelpと競合するから使えない。
netmiko_execute_parser.add_argument("-i", "--ip", nargs="?", default=None)
netmiko_execute_parser.add_argument("-u", "--username", type=str, default="")
netmiko_execute_parser.add_argument("-p", "--password", type=str, default="")
netmiko_execute_parser.add_argument("-c", "--command", type=str, default="")
netmiko_execute_parser.add_argument("-d", "--device_type", type=str, default="cisco_ios")
netmiko_execute_parser.add_argument("-P", "--port", type=int, default=22)
netmiko_execute_parser.add_argument("-t", "--timeout", type=int, default=10)
netmiko_execute_parser.add_argument("-l", "--log", action="store_true")
netmiko_execute_parser.add_argument("-m", "--memo", type=str, default="")


@cmd2.with_argparser(netmiko_execute_parser)
def do_execute(self, args):
    if not args.ip:
        return _do_execute_interactive(self)

    try:
        device = {
            "device_type": args.device_type,
            "ip": args.ip,
            "username": args.username,
            "password": args.password,
            "port": args.port,
            "timeout": args.timeout
        }
   

        connection = ConnectHandler(**device)
        # 将来的にはdevice_typeでCisco以外の他機種にも対応。
        hostname = connection.find_prompt().strip("#>")
        output = connection.send_command(args.command)
        connection.disconnect()


        if args.memo and not args.log:
            print_warning(self.poutput, "--memo は --log が指定されているときだけ有効ケロ🐸")
        

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
                print_info(self.poutput, "💾ログ保存モードONケロ🐸🔛")
                print_success(self.poutput, "🔗接続成功ケロ🐸")
                self.poutput(output)
                print_success(self.poutput, f"💾ログ保存完了ケロ🐸⏩⏩⏩ {file_name}")
        
        else:
            print_success(self.poutput, "🔗接続成功ケロ🐸")
            self.poutput(output)





    except Exception as e:
        print_error(self.poutput, f"エラー？接続できないケロ。🐸 \n {e}")
    


def _do_execute_interactive(self):
    pass




