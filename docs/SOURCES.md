# 情報源の調査結果（こども・母子保健）

2026-10-02 に、この開発環境（Claude Code Web版、ネットワークアクセス Full）から確認した結果。採用・候補の設定は `config/sources.yaml` にある（候補は `enabled: false`）。

| | 機関・ページ | URL | 取得方式 | 取得できる範囲 | robots.txt | 利用条件 | 状態 |
|---|---|---|---|---|---|---|---|
| ① | こども家庭庁「新着・更新」 | https://www.cfa.go.jp/news | HTML一覧（RSSは見つからず） | 1ページ約10件、`?page=N` で過去分（約290ページ）。各件に種別と掲載日（`<time datetime>`） | `/news` は許可（禁止は `/admin/`・`/search/` 等） | 公共データ利用規約（PDL1.0）。出典の記載で利用可 https://www.cfa.go.jp/copyright-policy | **採用**（`cfa-news`） |
| ② | 厚生労働省「新着情報」 | https://www.mhlw.go.jp/stf/news.rdf | RSS 1.0 | 直近数日分の約120件（省全体） | 禁止は `/cgi-bin/`・`/images/` 等のみ | PDL1.0 https://www.mhlw.go.jp/chosakuken/index.html | 候補（`mhlw-news`、無効）。母子保健と無関係な記事が多い |
| ③ | 国立成育医療研究センター「新着情報」 | https://www.ncchd.go.jp/news/ | HTML一覧（RSSなし） | 1ページに過去分約300件。各行に掲載日（`.h_date`） | 禁止は `/mt/` のみ | 著作権保護、**無断転載・複製は禁止**（引用は出所明示） https://www.ncchd.go.jp/site.html | 候補（`ncchd-news`、無効）。採用前に広報へ確認 |
| ④ | e-Gov パブリックコメント | public-comment.e-gov.go.jp | — | — | 確認できず | — | **この環境からはブロックされる**（HTTP 403「アクセスがブロックされています」） |

## 情報源を追加するとき

1. Claude Code に「② を有効にして」「〇〇のページを情報源に追加して」のように頼む。
2. 環境のネットワークアクセスで、そのドメインへの接続を許可する（Full なら不要）。
3. Claude Code が試し読み（`--dry-run`：一覧だけを読み、本文は取得せず保存もしない）で題名・日付が正しく取れるかを確認し、必要なら `link_rules`（`item_selector`・`title_selector`・`date_selector`・`include`/`exclude`）を調整する。
4. 少数（`--max-items 5`）だけ取得して、出典・本文・日付の根拠を確認してから本運用に入れる。
