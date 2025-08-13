import re
import json
from typing import Any
from datetime import datetime
from pathlib import Path


def sanitize_filename(text: str) -> str:
    """
    ファイル名に使用できない文字を安全な文字に変換する。
    禁止文字: \\ / : * ? " < > | -> "_" アンダースコア
    スペース: " " -> "-" ハイフン
    """

    text = text.replace(" ", "-")
    return re.sub(r'[\\/:*?"<>|]', '_', text).strip()


def save_log(result_output_string: str, hostname: str, args, mode: str = "execute") -> Path | None:
    """
    プレーンテキスト出力を日時付き .log として保存する。

    ファイル名: {YYYYmmdd-HHMMSS}_{hostname}_{command|list}[_{memo}].log
    保存先   : logs/{mode}/{YYYYmmdd}/

    Parameters
    ----------
    result_output_string : str
        コマンド実行結果（テキスト）
    hostname : str
        ログファイル名に含めるホスト識別子
    args : argparse.Namespace
        CLI 引数（--log, --memo, --command, --commands-list などを参照）
    mode : str, optional
        保存モード("execute", "console", "configure", "scp", "login" など)

    Returns
    -------
    Path | None
        実際に保存した場合は保存先 Path、保存しない場合(None)は None

    Raises
    ------
    ValueError
        --memo のみ指定 / ファイル名が決定できない / SCPモードでput/get未指定 などの論理エラー
    OSError
        ファイル/ディレクトリ作成や書き込みに失敗した場合（そのまま伝播）
    """

    # --memoがあるのに--logがないとValueError
    if getattr(args, "memo", "") and not getattr(args, "log", False):
        raise ValueError("--memo は --log が指定されているときだけ有効ケロ🐸")
    
    # --logがなければ何もしない。
    if not getattr(args, "log", False):
        return None

    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    
    log_dir = Path("logs") / mode / date_str
    log_dir.mkdir(parents=True, exist_ok=True)

    log_base_name: str | None = None

    if mode == "configure":
        log_base_name = sanitize_filename(getattr(args, "config_list", "CONFIG"))
    elif mode == "scp":
        source = getattr(args, "src", "")
        scp_file_name = Path(source).name if source else "UNKNOWN"
        if getattr(args, "put", False):
            log_base_name = sanitize_filename(f"SCP_PUT_{scp_file_name}")
        elif getattr(args, "get", False):
            log_base_name = sanitize_filename(f"SCP_GET_{scp_file_name}")
        else:
            raise ValueError("SCPモードでは --put または --get のどちらかを指定する必要があるケロ🐸")
    elif mode == "login":
        log_base_name = "LOGIN"
    elif getattr(args, "command", ""):
        if mode == "console":
            log_base_name = sanitize_filename(f"{args.command}_by_console")
        else:
            log_base_name = sanitize_filename(args.command)
    elif getattr(args, "commands_list", ""):
        if mode == "console":
            log_base_name = sanitize_filename(f"{args.commands_list}_by_console")
        else:
            log_base_name = sanitize_filename(args.commands_list)
    else:
        if not getattr(args, "no_output", False):
            raise ValueError("args.command または args.commands_list のどちらかが必須ケロ！🐸")
        else:
            return None
    
    if not log_base_name:
        if not getattr(args, "no_output", False):
            raise ValueError("ログファイル名が決定できなかったケロ🐸")
        else:
            return None

    if getattr(args, "memo", ""):
        sanitized_memo = sanitize_filename(args.memo)
        file_name = f"{timestamp}_{hostname}_{log_base_name}_{sanitized_memo}.log"
    else:
        file_name = f"{timestamp}_{hostname}_{log_base_name}.log"
    
    log_path = log_dir / file_name

    # loginコマンドではファイルパスのみ返す。(loginコマンドで処理するため。)
    if mode == "login":
        return log_path

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(result_output_string)
    
    return log_path


def save_json(json_data: Any, hostname: str, args, *, parser_kind: str, mode: str = "execute") -> Path | None:
    """
    パース済みデータを JSON で保存する。

    ファイル名: {YYYYmmdd-HHMMSS}_{hostname}_{command|list}[_{memo}]_{parser}.json
    保存先   : logs/{mode}_json/{YYYYmmdd}/

    Parameters
    ----------
    json_data : Any
        JSON へ保存するデータ（list/dict 等）
    hostname : str
        ログファイル名に含めるホスト識別子
    args : argparse.Namespace
        CLI 引数（--log, --memo, --command, --commands-list などを参照）
    parser_kind : str
        "genie" | "textfsm" 等のパーサ名（拡張子前サフィックスに使用）
    mode : str, optional
        保存モード("execute", "console", "configure", "scp", "login" など)

    Returns
    -------
    Path | None
        実際に保存した場合は保存先 Path、保存しない場合(None)は None

    Raises
    ------
    ValueError
        --memo のみ指定 / ファイル名が決定できない / SCPモードでput/get未指定 などの論理エラー
    OSError
        ファイル/ディレクトリ作成や書き込みに失敗した場合（そのまま伝播）
    """

    # --memoがあるのに--logがないとValueError
    if getattr(args, "memo", "") and not getattr(args, "log", False):
        raise ValueError("--memo は --log が指定されているときだけ有効ケロ🐸")
    
    # --logがなければ何もしない。
    if not getattr(args, "log", False):
        return None
    
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    
    # .logと.jsonは別ディレクトリに保存。
    log_dir = Path("logs") / f"{mode}_json" / date_str
    log_dir.mkdir(parents=True, exist_ok=True)

    log_base_name: str | None = None

    if mode == "configure":
        log_base_name = sanitize_filename(getattr(args, "config_list", "CONFIG"))
    elif mode == "scp":
        source = getattr(args, "src", "")
        scp_file_name = Path(source).name if source else "UNKNOWN"
        if getattr(args, "put", False):
            log_base_name = sanitize_filename(f"SCP_PUT_{scp_file_name}")
        elif getattr(args, "get", False):
            log_base_name = sanitize_filename(f"SCP_GET_{scp_file_name}")
        else:
            raise ValueError("SCPモードでは --put または --get のどちらかを指定する必要があるケロ🐸")
    elif mode == "login":
        log_base_name = "LOGIN"
    elif getattr(args, "command", ""):
        if mode == "console":
            log_base_name = sanitize_filename(f"{args.command}_by_console")
        else:
            log_base_name = sanitize_filename(args.command)
    elif getattr(args, "commands_list", ""):
        if mode == "console":
            log_base_name = sanitize_filename(f"{args.commands_list}_by_console")
        else:
            log_base_name = sanitize_filename(args.commands_list)
    else:
        if not getattr(args, "no_output", False):
            raise ValueError("args.command または args.commands_list のどちらかが必須ケロ！🐸")
        else:
            return None
    
    if not log_base_name:
        if not getattr(args, "no_output", False):
            raise ValueError("ログファイル名が決定できなかったケロ🐸")
        else:
            return None

    if getattr(args, "memo" , ""):
        sanitized_memo = sanitize_filename(args.memo)
        if parser_kind:
            file_name = f"{timestamp}_{hostname}_{log_base_name}_{sanitized_memo}_{parser_kind}.json"
        else:
            file_name = f"{timestamp}_{hostname}_{log_base_name}_{sanitized_memo}.json"
    else:
        if parser_kind:
            file_name = f"{timestamp}_{hostname}_{log_base_name}_{parser_kind}.json"
        else:
            file_name = f"{timestamp}_{hostname}_{log_base_name}.json"
    
    log_path = log_dir / file_name

    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(json.dumps(json_data, ensure_ascii=False, indent=2))
    
    return log_path
