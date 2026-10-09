# Make10 デイリーの集計（Cloudflare Workers + D1）

デイリーの「みんなの結果」を数えるサーバー。仕様は `DAILY-SPEC.md` の 17 章。
送り先は `https://api.make10.app/r`（Workers の Custom Domain）。

| ファイル | 中身 |
|---|---|
| `src/index.js` | Worker の本体（`POST /r` で足す・`GET /r?n=` で読む） |
| `schema.sql` | D1 の表（1 日＝問題番号を 1 行。1 件ごとの行は持たない） |
| `wrangler.toml` | 設定（名前・Custom Domain・起点日・D1 のつなぎ先） |
| `test/local_test.mjs` | 手元の試し（断る 25 通り・100 件同時を 2 回・帯の境目） |
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
- 起点日は、試しのあいだだけ「今日が #11」になる日に差し替える（`wrangler.toml` の値は書き換えない）
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

**公開のとき（DAILY-SPEC 18-1 の⑪）**

- 起点日を公開日の月曜に直して（`make10.py` の `DAILY_START`）、`python make10.py daily` → `npm run deploy`
- 試しのデータを本番に入れていないこと（入れてしまったら `npx wrangler d1 execute make10-daily --remote --command "DELETE FROM days"`）

## 値の決まり

- 受け付ける問題番号は、サーバーの今の日付（UTC）から見て前後 1 日（時間帯の差のぶん）
- 時間は 1〜86,400 秒の整数（ギブアップのときは見ない）。ヒントは 0〜2。結果は `s`（解いた）か `g`（ギブアップ）
- `Origin` が `https://make10.app` でない要求は断る
- 時間の帯は 30 秒未満・1 分未満・2 分未満・5 分未満・5 分以上（`src/index.js` の `BANDS`。ページの側と同じ値にする）
