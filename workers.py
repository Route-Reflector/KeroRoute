from load_and_validate_yaml import load_sys_config


#######################
###  CONST_SECTION  ###
#######################
DEFAULT_MAX_WORKERS = 20 # 並列スレッド上限。(sys_config.yamlに設定が無い場合に参照。)


def default_workers(group_size: int, args) -> int:
    """
    並列実行に使うワーカースレッド数（max_workers）を決定する。

    決定ロジックの優先順位：
    1. CLI 引数 `--workers` が指定されていればその値を使う（1以上の整数のみ有効）
    2. 指定がなければ `sys_config.yaml` の `executor.default_workers` を参照
    3. どちらにもなければ `DEFAULT_MAX_WORKERS`（定数）を使用

    ただし、最終的には `group_size`（ホスト台数）と `DEFAULT_MAX_WORKERS` の両方を超えないように調整する。

    Parameters
    ----------
    group_size : int
        グループに含まれるホストの台数（並列実行する対象数）
    args : argparse.Namespace
        コマンドライン引数オブジェクト。`args.workers` を参照

    Returns
    -------
    int
        実際に ThreadPoolExecutor に渡す `max_workers` の値

    Raises
    ------
    ValueError
        - `--workers` に無効な値（0以下や非整数）が指定された場合
        - `sys_config.yaml` に不正な型や値が書かれていた場合
    """
    workers = args.workers

    # ❶ CLI 指定があればそれを優先 (0|負数はerror)
    if workers is not None:
        if not isinstance(workers, int):
            raise ValueError("--workers は整数である必要があるケロ🐸")

        if workers <= 0:
            raise ValueError("--workers には1以上の整数を指定してくださいケロ🐸")
    
    # ❷ 未指定なら system_config
    else:
        system_config = load_sys_config() or {}
        executor_config = system_config.get("executor") or {}
        workers = executor_config.get("default_workers", DEFAULT_MAX_WORKERS)

        if not isinstance(workers, int):
            raise ValueError("sys_config.yaml の executor.default_workers は整数である必要があるケロ🐸")
        
        if workers <= 0:
            raise ValueError("executor.default_workers には1以上の整数を指定してくださいケロ🐸")

    # ❸ 上限と対象台数でクリップ(最低1にしておくと安全)
    workers = max(1, min(workers, group_size, DEFAULT_MAX_WORKERS))
    return workers