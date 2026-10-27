# X への毎日の投稿と、反応の記録（promo/）

デイリー（https://make10.app/daily/ ）の問題を、毎日 1 本 X（旧 Twitter）に投稿し、反応を表に残す仕組み。
**2 週間、3 つの型を順に試し、その後で人が型を 1 つ選んで続ける。型を自動で選ぶ処理は無い**（決めるのは人）。

`docs/` の外なので配信されない。デイリーのページ（`docs/daily/`）とサーバー（`worker/`）には触らない（ページは読むだけ）。

## 仕組み

| いつ（UTC） | 日本 | 何をする | 中身 |
|---|---|---|---|
| 毎日 8:00 | 17:00 | `promo/collect.py` | X・Cloudflare Web Analytics・みんなの結果の数を集めて CSV に足し、まとめ（`report.md`）を書き直す |
| 毎日 8:30 | 17:30 | `promo/post.py` | その日の問題を 1 本投稿し、`posts.csv` に 1 行足す |

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

### 投稿の 3 つの型

型は問題番号で順に回す（(番号 - 1) を 3 で割った余り。#1 が A・#2 が B・#3 が C・#4 が A…）。**リンクは付けない**
（リンク付きの投稿は API の料金が高い。リンクはプロフィールに置く）。**答えは載せない**（送る前に `post.py` が、決まった形か・
列の解答のどれも入っていないか・280 字以内かを確かめ、外れたら送らずに失敗にする）。文には「link in profile」と書く。

文は 2026-10-27 に今の形（**文の版 2**）にした。#1・#2 は前の短い文（版 1。`Make10 #1` / `8 7 5 2` / `#Make10` の形）で送った。
例は #12（6 1 8 3）の日。

**A**

```
Make10 Daily #12
Today's numbers: 6 · 1 · 8 · 3
Use all four, in order, to make 10.
Play free — link in profile.
#Make10 #DailyPuzzle #MathPuzzle
```

**B**

```
Can you make 10 from 6 · 1 · 8 · 3?
Keep the order. + − × ÷ ^ ! ( ) allowed.
Make10 Daily #12 — link in profile.
#Make10 #DailyPuzzle #BrainTeaser
```

**C**

```
Make10 Daily #12: 6 · 1 · 8 · 3
Yesterday's puzzle: 63% solved, 41% with no hints.
Your turn — make 10. Link in profile.
#Make10 #DailyPuzzle #MathPuzzle
```

- C の 2 行目は、昨日の問題のみんなの結果（`GET https://api.make10.app/r?n=…`）。正解率 ＝ 解いた ÷（解いた ＋ ギブアップ）、
  ヒントなし ＝ ヒント 0 回で解いた ÷ 解いた（ページの「みんなの結果」と同じ数え方・同じ四捨五入）
- **集計が 30 件未満・取れない・#1（昨日が無い）のときは、2 行目を除いて送り**、`posts.csv` の `c_note` に理由を残す。
  解いた人が 0 のときは、ヒントなしを付けずに `Yesterday's puzzle: 0% solved.` にする
- 字数は X の数え方（英数字や `·`・`—` は 1 字、`−` や日本語は 2 字）で 280 字まで。いちばん長い文でも 160 字ほど
- B の 2 行目（使える記号の一覧）だけは記号を書く。ほかの行に演算の記号や括弧があれば、`post.py` は送らない
- 制約のある日（使えない演算がある日）も、文は同じ（ページの共有の文と同じく、制約は書かない）

### 表（`promo-data` ブランチの `promo/data/`）

どれも 1 日（集計は 1 問）1 行。同じ日を何度集めても、その行を上書きするので重複しない。日付は UTC。

| ファイル | 1 行 | 中身 |
|---|---|---|
| `posts.csv` | 投稿 1 本 | 日付・番号・型・**文の版**（`tmpl`。今は 2。列ができる前の #1・#2 は空で、読むときに 1 とみなし、次に書き戻すときに 1 が入る）・数字・文・C の記録（`c_note`）・tweet の番号・投稿の時刻・その時のフォロワー数。X の指標（表示回数・いいね・返信・リポスト・引用・プロフィールのクリック）を 2 組: **約 24 時間の値**（`m24_*`。投稿から 20〜36 時間の間に初めて集めた値。毎日 8:00 に集めるので、ふつうは 23.5 時間の値）と、**最新の値**（`last_*`。投稿から 7 日まで毎日上書き） |
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

- X の API は使った分だけ料金がかかる（投稿・読み取りとも。Developer Portal で残高と上限を見る）。この仕組みが 1 日に呼ぶのは、
  投稿 1 回・自分の情報 1 回・投稿の指標の読み取り 1 回（最大 7 本ぶん）
- 非公開の指標（表示回数・プロフィールのクリック）は、投稿したアカウント自身の鍵（OAuth 1.0a のユーザーの鍵）で、投稿から 30 日以内だけ読める
- 型を固定するときは **Variables**（同じ画面の隣のタブ）に `PROMO_TYPE` を入れる（下の「型を 1 つに決める」）

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
python promo/post.py --dry-run           # 今日の文と型を出すだけ（C の日は、本物の集計を 1 回読む）
python promo/post.py --dry-run --now 2026-10-27T08:30:00Z   # その時刻の文
```

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
- **偏りを並べて出す**: 型ごとの曜日の内訳・何日目に出たかの平均・フォロワーの増え。日がたつとフォロワーが増えるので、
  同じ型でも後の日ほど数が大きくなりやすい（3 つを順に回すので、どの型も 2 週間に 4〜5 回ずつ、曜日もずれていく）
- **勝ち負けは決めない。** 表を読んで、人が決める
- 「X から来た人」は、投稿した日（UTC）の訪問だけを数える（投稿は UTC 8:30 なので、その日の残り 15.5 時間ぶん）。
  プロフィールのリンクからでも、ほかの人の投稿からでも、X から来た訪問は全部入る

## 型を 1 つに決める（2 週間の後。人が行う）

1. `report.md` を読んで、続ける型を決める（A・B・C のどれか）
2. GitHub の Settings → Secrets and variables → Actions → **Variables** → New repository variable で、名前 `PROMO_TYPE`・値に `A` か `B` か `C` を入れる
3. 次の投稿から、その型だけになる（コードは変えない。`posts.csv` の `type` にも残る）。3 つを回すのに戻すときは、`PROMO_TYPE` を消す
4. 型の文そのものを変えるときは、`promo/post.py` の `compose()` と、決まった形の確かめ `SHAPES` を一緒に直し、**文の版 `TMPL` を 1 つ上げて**、
   `python promo/test_promo.py` を流す（`report.py` は版ごとに分けて集計するので、前の文の数と混ざらない）

## 止め方

- **しばらく止める**: Actions → promo →「…」→ **Disable workflow**。戻すときは Enable workflow
- **やめる**: `.github/workflows/promo.yml` を消して main に入れる。X の App の鍵は Developer Portal で作り直す（Regenerate）か App を消し、
  GitHub の Secrets も消す。記録は `promo-data` ブランチに残る（要らなければブランチを消す）
- 投稿を 1 日だけ飛ばすことはできない（その日だけ Disable にする）
- 60 日間リポジトリにコミットが無いと、GitHub が定期実行を止める（`promo-data` へのコミットが数に入るかは確かめていない。止まったら Enable workflow）。
  止まるとワークフローそのものが Disabled になるので、Cloudflare から起こす分も GitHub に断られる（ログに 204 以外が出る。確かめていない）
- Cloudflare から起こす分も止めるときは、上の「止める・鍵の期限が切れたら」。**Disable workflow にすると、どちらから起こしても走らない**
