# 🐸 KeroRoute

A network automation tool for **rookie network engineer.**
KeroRoute makes CLI-based automation **fun**, **friendly**, and **froggy** 🐸

CLI-based network automation tool for lazy NetEngs 🐸

> [!WARNING]  
> 🚧 **Work in Progress (WIP)**  
> ⚠️ **This tool is under active development. Use at your own risk.**  
>  開発中のツールです。不具合や仕様変更の可能性があります。


## KeroRouteとは

**netmiko**を利用したCLI形式のNetwork Automation Toolです。  
ルーキーネットワークエンジニア向けに作られています。

ciscoルータで作業する感覚で、pyatsやansible等のNetwork Automation Toolより学習コストが少なく始められます。  

🐸がぺちぺち跳ねるような感覚で Network Automation に親しんで行きましょう。

また、既存のレガシーソフトウェアを置き換える🐸のが目標です。

ネットワークは好きですが、ネットワークエンジニアという仕事が嫌いなあなたにピッタリのツールです。

仕事用のツールは硬派で無骨なソフトが多いのであえてemojiやメッセージ文言を取り入れています。

## 特徴 | Features
- 🐸 シンプルな CLI (cmd2 + rich)
- 📦 execute (単一コマンド / コマンドリスト)
- 🗂️ YAMLインベントリによるホスト管理
- 💾 ログの保存・メモ付き
- 🔍 show コマンドで情報可視化 (hosts, groups, logs, diff)

## インストール | Install

**ONLY on Linux !!**
現状linuxのみをサポートしています。windowsの場合はwsl2やgit editorを利用してください。

## Python Version
Tested on Python 3.11
(Pipfile で固定、python_version = "3.11")

### Minimal Runtime Only
```bash
git clone https://github.com/Route-Reflector/KeroRoute.git
cd KeroRoute
pip install -r requirements.txt
python main.py
```

### Full development setup
```bash
# runtime + dev tools
pip install -r requirements.txt -r requirements-dev.txt

# or with Pipenv
pipenv install --dev
pipenv shell

# run tests & lint
pytest
ruff check .
```

### Generating requirements.txt (for maintainers)
```bash
pipenv requirements          > requirements.txt
pipenv requirements --dev    > requirements-dev.txt
```

---

## 使用方法 | How to use

### execute

```bash
execute -i xx.xx.xx.xx -u username -p password -c "show ip int brief" 
```

#### log を保存する場合

```bash
execute -i xx.xx.xx.xx -u username -p password -c "show ip int brief" --log
```

#### log にメモを保存する場合

```bash
execute -i xx.xx.xx.xx -u username -p password -c "show ip int brief" --log --memo "設定変更後"
```
---

## 🗺️ Roadmap

---

### ✅ version 0.x – 実装済み（開発中）

- 🐸 execute コマンド (--host / --group / --log / --memo 対応)
- 🌐 IPv6対応
- 📦 コマンドリスト (YAML形式) による複数コマンド実行
- 🧵 並列処理 (複数ホストへの同時接続 & 実行)
- 🛠️ configure コマンド (YAMLから設定投入)
- 🐸 console接続 (Netmikoによるシリアル対応)
- 💾 ログ自動保存 (実行時刻 + ホスト名 + コマンド名 + メモ)
- 📁 ログの自動日付ディレクトリ振り分け  
  - example: logs/2025-05-01/ログファイル名.log
- 🎨 rich出力 (カラー & 絵文字)
- 🔍 show コマンド (inventory / group / commands / logs / diff)  
---

### 🚧 version 1.0 - 実装予定 (実用レベルの安定版)

- 🔐 GPGによる認証情報の暗号化・復号化
- 📊 プログレスバー表示
- 🚨 接続失敗やタイムアウト時のレポート (成功 / 失敗表示)
- 🪜 多段SSH対応 (bastion経由で複数ホストを経由して接続)
- 🧪 単体テスト/CI対応 (pytest) 
- ⚙️ グローバル設定ファイルの導入 (ログディレクトリ・カラー・認証方式)

---


### 🌈 beyond 1.0 

- 📦 Docker化対応
- 🔔 通知機能 (サウンド / トースト通知 / Slack)
- 🧾 接続結果のまとめ表示 (例: 3台成功 / 2台失敗)

## ライセンス | License

This project is licensed under the MIT License – see the [LICENSE](./LICENSE) file for details.  
このプロジェクトはMIT License で提供されています。
