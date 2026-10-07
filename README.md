# 外部環境情報収集MVP（info_test_rs）

中央官庁・公的機関の公開情報を収集し、短い概要と登録済みタグを付けて、最新一覧とテーマ別Wikiで閲覧するための個人開発の検証版です。

> 現在は **段階3-a**（AI要約・タグ付けの実装。テストは模擬のみ）まで進んでいます。こども家庭庁の新着5件を取得済みで、画面は実データ表示です。実際のAIによる要約はまだ行っていません（段階3-bで、費用の承認後に実行）。
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
| `collector/` | Pythonの処理（収集、スキーマ検証、公開用変換、週次レポート） |
| `demo/` | 架空のデモデータ（`demo/data/`）と、その情報源・タグ修正（`demo/config/`） |
| `web/` | 画面（TypeScript＋Vite）。`web/src/` がプログラム、`web/tests/` が画面のテスト |
| `web/public/data/` | 画面用JSON（公開用変換の出力。画面はこれだけを読む） |
| `viewer/info_viewer.html` | 画面とデータを1つにまとめたファイル（ダブルクリックで開ける。実データ） |
| `viewer/info_viewer_demo.html` | 同じく架空データ版 |
| `docs/SOURCES.md` | 情報源の調査結果と、追加するときの手順 |
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

画面とデータを1つにまとめたファイル `viewer/info_viewer.html`（実データ）を開きます。架空データの画面は `viewer/info_viewer_demo.html` です。インターネットへの通信は行わず、ファイルの中だけで動きます。

1. ブラウザで https://github.com/inukaitk/info_test_rs/blob/main/viewer/info_viewer.html を開きます（GitHubへのサインインが必要です）。
2. ファイル表示の右上にある **下向き矢印のボタン（Download raw file）** を押します。「ダウンロード」フォルダに `info_viewer.html` が保存されます。
3. エクスプローラーで「ダウンロード」フォルダを開き、`info_viewer.html` を **ダブルクリック** します。ブラウザで画面が開きます。
4. 「最新情報」に記事が並んでいれば成功です（`info_viewer_demo.html` の場合は上部に赤い帯で「**架空データ**」と表示されます）。

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

  ➜  Local:   http://localhost:5173/info_test_rs/
```

ブラウザ（Edge や Chrome）で **http://localhost:5173/info_test_rs/** を開きます（公開時と同じく、リポジトリ名のフォルダの下で動きます）。
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
npm run preview    # 作ったファイルで画面を起動する。http://localhost:4173/info_test_rs/ を開く
```

### 画面の使い方

画面上部のメニューから切り替えます。どの画面もURL（`#/wiki/…` など）をそのまま共有・ブックマークできます。右上には **修正依頼** のリンクがあります（`config/site.yaml` の `correction_request_url`。未設定なら「未設定」と表示）。

| 画面 | 内容 |
|---|---|
| **最新情報**（最初に開く画面） | 直近7日間（最終収集日を含む）に**公開された記事**（公開日が不明な記事は取得日で数えます）。取得状況の注意、週次レポート・Wiki・修正依頼へのリンクも表示します。日数は `config/site.yaml` の `latest_days` |
| **記事を探す** | 全期間の記事をタグ・機関・期間（公開日）で絞り込み、文字検索（空白区切りは「すべてを含む」）。期間で絞り込むと日付不明の記事は含めず、その件数を知らせます。絞り込み結果を **CSV・JSONで保存** できます（CSVはExcelで開けます） |
| **Wiki** | タグごとの説明と、該当する記事を公開日の年月ごとに新しい順で並べます（全期間）。日付不明の記事は最後に別枠で表示します |
| **週次レポート** | 期間（最終収集日までの7日ごと）を選び、新規・変更の記事、タグ別件数、情報源別の取得状況を表示します。**Markdownで保存** でファイルにできます |
| **取得状況** | 最終実行、最終全情報源成功、情報源ごとの成否・失敗理由・探索できた範囲、日付不明・本文未取得・未要約の件数、実行履歴。データが古いとき（`site.yaml` の `stale_after_days` を超えたとき）や失敗が続く情報源があるときは注意を表示します |
| **情報源** | 収集中の情報源と候補（未採用）の一覧。URL、取得方式（RSS／HTML一覧、添付PDFを読むか）、取得状況、制約・メモ（`config/sources.yaml` の `notes`） |
| **記事詳細** | タイトルを押すと開きます。出典リンク、日付とその根拠、概要・論点・対象・確認できた日付、タグとその由来、AI処理状態、変更履歴 |

タグの見分け方：青い「AI」はAIが付けたタグ、点線で橙色の「人が追加」は人が追加したタグ、取り消し線は人が外したタグです。

## 自動更新とWeb公開（GitHub Actions と Pages）

`.github/workflows/weekly-update.yml` が、**毎週日曜の日本時間15時**に次を自動で行います（協定世界時 日曜6時。混雑時は遅れたり、まれに抜けたりします）。

1. こども家庭庁（採用した情報源）から新しい記事を収集する
2. AIで要約・タグ付けする（Secrets の `INFO_AI_API_KEY` を使う。費用の目安は週に十数件で約$0.3）
3. 検証・テストを通ったら、`data/` などを `main` にコミットする
4. そのコミットから画面を作り、GitHub Pages に公開する

公開された画面に、実行ボタンはありません。手動で動かせるのは、リポジトリの **Actions** タブからだけです（書き込み権限のある人のみ）。

### 最初に一度だけ行う設定（GitHubの画面）

1. **Secrets**：リポジトリの **Settings** → **Secrets and variables** → **Actions** → **New repository secret** で、Name を `INFO_AI_API_KEY`、Secret に新しいAPIキーを入れて **Add secret**（登録済み）
2. **Pages**：**Settings** → **Pages** → **Build and deployment** の **Source** を **GitHub Actions** にする
3. **確認の実行**：**Actions** タブ → 左の「週次更新と公開」→ 右の **Run workflow** → **Run workflow**。緑のチェックになれば成功。完了後、Settings → Pages の上部、またはワークフローの実行画面の `deploy` に出るアドレス（`https://（アカウント名）.github.io/info_test_rs/`）で画面を開く

うまくいかないとき：赤いバツの実行を開き、失敗した手順のログを確認します。AIの手順だけが失敗した場合は、収集できた記事が「未要約」と表示された状態で公開されます。

## 外部連携用CSV

「週次レポート」のページの「Markdownで保存」の横の **「CSVで保存」** で、選んでいる週の「新規」と「変更」の記事を、固定の15列のCSVで保存できます。別のシステムで、記事を分析するためのものです（公開情報だけで、評価・重要度などの列はありません）。

- 列と形式のひな形：`docs/csv/external_news_template.csv`（架空のサンプル3行つき）。UTF-8 BOM付き、カンマ区切り、CRLF。Windowsの表計算ソフトで、そのまま開けます。
- ファイル名：`external_news_YYYYMMDD_HHmm.csv`（日本時間）。
- `excerpt` は本文の抜粋ではなく、このサイトで作った要約と主な論点です。公開日が日まで分からない記事は含まれません。
- `content_hash` は、題名と本文のSHA-256です。本文を取得できない記事は空欄で、`hash_status` が `unavailable` になります。
- 情報源を足すときは、`config/sources.yaml` に `csv_id`（固定ID。変えない）、`publisher`、`source_type` を書きます。

## ルールで付けるタグ（キーワード一致）

`config/tags.yaml` の `auto_rules` に書いた言葉が、記事の題名・本文にあれば、そのタグを自動で付けます（AIは使わず、費用はかかりません）。現在は「ベンダ動向」に、ベンダ名・製品名の言葉を登録しています。

- 言葉を足す・変える：`auto_rules` の `label`（画面に出す名前）と `pattern`（探す言葉。正規表現）を編集します。Claude Code に頼めば、編集してくれます。
- 実行：毎週の自動更新に入っています。手元で試すには `.venv/bin/python -m collector.rule_tags --dry-run`（保存せず、件数だけ表示）。
- 画面では、タグの左に「一致」と出ます。AIが付けたタグは「AI」、各ベンダ自身のサイトの記事に設定で付けたタグは「設定」です。記事詳細に、一致した名前と場所（題名・本文）が出ます。
- 本文は GitHub Actions では残らないため、本文のある環境（このクラウド環境など）で実行すると、本文で判定します。本文がない記事は、題名だけで判定します。

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

- テスト：最後に `309 passed` のように表示され、`failed` がなければ成功です（件数は今後増えます）。
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

## 収集する（クラウド環境で実行）

情報源（`config/sources.yaml`）から記事を集めて `data/` に保存します。段階2-aでは **テスト用の架空サイト（`tests/fixtures/web/`）だけ** で動かしています。

```bash
# テスト用の架空サイトから収集（実際のWebにはアクセスしない）。出力先は /tmp/fxdata（data/ は変えない）
.venv/bin/python -m collector.collect --fixtures tests/fixtures/web/manifest.yaml \
    --config-dir tests/fixtures/web/config --data /tmp/fxdata --start 2026-09-01 --end 2026-09-30
```

| 指定 | 意味 |
|---|---|
| `--start 2026-09-01 --end 2026-09-30` | 期間（日本時間、両端の日を含む）。公開日・更新日で判定し、**日付不明の記事は期間内と推定せず別枠で保存・報告**します。省略すると、前回の成功から14日さかのぼった日〜今日（初回は30日前〜今日） |
| `--source 情報源id` | 指定した情報源だけ（複数指定可） |
| `--data フォルダ` | 保存先（省略時は `data/`） |
| `--fixtures 対応表` | テスト用。URL とファイルの対応表で応答し、ネットワークに出ない |
| `--allow-network` | **実際のWebへアクセスする**。採用した情報源で、段階2-b以降に使います（付けないと実行できません） |
| `--cache フォルダ` | 抽出した本文の保存先（既定 `.cache/`、Gitに入らない。AI要約で使う） |

表示の例：

```
注意: 収集一部失敗（新規 10件、変更 0件、変化なし 0件、日付不明 2件、取得失敗 1件）
  - fx-news-rss: success（候補 8件）
      警告：許可ホスト以外のリンクを除外：許可ホスト以外です: evil.example.com
  - fx-broken: failed（候補 0件） 理由：一覧ページを取得できません：HTTP 500
  - fx-empty-rss: success（候補 0件）
      警告：一覧から記事を1件も抽出できませんでした（抽出規則が壊れている可能性があります）
```

- `OK:` はすべて成功、`注意:` は一部の情報源や記事が失敗（成功した分は保存済み）、`NG:` はすべて失敗です。
- 同じ期間で再実行しても記事は重複しません。本文が変わった記事は「版」が増えます（メニューやフッターだけの変化は無視）。
- 失敗した情報源は「最後に成功した時点」を進めず、次回に同じ範囲をもう一度確認します。本文の取得に失敗した記事は「再試行待ち」になり、次回自動で再取得します。
- 収集後に `python -m collector.export --mode real` で画面用JSONを作ると、画面に表示されます。

### 実際の情報源から取得する（段階2-b以降）

```bash
.venv/bin/python -m collector.collect --allow-network --dry-run --source cfa-news    # 試し読み（一覧だけ。保存しない）
.venv/bin/python -m collector.collect --allow-network --source cfa-news --max-items 5 # 少数だけ取得して data/ に保存
.venv/bin/python -m collector.export                                                 # 画面用JSONを作る
cd web && npm run build:standalone                                                   # 1ファイル版を作り直す
```

### 添付PDFも読む

情報源の設定に `attachments: {pdf: true, ...}` があると、記事ページからリンクされた PDF（報道発表資料・会議資料など）も読み、本文に加えます（1記事3件・1件10MB・30ページまで。座席図などは除外）。読めたかどうかは画面の記事詳細の「添付資料」に表示されます。PDFの本文は `.cache/` にだけ保存し、画面には出しません。画像として作られたPDFは読めません。

### 情報源を追加する

`config/sources.yaml` に候補（厚生労働省・国立成育医療研究センター）が `enabled: false` で入っています。Claude Code に「厚生労働省を有効にして」のように頼めば、有効化・試し読み・少数取得まで行います。新しいサイトを足すときも「〇〇のページを情報源に追加して」と頼めます。詳しくは `docs/SOURCES.md`。

## AIで要約・タグ付けする（段階3）

記事の本文（`.cache/text/`）を Claude API（Anthropic）に渡し、短い概要・論点・対象・確認できた日付・登録タグを作ります。設定は `config/ai.yaml`（モデル、考える量、1回の件数・文字数・トークン・再試行の上限、価格）。

```bash
.venv/bin/python -m collector.summarize --plan   # 処理予定の件数と概算費用を表示するだけ（APIは呼ばない・費用なし）
.venv/bin/python -m collector.summarize          # 実行する（APIキーが必要。費用が発生する）
.venv/bin/python -m collector.export             # 画面用JSONを作り直す
```

モデルを比べるとき（段階3-b で Sonnet と Haiku を比較する）：

```bash
.venv/bin/python -m collector.summarize --plan --model claude-haiku-4-5                         # モデルごとの概算費用
.venv/bin/python -m collector.summarize --model claude-sonnet-5-5 --compare-out /tmp/sonnet.json  # 結果をファイルにだけ書く（data/ は変えない）
.venv/bin/python -m collector.summarize --model claude-haiku-4-5  --compare-out /tmp/haiku.json
```

運用に使うモデルは、比較の結果を見て `config/ai.yaml` の `model` で決めます。価格は同じファイルの `prices` に、モデルごとに書いてあります。

- **APIの費用は Claude Code の契約とは別で、API の利用料として個人負担で発生します。**
- APIキーがないときは「AI未実行」として記録され、収集と画面の作成はそのまま動きます。
- 本文のキャッシュ（`.cache/`）はセッションをまたいで残りません。新しいセッションでは、先に `python -m collector.collect --allow-network --source cfa-news --max-items 5` を実行して本文を取り直してから要約します。
- 失敗（APIエラー・出力の形の誤り・登録外タグ・上限超過・拒否）は「未要約（理由）」として記録され、次回の実行で再処理されます。成功した記事は、本文・モデル・指示文の版・タグ定義が変わらない限り再処理しません。

### APIキーの準備（ユーザーが行う。キーをチャットに貼らない）

1. **Claude Console**（https://platform.claude.com/ ）にサインインし、支払い方法を登録します。
2. **利用上限を設定**します（使いすぎ防止。必ず先に行う）。
   - 組織全体：Console の「Settings → Billing」（https://platform.claude.com/settings/billing ）で月の上限額を設定します。
   - さらに絞るなら：この用途専用のワークスペースを作り、そのワークスペースに月の上限額を設定します（Console の「Settings → Workspaces」、またはレート制限の画面 https://platform.claude.com/settings/limits ）。
   - 上限に達すると、APIは翌月まで（または上限を上げるまで）止まり、エラーになります。
3. Console の「API Keys」で、（専用ワークスペースの）APIキーを作成します。表示されたキーは一度しか見られないので、そのまま次の手順で貼り付けます。**チャットやリポジトリ、メールには貼らないでください。**
4. **Claude Code Web版の環境変数に登録**します：Claude Code の画面で、セッションのタイトル部分にあるクラウド環境のメニュー →「Edit」→ 環境変数に
   ```
   INFO_AI_API_KEY=（作成したキー）
   ```
   を追加して保存します（`=` の前後に空白を入れない）。**新しいセッションから有効**になります。
   - `ANTHROPIC_API_KEY` という名前は Claude Code 自身の認証と重なるため、セッションに渡りません（設定画面にも「リクエストの認証には使用されません」と表示されます）。必ず `INFO_AI_API_KEY` の名前で登録してください。
   - 環境変数は、この環境を使える人には見えます。この環境は自分だけで使ってください。
5. **ネットワークアクセス**：環境のネットワーク設定が Full 以外なら、許可するドメインに **`api.anthropic.com`** を追加します。

キーを止めたいときは、Console の「API Keys」でキーを無効化（削除）します。

## 週次レポートを Markdown ファイルで出す

画面の「Markdownで保存」と同じ内容を、リポジトリの `reports/` に出力します（クラウド環境で実行）。

```bash
.venv/bin/python -m collector.report                # 最新の週を reports/ に出力（release_mode に従う）
.venv/bin/python -m collector.report --mode demo --all   # 架空データの全週を reports/demo/ に出力
```

成功すると `OK: …/weekly_2026-09-22_2026-09-28.md を出力しました（新規 4件、変更 1件）` のように表示されます。

## 画面のテスト（クラウド環境・開発用）

```bash
cd web
npm ci              # 部品を入れる
npm test            # 画面のテスト（絞り込み、XSS対策、架空データ表示など）。「Tests  56 passed」なら成功
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

このリポジトリは public です（部署レビューの前に切り替え。切り替え前に全コミット履歴を検査済み、DECISIONS.md）。Pages の画面もインターネット上で誰でも見られます。過去のコミット履歴も公開されるため、APIキーなどの秘密値、原文全文、内部情報はコミットしません。`.env` と `.cache/` は `.gitignore` で除外しています。
