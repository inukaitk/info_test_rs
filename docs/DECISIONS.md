# 決定事項と未確定事項

合理的で元に戻せる技術選択は開発中に決め、理由をここに短く記録する。リポジトリは将来publicになるため、ここにも公開して問題ない内容だけを書く。

## 前提（SPEC v0.3 から引き継ぐ決定事項）

- 対象は中央官庁・公的機関の公開情報と、一般的な分類タグだけ。自社製品の評価、重要度・優先度、内部メモ、顧客・案件情報は扱わない。
- 自社の関心や判断が読み取れるタグ（特定製品への影響、営業機会、要対応など）は作らない（SPEC 3章）。
- 初期の対象領域はこども・母子保健。情報源は2〜3から始める。
- 公開物に出すのは独自の短い概要、タグ、出典リンク、日付とその根拠だけ。原文全文や元PDFは出さない。
- 開発中はprivateリポジトリ。部署レビュー後にpublicへ切り替え、Pagesで全体公開する予定。履歴も公開されるため、Gitに入れるものはすべて公開される前提で扱う。
- 今回の作業範囲は段階3-bまで。publicへの切り替え、Pages公開、Actionsの定期実行はユーザーの明示的な指示まで行わない。
- ブラウザからの編集機能は作らない。タグや情報源の変更は、ユーザーの指示でClaude Codeが設定ファイルを編集する。
- AIの新規タグ候補は data/tag_candidates.json に記録するだけで、tags.yaml へ自動追加せず、画面にも出さない。
- APIキーはクラウド環境の環境変数にだけ置き、チャット・Git・ログ・JavaScriptへ書かない。

## 技術の決定（段階0-a、2026-10-02）

| 決定 | 理由 |
|---|---|
| Python 3.11 系、依存は requirements.txt で版を固定（PyYAML 6.0.3、jsonschema 4.26.0、pytest 9.1.1） | IMPLEMENTATIONの推奨。クラウド環境のPythonが3.11。版固定で再現性を保つ |
| 仮想環境は `.venv/`（Git管理外） | 標準の venv だけで済み、追加ツールが不要 |
| スキーマは JSON Schema（draft 2020-12）で schemas/ に置き、YAMLの設定もJSONのデータも同じ仕組みで検証する | 画面側（TypeScript）からも同じスキーマを使える。言語に依存しない |
| スキーマで書けない整合性（タグidの存在、IDとファイル名の一致、版の連番など）は `collector/validation.py` で確認する | 設定ファイルをまたぐ確認はスキーマでは表現しにくい |
| YAMLは重複キーを拒否し、日付（2026-10-01）を日付型に変換せず文字列として読む | 書き間違いの見逃し防止。日付の形式をスキーマで一律に確認するため |
| article_id は `a_` ＋ 正規化URLのSHA-256先頭16桁 | 正規化URLから決定的に決まり、日付・内容・AIモデルが変わってもIDが変わらない（IMPLEMENTATION 3.2） |
| run_id は `run_` ＋ 開始時刻（UTC、例 run_20260915T230000Z） | 時系列に並び、ファイル名にそのまま使える |
| 日時はタイムゾーン付きのISO 8601必須。公開日・更新日は精度に応じて YYYY / YYYY-MM / YYYY-MM-DD / 日時 | 日付だけ分かる記事を推定で日時にしないため。精度は date_precision に別記録 |
| 公開日が不明なら published_at は null、精度 unknown、根拠 null をスキーマで強制。根拠の方法に HTTP Last-Modified を含めない | 日付不明を推定で埋めない。Last-Modifiedだけで公開日を確定しない（IMPLEMENTATION 4章） |
| summary は analysis_status が success 以外なら内容欄（summary、ai_tags等）をすべて null にすることをスキーマで強制。success で該当タグなしは空配列 | 失敗を成功や「タグなし」として扱わないため |
| summary に new_tag_suggestions と API生応答は保存しない | 候補は tag_candidates へ、生応答は .cache/ のみ（公開しない） |
| 日付の根拠引用は200字まで、要約は300字まで（目安200字） | 原文の転載にならない短さに抑える。目安を少し超える出力で即失敗にしないための余裕 |
| データのファイル配置：`data/articles/<article_id>.json`（記事＋全版）、`data/summaries/<article_id>.json`（要約履歴）、`data/runs/<run_id>.json`、`data/state.json`（情報源id→状態）、`data/tag_candidates.json`。各ファイルに `schema_version: 1` | 記事単位でファイルが分かれ、差分が読みやすい。将来の形式変更を検出できる |
| sources.yaml の timezone は当面 Asia/Tokyo のみ許可 | 対象が国内の公的機関だけのため。必要になれば広げる |
| 架空の情報源には予約済みの例示用ドメイン（example.org / example.net / example.com）と「架空」「デモ」を含む名称を使う | 実在の機関・URLと誤認されないようにする |
| 廃止タグ（enabled: false）は tag_overrides で add できないが remove はできる | 廃止タグを新たに付けず、過去に付いたものは外せるようにする |

## 未確定事項

| 項目 | 決める時期 | 現状 |
|---|---|---|
| 採用する情報源（機関名、URL、取得方式） | 段階2-b（候補提示後にユーザーが選定） | config/sources.yaml は架空の3件 |
| 情報源ごとの利用条件・robots.txt・取得できる範囲 | 段階2-b | 未確認 |
| AI provider とモデル、価格 | 段階3-a（公式資料を確認して確認日とURLを記録） | 未定。Claude Codeの契約にAPI費用は含まれない前提 |
| prompt_version の付け方 | 段階3-a | 未定 |
| 修正依頼リンクのURL（Microsoft Forms等） | ユーザーが用意した時点 | config/site.yaml で null（画面では「未設定」） |
| サイト名 | 部署レビューまで | 仮に「外部環境情報（検証版）」 |
| Pagesのサブパス（リポジトリ名） | 段階1-b | 仮に info_test_rs |
| 週次の重複確認期間（初期値14日程度） | 段階2-a | 未設定 |
| 1回あたりの件数・トークン・再試行の上限値 | 段階3-a | 未設定 |
| 段階4（Actions・Pages公開）・段階5の要否と内容 | 部署レビュー後 | 対象外 |
