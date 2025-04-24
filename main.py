import cmd2


class KeroRoute(cmd2.Cmd):
    prompt = "🐸\033[92mKeroRoute> \033[0m"

    def initial_message(self):
        with open("kero-data/kero-logo.txt", "r") as logo_data:
            logo = logo_data.read()
        self.poutput(logo)

    def do_exit(self, _):
        self.poutput("\nKeroRouteを終了するケロ🐸🔚\n")
        return True 


if __name__ == "__main__":
    cli = KeroRoute()
    cli.initial_message()
    cli.cmdloop()

