import subprocess
import argparse
import ipaddress
import cmd2

from message import print_info, print_success, print_warning, print_error, ask


######################
### PARSER_SECTION ###
######################
ping_parser = argparse.ArgumentParser()
ping_parser.add_argument("ip", nargs="?", default=None)
ping_parser.add_argument("-c", "--count", type=int, default=4)
ping_parser.add_argument("-s", "--size", type=int, default=56)
ping_parser.add_argument("-t", "--ttl", type=int, default=64)
ping_parser.add_argument("-l", "--log", action="store_true")


@cmd2.with_argparser(ping_parser)
def do_ping(self, args):
    if not args.ip:
        return _do_ping_interactive(self)

    try:
        ipaddress.IPv4Address(args.ip)
    except ipaddress.AddressValueError:
        print_warning(self.poutput, "IPアドレス間違ってないケロ？🐸")
        return
    
    if args.log:
        #　ここにログを保存する処理。
        print_info(self.poutput, "💾ログ保存モードONケロ🐸🔛")

    try:
        result = subprocess.run(["ping", args.ip, "-c", str(args.count), "-s", str(args.size), "-t", str(args.ttl)], check=True)
        self.poutput(result.stdout)

    except subprocess.CalledProcessError:
        print_error(self.poutput, "なんか失敗したケロロ.....🐸")
        return

    print_success(self.poutput, "Pingの結果を確認するケロ🐸")


def _do_ping_interactive(self) -> None:

    ip: str = ask("どのIP/ホストにpingするケロ？🐸")        
    if ip == "":
        print_error(self.poutput, "IPアドレスは必須ケロ！🐸")
        return
    else:
        try:
            ipaddress.IPv4Address(ip)
        except ipaddress.AddressValueError:
            print_warning(self.poutput, "IPアドレス間違ってないケロ？🐸")
            return


    # repeatの最大値を決めておく？
    repeat: int = ask("何回送信するケロ？(default = 4)🐸: ")        
    if repeat == "":
        repeat = 4
    else:
        repeat = int(repeat)
    

    # pacekt_sizeの最小値と最大値も決めて置く？
    packet_size: int = ask("packetsizeはどうするケロ？(default = 56)🐸: ")
    if packet_size == "":
        packet_size = 56
    else:
        packet_size = int(packet_size)        


    # ttl は0から255の間かな？
    ttl: int = ask("ttlはどうするケロ？🐸(default = 64): ")        
    if ttl == "":
        ttl = 64
    else:
        ttl = int(ttl)


    log: str = ask("ログは保存するケロ？🐸(yes/no): ")        
    if log == "":
        log = "no"

    if log.lower() == "yes":
        # TODO: ここにログを保存する処理。
        print_info(self.poutput, "💾ログ保存モードONケロ🐸🔛")


    print_info(self.poutput, "ping実行中.....🐸💨")                  
    result =  subprocess.run(["ping", ip, "-c", str(repeat), "-s", str(packet_size), "-t", str(ttl)], check=True)
    self.poutput(result.stdout)

    print_success(self.poutput, "実行終了ケロ。実行結果を確認するケロ🐸🔚")        
