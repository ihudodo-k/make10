# Make10 デイリーの集計（Cloudflare Workers + D1）

デイリーの「みんなの結果」を数えるサーバー。仕様は `DAILY-SPEC.md` の 17 章。
送り先は `https://api.make10.app/r`（Workers の Custom Domain）。
D0.37 から、記録を別の端末へ移すための受け口（`/x`・`/x/take`）も持つ（仕様は `DAILY-SPEC.md` の 10-1）。

| ファイル | 中身 |
|---|---|
| `src/index.js` | Worker の本体（`POST /r` で足す・`GET /r?n=` で読む・`POST /x` で預かる・`POST /x/take` で渡して消す） |
| `schema.sql` | D1 の表（`days`: 1 日＝問題番号を 1 行。1 件ごとの行は持たない／`xfer`: 移すために預かった中身。10 分か、受け取られたら消す） |
| `wrangler.toml` | 設定（名前・Custom Domain・起点日・D1 のつなぎ先・移す受け口の回数の制限 `XFER_LIMIT`） |
| `test/local_test.mjs` | 手元の試し（断る 25 通り・100 件同時を 2 回・帯の境目・移す受け口の 13 項目） |
| `package.json`・`package-lock.json` | wrangler の版を固定する |

`node_modules/` と `.wrangler/` は Git に入れない（`.gitignore`）。

## 手元で試す（本番には触らない）

Node が要る（22 で確かめた）。

```
cd worker
npm install          # 初回だけ。wrangler が入る
npm test             # wrangler を手元で立ち上げ、手元の D1 で試す
```

- `npm test` は、データを毎回一時フォルダに作り、終わったら消す。Cloudflare へのログインは要らない
- 起点日は、試しのあいだだけ「今日が #11」になる日に差し替える（`wrangler.toml` の値は書き換えない）。
  預かる時間（本番は 10 分）も、試しのあいだだけ 3 秒に縮める（`XFER_TTL_MS`）
- 回数の制限は、手元の wrangler も数える。試しは `CF-Connecting-IP` を組ごとに変えて名乗る
- 1 つでも落ちたら終了コード 1

## 本番へ置く（人が行う。お金はかからない範囲 ―― Workers Free）

**1 回だけ行う準備**

1. Cloudflare にログインする（ブラウザが開く。`make10.app` のゾーンがあるアカウントで）
   ```
   npx wrangler login
   ```
2. D1 のデータベースを作る。出てきた `database_id` を、`wrangler.toml` の `database_id = "…"` に書く
   ```
   npx wrangler d1 create make10-daily
   ```
3. 表を作る（本番の D1 に）
   ```
   npm run schema:remote
   ```

**置く（デプロイ）**

4. 起点日が、ページと同じであることを確かめる（`python verify_daily.py --case server` が見る。
   起点日を変えるときは、リポジトリの直下で `python make10.py daily` を流す ―― ページと `wrangler.toml` の両方に書く）
5. 置く。`wrangler.toml` の `routes` に `api.make10.app`（`custom_domain = true`）が書いてあるので、
   **このコマンドが `api.make10.app` の DNS のレコードと証明書も作る**（Custom Domain の設定）
   ```
   npm run deploy
   ```
   - ダッシュボードで設定したいときは、`wrangler.toml` の `routes` の 3 行を消してから置き、
     Workers & Pages → make10-daily-api → Settings → Domains & Routes → Add → Custom Domain に `api.make10.app` を入れる
6. 動いていることを確かめる（公開の前は起点日が遠い未来なので、どの問題番号も `{"e":"range"}` で断られるのが正しい）
   ```
   curl -i -H "Origin: https://make10.app" "https://api.make10.app/r?n=1"
   ```
   - `HTTP/2 400`・`{"e":"range"}`・`access-control-allow-origin: https://make10.app` が返れば、つながっている
   - `Origin` を付けないと `403`・`{"e":"origin"}`

**D0.37（別の端末へ移す）を置くとき（1 回だけ）**

- 表 `xfer` を本番の D1 に足す。`schema.sql` はどの表も `CREATE TABLE IF NOT EXISTS` なので、もう一度流してよい（`days` の数は消えない）
  ```
  npm run schema:remote
  ```
- そのあと `npm run deploy`。回数の制限（`wrangler.toml` の `[[ratelimits]]`。Workers の Rate Limiting）は、置くと付く
  （無料のプランで使えるかは、置いたときに wrangler が知らせる。付いていない環境では、Worker は数えずに通す）
- 確かめ（`Origin` を付けて、形の違うコードを送ると 400 が返る。つながっていれば、預けも消しもしない）
  ```
  curl -i -X POST -H "Origin: https://make10.app" -H "Content-Type: text/plain" --data "{\"c\":\"x\"}" https://api.make10.app/x/take
  ```
  - `HTTP/2 400`・`{"e":"body"}` が返れば、つながっている（置く前の Worker なら `404`・`{"e":"path"}`）
- **置くまでは、ページの「別の端末へ移す」は「通信できませんでした」になる**（ページは先に公開される）

**公開のとき（DAILY-SPEC 18-1 の⑪）**

- 起点日を公開日の月曜に直して（`make10.py` の `DAILY_START`）、`python make10.py daily` → `npm run deploy`
- 試しのデータを本番に入れていないこと（入れてしまったら `npx wrangler d1 execute make10-daily --remote --command "DELETE FROM days"`）

## 値の決まり

- 受け付ける問題番号は、サーバーの今の日付（UTC）から見て前後 1 日（時間帯の差のぶん）
- 時間は 1〜86,400 秒の整数（ギブアップのときは見ない）。ヒントは 0〜2。結果は `s`（解いた）か `g`（ギブアップ）
- `Origin` が `https://make10.app` でない要求は断る
- 時間の帯は 30 秒未満・1 分未満・2 分未満・5 分未満・5 分以上（`src/index.js` の `BANDS`。ページの側と同じ値にする）
- 移す受け口（D0.37）: コードは見間違えやすい字を除いた 31 字の 6 文字（`CODE_CHARS`。ページの `MOVE_RE` と同じ）・
  預かるのは 10 分・受け取ったらその場で消す（読むのと消すのは 1 文）・中身は 262,144 文字まで・
  1 つの IP から 1 分に 10 回まで（IP は数えるのに使うだけで、D1 には書かない）
