import argparse
from netmiko import ConnectHandler
import cmd2


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

        output = connection.send_command(args.command)
        connection.disconnect()
        self.poutput("🔗接続成功ケロ🐸")
        self.poutput(output)

        # ここにログを保存する場合のコードを書く。

    except Exception as e:
        self.poutput("🚥エラー？接続できないケロ。🐸")
    


def _do_execute_interactive(self):
    pass




