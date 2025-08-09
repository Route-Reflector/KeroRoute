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


def _save_log(result_output_string: str, hostname: str, args, mode: str = "execute") -> Path | None:
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
    pathlib.Path | None
        login モードではファイルパスを返し、その他はNone

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
        if not args.no_output:
            print_info("💾ログ保存モードONケロ🐸🔛")
        
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        timestamp = now.strftime("%Y%m%d-%H%M%S")
        
        log_dir = Path("logs") / mode / date_str
        log_dir.mkdir(parents=True, exist_ok=True)

        log_base_name: str | None = None

        if mode == "configure":
            log_base_name = sanitize_filename(args.config_list)
        elif mode == "scp":        
            scp_file_name = Path(args.src).name
            if args.put:
                log_base_name = sanitize_filename(f"SCP_PUT_{scp_file_name}")
            elif args.get:
                log_base_name = sanitize_filename(f"SCP_GET_{scp_file_name}")
            else:
                raise ValueError("SCPモードでは --put または --get のどちらかを指定する必要があるケロ🐸")
        elif mode == "login":
            log_base_name = "LOGIN"
        elif args.command:
            if mode == "console":
                log_base_name = sanitize_filename(f"{args.command}_by_console")
            else:
                log_base_name = sanitize_filename(args.command)
        elif args.commands_list:
            if mode == "console":
                log_base_name = sanitize_filename(f"{args.commands_list}_by_console")
            else:
                log_base_name = sanitize_filename(args.commands_list)
        else:
            if not args.no_output:
                raise ValueError("args.command または args.commands_list のどちらかが必須ケロ！🐸")
            else:
                return None
        
        if not log_base_name:
            if not args.no_output:
                raise ValueError("ログファイル名が決定できなかったケロ🐸")
            else:
                return None

        if args.memo == "":
            file_name = f"{timestamp}_{hostname}_{log_base_name}.log"
        else:
            sanitized_memo = sanitize_filename(args.memo)
            file_name = f"{timestamp}_{hostname}_{log_base_name}_{sanitized_memo}.log"
        
        log_path = log_dir / file_name

        # loginコマンドではファイルパスのみ返す。(loginコマンドで処理するため。)
        if mode == "login":
            return log_path

        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(result_output_string)
            if not args.no_output:
                print_success(f"💾ログ保存完了ケロ🐸⏩⏩⏩ {log_path}")