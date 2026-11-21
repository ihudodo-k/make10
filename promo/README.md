# X への毎日の投稿と、反応の記録（promo/）

デイリー（https://make10.app/daily/ ）の問題を、毎日 1 本 X（旧 Twitter）に投稿し、反応を表に残す仕組み。
**文の型（4 つ）と画像の型（3 つ）を問題番号で順に試し、その後で人が選んで続ける。型を自動で選ぶ処理は無い**（決めるのは人）。

`docs/` の外なので配信されない。デイリーのページ（`docs/daily/`）とサーバー（`worker/`）には触らない（ページは読むだけ）。

## 仕組み

| いつ（UTC） | 日本 | 何をする | 中身 |
|---|---|---|---|
| 毎日 8:00 | 17:00 | `promo/collect.py` | X・Cloudflare Web Analytics・みんなの結果の数を集めて CSV に足し、まとめ（`report.md`）を書き直す |
| 毎日 8:30 | 17:30 | `promo/post.py` | その日の問題の画像（`promo/image.py`）を付けて 1 本投稿し、`posts.csv` に 1 行足す |

- 動かすのは GitHub Actions の `.github/workflows/promo.yml`。**時刻に起こすのは Cloudflare Workers の Cron Triggers**（`promo/cron/`。
  下の「定期実行の起こし役」）。promo.yml の `schedule` は予備として残してある。**main に入ってから動く**
- 集めた CSV は **main ではなく、専用のブランチ `promo-data`** に bot がコミットする（`promo/data/` の中。main の履歴を汚さない・
  公開ページを動かさない）。最初の実行で、空のブランチとして作られる
- 失敗したらワークフローが失敗になり、GitHub の標準の通知（メール）が届く（`site-check` と同じ。届く先の設定は CLAUDE.md の見守りの手順）
- collect と post は同時に走らない（`concurrency`）。どちらも、始める前に手元の試し（`test_promo.py --no-chrome`）を流し、落ちたら何もしない

### なぜ日本の 17:30 か

問題番号は **UTC の日付**で数える（集計のサーバーと同じ）。ページは端末の日付で数えるので、UTC 8:30 なら、
日本（17:30）・ヨーロッパ（朝）・アメリカ本土（西海岸は夏時間で 1:30・冬時間で 0:30）のどこでも、ページは投稿と同じ問題を出す。
冬時間の西海岸は UTC 8:00 に日付が変わるので、それより後にした。**ハワイ（UTC-10）と、冬時間のアラスカ（UTC-9）は、まだ前の日の問題**
（ハワイと、冬時間の西海岸の UTC 7:30 と 8:30 は、`test_promo.py` がページの JS で確かめている）。GitHub の定期実行（`schedule`）は
2026-10-26・27 に約 6 時間遅れて走った（collect 8:00 → 14:39・13:44、post 8:30 → 15:19）ので、時刻は Cloudflare から起こす（下）。

## 定期実行の起こし役（`promo/cron/`。Cloudflare Workers の Cron Triggers）

Cloudflare の Worker `make10-promo-cron` が、UTC 8:00 と 8:30 に GitHub の API
（`POST /repos/ihudodo-k/make10/actions/workflows/promo.yml/dispatches`、`ref` は `main`）で promo.yml を起こす。
集計のサーバー（`worker/`・`make10-daily-api`）とは別の Worker で、そちらには触らない。

| Cron（UTC） | 送る inputs | promo.yml の中 |
|---|---|---|
| `0 8 * * *` | `task: collect`・`dry_run: false` | `TASK=collect`・`DRY=false`（schedule のときと同じ） |
| `30 8 * * *` | `task: post`・`dry_run: false` | `TASK=post`・`DRY=false`（schedule のときと同じ） |

- 中身は `src/dispatch.js`（入口は `src/index.js`。**`index.js` に名前付きの export を置かない** ―― Workers が入口として読み、起動しない）。
  Cron の式は `wrangler.toml` の `[triggers]` と `dispatch.js` の `JOBS` の両方に書く（食い違いは試しが止める）
- **HTTP の入口は何もしない**（どの道も 404。`workers.dev` の URL も routes も無い）。外から叩いて投稿させることはできない
- GitHub が 204 以外を返したら、状態と本文の先頭（300 字）をログに出す。2xx 以外は失敗にする
  （Cloudflare のダッシュボードの Workers & Pages → make10-promo-cron → Logs と、Settings の Trigger Events に残る）
- **予備の `schedule` と両方が走っても壊れない**: post はその日の行が `posts.csv` にあれば送らない。collect は同じ日の行を上書きする
  （約 24 時間の値 `m24_*` は初めて集めたときだけ書くので、後から来た collect では変わらない）。`concurrency` で同時には走らず、
  後から来た分は前の分が `promo-data` に書いた後で始まる。待っている分は、さらに後から来た分に置き換わる（GitHub の決まり）が、
  Cloudflare の 2 つは時刻どおりに来るので、どの順でも、その日の collect と post は 1 回ずつは走る
- 手元の試し（鍵なし。GitHub には送らない）: `promo/cron/` の中で `npm.cmd test`。送る URL・inputs・ヘッダー、204 以外の扱い、
  404、式の一致、promo.yml の `TASK`・`DRY` の式、本物のランタイム（`wrangler dev --test-scheduled`。鍵を入れずに立ち上げる）を見る。
  `promo/cron/.dev.vars` は作らない（あると試しの 6 番は止まる）

### GitHub の鍵を作る（人が行う）

1. GitHub の右上のアイコン → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
2. Token name は `make10-promo-cron` など。**Expiration は期限を決める**（たとえば 1 年）。**期限の日を控える**（切れる前に作り直す）
3. Repository access は **Only select repositories** で `ihudodo-k/make10` だけ
4. Permissions → Repository permissions で **Actions を Read and write** にする。ほかは触らない（Metadata の Read は自動で付く）
5. Generate token を押し、出た値（`github_pat_…`）をすぐ下の「入れる」に使う。**ファイル・コミット・チャットには書かない**

### 入れる・置く・確かめる（人が行う。PowerShell で）

コマンドの書き方は `worker/README.md` の「コマンドの書き方」と同じ（最初に Node のパスを足す・`npm.cmd`・`npx.cmd` と書く）。

```
$env:Path = "C:\Users\0ihud\tools\node-v22.23.3-win-x64;" + $env:Path
cd C:\ゲーム\make10\promo\cron
npm.cmd ci
npm.cmd test
npx.cmd wrangler login
npx.cmd wrangler deploy
npx.cmd wrangler secret put GH_TOKEN
```

- `deploy` を先にする（Worker ができてから、その Worker に secret を入れる）。`deploy` と `secret put` は続けて流す
  （間に UTC 8:00 か 8:30 が来ると、その回は「GH_TOKEN が無い」で失敗し、予備の `schedule` だけが走る）
- `secret put` は値を聞いてくるので、作った鍵を貼って Enter（画面には出ない）。入れた鍵はすぐに効く（deploy し直さなくてよい）
- `Authentication error [code: 7403]`・`[code: 10000]` で落ちたら `npx.cmd wrangler logout` → `npx.cmd wrangler login`
- 確かめ:
  1. `npx.cmd wrangler deployments list` に今の deploy が出る。ダッシュボードの make10-promo-cron → Settings → Trigger Events に `0 8 * * *` と `30 8 * * *`
  2. `npx.cmd wrangler secret list` に `GH_TOKEN` が出る（値は出ない）
  3. 次の UTC 8:00（日本の 17:00）の後に、GitHub の Actions → promo に **event が workflow_dispatch** の実行が数分のうちに並ぶ
     （予備の schedule の実行は、event が schedule で、遅れて並ぶ）。ログの「何を流すか」が `task=collect dry_run=false event=workflow_dispatch`
  4. 8:30 の後も同じく `task=post dry_run=false event=workflow_dispatch` で、X に 1 本出る。遅れて来た schedule の post は「送ってある。送らない」で終わる
  5. 起こせなかったときは `npx.cmd wrangler tail make10-promo-cron` を流したまま次の時刻を待つか、ダッシュボードの Logs を見る

### 止める・鍵の期限が切れたら

- **Cloudflare から起こすのを止める**: ダッシュボードの make10-promo-cron → Settings → Trigger Events で Cron を消す。
  または `wrangler.toml` の `crons = []` にして `npx.cmd wrangler deploy`。Worker ごと消すなら `npx.cmd wrangler delete make10-promo-cron`。
  予備の `schedule` は残るので、promo そのものは遅れて走り続ける（全部止めるのは下の「止め方」）
- GitHub の鍵を消すと（Developer settings → Fine-grained tokens → Delete）、その時から起こせなくなる
- **鍵の期限が切れたときの症状**: Cloudflare からは起こせず（ログに `GitHub が 204 以外を返した: 401 … Bad credentials`）、
  **予備の `schedule` だけが遅れて走る**（Actions の promo の実行が event schedule だけになり、数時間遅れる）。
  GitHub からは失敗のメールが来ない（promo.yml は失敗していない）ので、遅れに気づいたらまず鍵の期限を見る。
  直し方は、上の「GitHub の鍵を作る」で作り直して、`npx.cmd wrangler secret put GH_TOKEN` で入れ直す（deploy は要らない）

### 投稿の文（4 つの型。版 5）

よく伸びている数学パズルの投稿にならって、**短い 1〜2 行 ＋ `#Make10`** にした（版 4。2026-11-21〜。版 5 で B に順の決まりを足した）。
型は問題番号で順に回す（(番号 - 1) を 4 で割った余り。#1 が A・#2 が B・#3 が C・#4 が D・#5 が A…）。
画像の型（下。3 つ）と周期がずれるので、**12 日で文と画像の全部の組み合わせが 1 回ずつ出る**。例は 6 8 2 3 の日。

| 型 | 文 |
|---|---|
| A | `Make 10 with 6, 8, 2, 3 — in this order. Can you?` |
| B | `Looks easy. Is it?` ／ `6, 8, 2, 3 → 10, in this order. Reply with your answer.` |
| C | `Four digits, one target: 10.` ／ `6, 8, 2, 3 — in this order.` |
| D | `Today's digits: 6, 8, 2, 3.` ／ `Keep the order. Make 10.` |

どの型も最後の行は `#Make10`（ハッシュタグはこれ 1 つだけ）。**どの型にも順の決まり（`in this order` か `Keep the order`）を入れる**（並べ替えた答えの返信が来たため。試しが全日 × 4 型で確かめる）。

- **リンクは付けない**（リンク付きの投稿は API の料金が高い。リンクはプロフィールに置く）。**文にリンクの案内も書かない**
- **答えは載せない。根拠の無い数字（「1% しか解けない」など）や、嘘になる言い回しは使わない。** 送る前に `post.py` が、決まった形か・
  数字がその日の問題か・列の解答のどれも入っていないか・演算の記号が無いか・280 字以内かを確かめ、外れたら送らずに失敗にする。
  試し（`test_promo.py`）は、全日 × 4 型で、数が 4 つの数字と 10 のほかに無いこと・ハッシュタグが `#Make10` だけなことも見る
- 字数は X の数え方（英数字や `·`・`—` は 1 字、`→` や `−` や日本語は 2 字）で 280 字まで。いちばん長い文でも 70 字ほど
- B は返信で答えを促すので、返信に答えが並ぶ（ネタばれになる）ことがある
- 文の版: 版 1 は #1・#2 の短い文。版 2 は 2026-10-27 からの文（`link in profile` と `#DailyPuzzle`）。版 3 は画像が付き、
  リンクの案内を消し、ハッシュタグ 3 つ・型 C に昨日のみんなの結果の行（集計が 30 件未満なら除き、`c_note` に理由）・型 B に使える記号の行。
  **版 4 で、昨日の結果の行と記号の行と 3 つのハッシュタグをやめ、型を 4 つにした**（`c_note` は前の行のために列だけ残す）。
  **版 5 は、B の 2 行目に `, in this order` を足しただけ**（版 4 の B には順の決まりが無く、並べ替えた答えの返信が来た）

### 画像（`promo/image.py`）

毎日の投稿に、その日の問題の画像（**縦長 1080×1350・4:5**）を付ける。

- 絵: 大きな穴埋めの式「6 ? 8 ? 2 ? 3 = 10」・その下の小さな「Use + − × ÷ ^ ! ( )」・並べ替えの禁止の 1 行
  「Keep the order. Don't swap the digits.」・右下の小さな「Make10 #番号」の 4 つだけ（禁止の行は、数字を並べ替えた答えの返信が来たので足した）。
  **答えや手がかりは載せない**（渡すのは番号・4 つの数字・制約だけ。撮る前に、画面の文字が決まった並びと同じかを確かめる）
- 制約がある日（全体の約 37%）は、使えない記号を「Use」の行から消す（代わりの文の記号と同じ並び。どちらも `common.allowed_syms`。
  全日で同じことを `test_promo.py` が確かめる）
- **見た目の型は 3 つ**。問題番号で順に回す（`image.style_of`。#1 が 1・#2 が 2・#3 が 4・#4 が 1…）。`posts.csv` の `style` に残す

| 型 | 地 | 字 | 色 | 形式 |
|---|---|---|---|---|
| 1 | 白い紙の質感（#FBFAF6） | Caveat Brush（マーカー） | 青 #1F4FC4 | JPEG 品質 90（約 240KB） |
| 2 | 生成りの紙の質感（#F3EAD6） | Caveat の太さ 600（ペン） | 赤 #BF2A2A | JPEG 品質 90（約 245KB） |
| 4 | 淡い青（#DCEAF5） | Itim | 黒 #1B1B1B | PNG（約 45KB） |

- 型 3（白地 ＋ Zen Kaku Gothic New の黒の太字）は見本の後に外した。番号は記録の名前なので詰めない
- 手書きの字は、google/fonts にある OFL の字から、数字・`?`・記号を持ち、**「1」に上のはね（旗）があるもの**を選んだ
  （旗が無いと「10」が「l0」、「Make10」が「Makel0」に読める。Kalam Bold はこれで外した）。記号の行は 84px で、
  「^」と「−」は字の大きさを上げて形が見えるようにしている（型ごとの倍率は `STYLES` の `caret`・`minus`）
- 紙の質感はプログラムで作る（SVG の feTurbulence。seed を決めてあり、写真や他人の画像は使わない）。手書きの揺れも決まった値の並び。
  **同じ入力なら同じバイト列の画像になる**。紙の型は粒があるので PNG だと約 1.7MB になり、JPEG にした（PNG との差は平均 2.4 / 255。目では分からない）
- 式の幅は 960px まで（超えたら描かずに失敗）。列の全日で収まることを `test_promo.py` が型ごとに測る
  （いちばん広い日: 型 1 #94・型 2 #147・型 4 #480）
- 描くのは headless Chrome（Actions の ubuntu-latest に入っている。pip を増やさない）。字は google/fonts の決まったコミット
  （手書きは `06bfe0d6`）から取り、SHA-256 を確かめる（リポジトリには入れない）。**読めないとき、画面に出す字のどれかを字が持っていない
  ときは、別の字で描かずに失敗にする**（持っているかは字のファイルの cmap を読んで確かめる）
- 上げるのは `POST /2/media/upload`（multipart・`tweet_image`。形式は中身の頭から決め、JPEG は `image/jpeg`・`make10.jpg`）、
  代わりの文（`Make10 #8. Digits: 6, 8, 2, 3. Use all four, in order, to make 10. Use + − × ÷ ^ ! ( ).`。最後の記号は「Use」の行と同じ）は
  `POST /2/media/metadata`、投稿は `POST /2/tweets` の `media.media_ids`。鍵は今の OAuth 1.0a のまま

**その日の投稿を落とさない**:

| 起きたこと | どうする | `posts.csv` の `image` / `style` |
|---|---|---|
| 画像を作れない・上げられない・形式が分からない | 文字だけで送り、ログに `注意: 画像なしで投稿する: 理由` | `0` / 空 |
| 代わりの文だけ入らない | 画像は付けて送り、ログに注意 | `1` / 型 |
| 画像付きの投稿が 4xx で断られた | 文字だけで 1 回送り直す | `0` / 空 |
| 画像付きの投稿が 5xx・通信の失敗 | 送り直さずに失敗にする（出ているかもしれないので、2 本にしない） | 行を足さない |

手で流す `dry_run` の post は、送らずに画像を作り、実行の画面の **Artifacts** の `promo-image` に残す（7 日で消える。拡張子は形式に合わせる）。

### 画像を上げられるかを確かめる（`media_test`。人が行う）

投稿はせず、`posts.csv` にも書かない。X に画像を上げ、代わりの文を入れて、`media_id` と状態をログに出すだけ。

1. Actions → promo →「Run workflow」で、`task` を **media_test** にして流す（`dry_run` のチェックは関係ない。**上げる分の料金はかかる**）
2. ログの「画像を X に上げるだけ」に `media_id: … 上げたときの状態: HTTP 200 代わりの文の状態: 200` が出れば緑。画像は Artifacts の `promo-image` にも残る

赤になったら、ログの `HTTP` の数字を見る:

| 状態 | 見る所 |
|---|---|
| 401 | 鍵の取り違え・作り直しの反映漏れ。OAuth 1.0a の鍵のままでは受け付けないときもここに出る |
| 403 | App の権限が Read and write か（変えたら Access Token を作り直す）。本文に OAuth 2.0 や `media.write` とあれば、**今の鍵では上げられない**ので、OAuth 2.0 のユーザーの鍵に替える作業が要る |
| 402・`credits` の文 | Developer Console の残高と上限 |
| 429 | 回数の制限。時間を置く |
| 400 | 本文の形。`post.py` を直す（X の仕様が変わった可能性） |

断られたままでも毎日の投稿は止まらない（文字だけで出る）。`posts.csv` の `image` が `0` の日が続いたら、ここへ戻る。

### 表（`promo-data` ブランチの `promo/data/`）

どれも 1 日（集計は 1 問）1 行。同じ日を何度集めても、その行を上書きするので重複しない。日付は UTC。

| ファイル | 1 行 | 中身 |
|---|---|---|
| `posts.csv` | 投稿 1 本 | 日付・番号・文の型（`type`）・**文の版**（`tmpl`。今は 5。列ができる前の #1・#2 は空で、読むときに 1 とみなし、次に書き戻すときに 1 が入る）・数字・文・版 3 の C の記録（`c_note`。版 4 では空）・**画像を付けたか**（`image`。`1` か `0`。列ができる前の行は空）・**画像の型**（`style`。`1`・`2`・`4`。画像を付けなかった日と、列ができる前の行は空）・tweet の番号・投稿の時刻・その時のフォロワー数。X の指標（表示回数・いいね・返信・リポスト・引用・プロフィールのクリック）を 2 組: **約 24 時間の値**（`m24_*`。投稿から 20〜36 時間の間に初めて集めた値。毎日 8:00 に集めるので、ふつうは 23.5 時間の値）と、**最新の値**（`last_*`。投稿から 7 日まで毎日上書き） |
| `visits.csv` | 1 日 | make10.app/daily/ の訪問数・ページの表示数・参照元が `t.co` の訪問・`x.com`（と `twitter.com`）の訪問。毎日、昨日までの 7 日ぶんを書き直す |
| `agg.csv` | 1 問 | 昨日（UTC）の問題の、解いた数 `s`・ギブアップ `g`・ヒントなしで解いた数 `s0`・遊んだ人 `players`（s ＋ g） |
| `report.md` | — | 型ごとのまとめ（下の「まとめを読む」）。collect のたびに書き直す |

- **集計のサーバーは今日の前後 1 日しか答えない**ので、collect が落ちた日のみんなの結果は後から取れない（表の行が抜ける）。
  取るのは次の日の UTC 8:00 なので、その後にハワイなどで遊んだ分は入らない
- X の指標は、`posts.csv` にある投稿（`post.py` が送ったもの）だけを読む。手で投稿したものは入らない

## 鍵の作り方と入れ方

鍵は GitHub の **Settings → Secrets and variables → Actions → Secrets** に入れる（名前は下のとおり）。
ワークフローの外（このリポジトリのファイル・コミット・ログ）には書かない。スクリプトは鍵の値を出さない（足りないときは名前だけ出す）。

| Secret の名前 | 作り方 |
|---|---|
| `X_API_KEY`・`X_API_SECRET` | X の Developer Portal（https://developer.x.com/ ）で Project と App を作り、App の「Keys and tokens」の **API Key and Secret**（Consumer Keys） |
| `X_ACCESS_TOKEN`・`X_ACCESS_SECRET` | 同じ画面の **Access Token and Secret**。**先に App の「User authentication settings」で権限を Read and write にしてから**作る（後から権限を変えたら、作り直す。Read だけの鍵では投稿が 403 になる）。投稿するアカウント（Make10 のアカウント）でログインして作る |
| `CF_API_TOKEN` | Cloudflare の My Profile → API Tokens → Create Token → Custom token。権限は **Account → Account Analytics → Read** だけ。Account Resources は make10.app のあるアカウント |
| `CF_ACCOUNT_ID` | Cloudflare のダッシュボードの右側（アカウントのホーム）にある Account ID |

- X の API は使った分だけ料金がかかる（投稿・読み取りとも）。この仕組みが 1 日に呼ぶのは、
  投稿 1 回・画像の upload 1 回・代わりの文 1 回・自分の情報 1 回・投稿の指標の読み取り 1 回（最大 7 本ぶん）
- **料金の確かめ方**: X の Developer Console（https://console.x.com/ ）の料金表で、`Content: Create`・`Media Metadata`・Media の upload の行の単価を見る。
  残高と上限も同じ所で見る。説明書の表は https://docs.x.com/x-api/getting-started/pricing 。2026-11 に見たときは投稿 $0.015・Media Metadata $0.005 で、
  upload だけの単価は説明書に見つからなかった（値は変わるので、ここの数字ではなく Console を正とする）
- 非公開の指標（表示回数・プロフィールのクリック）は、投稿したアカウント自身の鍵（OAuth 1.0a のユーザーの鍵）で、投稿から 30 日以内だけ読める
- 文の型を固定するときは **Variables**（同じ画面の隣のタブ）に `PROMO_TYPE` を入れる（下の「型を 1 つに決める」）

## 最初に動かすとき（人が行う）

1. 上の 6 つの Secret を入れる
2. main に入れる（定期実行は main に入ってから動く）
3. Actions → promo →「Run workflow」で、`task` を **post**・`dry_run` に **チェックを入れたまま**流す。ログに、送る文と型が出る（送らない）
4. 同じく `task` を **collect**・`dry_run` にチェックを入れたまま流す。X・Cloudflare・集計の数がログに出る（`promo-data` には書かない）。
   ここで Cloudflare が断るなら、トークンの権限か Account ID を見直す
5. **最初の本物の投稿は、`task` を post・`dry_run` のチェックを外して手で流す。** X に 1 本出て、`promo-data` ブランチに `posts.csv` ができる
6. その後は毎日、定期実行が collect と post を流す（時刻に起こすのは `promo/cron/` の Worker。置き方は上の「定期実行の起こし役」）

手元で試すとき（鍵は要らない。本物には送らない）:

```
python promo/test_promo.py               # 手元の試し（返事のまねのサーバーで X・Cloudflare・集計を試す。ページとの照合に Chrome を使う）
python promo/test_promo.py --no-chrome   # Chrome を使う照合を飛ばす
python promo/post.py --dry-run           # 今日の文と型を出し、画像を作るだけ
python promo/image.py --no 8 --out 8.jpg # #8 の画像を作る（#8 は型 2 なので JPEG。--style 4 で型を決めて作れる）
python promo/post.py --dry-run --now 2026-10-27T08:30:00Z   # その時刻の文
```

Windows の端末（cp932）では、試しの出力の「·」で止まることがある。そのときは `PYTHONIOENCODING=utf-8` を付けて流す（Actions の ubuntu は utf-8）。

## まとめを読む

`promo-data` ブランチの `promo/data/report.md`（GitHub でそのブランチに切り替えて開く。collect の実行結果の Summary にも出る）。
手元で作るときは:

```
git fetch origin promo-data
git worktree add ../make10-promo-data promo-data
python promo/report.py --data ../make10-promo-data/promo/data
```

- **文の版ごとに分けて出す**（新しい版が上）。版が違えば同じ型の名前でも別の文なので、混ぜない。日ごとの表には版の列がある
- 型ごと: 投稿の数・表示の平均・表示 1,000 回あたりの反応（いいね ＋ 返信 ＋ リポスト）とプロフィールのクリック・
  X から来た人（その日の `t.co` ＋ `x.com` の訪問）の平均・その日の遊んだ人数の平均。比べる X の数は約 24 時間の値
- **画像の型ごと**（「## 画像の型」の節）: 同じ数を画像の型（1・2・4）ごとに出す。画像を付けた日だけ（`style` が空の日は入らない）。
  文の型 × 画像の型の表（投稿の数 / 表示の平均）もある。日ごとの表には「画像」の列がある
- **偏りを並べて出す**: 型ごとの曜日の内訳・何日目に出たかの平均・フォロワーの増え。日がたつとフォロワーが増えるので、
  同じ型でも後の日ほど数が大きくなりやすい（文は 4 つ・画像は 3 つを順に回すので、2 週間でどの文も 3〜4 回、どの画像も 4〜5 回。
  組み合わせは 12 日で 1 周なので、組み合わせごとには 1 本前後しか無い）
- **勝ち負けは決めない。** 表を読んで、人が決める
- 「X から来た人」は、投稿した日（UTC）の訪問だけを数える（投稿は UTC 8:30 なので、その日の残り 15.5 時間ぶん）。
  プロフィールのリンクからでも、ほかの人の投稿からでも、X から来た訪問は全部入る

## 型を 1 つに決める（2 週間の後。人が行う）

1. `report.md` を読んで、続ける文の型を決める（A・B・C・D のどれか）
2. GitHub の Settings → Secrets and variables → Actions → **Variables** → New repository variable で、名前 `PROMO_TYPE`・値に `A`〜`D` のどれかを入れる
3. 次の投稿から、その文の型だけになる（コードは変えない。`posts.csv` の `type` にも残る）。4 つを回すのに戻すときは、`PROMO_TYPE` を消す
4. 型の文そのものを変えるときは、`promo/post.py` の `TEXTS` を直し（決まった形の確かめ `SHAPES` は `TEXTS` から作る）、**文の版 `TMPL` を 1 つ上げて**、
   `python promo/test_promo.py` を流す（`report.py` は版ごとに分けて集計するので、前の文の数と混ざらない）

画像の型を 1 つに決める入口（Variables）は無い。決めたら、`promo/image.py` の `ORDER` をその型だけにする
（コードを変えるので、ブランチで直して `python promo/test_promo.py` を流す）。

## 止め方

- **しばらく止める**: Actions → promo →「…」→ **Disable workflow**。戻すときは Enable workflow
- **やめる**: `.github/workflows/promo.yml` を消して main に入れる。X の App の鍵は Developer Portal で作り直す（Regenerate）か App を消し、
  GitHub の Secrets も消す。記録は `promo-data` ブランチに残る（要らなければブランチを消す）
- 投稿を 1 日だけ飛ばすことはできない（その日だけ Disable にする）
- 60 日間リポジトリにコミットが無いと、GitHub が定期実行を止める（`promo-data` へのコミットが数に入るかは確かめていない。止まったら Enable workflow）。
  止まるとワークフローそのものが Disabled になるので、Cloudflare から起こす分も GitHub に断られる（ログに 204 以外が出る。確かめていない）
- Cloudflare から起こす分も止めるときは、上の「止める・鍵の期限が切れたら」。**Disable workflow にすると、どちらから起こしても走らない**
