# "_"を"-"に変えて登録する。example: device_type -> device-type
CAPABILITY_MAP: dict[str, dict[str, set[str]]]  = {
    "execute":{
        "ssh": {"via", "ip", "host", "group", "command", "commands-list", "quiet", "no-output", "username", "password",
                "secret", "device-type", "port", "timeout", "log", "memo", "workers", "ordered", "parser",
                "textfsm-template", "force"},
        "telnet":{"via", "ip", "host", "group", "command", "commands-list", "quiet", "no-output", "username", "password",
                "secret", "device-type", "port", "timeout", "log", "memo", "workers", "ordered", "parser",
                "textfsm-template", "force"},
        "console": {"via", "host", "group", "command", "commands-list", "connect-only", "quiet", "no-output", "serial",
                    "baudrate",  "username", "password", "secret", "device-type", "read-timeout", "log", "memo",
                    "workers", "ordered", "parser", "textfsm-template", "force"},
        "restconf": {"via"}
    },

    "configure": {
        "ssh": {"via", "ip", "host", "group", "config-list", "quiet", "no-output", "username", "password",
                "secret", "device-type", "port", "timeout", "log", "memo", "workers", "ordered", "parser",
                "textfsm-template", "force"},
        "telnet": {"via"},
        "console": {"via", "host", "group", "config-list", "connect-only", "quiet", "no-output", "serial",
                    "baudrate",  "username", "password", "secret", "device-type", "read-timeout", "log", "memo",
                    "workers", "ordered", "parser", "textfsm-template", "force"},
        "restconf": {"via"},
    },

    "login": {  
        "ssh": {"via", "ip", "host", "group", "username", "password", "secret" },
        "telnet": {"via"},
        "console": {"via"},
    },

    "show": {
        "default": {"hosts", "host", "groups", "group", "commands-lists", "commands-list", "logs", "log", "log-last", "diff",
              "config-lists", "config-list", "mode", "date", "style", "keep-html"}
    },

    "secure_copy": {
        "default": {"ip", "host", "group", "get", "put", "src", "dest", "username", "password", "secret", "device-type",
                    "port", "timeout", "log", "memo", "workers"}
    },
    
    "ping": {
        "default": {"ip", "count", "size", "ttl", "log"}
    }
} 


# ---- 2) HELPERS: 関数（表記揃え & 許可集合の取得 & 検証）----
def allowed_options(module: str, via: str | None) -> set[str]:
    """許可集合を返す。via が None のときは 'default' を見る（via不要系）。なければ空集合。"""
    via_key = via or "default"
    return CAPABILITY_MAP.get(module, {}).get(via_key, set())

def canonicalize(opts: list[str]) -> list[str]:
    """argparse由来の no_output → no-output などを正規化"""
    return [opt.replace("_", "-") for opt in opts]

def validate_options(module: str, used_options: list[str], via: str | None) -> list[str]:
    """不許可オプションだけ返す（ハイフン表記に揃えて比較）"""
    allowed = allowed_options(module, via)
    used = set(canonicalize(used_options))
    return sorted(used - allowed)

# ---- 3) GUARDS: コマンドごとの“使われたオプション”収集＋検証 ----
def collect_used_options_for_execute(args, via: str) -> list[str]:
    used: list[str] = []

    if getattr(args, "via", None):                   used.append("via")

    ###########
    ### ssh ###
    ###########
    if via == "ssh":
        # target
        if getattr(args, "ip", None):                used.append("ip")
        if getattr(args, "host", None):              used.append("host")
        if getattr(args, "group", None):             used.append("group")

        # command options
        if getattr(args, "command", None):           used.append("command")
        if getattr(args, "commands_list", None):     used.append("commands_list")
        
        # silencer
        if getattr(args, "quiet", False):            used.append("quiet")
        if getattr(args, "no_output", False):        used.append("no_output")
        
        # parser
        if getattr(args, "parser", None):            used.append("parser")
        if getattr(args, "textfsm_template", None):  used.append("textfsm_template")
        
        # group_relative
        if getattr(args, "workers", None):           used.append("workers")
        if getattr(args, "ordered", False):          used.append("ordered")

        # device_relative
        if getattr(args, "username", None):          used.append("username")
        if getattr(args, "password", None):          used.append("password")
        if getattr(args, "secret", None):            used.append("secret")
        if getattr(args, "device_type", None):       used.append("device_type")
        if getattr(args, "port", None):              used.append("port")
        if getattr(args, "timeout", None):           used.append("timeout")
        if getattr(args, "log", False):              used.append("log")
        if getattr(args, "memo", None):              used.append("memo")
        if getattr(args, "force", False):            used.append("force")

    ##############
    ### telnet ###
    ##############
    if via == "telnet":
        # target
        if getattr(args, "ip", None):                used.append("ip")
        if getattr(args, "host", None):              used.append("host")
        if getattr(args, "group", None):             used.append("group")

        # command options
        if getattr(args, "command", None):           used.append("command")
        if getattr(args, "commands_list", None):     used.append("commands_list")
        
        # silencer
        if getattr(args, "quiet", False):            used.append("quiet")
        if getattr(args, "no_output", False):        used.append("no_output")
        
        # parser
        if getattr(args, "parser", None):            used.append("parser")
        if getattr(args, "textfsm_template", None):  used.append("textfsm_template")
        
        # group_relative
        if getattr(args, "workers", None):           used.append("workers")
        if getattr(args, "ordered", False):          used.append("ordered")

        # device_relative
        if getattr(args, "username", None):          used.append("username")
        if getattr(args, "password", None):          used.append("password")
        if getattr(args, "secret", None):            used.append("secret")
        if getattr(args, "device_type", None):       used.append("device_type")
        if getattr(args, "port", None):              used.append("port")
        if getattr(args, "timeout", None):           used.append("timeout")
        if getattr(args, "log", False):              used.append("log")
        if getattr(args, "memo", None):              used.append("memo")
        if getattr(args, "force", False):            used.append("force")

    ###############
    ### console ###
    ###############
    if via == "console":
        # target
        if getattr(args, "ip", None):                used.append("ip")
        if getattr(args, "host", None):              used.append("host")
        if getattr(args, "group", None):             used.append("group")

        # command options
        if getattr(args, "command", None):           used.append("command")
        if getattr(args, "commands_list", None):     used.append("commands_list")
        
        # silencer
        if getattr(args, "quiet", False):            used.append("quiet")
        if getattr(args, "no_output", False):        used.append("no_output")
        
        # parser
        if getattr(args, "parser", None):            used.append("parser")
        if getattr(args, "textfsm_template", None):  used.append("textfsm_template")
        
        # group_relative
        if getattr(args, "workers", None):           used.append("workers")
        if getattr(args, "ordered", False):          used.append("ordered")

        # device_relative
        if getattr(args, "username", None):          used.append("username")
        if getattr(args, "password", None):          used.append("password")
        if getattr(args, "secret", None):            used.append("secret")
        if getattr(args, "device_type", None):       used.append("device_type")
        if getattr(args, "port", None):              used.append("port")
        if getattr(args, "timeout", None):           used.append("timeout")
        if getattr(args, "log", False):              used.append("log")
        if getattr(args, "memo", None):              used.append("memo")
        if getattr(args, "force", False):            used.append("force")
    
        # console_relative
        if getattr(args, "connect_only", False): used.append("connect_only")
        if getattr(args, "serial", None):        used.append("serial")
        if getattr(args, "baudrate", None):      used.append("baudrate")
        if getattr(args, "read_timeout", None):  used.append("read_timeout")

    ################
    ### restconf ###
    ################
    if via == "restconf":
        pass

    return used


def collect_used_options_for_configure(args, via: str) -> list[str]:
    used: list[str] = []
    
    if getattr(args, "via", None):                   used.append("via")
    
    
    if getattr(args, "ip", None):                used.append("ip")
    if getattr(args, "host", None):              used.append("host")
    if getattr(args, "group", None):             used.append("group")
    if getattr(args, "config_list", None):     used.append("config_list")
    if getattr(args, "quiet", False):            used.append("quiet")
    if getattr(args, "no_output", False):        used.append("no_output")
    if getattr(args, "ordered", False):          used.append("ordered")
    if getattr(args, "parser", None):            used.append("parser")
    if getattr(args, "textfsm_template", None):  used.append("textfsm_template")
    if getattr(args, "username", None):          used.append("username")
    if getattr(args, "password", None):          used.append("password")
    if getattr(args, "secret", None):            used.append("secret")
    if getattr(args, "device_type", None):       used.append("device_type")
    if getattr(args, "port", None):              used.append("port")
    if getattr(args, "timeout", None):           used.append("timeout")
    if getattr(args, "log", False):              used.append("log")
    if getattr(args, "memo", None):              used.append("memo")
    if getattr(args, "workers", None):           used.append("workers")
    if getattr(args, "force", False):            used.append("force")

    # 将来 console 経由の configure を入れるならここに console 用オプションを追加
    # if via == "console":
    #     if getattr(args, "connect_only", False): used.append("connect_only")
    #     if getattr(args, "serial", None):        used.append("serial")
    #     if getattr(args, "baudrate", None):      used.append("baudrate")
    #     if getattr(args, "read_timeout", None):  used.append("read_timeout")
    return used

class CapabilityError(Exception):
    """Capability検証に失敗したときの入力エラー"""

def guard_execute(args) -> None:
    via = getattr(args, "via", None) or "ssh"  # いまはssh既定。後で --via を必須にしてもOK
    used_options = collect_used_options_for_execute(args, via)
    bad_options = validate_options("execute", used_options, via)
    if bad_options:
        allowed = ", ".join(sorted(allowed_options("execute", via))) or "(none)"
        msg = (
            f"[capability] execute via {via} では使えないケロ: {', '.join(bad_options)} 🐸\n"
            f"使えるのは: {allowed} ケロ🐸"
        )
        raise CapabilityError(msg)


def guard_configure(args) -> None:
    """OKなら何もしない。NGなら CapabilityError を投げる。"""
    via = getattr(args, "via", None) or "ssh"  # いまは ssh 既定
    used_options = collect_used_options_for_configure(args, via)
    bad_options = validate_options("configure", used_options, via)
    if bad_options:
        allowed = ", ".join(sorted(allowed_options("configure", via))) or "(none)"
        msg = (
            f"[capability] configure via {via} では使えないケロ: {', '.join(bad_options)} 🐸\n"
            f"使えるのは: {allowed} ケロ🐸"
        )
        raise CapabilityError(msg)