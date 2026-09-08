# Make10 デザイントークン

メニュー・設定など新しい画面を作るときの共通の物差し。
値はすべて `docs/index.html` の実装から抜いたもので、問題画面（`#play`）は
実機で調整を重ねた結果なので、そこにある値を正とする。

**この文書の使い方**

- 画面を作る・変えるときは必ずこれを読む
- 「未定」と書いた項目は発明で埋めない。決めるときはこの文書を更新する
- CLAUDE.md と重複する内容はこちらが詳細版。CLAUDE.md からは参照だけ

---

## 1. 配色

### 1-1. テーマ変数の役割

テーマは **藍（`ai`）1 つ**。白（`paper`）は開発者パネルからのみ切り替えられる
（定義だけ残す。1-3 の paper 検証と将来のライトモード用）。`sumi` / `fuji` は削除。
`body[data-theme=…]` で切り替わる。**色は 16 進で直接書かず、必ず変数を使う。**
1 か所でも直値を書くと paper 側で破綻する。

| 変数 | 役割 | 使ってよい | 使ってはいけない |
|---|---|---|---|
| `--ink` | 画面全体の地。背景グラデの軸 | `body` 背景、地に沈める要素 | 文字色 |
| `--panel` | 面。一段持ち上がった領域 | カード / トレイ / ルール枠 / トースト / ヒント / 正解カード / バナー / シート内の面 | 本文の地（沈むべき所） |
| `--edge` | 枠線・仕切り線 | `border` / 区切り線 / 無効スイッチの地 / バーの地 | 文字色 |
| `--paper` | 主たる文字色（最も明るい。paper テーマでは最も暗い） | 数字 / 見出し / 本文 / 進捗の数値・バー / アイコン線 | 面の地 |
| `--dim` | 読ませる副次テキスト（`--paper` の 70%。`color-mix` を変数化） | `.small` / 遷移矢印 `.chev` / プレースホルダ / `.mode` の右端の値 / リスト画面のキャプション | 本文（`--paper` 85%）／「無効」の表現（それは `--slate`） |
| `--slate` | **「無効・効いていない」専用**（コントラスト不足のため副次テキストから分離） | 無効トークン `.tok.dead` / 使用禁止チップ `.chip.off` / 効いていない括弧 / トグルつまみ(off) | **読ませる副次テキスト**（`--dim` を使う） |
| `--coral` | 注意・エラー | 相方のいない括弧 / 削除ドラッグ中の縁取り / 警告文 | 通常状態の装飾。多用しない |
| `--teal` | **開発者パネル専用**。アプリ本体では使わない | `#devpanel` の `h3` / `.dv b` / `input` の `accent-color` のみ | アプリ本体すべて |
| `--gold` | **現在未使用**。達成表示の設計が決まるまで定義だけ残す | （なし） | すべて（設計未定） |
| `--line` | 背景の幾何学模様の線（rgb 3 値、`rgba()` で 3〜5% に落として使う） | `#bg` のみ | それ以外 |

`--tileBg` `--tileInk` `--par`（数字がタイルだった頃の名残）は参照 0 件だったので 2.9 で削除。

### 1-2. モノクロ原則（アプリ全体）

**アプリ全体でアクセント色を使わない。** 色は `--coral`（注意・エラー）と
`--slate`（無効・効いていない）だけが意味を持つ。それ以外は明るさ・太さ・大きさで差をつける。

特に問題画面では、数字・演算子・括弧を色で区別せず
（数字 = 最も明るく大きい → 演算子 = 落とした白で小さめ → 括弧 = さらに落とす）、
正解でも色は変えない（いちばん明るい白にして「10」を少し大きくするだけ）。

**問題画面のトークンの背後に面を塗らない。** 数字も記号もタイルではなく素の文字で、
塗り・角丸・影を持たない。状態は**下線**で示す（差し替えできる演算子 `.tok.swap`、
トレイで選択中のチップ `.chip.sel`）。唯一の例外は**隙間の枠 `.zone`**で、これは
記号ではなく「これから置く場所」を表す面。3.8 で `.tok.swap` の塗りを外し、
トークンに面を塗る箇所は無くなった。

**下線に明るさを足すのはトレイだけ。** `.chip.sel` は下線と一緒に記号を `--paper` まで
明るくするが、`.tok.swap` は下線だけにする（3.9）。式の中には「数字 → 演算子 → 括弧」の
明るさの段階があり、強調中だけ演算子を数字と同じ明るさにするとその段階が一時的に崩れる。
トレイの中にはこの段階が無いので、同じ表現でも事情が違う。

- **コーラル** … 注意・エラー（括弧の不一致、外へドラッグして削除、計算不能）
- **グレー（`--slate`）** … 無効・効いていない（使用禁止の記号、計算に効かない括弧）。
  読ませたい副次テキストには使わない（`--dim`）
- `--teal` / `--gold` はアプリ本体に出さない（`--teal` は開発者パネル専用、`--gold` は未使用）

### 1-3. すべての前提: paper テーマで破綻しないこと

`paper` は地が明るく `--paper`（＝文字色）が暗い、明暗が反転したテーマ。
`color-mix(… var(--paper) N%, transparent)` のような相対指定は 4 テーマで
明暗どちらにも転ぶ。**新しい配色は必ず paper でも確認する。**片方向にしか
効かない書き方（`rgba(255,255,255,…)` 等）は使わない。

---

## 2. 文字

### 2-1. 書体とウェイト

- **Zen Kaku Gothic New** 単体。数字・記号・日本語すべてこれ。
  縦に細い直線的な書体（`system-ui` 等はフォールバック）
- Google Fonts から読むウェイトは **400 / 500 / 700** の 3 つだけ
- **Zen Kaku には 600 と 800 が無い。** 600 を指定すると 700 に解決される。
  実質使えるのは 400 / 500 / 700。太字は 700（`.tok` の 600 指定も 700 相当）
- 本文の既定は 500（`body`）。400 は読み込むが CSS では未使用（**用途は未定**）
- `font-variant-numeric: tabular-nums` が `.eq` `.num` `.sheet .kv b` `.dv b`
  `.facttable .c` に付いているが、**Zen Kaku Gothic New 本体では効かない**。
  この書体は `tnum` feature を持たず、数字も等幅でない（0〜9 の送り幅が
  409〜508 units/1000＝46px 換算で 18.8〜23.4px、2.6 で実測）。
  指定を残しているのは**フォールバック時の保険**（`system-ui` / `Hiragino Sans` 等では
  tabular-nums が効く）。Google Fonts の読み込み前・失敗時、および GAME-SPEC 11 章の
  フォント同梱が済むまでの Capacitor 環境ではフォールバックが実際に起こり得る。
  説明コメントは index.html の `.eq` に 1 箇所だけ置き、他 4 箇所はそれを参照する
- 階乗表の桁揃えは**対応不要**。値が 1〜479,001,600 と桁数がバラバラで、
  tnum があっても揃わない

### 2-2. 文字サイズ（px。compact = 高さ 700px 以下）

| 用途 | セレクタ | normal | compact |
|---|---|--:|--:|
| 結果表示・式 | `.eq` | 52 | 36 |
| 結果表示・待機 | `.eq.idle` | 21 | 17 |
| 正解の「10」 | `.eq.hit` | 60 | 42 |
| 部分結果 | `.eq.part` | 34 | 25 |
| 数字 | `.num` | 52 | 44 |
| 演算子 | `.tok.op` | 32 | 29 |
| 階乗 | `.tok.fac` | 39 | 34 |
| 括弧 | `.tok.lp` `.tok.rp` | 42 | 36 |
| トレイの記号 | `.chip` | 38 | 33 |
| ドラッグ中の分身 | `#ghost` | 34 | 34 |
| 画面見出し | `.sheet h2` / `.title`(ホーム) | 17 / 31 | 同 |
| 節見出し | `.sheet h3` | 14 | 14 |
| 本文 | `.sheet p` `li` / `.rule` | 13 / 14 | 13 |
| リスト項目 | `.toggle` | 13.5 | 13.5 |
| 補助文 | `.small` `.sub` `.code` `#trayhead` | 11〜12.5 | 同 |
| バナー内 | `#banner` | 11 | 11 |

**なぜ compact があるか**: 広告 52px を引くと縦が足りない端末向け。
**文字サイズも箱の寸法も `TOKEN_METRICS.compact` が持ち**、`applyMetrics()` が CSS 変数へ
流し込む（3.3〜4.0 で `@media` から順に移した）。媒体クエリに残っている文字サイズは
`.rule` と `.eq`（`.idle` / `.hit` / `.part`）だけで、トークンとトレイの文字サイズは
`numF` `opF` `facF` `parF` `chipF` が持つ。`@media` に残る寸法も
`.chip{height}` `.tray{border-radius}` `.foot` `.top` `.field` `.readout` など、
**変数にしていないものだけ**。

**トークンとトレイの行（`.num` `.tok.*` `.chip`）は `TOKEN_METRICS` が持つ確定値**で、
両モードとも実測で決めてある。全項目と経緯は 3-1。

---

## 3. 寸法

### 3-1. トークン・トレイ・ボタン（`TOKEN_METRICS`、JS が唯一の定義。CSS へは変数で流す）

**両モードとも 2026-09-08 に確定した値。** normal は実機（Android）で、compact は
DevTools のデバイス表示（412×690）で、それぞれ実際に見ながら決めた。
下の表は `TOKEN_METRICS` の**全項目**。

| 項目 | normal | compact | CSS 変数 | 意味 |
|---|--:|--:|---|---|
| `num` | 32 | 29 | `--numW` | 数字の箱幅 |
| `numMx` | 2 | 1 | `--numMx` | 数字の左右マージン。**この 1 項目だけ調整スライダーを持たなかった**ので、2.5 の実機調整の値をそのまま引き継いでいる |
| `numF` | 52 | 44 | `--numF` | 数字の文字サイズ（`.num`） |
| `op` | 30 | 24 | `--opW` | 演算子の箱幅 |
| `opF` | 32 | 29 | `--opF` | 演算子の文字サイズ（`.tok.op`） |
| `fac` | 19 | 17 | `--facW` | 階乗の箱幅 |
| `facF` | 39 | 34 | `--facF` | 階乗の文字サイズ（`.tok.fac`） |
| `facMl` | -3 | -3 | `--facMl` | 階乗の食い込み（`.tok.fac` の `margin-left`）。4.0 で定数 `FAC_ML` を廃止してここへ移した |
| `par` | 16 | 12 | `--parW` | 括弧の箱幅 |
| `parF` | 42 | 36 | `--parF` | 括弧の文字サイズ（`.tok.lp` `.tok.rp`） |
| `h` | 59 | 50 | `--tokH` | トークンの高さ |
| `chipF` | 38 | 33 | `--chipF` | トレイの記号の文字サイズ（`.chip`） |
| `trayGap` | 4 | 4 | `--trayGap` | トレイの `gap` |
| `trayPad` | 9 | 8 | `--trayPad` | トレイの `padding` |
| `btn` | 52 | 44 | `--btnW` | 丸ボタンの直径（`.iconbtn` `.plainbtn`） |
| `gear` | 42 | 38 | `--gearW` | `#gear` の直径 |
| `ic` | 28 | 26 | `--icW` | アイコン SVG の描画サイズ（`.ic`）。`btn` は箱しか変えないので別に持つ |

**compact は normal からの比では作っていない。** 2 つの列は別々に測った値なので、
項目によって縮み方が揃っていない（`par` は 16→12 で 4px 減るが `facMl` `trayGap` は同値）。
比で自動追従させる仕組みは 4.0 まであったが、両モードを実測で決める方針にしたときに
廃止した。**片方だけを直すと対の関係が崩れるので、変えるときは両方を実機で見ること。**

値を詰めるための調整スライダー（SIZE-TRIAL、3.3〜4.2）は、値が決まったので
**4.3 で撤去した。** 寸法を変えるときは `TOKEN_METRICS` を直接書き換える。
開発者パネルの実測値の節にある「数字の描画幅（両モード）と片側余白」が見張りになる
（下の片側余白がマイナスになったら箱から文字がはみ出している）。

数字の 1 文字は 32px の箱に入れて中央寄せ。長い式では合計幅が画面を超え、
式全体が `transform: scale()` で縮む（下限 `MIN_SCALE` = 50%）。

**いちばん幅を食う式**は 23 トークン。`canPut()` が許す挿入だけを辿る全探索
（6,890,240 状態）で求めた。内訳は数字 4・演算子 3・`(` 4・`)` 4・`!` 8 で、
これは各記号の上限そのもの ―― 演算子は数字の間に 1 つずつで 3 個、括弧は
`PAREN_STOCK` で 4 個ずつ、`!` は「左が数字か `)`」かつ「右が `!` でない」ので
ホスト 1 つにつき 1 個・ホストは数字 4 + `)` 4 の 8 箇所。合計幅は

```
4×(num + 2×numMx) + 3×op + 8×par + 8×(fac + facMl) = 490px（normal）／404px（compact）
```

例（探索が返した並び。実際に組める）: `((((5!)!)!)!)!+8!+3!+6!`

このときの縮小率は**画面幅で変わる。** 分母の「使える幅」（`#exprwrap` の実測幅）が
画面幅で決まるためで、**狭い端末ほど縮む。** 4.3 の確定値での実測は次のとおり
（`#app` の `max-width` が 430px なので、画面がそれより広くても 430px の行で頭打ちになる）。

| 画面幅 | 使える幅（normal） | normal | 使える幅（compact） | compact |
|--:|--:|--:|--:|--:|
| 430px | 388px | **79.2%** | 392px | **97.0%** |
| 390px | 348px | 71.0% | 352px | 87.1% |
| 360px | 318px | 64.9% | 322px | 79.7% |

**「79.2% / 97.0%」と書くときは画面幅 430px の値。** 下限 50% には 360px でも届かない。
compact のほうが縮まないのは、箱と文字を一段小さくしてあるぶんトークン幅の合計が
490px → 404px と小さいため。**縮小は仕様。不具合ではない**（GAME-SPEC 4-5）。

### 3-1-2. アイコンの線の太さと、設定を開くアイコン

**「設定を開く」は三本線に統一した（4.5）。** それまではホームが歯車 `ICON_GEAR`、
問題画面が三本線と、**同じ操作に 2 つの見た目**があった。三本線に寄せて歯車は廃止。
`#gear` の `title` / `aria-label` は「設定」のまま（役割は変わっていない）。
ホーム以外の画面で `#gear` が戻る矢印 `ICON_BACK`（`‹`）になる切り替えもそのまま。

**三本線の定義は `ICON_MENU` 1 つだけ。** `#menu`（問題画面）へは初期化時に、
`#gear`（ホーム）へは `go()` が、同じ文字列を流し込む。同じ絵柄が 2 つの定義を持つと
片方だけ直す事故が起きる。

アイコンはすべて**線だけで描く**（`.ic{fill:none;stroke:currentColor}`。塗りの
アイコンは 1 つも無い）。太さは **`.ic` の `stroke-width:1.5` が既定**。

**三本線だけは `2`。** `.ic.thick` を当てる。今の太さで確定していて、細くすると
他のアイコンより情報量が少ないぶん頼りなく見えるため。

**太さは「置き場所」ではなく「アイコン」に紐づける。** `.thick` は `ICON_MENU` の
文字列の中に書いてあるので、`#menu`（問題画面）でも `#gear`（ホーム）でも自動的に
同じ太さになる。CSS 側で `#menu .ic{...}` のように場所で指定すると、同じ絵柄なのに
場所によって太さが違う、という不一致を作ってしまう。

`normal` / `compact` で分けない（共通の直値）。大きさだけ `--icW` が変える（3-1）。
リスト画面の遷移矢印 `.chev` は `.ic` とは別クラスで、`stroke-width:2` のまま（6-3）。

### 3-2. 隙間（ドラッグ中に開く枠）

- `ZONE_BASE` = 演算子 38 / 階乗 32 / 括弧 34（標準幅。`shrink` 80% を掛ける前）
- `ZONE_MIN` = 20（圧縮しても下回らない幅）
- 隙間幅は固定ではなく毎回計算:
  `clamp(ZONE_MIN, (使える幅 − トークン幅 − Δ) / 枠数, ZONE_BASE × 0.80)`
- **なぜ可変か**: `(` のように枠が多い記号でも、数字を縮めずに収めるため

### 3-3. 余白

実装で使われている値は **2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 18, 20**。
**規則性なし**（4px / 8px グリッドではない）。おおむね面の内側 padding は 11〜14px、
要素間の gap / margin は 6〜12px でケースごとに調整されている。
新画面もこの範囲に収める。厳密なスケールは**未定**。

### 3-4. 角丸

| 対象 | px |
|---|--:|
| 小物（枠 `.zone` / バー `.bar`） | 5 |
| 小ボタン（`.th i` / `#factbtn`） | 6 |
| チップ `.chip` / 階乗表 | 9 |
| ボタン一般 / `#gear` / 入力欄 | 11 |
| トースト | 12 |
| ルール枠 / 式エリア / トグルスイッチ | 13 |
| カード / 正解カード | 15 |
| トレイ | 20（compact 16） |
| 丸アイコン `.iconbtn` | 50% |

ゆるく「小物 5〜6 / ボタン 11 / カード 13〜15 / トレイ 20」の 4 段。

### 3-5. タップ領域

- **Android の推奨は最小 48px（48dp）。** 新しく作る操作要素はこれを満たす
- 現状の実装はこれを下回るものがある（→ 7 章の不揃い）。踏襲しない

---

## 4. 動き

| 変数 | 値 | 使う場面 |
|---|---|---|
| `--dur` | 300ms（実行時。`applyDevVars` が設定。CSS 既定 `.14s` は上書きされる） | 枠の開閉、式の縮小（scale）の補間 |
| `--hotDur` | 200ms（同上。CSS 既定 `.1s`） | 吸着（`.zone.snap` の間の width 変化・色・不透明度） |
| `--zoneEase` | `cubic-bezier(.22,.72,.3,1)`（速く始まり減速して止まる） | 枠の開閉・式の縮小 |
| `--ease` | `cubic-bezier(.34,1.28,.64,1)`（行き過ぎて戻る） | 正解演出 `.num.pop` 専用 |

- **開閉に `--ease`（行き過ぎ系）を使わない。** y>1 のオーバーシュートで枠や式が
  最終幅より一瞬広がり、画面端をはみ出してから戻る。scale を先に算術で
  確定させている意味が無くなる。減速して止まる `--zoneEase` を使う
- **レイアウトを起こすアニメーションを避ける。** 位置・大きさは `transform`
  （`scale` / `translate`）で表現する。`width` / `top` / `left` は使わない
- **唯一の例外**は吸着した枠 1 個の `width`。1 要素だけ・短時間（`--hotDur`）に限る
- `prefers-reduced-motion: reduce` で全アニメーション・遷移を止める

---

## 5. 画面構成の原則

- **枠（区切り・カード）を増やす前に、大きさ・余白・明るさで区別できないか考える。**
  問題画面は色も枠も足さず、サイズと明るさだけで数字/演算子/括弧を分けている
- 問題画面は **高さ 100dvh、スクロールを発生させない**
  （`html,body{overflow:hidden}` ＋ `#app{height:100dvh}`）
- 画面下部に **広告バナー 52px（`--bannerH`）＋ 余白 14px（`--bannerGap`）** を確保。
  `#app` の `padding-bottom` で計上する
- compact への切り替えは `@media (max-height:700px)`

---

## 6. リスト画面（設定・メニュー）のルール

対象は `#settings` `#stats` `#help` `#home` `#heldpick`。実機で確認し **3.0 で確定**
（LIST-TRIAL 2.8 / COLOR-TRIAL 2.9 とも採用）。以下の値は `docs/index.html` の実装そのもの。
`@media (max-height:700px)` はリスト画面の要素を再指定しない（全高で同じ見た目）。

比較用の `docs/v27.html`（2.7・LIST-TRIAL 前）と `docs/v28.html`（2.8・COLOR-TRIAL 前）は
**3.0 の実機確認が済むまで残す**。GitHub Pages で `.../v27.html` `.../v28.html` として
実機で並べて見比べられるため。

### 6-1. 節の面と行（`#settings` `#stats`）

| 要素 | 値 |
|---|---|
| 節の面 `.group` | `background:var(--panel)` / `border:1px solid var(--edge)` / `border-radius:15px` / `margin-bottom:11px` / `overflow:hidden`（`:active` の地が角丸からはみ出さないように） |
| 行でない中身用 `.group.pad` | `padding:5px 14px`（統計のバーなど） |
| 行 `.toggle` / `.kv` | `padding:14px` / `min-height:48px` / `display:flex` `justify-content:space-between` `align-items:center` / 地・枠・角丸なし（面が持つ） / `margin:0` |
| 区切り線 | `.group .toggle:not(:last-child)::after` と `.group .kv:not(:last-child)::after`。`position:absolute` / `left:14px` `right:14px` `bottom:0` / `height:1px` / `background:var(--edge)`。節の最終行には引かない |
| 行の押下 | `.toggle:active{background:color-mix(in srgb,var(--paper) 10%,transparent)}`（直値を使わない） |
| `.kv b`（右の値） | `font-weight:700` / `font-variant-numeric:tabular-nums` |

### 6-2. 見出し・本文・シート

| 要素 | 値 |
|---|---|
| 画面見出し `.sheet h2` | 17px / 700 / `margin:2px 0 12px` |
| 節見出し `.sheet h3` | **14px / 700 / `color:var(--paper)`** / `margin:18px 0 7px`（面の外）。本文（`--paper` の 85%）より強くするため大きくする |
| 本文 `.sheet p` `.sheet li` | 13px / `line-height:1.75` / `color:var(--paper)` / `opacity:.85` |
| 副次テキスト `.small` / プレースホルダ | `color:var(--dim)`（`--dim` = `--paper` の 70%、1-1） |
| シート `.sheet` | `overflow-y:auto`（**縦スクロールする**。問題画面と違う） / `padding-bottom:12px` |

### 6-3. 遷移矢印・トグルスイッチ

**遷移矢印 `.chev`**（`#settings` の `go-help` / `go-stats` / `reset`）

- 文字 `›` をやめインライン SVG（`<path d="M9 6l6 6-6 6"/>`）。書体で位置・太さが揃わないため
- `16px` / `fill:none` / `stroke:currentColor` / `stroke-width:2` / round / `color:var(--dim)`
  （`.ic` とは別クラスなので、`.ic` の既定 1.5 の影響を受けない。3-1-2）

**トグルスイッチ `.toggle span.sw`**

- トラック `44×25` / `border-radius:13px` / off 時 `background:var(--edge)` / `transition:background .18s`
- つまみ `::after` `19×19` / `top:3px` `left:3px` / `border-radius:50%` / off 時 `background:var(--slate)` / `transition:transform .18s,background .18s`
- on 時: トラック `color-mix(in srgb,var(--paper) 45%,transparent)` / つまみ `transform:translateX(19px)` ＋ `background:var(--paper)`
- 状態は**つまみの左右位置**で伝える。色（`--paper`）は補助でアクセント色は使わない

### 6-4. 選択行 `.mode`（`#home` のモード、`#heldpick`）

| 要素 | 値 |
|---|---|
| `.modes` | `display:flex` 縦 / `gap:9px` / `margin-top:4px` |
| `.mode` | `<button>`。`display:flex` `align-items:center` / `gap:12px` / `padding:14px` / `min-height:48px` / `text-align:left` / `width:100%`。地・枠・角丸は `button` 既定（`background:var(--panel)` / `border:1px solid var(--edge)` / `border-radius:11px`） |
| `.mode.lock` | `opacity:.55`（「押せない」の意味に限定。空でも遷移する `#m-held` には付けない） |
| `.mode .mi`（アイコン） | `width:calc(var(--icW) + 6px)` / flex 中央。中身は `.ic`（`--icW` 角 / `stroke:currentColor` / `stroke-width:1.5` / round）のインライン SVG。挑戦モードの 3 状態（`ICON_LOCK` / `ICON_STAR` / `ICON_TROPHY`）は `innerHTML` 差し替え |
| `.mode .mt`（名前） | `flex:1` / 15px / 700 / `color:var(--paper)`。プレーンテキスト（`<b>`/`<span>` の入れ子はやめた） |
| `.mode .mv`（右端の値） | `flex:0 0 auto` / 13px / `color:var(--dim)` / `white-space:nowrap`。値は `renderHome()` / `renderHeldPick()` が入れる。ホームの `m-held` は 0 のとき空文字、`#heldpick` は 0 でも `N / M` を出す |

行の高さ = `padding 14×2 + 中身 max(24px アイコン, ~18px テキスト) ≈ 52px`（`min-height:48px` を満たす）。

### 6-5. 開発者パネル `#devpanel`（`#app` 直下・リスト画面のルールの対象外）

**`#app` の直下に置く。`#settings` の中ではない**（3.4 で移した）。`position:fixed` に
するだけでは足りない ―― `#settings` が `display:none` のとき中身は描画されないので、
**DOM 上の場所そのものを外に出す**必要がある。

**`SCREENS` には入れない。** `go()` が切り替える「画面」ではなく、どの画面にも重なる
道具だから。開閉は `devPanelShow(on)` が `.hide` を付け外しする（`G.dev` のときだけ開く）。
導線は設定シートの `#dv-open`（開いたあと元の画面へ戻る）と、パネル内の `#dv-close`。

| 項目 | 値 |
|---|---|
| 位置 | `position:fixed` / `bottom:0` / `left:50%` ＋ `transform:translateX(-50%)` |
| 大きさ | `width:min(100vw,430px)` / `height:40dvh` |
| 重なり | `z-index:60`（`#gear` の 50、`#banner` の 40 より前面） |
| スクロール | `overflow-y:auto` / `overscroll-behavior:contain` |
| 地・縁 | `background:var(--panel)` / `border-top:1px solid var(--edge)` / `box-shadow:0 -8px 24px rgba(0,0,0,.38)` / `padding:0 14px 18px` |

**半透明にしない。** トレイの記号は白い線なので、透けると太さや明るさの判断が狂う。

**ヘッダ `#devhead`** は `position:sticky` `top:0` でスクロールしても残る
（`padding:10px 0 8px` / `border-bottom:1px dashed var(--edge)` / `margin-bottom:8px`）。
ボタンは **`#dv-pos`（上へ／下へ）・`#dv-min`（たたむ／ひらく）・`#dv-close`（閉じる）の 3 つ**。
3 つ入ると 1 行に収まらないので、**ボタン側は縮めず見出しのほうを省略表示にする**
（`#devhead h3{min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}`、
`#devhead>span{flex:0 0 auto}`）。折り返すとヘッダが 3 行になり、上側に付けたときの視界を食う。

**`.dvtop`** … 上側へ付け替える（`top:0` / `bottom:auto` / 縁と影を上下反転）。
式を見たいときは下、トレイを見たいときは上。どちらに付いているかは `devVars.devTop`（0/1）
に保存し、開き直しても維持する。**このクラス名を `.top` にしてはいけない** ―― 問題画面の
ヘッダ `.top{display:flex}` に当たってしまい、**パネル自体が横並びの flex になって
中身が内容幅まで縮む**（4.0 で実際に踏んだ）。

**`.min`** … たたむ。`#devbody` を `display:none` にし、`#devhead` の `padding` を
`5px 0` へ詰めて区切り線と下余白を外す。帯だけにしてトレイまで見えるようにするため。

**節の折りたたみ（4.1）。** `#devbody` の中の `<h3 class="sec" data-sec="…">` を押すと、
その見出しから**次の見出しまで**が開閉する。開いているときは頭に `▾`、閉じているときは `▸`
（`h3 .mk`）。状態は `G.devSecs`（`devVars` とは別。1=開 / 0=閉）に保存する。

節は 3 つ。**`basic`（枠・吸着のスライダー 7 本と配色・「既定値に戻す」）**、
**`meas`（実測値。読み取り専用）**、**`copy`（`#dv-copyline` の受け渡し用 1 行）**。
既定は `basic` と `meas` を開き `copy` を閉じる ―― スライダーを動かして実測値を読む、が
1 往復なので同時に開いているほうが速い。画面高 690px（パネルの `clientHeight` 275px）での
実測は `basic` のみ 636px・`basic`+`meas` 964px で、どちらにしてもスクロールは要る。

4.3 で SIZE-TRIAL を撤去したので、寸法の 3 節（式のトークン／トレイ／ボタン・アイコン）と
それをまとめる帯の見出し、編集中のモード表示 `#dv-mode`、`#dv-size-reset` は無くなった。
`applySecs()` に残っている「`data-sec` の無い `h3` は節として扱わない」分岐は、
またそういう帯を置いたときに中身を巻き込まないための保険。

**`.min` と混ぜないこと。** `.min` は `#devbody` ごと消して**パネルを帯にする**もの、
節の折りたたみは `#devbody` の**中**を節単位で畳むもの。対象が入れ子なので競合しない。
なお `hidden` 属性は UA スタイルの `[hidden]{display:none}` なので、作者スタイルの
`.dv{display:flex}` に負ける。`#devbody [hidden]{display:none!important}` で明示的に打ち消す。

**`#devpanel h3` は `.sheet h3` と同じ様式を明示する**（`font-size:14px` / `font-weight:700` /
`margin:18px 0 7px`、4.0）。3.4 で `#settings` の外へ出して以来 `.sheet h3` が効かず、
ブラウザ既定の見出しのままになっていた。

- 色は `#devpanel h3` と `.dv b` と `input` の `accent-color` が `--teal` のまま（開発用に目立たせる）

### 6-6. 余白と角丸

- **行・面の内側 `padding` と区切り線のインセットは 14px で統一**
  （`.toggle` `.kv` `.card` `.mode` `.group.pad`、区切り線 `left/right:14px`）
- 縦方向の余白（見出し前後 `18/7`、面の間 `margin-bottom:11`、行間 `gap:9`、シート下 `12`）は
  7〜18px でケースごと。**厳密なスケールは無い**（3-3 と同じ状況）
- 角丸: 面（`.group` `.card`）15px / ボタン（`.mode`）11px / バー 5px / スイッチ 13px（3-4 の段と一致）

### 6-7. 未定

- リスト画面の背景 — `#bg` のグラデ／模様を敷くか無地か（実装に指針なし）

---

## 7. 実装で見つかった不揃い（未修正・報告のみ）

新画面を作るときに踏襲しないこと。直すかどうかは別途判断。

1. **古いコメント**: `:root` の `--hotDur` 説明「吸着の合図は色だけ。幅は動かさない」は
   現状と不一致。実際は `.zone.snap` の間 `width` が動く（Δ ぶん広がる）
2. **タップ領域が 48px 未満（問題画面・ナビのみ）**: 4.3 の確定値での現状は次のとおり。
   `.iconbtn` `.plainbtn` は **normal 52px で満たすが compact 44px は未達**。
   `#gear` は **normal 42px / compact 38px でどちらも未達**。
   `ZONE_MIN` 20px も未達（吸着の catch 半径 40px で補う）。
   リスト画面の行（`.toggle` `.kv` `.mode`）は 48px を満たす
3. **未検証のコメント**: `.eq.hit` の 60px / compact 42px は「`.readout` が伸縮するので
   収まる（要実機確認）」とコメントされたまま
