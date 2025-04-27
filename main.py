import subprocess, argparse
import cmd2

import ping


"""
cmd3のコマンドライン引数はすべて文字列型となるため、注意が必要。
たとえば、Trueと入力しても実際には"True"となるため型変換が必要。
"""

class KeroRoute(cmd2.Cmd):
    # prompt = "🐸\033[92mKeroRoute> \033[0m"
    prompt = "🐸\033[38;5;190mKeroRoute> \033[0m"


    def initial_message(self):
        with open("kero-data/kero-logo.txt", "r") as logo_data:
            logo = logo_data.read()
        self.poutput(logo)

    def do_exit(self, _):
        self.poutput("\nKeroRouteを終了するケロ🐸🔚\n")
        return True 
          



KeroRoute.do_ping = ping.do_ping


if __name__ == "__main__":
    cli = KeroRoute()
    cli.initial_message()
    cli.cmdloop()

