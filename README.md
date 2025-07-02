# 🐸 KeroRoute

A network automation tool for **ROOKIE network engineer.**
KeroRoute makes CLI-based automation **fun**, **friendly**, and **froggy** 🐸

## KeroRouteとは
**netmiko**を利用したCLI形式のnetwork automation toolです。
ルーキーネットワークエンジニア向けに作られています。

ciscoルータで作業する感覚で、pyatsやansible等のnetwork automation toolより学習コストが少なく始められます。
🐸がぺちぺち跳ねるような感覚でnetwork automation に親しんで行きましょう。

また、既存のレガシーソフトウェアを置き換える🐸のが目標です。

3Cdaemonとかまだ使ってませんか？

ネットワークは好きですが、ネットワークエンジニアという仕事が嫌いなあなたにピッタリのツールです。

仕事用のツールは硬派で無骨なソフトが多いのであえてemojiやメッセージ文言は遊んでいます。

## 特徴 | Features
* execute
* ping


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

version 1.0
---
* カラー＆絵文字出力

* executeコマンド（ログ保存/メモ付き対応）
  * --host, --group によるYAMLインベントリ対応
  * コマンドリスト機能

* pingコマンド

* tracerouteコマンド

*  ログ出力形式のカスタマイズ（JSON, txt, etc）

*  ログ保存先ディレクトリの指定 or 切替

*  ログの自動日付ディレクトリ振り分け
  例： logs/2025-05-01/ログファイル名.log

* GPGによる認証情報の暗号化

* diff比較
---


version 2.0 
---

* Docker化対応

* ASCIIロゴや読み物表示のカスタマイズ性向上

* Ansible 対応

* Terraform 対応

* pyats 対応

* Pyconsoleによるconsole対応

* 多段SSH(マルチホップ)対応

* FTP | TFTP | SFTP 対応 
---


version x.0 
---

* 起動時の読み物表示（ゲームのロード画面風）

* 暇つぶしコマンド（叩くとネット語録や小ネタが出る）

* グローバル設定ファイルの導入（ログディレクトリ・カラー・認証方式）

* 単体テスト/CI対応（pytest）

* 出力のparse
  出力のフィルタリング/色分け（例："up"を緑に、"down"を赤に）

* 接続失敗やタイムアウトのホスト一覧をまとめて表示
  3台成功 / 2台失敗 とかを最後にまとめたい。

* マルチスレッド処理 | 並列処理対応 (複数ホストへの同時接続・実行)

* ドキュメントの自動生成

* プログレスバー対応

* 通知機能
  コマンド実行完了時に通知(サウンド、トースト通知、Slack連携など)


## ライセンス | License

This project is licensed under the MIT License – see the [LICENSE](./LICENSE) file for details.
このプロジェクトはMIT License で提供されています。
