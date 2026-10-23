# Make10 デイリーの集計（Cloudflare Workers + D1）

デイリーの「みんなの結果」を数えるサーバー。仕様は `DAILY-SPEC.md` の 17 章。
送り先は `https://api.make10.app/r`（Workers の Custom Domain）。
D0.37 から、記録を別の端末へ移すための受け口（`/x`・`/x/take`）も持つ（仕様は `DAILY-SPEC.md` の 10-1）。

| ファイル | 中身 |
|---|---|
| `src/index.js` | Worker の本体（`POST /r` で足す・`GET /r?n=` で読む・`POST /x` で預かる・`POST /x/take` で渡して消す） |
| `schema.sql` | D1 の表（`days`: 1 日＝問題番号を 1 行。1 件ごとの行は持たない／`xfer`: 移すために預かった中身。受け取られたら消す。10 分を過ぎた行は受け取れず、次に誰かが預けたときか、そのコードで受け取ろうとしたときに消す。期限に索引 `xfer_x`（D0.44）） |
| `schema_each.mjs` | `schema.sql` の文を 1 つずつ `wrangler d1 execute --command` で流す（`npm run schema:remote` と `npm test` が使う。2026-10-21）。改行が CRLF の `schema.sql`（Windows の Git が取り出した形）でも分けられる（2026-10-23） |
| `wrangler.toml` | 設定（名前・Custom Domain・起点日・D1 のつなぎ先・移す受け口の回数の制限 `XFER_LIMIT`） |
| `test/local_test.mjs` | 手元の試し（断る 25 通り・100 件同時を 2 回・帯の境目・移す受け口の 13 項目・中身の上限の 12 項目・索引の 1 項目・返事のヘッダーの 1 項目・表を作る文の分け方の 1 項目） |
| `package.json`・`package-lock.json` | wrangler の版を固定する |

`node_modules/` と `.wrangler/` は Git に入れない（`.gitignore`）。

## コマンドの書き方（Windows の PowerShell）

この README のコマンドは、Windows の PowerShell で打つ形で書いてある。この PC では Node が PATH に入っていないので、開いた PowerShell で最初に 1 行流す（その窓の中だけ効く）
```
$env:Path = "C:\Users\0ihud\tools\node-v22.23.3-win-x64;" + $env:Path
```
- `npm`・`npx` は `npm.cmd`・`npx.cmd` と書く（`npm` だけだと `npm.ps1` が選ばれ、スクリプトの実行の制限で止まることがある）
- `curl` は `curl.exe` と書く（Windows PowerShell 5.1 では `curl` が `Invoke-WebRequest` の別名）
- **`--remote` を付けたコマンド（`npm.cmd run schema:remote`・`npx.cmd wrangler d1 execute … --remote`）や `npm.cmd run deploy` が `Authentication error [code: 7403]`・`[code: 10000]` で落ちたら、ログインし直してからもう一度流す**（2026-10-21 はこれで直った）
  ```
  npx.cmd wrangler logout
  npx.cmd wrangler login
  ```

## 手元で試す（本番には触らない）

Node が要る（22 で確かめた）。

```
cd worker
npm.cmd install          # 初回だけ。wrangler が入る
npm.cmd test             # wrangler を手元で立ち上げ、手元の D1 で試す
```

- `npm.cmd test` は、データを毎回一時フォルダに作り、終わったら消す。Cloudflare へのログインは要らない
- 起点日は、試しのあいだだけ「今日が #11」になる日に差し替える（`wrangler.toml` の値は書き換えない）。
  預かる時間（本番は 10 分）も、試しのあいだだけ 3 秒に縮める（`XFER_TTL_MS`）
- 回数の制限は、手元の wrangler も数える。試しは `CF-Connecting-IP` を組ごとに変えて名乗る
- 1 つでも落ちたら終了コード 1

## 本番へ置く（人が行う。お金はかからない範囲 ―― Workers Free）

**1 回だけ行う準備**

1. Cloudflare にログインする（ブラウザが開く。`make10.app` のゾーンがあるアカウントで）
   ```
   npx.cmd wrangler login
   ```
2. D1 のデータベースを作る。出てきた `database_id` を、`wrangler.toml` の `database_id = "…"` に書く
   ```
   npx.cmd wrangler d1 create make10-daily
   ```
3. 表を作る（本番の D1 に）
   ```
   npm.cmd run schema:remote
   ```
   - `schema.sql` の文を、1 つずつ `--command` で流す（`schema_each.mjs`）。`--file`（Cloudflare の `/import` を使う）は、
     本番で `Authentication error [code: 10000]` で落ちたため（2026-10-21。`--command` は通った）。どの文も `IF NOT EXISTS` なので、もう一度流してよい
   - `schema_each.mjs` が使えないときは、同じことを手で 1 文ずつ流す（`schema.sql` の文を 1 行にして `--command` に入れる）。例:
     ```
     npx.cmd wrangler d1 execute make10-daily --remote --command "CREATE INDEX IF NOT EXISTS xfer_x ON xfer (x)"
     ```
   - `Authentication error [code: 7403]`・`[code: 10000]` で落ちたら、ログインし直す（上の「コマンドの書き方」）

**置く（デプロイ）**

4. 起点日が、ページと同じであることを確かめる（`python verify_daily.py --case server` が見る。
   起点日を変えるときは、リポジトリの直下で `python make10.py daily` を流す ―― ページと `wrangler.toml` の両方に書く）
5. 置く。`wrangler.toml` の `routes` に `api.make10.app`（`custom_domain = true`）が書いてあるので、
   **このコマンドが `api.make10.app` の DNS のレコードと証明書も作る**（Custom Domain の設定）
   ```
   npm.cmd run deploy
   ```
   - ダッシュボードで設定したいときは、`wrangler.toml` の `routes` の 3 行を消してから置き、
     Workers & Pages → make10-daily-api → Settings → Domains & Routes → Add → Custom Domain に `api.make10.app` を入れる
6. 動いていることを確かめる（公開の前は起点日が遠い未来なので、どの問題番号も `{"e":"range"}` で断られるのが正しい）
   ```
   curl.exe -i -H "Origin: https://make10.app" "https://api.make10.app/r?n=1"
   ```
   - `HTTP/2 400`・`{"e":"range"}`・`access-control-allow-origin: https://make10.app` が返れば、つながっている
   - `Origin` を付けないと `403`・`{"e":"origin"}`

**D0.37（別の端末へ移す）を置くとき（1 回だけ）**

- 表 `xfer` を本番の D1 に足す。`schema.sql` はどの表も `CREATE TABLE IF NOT EXISTS` なので、もう一度流してよい（`days` の数は消えない）
  ```
  npm.cmd run schema:remote
  ```
- そのあと `npm.cmd run deploy`。回数の制限（`wrangler.toml` の `[[ratelimits]]`。Workers の Rate Limiting）は、置くと付く
  （無料のプランで使えるかは、置いたときに wrangler が知らせる。付いていない環境では、Worker は数えずに通す）
- 確かめ（`Origin` を付けて、形の違うコードを送ると 400 が返る。つながっていれば、預けも消しもしない）
  ```
  curl.exe -i -X POST -H "Origin: https://make10.app" -H "Content-Type: text/plain" --data '{"c":"x"}' https://api.make10.app/x/take
  ```
  - `HTTP/2 400`・`{"e":"body"}` が返れば、つながっている（置く前の Worker なら `404`・`{"e":"path"}`）
- **置くまでは、ページの「別の端末へ移す」は「通信できませんでした」になる**（ページは先に公開される）

**公開のとき（DAILY-SPEC 18-1 の⑪）**

公開日（月曜）の**前日まで（たとえば日曜の昼）**に済ませる。全体の手順は `CLAUDE.md` の「前日にやること」。ここはサーバーの分。
**サーバーを先に置き、確かめてから、ページを push する**（ページが先だと、公開日の結果が `range` で断られ、ページが送った印を付けるので二度と数えられない）。

1. 起点日を公開日の月曜に直して（`make10.py` の `DAILY_START`）、リポジトリの直下で `python make10.py daily`（ページと `wrangler.toml` の両方に書く）
2. 試しのデータを本番に入れていないこと（入れてしまったら `npx.cmd wrangler d1 execute make10-daily --remote --command "DELETE FROM days"`）
3. `worker/` の中で、試してから置く
   ```
   npm.cmd test
   npm.cmd run deploy
   ```
4. 確かめ。サーバーは起点日の前日（UTC。日本では日曜の 9 時）から 1 問目を受け付ける
   ```
   curl.exe -i -H "Origin: https://make10.app" "https://api.make10.app/r?n=1"
   ```
   - 日曜の 9 時を過ぎていれば `200`・`{"n":1,…}`（新しい起点日が入った）。それより前なら、まだ `400`・`{"e":"range"}` が正しい
5. ここまで済んでから、ページを push する

## 値の決まり

- 受け付ける問題番号は、サーバーの今の日付（UTC）から見て前後 1 日（時間帯の差のぶん）
- 時間は 1〜86,400 秒の整数（ギブアップのときは見ない）。ヒントは 0〜2。結果は `s`（解いた）か `g`（ギブアップ）
- `Origin` が `https://make10.app` でない要求は断る
- 時間の帯は 30 秒未満・1 分未満・2 分未満・5 分未満・5 分以上（`src/index.js` の `BANDS`。ページの側と同じ値にする）
- 移す受け口（D0.37）: コードは見間違えやすい字を除いた 31 字の 6 文字（`CODE_CHARS`。ページの `MOVE_RE` と同じ）・
  預かるのは 10 分・受け取ったらその場で消す（読むのと消すのは 1 文）・中身は 262,144 文字まで・
  1 つの IP から 1 分に 10 回まで（IP は数えるのに使うだけで、D1 には書かない）

**D0.43〜D0.45（公開前の安全の点検）を置くとき（1 回だけ）**

- 索引 `xfer_x` を本番の D1 に足す（D0.44）。`schema.sql` は `CREATE … IF NOT EXISTS` だけなので、もう一度流してよい（数も預かった中身も消えない）
  ```
  npm.cmd run schema:remote
  ```
- `npm.cmd test` が全部通ることを見てから `npm.cmd run deploy`

## Cloudflare の WAF の回数制限（人が行う。1 回だけ。公開前の安全の点検の H2）

`Origin` の確かめは、ブラウザ以外（curl）からは偽れる。偽った要求を大量に送られると、Workers の無料の回数（1 日 10 万回）と
D1 の書き込み（1 日 10 万行）を使い切られ、その日のあいだ集計とデータ移行が止まる。そこで、Worker が動く前に Cloudflare の WAF で止める
（止めた要求は Workers の回数にも D1 にも入らない）。決まりは `DAILY-SPEC.md` の 17-3。

1. Cloudflare のダッシュボード → `make10.app` のゾーン → Security → WAF → **Rate limiting rules** → Create rule
2. 名前: `api-rate`（何でもよい）
3. 当てる要求（Edit expression で書く）:
   ```
   (http.host eq "api.make10.app" and http.request.uri.path in {"/r" "/x" "/x/take"})
   ```
4. 数え方: **同じ IP**（Characteristics は IP）で、**10 秒に 5 回**（Requests 5・Period 10 seconds）を超えたら
5. すること: **Block**、続ける時間 **10 秒**（Duration 10 seconds）。返事は既定のまま（429）
6. Deploy

- 止めた返事（429）には CORS のヘッダーが付かないので、ページからは通信の失敗に見える。集計は送れなかった日を次に開いたときに送り直し、
  データ移行は「通信できませんでした。時間をおいて試してください」と出す（`verify_daily.py` のケース `inputs` が、この形の返事で確かめている）
- 同じ IP を多くの人で使う回線（学校・会社・携帯の回線の一部）では、ふつうに遊んでいても 10 秒に 5 回を超えることがありうる。
  そのときも、送れなかった集計は次に開いたときに送り直す

**確かめ**（Windows の PowerShell なら `curl.exe` と書く。`curl` だけだと別のコマンドになる）。同じ IP から 6 回続けて送ると、6 回目が 429 になる
（公開前は、1〜5 回目は `{"e":"range"}` の 400）。10 秒待つと、また 400 に戻る
```
for /l %i in (1,1,6) do @curl.exe -s -o NUL -w "%{http_code}\n" -H "Origin: https://make10.app" "https://api.make10.app/r?n=1"
```
（PowerShell では `1..6 | % { curl.exe -s -o NUL -w "%{http_code}`n" -H "Origin: https://make10.app" "https://api.make10.app/r?n=1" }`）

**本番での結果**（2026-10-21。人が設定して確かめた）: 設定（10 秒に 5 回・Block 10 秒・Active）は正しいのに、
約 0.45 秒おきに 20 回送って、429 は 19 回目の 1 回だけだった。Cloudflare の数え方が緩い（決めた回数ちょうどでは止まらない）ためと考え、
このまま公開することにした（ユーザーが決めた）。
大量の送信を続けられたときは、ある程度の数を超えてから止まる。

**攻撃が続くなら、Workers の有料プラン（Workers Paid）に切り替える。** 無料の回数（Workers 1 日 10 万回・D1 の書き込み 1 日 10 万行）を
使い切られると、その日のあいだ集計とデータ移行が止まる。有料のプランは上限が大きく、超えた分は使った量に応じて払う形なので、止まりにくい
（その代わり、送られた分だけお金がかかる。切り替えは人が行う）。
