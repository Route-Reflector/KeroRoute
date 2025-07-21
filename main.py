import cmd2

import ping
import executor
import console
import configure
import show


from message import print_info

"""
cmd2のコマンドライン引数はすべて文字列型となるため、注意が必要。
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
        print_info("KeroRouteを終了するケロ🐸🔚")
        return True 

KeroRoute.do_ping = ping.do_ping
KeroRoute.do_execute = executor.do_execute
KeroRoute.do_console = console.do_console
KeroRoute.do_configure = configure.do_configure
KeroRoute.do_show = show.do_show


if __name__ == "__main__":
    cli = KeroRoute(suggest_similar_command=True)
    cli.initial_message()
    cli.cmdloop()
