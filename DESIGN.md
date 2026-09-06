# Make10 デザイントークン

メニュー・設定など新しい画面を作るときの共通の物差し。
値はすべて `web/index.html` の実装から抜いたもので、問題画面（`#play`）は
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
  tabular-nums が効く）。Google Fonts の読み込み前・失敗時、および 11 章のフォント
  同梱が済むまでの Capacitor 環境ではフォールバックが実際に起こり得る。
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
| 数字 | `.num` | 46 | 36 |
| 演算子・階乗 | `.tok.op` `.tok.fac` | 31 | 26 |
| 括弧 | `.tok.lp` `.tok.rp` | 37 | 31 |
| トレイの記号 | `.chip` | 33 | 26 |
| ドラッグ中の分身 | `#ghost` | 34 | 34 |
| 画面見出し | `.sheet h2` / `.title`(ホーム) | 17 / 31 | 同 |
| 節見出し | `.sheet h3` | 13 | 13 |
| 本文 | `.sheet p` `li` / `.rule` | 13 / 14 | 13 |
| リスト項目 | `.toggle` | 13.5 | 13.5 |
| 補助文 | `.small` `.sub` `.code` `#trayhead` | 11〜12.5 | 同 |
| バナー内 | `#banner` | 11 | 11 |

**なぜ compact があるか**: 広告 52px を引くと縦が足りない端末向け。
文字サイズだけを媒体クエリで縮め、箱の寸法は `TOKEN_METRICS.compact` が持つ。

---

## 3. 寸法

### 3-1. トークン（`TOKEN_METRICS`、JS が唯一の定義。CSS へは変数で流す）

| 項目 | normal | compact | 意味 |
|---|--:|--:|---|
| `num` | 28 | 23 | 数字の箱幅。実機調整で確定 |
| `numMx` | 2 | 1 | 数字の左右マージン |
| `op` | 34 | 29 | 演算子の箱幅 |
| `fac` | 19 | 16 | 階乗の箱幅 |
| `par` | 20 | 18 | 括弧の箱幅 |
| `h` | 64 | 50 | トークンの高さ |
| `FAC_ML` | -2 | -2 | 階乗の食い込み（`margin-left`）。定数で共通 |

数字の 1 文字は 28px の箱に入れて中央寄せ。長い式では合計幅が画面を超え、
式全体が `transform: scale()` で縮む（下限 `MIN_SCALE` = 50%、実測 85% 程度）。
**縮小は仕様。不具合ではない**（GAME-SPEC 4-5）。

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
| 小物（枠 `.zone` / 差し替え `.tok.swap` / バー `.bar`） | 5 |
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
- 現状の実装はこれを下回るものがある（→ 6 章の不揃い）。踏襲しない

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
（LIST-TRIAL 2.8 / COLOR-TRIAL 2.9 とも採用）。以下の値は `web/index.html` の実装そのもの。
`@media (max-height:700px)` はリスト画面の要素を再指定しない（全高で同じ見た目）。

比較用の `web/v27.html`（2.7・LIST-TRIAL 前）と `web/v28.html`（2.8・COLOR-TRIAL 前）は
**Git 導入まで残す**。まだバージョン管理下に無く、実装を戻せる手段がこの 2 ファイルしかない。

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
| `.mode .mi`（アイコン） | `width:30px` / flex 中央。中身は `.ic`（24×24 / `stroke:currentColor` / `stroke-width:2` / round）のインライン SVG。挑戦モードの 3 状態（`ICON_LOCK` / `ICON_STAR` / `ICON_TROPHY`）は `innerHTML` 差し替え |
| `.mode .mt`（名前） | `flex:1` / 15px / 700 / `color:var(--paper)`。プレーンテキスト（`<b>`/`<span>` の入れ子はやめた） |
| `.mode .mv`（右端の値） | `flex:0 0 auto` / 13px / `color:var(--dim)` / `white-space:nowrap`。値は `renderHome()` / `renderHeldPick()` が入れる。ホームの `m-held` は 0 のとき空文字、`#heldpick` は 0 でも `N / M` を出す |

行の高さ = `padding 14×2 + 中身 max(24px アイコン, ~18px テキスト) ≈ 52px`（`min-height:48px` を満たす）。

### 6-5. 開発者パネル `#devpanel`（`#settings` 内・リスト画面のルールの対象外）

- `margin-top:18px` / `padding-top:14px` / `border-top:1px dashed var(--edge)` で区切る
- 見出し `#devpanel h3` と `.dv b` と `input` の `accent-color` は `--teal` のまま（開発用に目立たせる）

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

1. **`--dur` / `--hotDur` の二重値**: CSS `:root` は `.14s` / `.1s`、実行時は
   `applyDevVars` が 300ms / 200ms に上書き。静的に読むと違う値が見える
2. **古いコメント**: `:root` の `--hotDur` 説明「吸着の合図は色だけ。幅は動かさない」は
   現状と不一致。実際は `.zone.snap` の間 `width` が動く（Δ ぶん広がる）
3. **タップ領域が 48px 未満（問題画面・ナビのみ）**: `.iconbtn` `.plainbtn` は 44px
   （compact で 38px）、`#gear` 38px、`ZONE_MIN` 20px（吸着の catch 半径 40px で補う）。
   リスト画面の行（`.toggle` `.kv` `.mode`）は 48px を満たす
4. **未検証のコメント**: `.eq.hit` の 60px / compact 42px は「`.readout` が伸縮するので
   収まる（要実機確認）」とコメントされたまま
