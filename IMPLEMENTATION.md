# 外部環境情報収集MVP 実装指針

作成日 2026年10月1日 / 版 0.3

SPEC.mdを満たすための推奨設計。既存リポジトリがある場合は既存の技術を優先する。採用するパッケージ・モデル・Actionは実装時に公式資料で現行仕様を確認し、依存バージョンを固定する。

## 1 全体構成

| 要素 | 初期の選択 | 担当する処理 |
|---|---|---|
| 開発 | Claude Code Web版（クラウド環境） | コード、設定、テスト、説明書の作成、収集・AI処理の試行 |
| 収集とAI | PythonのCLI | RSS/HTML/PDF取得、本文抽出、重複処理、AI API呼び出し |
| 永続データ | 小規模なJSONファイル | 記事、版、要約、実行履歴、情報源の成功地点 |
| 閲覧 | TypeScriptとViteの静的サイト | 一覧、検索、詳細、Wiki、週次レポート、取得状況 |
| 定期実行（段階4以降） | GitHub Actions | CLI実行、データ保存、公開用変換、ビルド |
| 配信（段階4以降） | GitHub Pages | ビルド済みの静的ファイル |

サーバーや外部DBは追加しない。ブラウザから公的サイトを直接取得したり、APIキーを使ってAIを呼び出したりしない。段階3-bまでの収集・AI処理はClaude Code Web版のクラウド環境で実行し、結果のdata/をコミットする。PCでは画面の閲覧だけを行うので、PC側に必要なのはGitとNode.jsだけになるようにする。

クラウド環境のネットワークアクセスは環境ごとの設定に従う。採用した情報源とAI APIのドメインが許可されていない場合、取得は失敗する。失敗したときは、ネットワーク制限によるものかサイト側の問題かを区別して報告する。

## 2 ファイル構成

```text
CLAUDE.md
README.md
docs/handoff/SPEC.md
docs/handoff/IMPLEMENTATION.md
docs/DECISIONS.md
config/sources.yaml
config/tags.yaml
config/tag_overrides.yaml
config/site.yaml
schemas/
collector/
tests/fixtures/
tests/
data/articles/
data/summaries/
data/runs/
data/state.json
data/tag_candidates.json
demo/
reports/
web/
.env.example
.gitignore
.cache/            （Git管理外）
```

原文本文、一時PDF、API生応答は.cache/に置き、Gitと公開物から除外する。.cache/はセッションをまたいで残らないため、必要になれば再取得する。リポジトリは将来publicにするため、Gitに入れるものはすべて公開されても問題ない内容に限る。

## 3 設定とデータ

設定はYAML。人が変更する設定（config/）と自動処理が生成するデータ（data/）を分ける。設定ファイルもスキーマ検証する。

### 3.1 設定

| ファイル | 主な項目 |
|---|---|
| sources.yaml | id、機関名、入口URL、取得方式（rss/html/manual）、許可ホスト、記事リンク規則、ページ送り規則、タイムゾーン、取得上限、有効フラグ |
| tags.yaml | id、名称、説明、関連キーワード、有効フラグ |
| tag_overrides.yaml | article_id、追加するtag_ids、除外するtag_ids、更新日、理由（任意・公開される前提で書く） |
| site.yaml | サイト名、修正依頼リンクURL、release_mode（demo/real）、表示件数 |

タグは管理者がClaude Codeに指示してtags.yamlを編集する。Claude Codeは、自社の関心や判断が読み取れるタグ名・説明（特定製品への影響、営業機会、要対応など）を追加するよう指示された場合、SPEC 3章を示して確認を求める。

タグを無効化しても、過去の記事に付いた記録は消さない。画面では無効タグを非表示または「廃止」と表示する。

### 3.2 保存レコード

| レコード | 主な項目 |
|---|---|
| article | article_id、source_id、canonical_url、title、published_at、updated_at、date_basis、date_precision、first_seen_at、last_seen_at、latest_version、status |
| article_version | article_id、version、content_hash、取得日時、抽出状態、変更種別 |
| summary | article_id、article_version、summary、key_points、targets、dates（各日付に原文の根拠）、ai_tags（tag_idと理由）、uncertainties、analysis_status、model、prompt_version、tags_version、usage、処理日時 |
| run | run_id、開始・終了、実行方法、指定期間、情報源別の結果、件数、失敗、API使用量 |
| source_state | source_id、最終探索成功時刻、探索範囲、再試行対象、連続失敗数 |
| tag_candidate | 候補名、理由、提案元のarticle_id、初出日時 |

画面に出す最終的なタグは「ai_tags ＋ 追加 － 除外」で計算する。AIの再処理ではsummaryだけを更新し、tag_overrides.yamlには書き込まない。

article_idは正規化URLから決定的に生成する。日付・内容・AIモデルの変化でIDを変えない。URL正規化はフラグメントと既知の追跡パラメーターを除く程度にし、意味のあるクエリーを安易に削除しない。

## 4 収集処理

1. 設定を検証し、対象の情報源を確定する。
2. RSSまたは一覧ページから候補URLを列挙する。ページ送りは上限内で追い、探索した範囲を記録する。
3. URLとリダイレクト先が許可ホストか検証する。localhost、内部IP、file等の非HTTPスキームは拒否する。
4. 件数・サイズ・待機時間・timeoutを制限して取得する。User-Agentを設定し、利用条件とrobots.txtを確認し、アクセス負荷を抑える。
5. 本文・タイトル・日付・PDFのテキストを抽出する。ナビゲーションやフッターの変化を本文の変更と誤判定しない。
6. published_atとupdated_atの根拠を保存する。HTTPのLast-Modifiedだけで公開日を確定しない。first_seen_atは発見日として扱う。
7. 正規化URLと本文hashで新規・変更・既存を判定する。既存記事は消さず、意味のある本文変更には版を追加する。
8. 結果を一時ファイルへ書き、検証後に置き換える。情報源ごとに成功地点を管理する。

### 4.1 期間指定

CLIの--start/--endはYYYY-MM-DD、Asia/Tokyoの両端を含む日付。内部では開始日0時以上・終了日の翌日0時未満に変換する。日付しかない記事は日付の精度も記録する。対象は情報源の一覧ページ等に残っている範囲であり、消えた過去情報の復元は対象外。

### 4.2 週次と失敗

各情報源の前回成功地点から、初期値14日程度の重複確認期間を設ける。一部の情報源が失敗しても成功分は保存するが、失敗した情報源の成功地点は進めない。本文取得失敗とAPI処理失敗は再試行対象に登録する。HTTP取得成功と要約成功は別の状態として持つ。取得件数0件が正常か抽出規則の破損かを区別できるよう、急減や抽出0件を警告する。

画像PDF・動的ページ・取得禁止のサイトは未対応として記録し、タイトルとURLの手動登録で代替できるようにする。OCRやブラウザ自動操作は追加しない。

## 5 AI処理（要約とタグ付け）

providerとmodelは設定で指定し、1つだけ実装する。現行のSDK・API仕様・価格は実装時に公式資料で確認し、確認日をDECISIONS.mdに記録する。APIキーがない場合は「AI未実行」と表示し、キーワード一致などの結果をAIの結果として扱わない。

### 5.1 入力

抽出本文、出典URL、公開日、有効な登録タグの一覧（id・名称・説明）。本文は信頼できないデータとして明確に区切り、本文中の「指示」「ツール実行要求」「秘密の開示要求」には従わせない。LLMにURL取得・shell・Git操作等の権限を渡さない。

### 5.2 出力と検証

出力はJSONスキーマで検証する。

- summary：200字程度までの日本語の概要。原文で確認できる事実だけを書く。
- key_points：主要な論点（5件まで）。
- targets：対象者・対象機関。
- dates：施行日・締切等。原文の短い根拠引用がないものは出力させない。
- ai_tags：登録タグのidと選んだ理由。登録外のidは検証で拒否する。
- new_tag_suggestions：登録外で必要と思われるタグ名と理由。tag_candidatesへ記録し、画面には出さない。
- uncertainties：確認できなかった点。

検証に失敗した出力、APIエラー、上限超過は、それぞれの状態で記録して画面に「未要約」と表示する。成功扱いにしない。

### 5.3 キャッシュと上限

本文hash、model、prompt_version、tags_version（タグ定義のhash）をキャッシュキーにし、変更がない記事は再処理しない。タグ定義を変えた場合は再処理対象を一覧で示し、実行は管理者の指示で行う。

1回あたりの件数、入力文字数、トークン量、再試行回数に上限を設ける。実使用量を記録し、価格表を確認できた場合は概算費用を計算する。概算だけで課金上限を保証しないので、API側の利用上限も設定する。APIキーがなくても収集と画面ビルドは動作させる。

## 6 静的画面

日本語で、落ち着いた見た目とし、情報の比較と根拠の確認を優先する。チャットUIや凝った装飾は追加しない。

- トップ：最終更新、取得状況の要約、新着件数、修正依頼リンク。
- 最新一覧：日付、機関、タイトル、概要、タグ。絞り込みと文字検索。
- 記事詳細：SPEC 4.5の項目。タグはAI付与と人の修正を区別して表示する。
- Wiki：タグごとの説明、期間別の記事リンク。
- 週次レポート：期間内の新規・変更、タグ別件数、情報源別の取得状況。
- 取得状況：情報源ごとの成否、失敗理由、日付不明件数、未処理件数。

検索は公開用JSONに対してブラウザ内で行う。Viteのbaseをリポジトリ名のサブパスに対応させ、hashルーティングを使って直リンクの404を避ける。取得した文字列はエスケープし、HTML/MarkdownのレンダリングでXSS対策をする。

release_mode=demoのときは架空データだけを使い、全画面に「架空データ」と表示する。release_mode=realのときは実データを使う。

## 7 公開を前提とした安全策

リポジトリをpublicにする予定のため、段階0から次を守る。

- 公開用変換はallowlist方式とし、許可したフィールドだけを画面用JSONへ出力する。原文全文、API生応答、tag_candidates、ログは含めない。
- .env、.cache/、ログを.gitignoreに入れる。秘密値や.cache/がコミット対象に入っていないかを確認するテスト（またはpre-commit）を用意する。
- APIキーはClaude Code Web版の環境変数（段階4以降はGitHub Secrets）にだけ置き、チャット・コード・ログ・JavaScriptへ書かない。ローカルで実行する場合は.envを使う。
- 開発中はprivateリポジトリで進める。publicへ切り替える前に、全コミット履歴に秘密値・原文全文・内部情報が含まれていないことを検査する。

## 8 段階と完了の証拠

| 段階 | 実装内容 | 完了の証拠 |
|---|---|---|
| 0-a | 計画、DECISIONS.md、設定・データのスキーマ、設定例 | スキーマ検証テストの通過 |
| 0-b | 架空デモデータ、公開用変換、秘密値混入の検査 | 許可項目以外が出力されないテストの通過 |
| 1-a | 一覧・詳細・絞り込み・検索 | ローカル起動、架空データ表示の確認 |
| 1-b | Wiki・週次レポート・取得状況・修正依頼リンク | ビルド成功、サブパスと直リンクの確認 |
| 2-a | RSS/HTML/PDF収集、期間・版・失敗処理（fixture） | 重複・日付境界・本文変更・部分失敗のテスト通過 |
| 2-b | 情報源の候補提示、選定後の少数実取得 | 実記事の出典・日付根拠・取得状況の画面確認 |
| 3-a | AI要約・タグ付け（モック） | スキーマ検証、登録外タグ拒否、異常系、タグ修正の維持のテスト通過 |
| 3-b | 実APIで少数件 | 件数と概算費用の提示、承認後の実行、原文との照合結果 |

各段階が終わったら報告して止まり、次の段階は管理者の指示で始める。

## 9 テスト

オフラインのfixtureで、URL重複、日付境界と日付不明、本文変更とナビ変化、部分失敗時のstate、AI出力のJSON異常、登録外タグ、APIキーなし、上限超過、タグ修正の維持、タグ定義変更時の再処理対象、公開用変換の除外項目、XSS、サブパスでの表示を検証する。

実データの確認は、管理者が選んだ情報源で少数件に限る。fixtureの通過を実収集の成功として扱わない。

## 10 段階4以降の参考（部署レビュー後に詳細化）

- CI：pull_requestとpushで、秘密値なしのスキーマ検証・オフラインテスト・型検証・ビルド。
- 収集と公開：workflow_dispatchとscheduleで収集・要約し、データをcommitしてSHAを確定し、同じworkflow内でそのSHAから公開用変換・ビルド・Pages配信を行う。GITHUB_TOKENによるpushで別workflowが連鎖実行されると期待しない。
- 週次の案は月曜08:17 JST（UTCでは日曜23:17、cron「17 23 * * 0」）。実装時に現行のschedule仕様を確認する。定期実行には遅延・欠落があり得る。publicリポジトリでは無活動による定期実行の停止もあり得る。
- APIキーはGitHub Secretsに置く。Actionsのログはpublicリポジトリでは公開されるため、本文や生応答をログに出さない。

## 11 実装時に確認する公式資料

2026年10月1日時点で参照。設定や契約は実装時に再確認する。

- GitHub Pagesの性質と利用プラン https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
- Actionsのイベントとschedule https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- 定期workflowの無活動停止 https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows
- Secrets https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- Claude Codeの費用と利用方式 https://code.claude.com/docs/en/costs
- Anthropic APIを選ぶ場合の公式文書 https://platform.claude.com/docs/en/home

モデル名、API価格、パッケージの版はこの資料で固定しない。採用時に調べたURLと確認日を記録する。
