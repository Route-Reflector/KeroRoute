import cmd2
from random import choice

import ping
import executor
import console
import configure
import secure_copy
import show
import login


from message import print_info
from load_and_validate_yaml import load_sys_config
"""
cmd2のコマンドライン引数はすべて文字列型となるため、注意が必要。
たとえば、Trueと入力しても実際には"True"となるため型変換が必要。
"""

_sys_config_cache = None  # 一度だけ読み込むようにキャッシュ

_sys_config_cache = load_sys_config()

startup_message = [
    "🐸 KeroRoute - A Network Automation Tool for the Rest of Us.",
    "🐸 KeroRoute - For Network Engineers, Not For Architects.",
    "🐸 Just leap forward. Like a frog.",
    "🐸 An***le is Fake. KeroRoute is Real.",
    "🐸 What network engineers really needed.",
    "🐸 Idempotency not included. But Idempotency is always in YOU.",
    "🐸 We fix networks, not excel.",
    "🐸 The Network Automation will not be GUI-fied.",
    "🐸 AI won’t replace your hands. It won’t replace SFPs either. You still have to.",
    "🐸 KeroRoute -  From console to gNMI, and every leap in between.",
    "🐸 KeroRoute -  Still using SNMP ? SNMP has served for decades, Let it rest.",
    "🐸 KeroRoute -  Still using TELNET ? TELNET has served for decades, Let it rest.",
    "🐸 Fancy dashboards can’t fix a mispatched port.",
    "🐸 No AI can replace on-site troubleshooting.",
    "🐸 Automation is great. So is zip-tying cables in a rack at 2AM.",
    ]


class KeroRoute(cmd2.Cmd):
    # prompt = "🐸\033[92mKeroRoute> \033[0m"
    prompt = "🐸\033[38;5;190mKeroRoute> \033[0m"

    def initial_message(self):
        with open("kero-data/kero-logo.txt", "r") as logo_data:
            logo = logo_data.read()
        self.poutput(logo)

        message = choice(startup_message)

        self.poutput(f"\033[38;5;190m\n{message}\n\033[0m")

    def do_exit(self, _):
        print_info("KeroRouteを終了するケロ🐸🔚")
        return True 

KeroRoute.do_ping = ping.do_ping
KeroRoute.do_execute = executor.do_execute
KeroRoute.do_console = console.do_console
KeroRoute.do_configure = configure.do_configure
KeroRoute.do_scp = secure_copy.do_scp
KeroRoute.do_show = show.do_show
KeroRoute.do_login = login.do_login


if __name__ == "__main__":
    cli = KeroRoute(suggest_similar_command=True)
    cli.initial_message()
    cli.cmdloop()
