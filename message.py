def print_info(poutput, message: str):
    poutput(f"\033[96m🪧[INFO] {message}\033[0m")

def print_success(poutput, message: str):
    poutput(f"\033[92m💯[SUCCESS] {message}\033[0m")

def print_warning(poutput, message: str):
    poutput(f"\033[33m🚧[WARNING] {message}\033[0m")  # amber風
    # poutput(f"\033[33m🚥{message}\033[0m")  # amber風

def print_error(poutput, message: str):
    poutput(f"\033[91m🚨[ERROR] {message}\033[0m")


def ask(message: str) -> str:
    colored = f"\033[96m📋[INPUT] {message}\033[0m"
    return input(colored)


