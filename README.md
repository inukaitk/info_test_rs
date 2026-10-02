# 外部環境情報収集MVP（info_test_rs）

中央官庁・公的機関の公開情報を収集し、短い概要と登録済みタグを付けて、最新一覧とテーマ別Wikiで閲覧するための個人開発の検証版です。

> 現在は **段階1-a**（画面：最新情報・記事を探す・記事詳細）まで進んでいます。
> 現在の設定・データはすべて **架空** です。

## フォルダ構成

| フォルダ・ファイル | 内容 |
|---|---|
| `CLAUDE.md` | Claude Code への開発指示 |
| `docs/handoff/` | 仕様（SPEC.md）と実装指針（IMPLEMENTATION.md） |
| `docs/PLAN.md` | 段階0-a〜3-bの実装計画 |
| `docs/DECISIONS.md` | 決定事項と未確定事項 |
| `config/` | 人が変更する設定（情報源、タグ、タグ修正、画面設定） |
| `data/` | 自動処理が作るデータ（記事、版、要約、実行履歴、取得状態、タグ候補） |
| `schemas/` | 設定とデータの形式（JSON Schema） |
| `collector/` | Pythonの処理（スキーマ検証、公開用変換） |
| `demo/` | 架空のデモデータ（`demo/data/`）と、その情報源・タグ修正（`demo/config/`） |
| `web/` | 画面（TypeScript＋Vite）。`web/src/` がプログラム、`web/tests/` が画面のテスト |
| `web/public/data/` | 画面用JSON（公開用変換の出力。画面はこれだけを読む） |
| `viewer/info_viewer.html` | 画面とデータを1つにまとめたファイル（ダブルクリックで開ける） |
| `scripts/` | 架空データの作成、コミット前の安全確認 |
| `tests/` | テスト（`tests/fixtures/` は架空のテスト用データ） |

## PC（Windows）で画面を見る

見る方法は2つあります。**ソフトのインストールが許可されていないPCでは「方法A」を使ってください。**

| | 方法A：HTMLファイルを開く | 方法B：Node.js で起動する |
|---|---|---|
| 必要なもの | ブラウザ（Edge・Chrome）だけ | Git と Node.js のインストール |
| 操作 | ファイルをダウンロードしてダブルクリック | PowerShell でコマンドを実行 |
| 向いている用途 | 部署レビュー、社用PCでの確認 | 開発中の確認 |

### 方法A：HTMLファイルを開く（インストール不要）

画面とデータを1つにまとめたファイル `viewer/info_viewer.html` を開きます。インターネットへの通信は行わず、ファイルの中だけで動きます。

1. ブラウザで https://github.com/inukaitk/info_test_rs/blob/main/viewer/info_viewer.html を開きます（GitHubへのサインインが必要です）。
2. ファイル表示の右上にある **下向き矢印のボタン（Download raw file）** を押します。「ダウンロード」フォルダに `info_viewer.html` が保存されます。
3. エクスプローラーで「ダウンロード」フォルダを開き、`info_viewer.html` を **ダブルクリック** します。ブラウザで画面が開きます。
4. 画面の上部に赤い帯で「**架空データ**」と表示され、「最新情報」に記事が並んでいれば成功です。

画面の内容が更新されたら（Pull Request を merge した後）、同じ手順でダウンロードし直してください。
ファイルはメールやTeamsで共有して、相手のPCでもそのまま開けます（現在の内容はすべて架空データです）。

### 方法B：Node.js で起動する

PCでは Python は不要です。画面用JSON（`web/public/data/`）はリポジトリに入っているので、Git と Node.js だけで画面を開けます。
以下はすべて **Windows PowerShell** で実行します（スタートメニューで「PowerShell」と入力して開きます）。
社用PCでは、インストールの前に社内の規定を確認してください。

#### 1. Git と Node.js を準備する（初回のみ）

1. Git を https://git-scm.com/download/win からダウンロードしてインストールします（設定は既定のままで構いません）。
2. Node.js を https://nodejs.org/ja から **LTS** と書かれた版をダウンロードしてインストールします（設定は既定のままで構いません）。
3. PowerShell を一度閉じて開き直し、次の3つを実行します。

```powershell
git --version     # Git の版を表示する。例：git version 2.51.0.windows.1
node --version    # Node.js の版を表示する。v22.12 以上なら OK（例：v24.11.0）
npm --version     # npm（Node.js に同梱）の版を表示する。例：11.6.2
```

「認識されません」と表示された場合はインストールできていないか、PowerShell を開き直していません。

#### 2. リポジトリを PC にコピーする（初回のみ）

このリポジトリは private なので、初回は GitHub へのログインを求められます（ブラウザが開いたら GitHub にサインインして許可します）。

```powershell
cd $HOME\Documents                                         # 「ドキュメント」フォルダへ移動する
git clone https://github.com/inukaitk/info_test_rs.git      # リポジトリをコピーする（info_test_rs フォルダができる）
cd info_test_rs\web                                         # 画面のフォルダへ移動する
npm ci                                                      # 画面に必要な部品を入れる（数十秒〜数分）
```

`npm ci` の最後に `added 〇〇 packages` と表示されれば成功です（`npm warn` は無視して構いません）。

#### 3. 画面を起動する（毎回）

```powershell
cd $HOME\Documents\info_test_rs\web    # 画面のフォルダへ移動する
npm run dev                             # 画面を起動する（止めるまで動き続ける）
```

成功すると次のように表示されます。

```
  VITE v8.x.x  ready in 300 ms

  ➜  Local:   http://localhost:5173/
```

ブラウザ（Edge や Chrome）で **http://localhost:5173/** を開きます。
画面の上部に赤い帯で「**架空データ**」と表示され、「最新情報」に架空の記事が4件並んでいれば成功です（「記事を探す」では20件すべてを見られます）。
終了するときは PowerShell で `Ctrl` キーを押しながら `C` を押します。

#### 4. 最新の内容に更新する（Pull Request を merge した後）

```powershell
cd $HOME\Documents\info_test_rs    # リポジトリのフォルダへ移動する
git pull                           # GitHub の最新の内容を取り込む
cd web
npm ci                             # 部品に変更があっても対応できるよう入れ直す
npm run dev                        # 画面を起動する
```

#### 参考：公開時と同じ形で確認する

```powershell
cd $HOME\Documents\info_test_rs\web
npm run build      # 公開用のファイルを web\dist に作る。最後に「✓ built in …」と出れば成功
npm run preview    # 作ったファイルで画面を起動する。http://localhost:4173/ を開く
```

### 画面の使い方

- **最新情報**（最初に開く画面）：直近7日間（最終収集日を含む）に**新しく見つけた記事**を表示します。日数は `config/site.yaml` の `latest_days` で変えられます。
- **記事を探す**：これまでに集めた全期間の記事を、タグ・機関・期間（公開日）で絞り込み、文字検索（空白で区切ると「すべてを含む」）できます。絞り込んだ状態のURLをそのまま共有できます。期間で絞り込むと、日付不明の記事は含めず「日付不明の記事 〇件は期間の絞り込みに含めていません」と知らせます。
- タグを押すと、そのタグの記事を「記事を探す」で表示します（タグ別の Wiki は段階1-bで追加します）。
- **記事詳細**：タイトルを押すと開きます。出典リンク、日付とその根拠、概要・論点・対象・確認できた日付、タグとその由来、AI処理状態、変更履歴を表示します。
- タグの見分け方：青い「AI」はAIが付けたタグ、点線で橙色の「人が追加」は人が追加したタグ、取り消し線は人が外したタグです。

## 設定ファイル（config/）

| ファイル | 内容 |
|---|---|
| `sources.yaml` | 情報源（id、機関名、入口URL、取得方式 rss/html/manual、許可ホスト、リンク規則、ページ送り、取得上限、有効フラグ） |
| `tags.yaml` | 登録タグ（id、名称、説明、関連キーワード、有効フラグ）。廃止は削除せず `enabled: false` |
| `tag_overrides.yaml` | 記事ごとのタグ修正（追加・除外）。画面のタグ ＝ AIタグ ＋ 追加 － 除外 |
| `site.yaml` | サイト名、修正依頼リンクURL、release_mode（demo/real）、表示件数 |

タグや情報源の変更は、Claude Code に「○○というタグを追加して」のように依頼してください。変更後は下の検証コマンドで形式を確認します。

## 必要なツールと確認方法

Python の処理（収集・AI処理・検証・テスト）は、主に Claude Code Web版のクラウド環境で実行します。
PCで画面を見るだけなら Git と Node.js があれば足ります（下の「PC（Windows）で画面を見る」を参照）。

以下は Windows PowerShell の例です。PowerShell は、スタートメニューで「PowerShell」と入力して開きます。

| ツール | 用途 | 確認コマンド | 成功時の表示の例 |
|---|---|---|---|
| Git | リポジトリの取得 | `git --version` | `git version 2.xx.x.windows.1` |
| Node.js（LTS版） | 画面のビルドと表示（段階1-a以降） | `node --version` | `v22.xx.x` など |
| npm（Node.jsに同梱） | 画面の部品のインストール | `npm --version` | `10.x.x` など |
| Python 3.11以上 | 検証・テストをPCでも動かしたい場合のみ（任意） | `python --version` | `Python 3.11.x` など |

「認識されません」と表示された場合は、そのツールが入っていません。
- Git：https://git-scm.com/download/win からインストールします。
- Node.js：https://nodejs.org/ja から「LTS」と書かれた版をインストールします。
- Python（任意）：https://www.python.org/downloads/windows/ からインストールし、最初の画面で「Add python.exe to PATH」にチェックを入れます。

インストール後は PowerShell を一度閉じて開き直してから、確認コマンドを実行してください。

## テストと検証の実行方法

リポジトリのフォルダ（`README.md` があるフォルダ）で実行します。

### クラウド環境（Claude Code）・Linux・Mac

```bash
python3 -m venv .venv                       # Python の作業用環境を作る（初回のみ）
.venv/bin/pip install -r requirements.txt   # 必要な部品を入れる（初回と requirements.txt 変更時）
.venv/bin/python -m pytest                  # テストを実行する
.venv/bin/python -m collector.validate      # config/ と data/ を検証する
```

### Windows PowerShell（任意）

```powershell
cd $HOME\Documents\info_test_rs                     # cloneしたフォルダへ移動（場所は環境に合わせる）
python -m venv .venv                                # 作業用環境を作る（初回のみ）
.\.venv\Scripts\pip install -r requirements.txt     # 必要な部品を入れる
.\.venv\Scripts\python -m pytest                    # テストを実行する
.\.venv\Scripts\python -m collector.validate        # config/ と data/ を検証する
```

### 成功時の表示

- テスト：最後に `176 passed` のように表示され、`failed` がなければ成功です（件数は今後増えます）。
- 検証：`OK: 設定とデータはスキーマ検証を通過しました` と表示されれば成功です。
  問題があると `NG: 1 件の問題があります` に続けて、ファイル名と問題の箇所が表示されます。

## 画面用JSONを作る（公開用変換）

`config/` と `data/`（または `demo/`）から、画面に出してよい項目だけを取り出して `web/public/data/` に3つのファイルを作ります。

| ファイル | 内容 |
|---|---|
| `meta.json` | サイト名、修正依頼リンク、release_mode、タグ一覧、情報源一覧 |
| `articles.json` | 記事の一覧と詳細（日付と根拠、概要、論点、タグとその由来、AI処理状態、版の履歴） |
| `status.json` | 取得状況（最終実行、最終全情報源成功、情報源ごとの成否、日付不明・未要約の件数、実行履歴） |

```bash
.venv/bin/python -m collector.export                # config/site.yaml の release_mode に従う（今は demo）
.venv/bin/python -m collector.export --mode demo    # 架空データ（demo/）から作る
.venv/bin/python -m collector.export --mode real    # 実データ（data/）から作る
```

成功すると `OK: demo モードで記事 20 件の画面用JSONを …/web/public/data に出力しました` と表示されます。
入力データに問題があるときや、出力に秘密値らしい文字列が含まれるときは `NG:` と理由が表示され、ファイルは書き換えられません。

画面用JSONに **含めないもの**：原文全文、AI APIの生応答、AIのタグ候補（`data/tag_candidates.json`）、`.cache/` の中身、APIキー等の秘密値。
タグは「AIタグ ＋ 追加 － 除外」（追加・除外は `config/tag_overrides.yaml`）で計算し、AIが付けたものか人が追加したものかを区別して出力します。

架空データを作り直すとき（内容を変えたいときだけ）：

```bash
.venv/bin/python scripts/make_demo_data.py          # demo/data と demo/config/tag_overrides.yaml を作り直す
.venv/bin/python -m collector.validate --demo       # 架空データを検証する
.venv/bin/python -m collector.export --mode demo    # 画面用JSONを作り直す
```

## 画面のテスト（クラウド環境・開発用）

```bash
cd web
npm ci              # 部品を入れる
npm test            # 画面のテスト（絞り込み、XSS対策、架空データ表示など）。「Tests  33 passed」なら成功
npm run typecheck   # 型の確認。何も表示されなければ成功
npm run build       # 型の確認と公開用ファイルの作成
npm run build:standalone   # 1ファイル版 viewer/info_viewer.html を作り直す
```

画面用JSON（`web/public/data/`）や画面のプログラムを変えたら、`npm run build:standalone` で1ファイル版も作り直してコミットします（古いままだと Python のテスト `tests/test_viewer.py` が失敗して気づけます）。

## コミット前の安全確認

`.env`（秘密値）、`.cache/`（原文・生応答）、`node_modules/`、ログ、APIキーらしい文字列がコミット対象に入っていないかを確認します。テスト（`pytest`）でも同じ確認をしています。

```bash
.venv/bin/python scripts/check_repo_safety.py           # Gitで管理されている全ファイルを確認
.venv/bin/python scripts/check_repo_safety.py --staged  # git add 済みのファイルだけを確認
git config core.hooksPath .githooks                     # コミットのたびに自動で確認する（cloneごとに一度だけ）
```

成功すると `OK: .env・.cache/・秘密値はコミット対象に含まれていません` と表示されます。問題があるとコミットが止まり、該当するファイルが表示されます。

## 公開に関する注意

このリポジトリは部署レビュー後に public へ切り替える予定です。過去のコミット履歴も公開されるため、APIキーなどの秘密値、原文全文、内部情報はコミットしません。`.env` と `.cache/` は `.gitignore` で除外しています。
