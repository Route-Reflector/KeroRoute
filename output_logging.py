import re
from datetime import datetime
from pathlib import Path

from message import print_info, print_success, print_warning, print_error


def sanitize_filename(text: str) -> str:
    """
    ファイル名に使用できない文字を安全な文字に変換する。
    禁止文字: \\ / : * ? " < > | -> "_" アンダースコア
    スペース: " " -> "-" ハイフン
    """

    text = text.replace(" ", "-")
    return re.sub(r'[\\/:*?"<>|]', '_', text).strip()


def _save_log(result_output_string: str, hostname: str, args, mode: str = "execute") -> None:
    """
    実行結果を日時付きファイルに保存するユーティリティ。

    ファイル名フォーマット
    --------------------
    ``{YYYYmmdd-HHMMSS}_{hostname}_{command|list}[_{memo}].log``

    Parameters
    ----------
    result_output_string : str
        コマンド実行結果全体（単発でも複数でも OK）。
    hostname : str
        ログファイル名に含めるホスト名。
    args : argparse.Namespace
        CLI 引数。`--log`, `--memo`, `--command`, `--commands-list` を参照。
    mode: str, optional
         ログ保存モード（"execute", "console", "configure"など）。デフォルトは "execute"。
    
    Returns
    -------
    None

    Raises
    ------
    ValueError
        - `--memo` だけ指定された場合
        - `--command` / `--commands-list` どちらも無い場合
    IOError
        ファイル書き込み失敗（上位で捕捉してもよい）
    """
    if args.memo and not args.log:
        msg = "--memo は --log が指定されているときだけ有効ケロ🐸"
        print_warning(msg)
        raise ValueError(msg)
    
    if args.log:
        print_info("💾ログ保存モードONケロ🐸🔛")
        date_str = datetime.now().strftime("%Y%m%d")
        log_dir = Path("logs") / mode / date_str
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        if mode == "configure":
            sanitized_command = sanitize_filename(args.config_list)
        elif mode == "scp":        
            scp_file_name = Path(args.src).name
            if args.put:
                sanitized_command = sanitize_filename(f"SCP_PUT_{scp_file_name}")
            elif args.get:
                sanitized_command = sanitize_filename(f"SCP_GET_{scp_file_name}")
        elif args.command:
            if mode == "console":
                sanitized_command = sanitize_filename(f"{args.command}_by_console")
            else:
                sanitized_command = sanitize_filename(args.command)
        elif args.commands_list:
            if mode == "console":
                sanitized_command = sanitize_filename(f"{args.commands_list}_by_console")
            else:
                sanitized_command = sanitize_filename(args.commands_list)
        else:
            raise ValueError("args.command または args.commands_list のどちらかが必須ケロ！🐸")

        if args.memo == "":
            file_name = f"{timestamp}_{hostname}_{sanitized_command}.log"
        else:
            sanitized_memo = sanitize_filename(args.memo)
            file_name = f"{timestamp}_{hostname}_{sanitized_command}_{sanitized_memo}.log"
        
        log_path = log_dir / file_name

        with open(log_path, "w") as log_file:
            log_file.write(result_output_string)
            print_success(f"💾ログ保存完了ケロ🐸⏩⏩⏩ {log_path}")