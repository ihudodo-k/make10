# Make10 開発の指示

4つの数字（0〜9、順序固定）の間に四則演算・累乗・階乗・括弧を入れて
10 を作るパズルゲーム。Capacitor で Android アプリ化し
Google Play で配布予定。

## ファイル構成

| パス | 内容 |
|---|---|
| docs/index.html | ゲーム本体。単一 HTML の試作。GitHub Pages の配信元 |
| docs/v27.html / docs/v28.html | 比較用に残した過去版（2.7 / 2.8）。3.0 の実機確認が済むまで残す |
| GAME-SPEC.md | ゲームの仕様書 |
| DESIGN.md | デザイントークン（配色・文字・寸法・動き・リスト画面のルール） |
| DATA-SPEC.md | データ生成の仕様書 |
| make10.py | 問題データ生成 |
| test_make10.py | make10.py の単体テスト |
| verify_render_roundtrip.py | 生成済み DB の検証（GAME-SPEC 12 章の往復チェック）。`solutions.display` を独立実装のパーサで読み直し、その木から値・`uses_fraction`・`score` を計算し直して DB の値と突き合わせる。make10.py は一切参照しない |
| make10.db | 生成済みの問題データ（生成物。**`.gitignore` で除外**） |
| make10_puzzles.json | make10.db から書き出す、ゲーム本体が読む JSON（生成物。形式は DATA-SPEC 8 章） |
| make10_backup_0099.db / make10_backup_full.db | 生成途中のバックアップ DB（**`.gitignore` で除外**） |
| assets/icons-ref/ | アイコンの参考画像 |
| assets/mockup-play-screen.png | 問題画面のモックアップ |
| __pycache__/ | Python のキャッシュ（**`.gitignore` で除外**） |

## ファイルの配置

- ゲーム本体は `docs/` 配下にある（`docs/index.html`）。仕様書・データ生成・DB は
  リポジトリ直下。**`docs/` の中と外に同名のディレクトリを作らない**
  （過去に `assets/fonts/` を直下だけ消して `web/assets/fonts/` を残す取り違えをした。
  当時はゲーム本体が `web/` 配下にあり、その後 `docs/` に改名した。
  ディレクトリ名は変わったが、この失敗の教訓はそのまま当てはまる）
- ファイルを削除・移動したときは、**同名のものが他の階層に残っていないか `find` で
  確認してから**完了報告を書く
- GitHub Pages は `main` ブランチの **`docs/` フォルダ**から配信される。
  手元の `docs/index.html` がそのまま公開されるので、
  **コピーやアップロードの手作業は要らない**
- 公開 URL は https://ihudodo-k.github.io/make10/ 。
  `docs/v27.html` `docs/v28.html` も同時に公開され、
  `.../v27.html` `.../v28.html` で比較できる

## 毎回守ること

### バージョン管理

- このプロジェクトは Git 管理下にある。**作業を始める前に `git status` で
  作業ツリーがきれいなことを確認する。** 未コミットの変更が残っていたら、
  何が残っているかを報告してから作業に入る
- **完了報告に `git status` も貼る。** `git diff --stat` は**新規の未追跡ファイルを
  出さない**ので、それだけでは「増えたファイル」を見落とす。削除されたファイルも同じ
- **完了報告に `git diff --stat` と `git diff` の出力を貼る。**
  報告文の説明より、実際に変わった行のほうが正確なため
- **指示されていないファイルを作らない・消さない・改名しない。**
  必要だと判断したら、実行せずに提案として報告する。指示書やデータの複製が黙って
  増えると、どちらが正なのか後から判断できなくなるため
- **コミットはしない。** 変更を残したまま報告する。コミットするかどうかは
  こちらが差分を見てから判断する
- `git push` も行わない

### バージョンと変更履歴

- index.html に変更を加えたら **必ず APP_VERSION を上げる**
- 小数第一位を 1 ずつ上げる（1.4 → 1.5、1.9 の次は 2.0）
- 1 回の作業で上げるのは 1 回だけ
- このファイルの変更履歴に 1 行追記する
- **過去の変更履歴の行は書き換えない。当時の記録として残す**

### 仕様書を実装と一緒に直す

- 挙動・画面・データ件数を変えたら、**同じ作業の中で**
  GAME-SPEC.md または DATA-SPEC.md を直す
- **完了報告に「どの仕様書のどこを直したか」を必ず書く**
- 仕様書を直さずに実装だけ終わらせない

### 原因を特定してから直す

- 不具合を直すときは、**原因を特定して報告してから**修正する
- 推測で書き換えない
- 「たぶんここだろう」で複数箇所を同時に変えない

### 性能は計測で判断する

- 「transform だから速い」のような机上判断で決めない
- 変更後に Chrome DevTools の Performance で確認する
- 過去に机上判断で誤った実装を入れた実績がある

## 実装のルール

### 表示文字列は元の木に戻せること

式を文字列にするとき、**標準的な文法で読み直したときに
元の構文木と同じ意味になること。** 値が一致するだけでは不十分。

過去に 2 回この種のバグを出している（GAME-SPEC 12 章）。

### 検証は生成と独立に実装する

生成側の関数を検証に流用しない。同じ前提を共有した検証は検証にならない。

### 寸法の定数は 1 箇所に持つ

トークンや枠の幅などの寸法は **JS 側に定数として持ち、
CSS へは変数で渡す。** CSS と JS に同じ数値を別々に書かない。

### ドラッグ中にレイアウトを起こさない

- 位置や大きさの変化は原則 transform で表現する
- width / top / left のアニメーションはレイアウトを起こす
- 例外的に width を使う箇所（吸着した枠）は、
  **1 要素だけ・短時間に限る**
- 縮小率は事前に算術で求める。offsetWidth を毎フレーム読まない

### 開発者パネルにキーを足したら load() をマージにする

load() は `{...DEV_DEFAULT, ...s.devVars}` の形を保つこと。
そのまま代入すると、古い保存データで新しいキーが undefined になり
レイアウト計算が NaN になる。

### 開発者パネルは削除しない

調整用に使い続けるため。

## 画面のルール

- **画面を作る・変えるときは DESIGN.md を読む。** 配色・文字サイズ・寸法・
  角丸・動き・リスト画面（設定・メニュー）のルールはすべてそちらにある
- 次の 2 点は毎回効くのでここにも残す:
  - **アプリ全体でアクセント色を使わない（モノクロ基調）。** 意味を持つ色は
    コーラル = 注意・エラー、`--slate` = 無効 だけ。`--teal` は開発者パネル専用、
    `--gold` は未使用（詳細は DESIGN.md 1-2）
  - 問題画面は高さ 100dvh。**スクロールを発生させない**
- 配色は藍テーマ 1 つ（白は開発者パネル専用）。色を直接書かず必ずテーマ変数から作る（詳細は DESIGN.md 1 章）

## 変更履歴

| ver | 日付 | 内容 |
|---|---|---|
| 1.4 | 2026-09-06 | devVars の既定値を実測値に更新、APP_VERSION 導入、CLAUDE.md を分割 |
| 1.5 | 2026-09-06 | 比較用の書体切り替えを開発者パネルに一時追加（FONT-TRIAL、決定後に削除） |
| 1.6 | 2026-09-06 | FONT-TRIAL の候補を Zen Kaku 系に入れ替え、数字ウェイト 700/900 切り替えを追加 |
| 1.7 | 2026-09-06 | 書体を Barlow Condensed ＋ Zen Kaku Gothic New（数字ウェイト 700）に確定し FONT-TRIAL を撤去。font-weight:800 は全て 700 に |
| 1.8 | 2026-09-06 | 書体を Zen Kaku Gothic New 単体に変更（伝達ミスの訂正）。Barlow Condensed の link と font-family 参照を削除 |
| 1.9 | 2026-09-06 | 比較用に League Gothic / Oswald を開発者パネルに一時追加（FONT-TRIAL2、ローカル同梱、wdth スライダー付き、決定後に削除） |
| 2.0 | 2026-09-06 | 書体を Zen Kaku Gothic New で確定。FONT-TRIAL2 と assets/fonts/（League Gothic・Oswald）を撤去 |
| 2.1 | 2026-09-06 | 配置候補の統合: 挿入後のトークン列が同一になる枠は最も右の1つだけ残す（既存の括弧の隣に同じ括弧を置くケース） |
| 2.2 | 2026-09-06 | 数字の箱幅 --numW と左右マージン numMx を開発者パネルで調整可能に（TOKEN_METRICS.normal を上書き、compact は比で追従）。数字0〜9の実描画幅と幅の整合チェックを実測値に追加 |
| 2.3 | 2026-09-06 | 開発者パネルの実測表示を退避値方式に変更。設定シートを開くと問題画面が display:none で測れないため、layoutZones()／fit() が画面表示中に測った値を devSnap に退避し、パネルはそれを計測時刻付きで表示するだけにする。未計測時は「未計測」表示 |
| 2.4 | 2026-09-07 | 「幅の整合」の退避を fit() から hideZones() へ移動（fit() はプレイ中ほとんど呼ばれない）。枠を閉じる直前に .expr 実測幅から live 枠の実測幅を引いてトークンだけの幅を退避する |
| 2.5 | 2026-09-07 | 数字の箱幅を確定（TOKEN_METRICS normal num:28/numMx:2、compact num:23/numMx:1）。numW/numMx の調整スライダーと devVars キー、applyMetrics() の上書き処理を撤去。実測表示（描画幅・幅の整合）は検算用に存置。GAME-SPEC 4-5 に「最長式で 85% 縮小がかかるのは仕様」と明記 |
| 2.6 | 2026-09-07 | A群の整理: 挑戦ロック時の効いていない揺れコードを削除／非表示中の階乗表を復元しないよう HIDDEN_UI 定数と factShow(on,persist) を追加（保存値は保持）／制約表示の k===1 死んだ分岐を削除し conOf() に k!==0 警告を追加 |
| 2.7 | 2026-09-07 | 2.6 の積み残し。未使用 CSS .chip .badge を削除（挙動変更はこれだけ）。tabular-nums は Zen Kaku では無効だがフォールバック用に存置する旨のコメントを .eq に追加。仕様書を実態に合わせて修正（GAME-SPEC 3: 制約違反はそもそも組めず判定は保険／GAME-SPEC 5: display:none!important／DESIGN.md 2-1: tabular-nums／CLAUDE.md: パス表記と「ファイルの配置」節）。web/assets/fonts/ の残骸はユーザー側で削除済みを確認 |
| 2.8 | 2026-09-07 | リスト画面の作り直し（試作・LIST-TRIAL）。設定行を .group（節ごとの面）＋インセット区切り線に。.sheet h3 を --slate に、遷移矢印 › を .chev（SVG）に、モードの絵文字を .ic 形式の SVG に統一。#settings/#stats を .group で囲み、.kv を設定行に統一、.th を padding 14px に。ついでに #ctot が scoreOn を無視していたバグ修正、#m-held の .lock を外す。比較用に web/v27.html（2.7）を保存。DESIGN.md 6-3 に試作の記録を追加（6-1/6-2 は未変更） |
| 2.9 | 2026-09-07 | 単色化（試作・COLOR-TRIAL）。--teal / --gold の使用箇所を --paper に統一（開発者パネルの --teal 3 箇所のみ据え置き）。#factbtn.on の直値 rgba を color-mix に。テーマを藍 1 つに絞り sumi/fuji を削除、白は開発者パネル専用として定義存置。未使用の --tileBg/--tileInk/--par を削除。applyTheme() に現存しないテーマ→藍の移行を追加。THEMES を 2 件に縮小し paper のスウォッチ色ずれ（#F2EFE6→#E8E3D5）を修正。比較用に web/v28.html（2.8）を保存。DESIGN.md 6-4 に試作の記録を追加（1 章・6-1・6-2 は未変更） |
| 3.0 | 2026-09-07 | COLOR-TRIAL を確定（DESIGN.md 1 章・1-2 に反映、6-4 削除、6-3 の却下手順を訂正）。明るさの段階を整理: --dim（--paper の 70%、color-mix を変数化）を新設し、リスト画面の副次テキスト（.small / .chev / プレースホルダ / .mode の値）を --slate → --dim に、.sheet h3 を --paper・14px に。--slate は「無効」専用に限定（#play の --slate は不変）。ホーム整理: .tag と m-course/m-free の説明文を撤廃、.mode を「アイコン＋名前＋右端の値（.mv）」の 1 行に。挑戦ロックの文言を「あと N 問」に短縮。#heldpick も同構造（0 でも件数表示）。GAME-SPEC 7-2 更新 |
| 3.1 | 2026-09-07 | バグ 3 件の修正。①非表示中は applyScale() が縮小率に触らないようにし、go("play") で測り直す（設定内のトグルで scale が 0.5 に落ちる／長い式の縮小が外れる／start() の初回描画が非表示のまま走る、をまとめて解消）。②設定のトグルの死んだガード if(SCR==="play")render() を playDirty＋enterPlay() に置換。③「全部消す」を clearAll() に分離し、時間・手数・ヒントを引き継ぐ。④ヒントを見た段階を G.hints として端末に保存（解き直し・再起動でも戻らない）。⑤solved フラグを導入し、record() を advance() から win() へ移して記録を 1 回だけに。正解カードは lastWin から出し直す。GAME-SPEC 3-1・4-3・8-1・9・10 を更新 |
| 3.2 | 2026-09-07 | 「全部消す」が正解カードを隠さないようにした（clearAll() の $("win") 非表示を !solved のときだけに）。正解後に押すと「つぎへ」が消えて先へ進めなくなっていた。記録は正解時に確定済みなので、カードは盤面の内容と独立に出したままでよい。GAME-SPEC 8-1 の該当行を修正 |
| 3.3 | 2026-09-07 | 寸法調整用スライダーの一時追加（SIZE-TRIAL、**決定後に撤去する**）。実機（Android）で数字・階乗・アイコンが小さすぎる件を実機で詰めるため、開発者パネルに 数字/階乗/演算子/括弧の文字サイズと箱幅・トークンの高さ・.iconbtn・#gear の 11 項目を追加。文字サイズと .iconbtn/#gear の寸法を CSS 直値から TOKEN_METRICS へ移し、applyMetrics() が --numF/--opF/--facF/--parF/--btnW/--gearW として流し込む形に統一（@media の文字サイズ 3 行と .iconbtn の上書きを削除）。スライダーは normal だけを動かし、compact は既定値どうしの比で追従（SIZE_KEYS / SIZE_RATIO / metricsFor()）。DEV_DEFAULT へ 11 キーを TOKEN_METRICS.normal 参照で追加、SIZE-TRIAL 専用のリセットボタンと compact 追従値の表示を追加。実測表示（数字の描画幅）もスライダーの値で測るように変更。**既定値は 1 つも変えていない** |
| 3.4 | 2026-09-08 | SIZE-TRIAL の調整環境を直す（**SIZE-TRIAL は決定後に撤去する**）。#devpanel を #settings の中から #app 直下へ移す**恒久的な構造修正**（position:fixed だけでは #settings が display:none のとき描画されないため、DOM 上の場所を出す必要がある）。画面下部に重ねる形にし（高さ 40dvh・パネル内スクロール・sticky ヘッダ）、開く導線は設定シートの #dv-open-row、閉じるのは #dv-close、全体を見渡すための「たたむ」#dv-min を追加。#devpanel は SCREENS に入れないので go() は無変更。renderDevPanel() から .hide の切り替えを外し、devOpen / devPanelShow() に分離。あわせて .plainbtn（メニューボタン）を .iconbtn と同じ --btnW 共有にし、@media の 38px 指定を削除。devSnap（2.3〜2.4）は据え置き |
| 3.5 | 2026-09-08 | アイコンの形の修正。①ICON_STAR のパスが左右非対称で viewBox 下端をはみ出していた（y=4〜23.6、stroke 込み 24.6）ので、中心 (12,12)・外周 8.2・内周 3.13 の左右対称な五芒星に書き直し。同じ壊れたパスが #heldpick の hp-chal にも直書きされていたので両方直した（y=3.8〜18.63 に収まる）。②#gear の絵文字 ⚙ を .ic 形式の SVG（ICON_GEAR、8枚歯）に置換。設定画面での ← は ICON_BACK（.chev を x=12 で左右反転した ‹）にし、go() が innerHTML と title/aria-label を差し替える形に変更。③他のアイコン 12 種はgetBBox で viewBox 内・対称性を確認し、いずれも問題なし（ICON_TROPHY の脚と台座の2.5px の隙間だけ報告済み・未修正）。形の修正のみでサイズ・デザインは変更なし |
| 3.6 | 2026-09-08 | ICON_TROPHY の脚を M12 14v3.5 → M12 14v6 に修正。脚が y=17.5 で終わっていて台座（y=20）との間に 2.5px の隙間ができていた座標の誤り。描画して脚と台座が繋がっていることを確認（脚 y 14〜20 / 台座 y 20、隙間 0）|
| 3.7 | 2026-09-08 | アイコンの描画サイズを SIZE-TRIAL に追加（**決定後に撤去する**）。--btnW は箱の大きさしか変えず、中の SVG は .ic{width:24px} 固定だったので、TOKEN_METRICS に ic:24 を追加し .ic{width:var(--icW)} に。スライダー「アイコンの線の大きさ」（16〜40）を追加。あわせて .ic に flex:0 0 auto を付けた ―― .top button{padding:6px 11px} が .iconbtn{padding:0} に競り勝って #back の内寸が 20px（#menu は 22px）しかなく、24px の .ic が flex で縮んでいた。これが「丸ボタンのスライダーを動かしても三本線が変わらない」の直接の原因。この修正で #back / #menu のアイコンは既定でも 20/22px → 24px になる（#clear / #hint は元から 24px）。.mode .mi は calc(var(--icW) + 6px) にして追従（既定 30px は不変）。.chev は .ic とは別クラス（16px 固定）なので影響なし |
| 3.8 | 2026-09-08 | 入力まわりの修正 4 件。①.tok.swap の塗った角丸タイル（--paper 18%・radius 5）を .chip.sel と同じ「記号を明るくして下線 1 本」に変更。問題画面でトークンに面を塗る箇所が無くなった。②差し替えの当たり判定を距離式に変更: nearZone() を nearest(sel,max) に一般化し nearZone / nearSwap を作成。tgt() は直撃を優先しつつ、外れたときは枠と差し替えを同じ距離で比べて近いほうを採る（同距離は枠）。許容距離 DEV_SWAP を DEV_CATCH とは別キー（devVars.swapCatch、既定 40）にして開発者パネルにスライダーを追加。演算子3つで隙間が無い状態の死に地（数字の上 32px×2）が解消。③式が変わらない差し替え（同じ記号を重ねただけ）で moves を増やさないようにした（ドラッグ・タップ両方）。④タップ配置で held があるときは式の記号を押しても消えないようにした（選択解除はトレイの同じチップ）。GAME-SPEC 4-1・4-3、DESIGN.md 1-2・3-4 を更新 |
| 3.9 | 2026-09-08 | .tok.swap から color:var(--paper) を外し、下線（box-shadow）だけの強調にした。式の中には「数字 → 演算子 → 括弧」の明るさの段階があり、強調中だけ演算子が数字と同じ明るさになるとその段階が一時的に崩れるため。.chip.sel が明るさを上げているのはトレイの中に明るさの段階が無いからで、式の中とは事情が違う。DESIGN.md 1-2 にこの区別を追記 |
| 4.0 | 2026-09-08 | SIZE-TRIAL にトレイと階乗の食い込みを追加（**SIZE-TRIAL は決定後に撤去する**）。①開発者パネルを上側／下側に付け替える #dv-pos を追加（devVars.devTop に保存）。下だとトレイが必ず隠れて調整できなかった。クラス名は .dvtop ―― .top にすると問題画面のヘッダ .top{display:flex} に当たってパネル自体が横並びの flex になる。ヘッダはボタン 3 つで折り返すので見出し側を省略表示に。②TOKEN_METRICS に chipF（.chip の文字サイズ 33/26）・trayGap（.tray の gap 2/2）・trayPad（.tray の padding 6/4）を追加し、CSS は var(--chipF)/var(--trayGap)/var(--trayPad) 受けに。@media の .chip{font-size:26px} と .tray{padding:4px} は二重管理になるので削除。③定数 FAC_ML(-2) を廃止し TOKEN_METRICS.facMl（normal/compact とも -2、比 1.0）へ移動。tokensWidth() も MET.facMl を見る。④SIZE-TRIAL が 16 項目になったので「式のトークン／トレイ／ボタン・アイコン」の 3 節に分割。#devpanel h3 に .sheet h3 と同じ様式を指定（3.4 で #settings の外へ出して以来効いていなかった）。**既定値は 1 つも変えていない** |
| 4.0 追補 | 2026-09-08 | DESIGN.md の訂正のみ（index.html は無変更・APP_VERSION 据え置き）。6-5 を 3.4 の #app 直下移動と 4.0 の .dvtop/.min/#devpanel h3 に合わせて全面改稿、3-1 の FAC_ML 行を facMl へ、2-2 の compact の説明を訂正 |
| 4.1 | 2026-09-08 | SIZE-TRIAL の normal を確定し、compact も実機で決められるようにした（**SIZE-TRIAL 自体はまだ撤去しない。撤去は次の作業**）。①TOKEN_METRICS.normal を実機の確定値へ（num32/op30/fac19/par16/h59/facMl-3/numF52/opF32/facF39/parF42/btn52/gear42/ic28/chipF38/trayGap0/trayPad9。numMx はスライダーが無いので 2 のまま）。compact は未確定のまま据え置き。②SIZE_RATIO（compact を比で追従させる仕組み）を廃止し、devVars を sizeN / sizeC の 2 組に分割。スライダーは matchMedia(COMPACT_MQ) で判定した「今の画面のモード」を直接編集し、モードが切り替わったら matchMedia の change で renderDevPanel() を呼び直す。sizeN/sizeC は入れ子なので {...DEV_DEFAULT} の浅いコピーだと既定値を共有して壊れる ―― devDefaults() を追加。3.3〜4.0 のフラットな保存データは load() で SIZE_KEYS を捨てて既定から作り直す。#dv-copyline を dev / normal / compact の 3 行（textarea）に。#dv-reset・#dv-size-reset は 2 組とも既定へ。compact の既定値がスライダーの下限を割っていた（trayPad 4<6 / btn 38<40）ので可動域の min を広げた。③開発者パネルの節を h3 クリックで折りたためるように（▾/▸、G.devSecs に保存、既定は SIZE-TRIAL の 3 節だけ開）。見出しの無かった先頭の塊に「枠・吸着（基本）」を与え、SIZE-TRIAL の帯は節ではないので折りたたみ対象外。#devpanel.min（パネル全体をたたむ）とは別物。④:root の --dur/--hotDur を .14s/.1s → .3s/.2s にして applyDevVars() の上書き値と揃えた（挙動は不変）。DESIGN.md 2-2・3-1・6-5・7 章、GAME-SPEC 4-5 を更新 |
| 4.2 | 2026-09-08 | 4.1 で書いた**誤った実測値の訂正**と、置き場所を誤っていた UI の削除。①DESIGN.md 3-1 と GAME-SPEC 4-5 に例として書いた最長の式 `(((( 5!!+8!!×3!!+6!! ))))` は**このゲームでは作れない**（canPut() は `!` の左に `!` を置けない。GAME-SPEC 2-4）。原因は 4.1 の計測スクリプトの出力行 `GLYPH[t.t]` ―― GLYPH は種類キー（"+" "!" "lp"）で引く表で t.t（"op" "fac"）では引けず、演算子と階乗が undefined になって join("") で消えた。残った `((((5836))))` から内訳（階乗 8・数字 4）を見て手で復元したのが誤り。**縮小率 79%/88% 自体は livePositions()＋put() で組んだ合法な状態から出ており正しかった。**②canPut() だけを辿る全探索（6,890,240 状態）で最長の式を求め直し、23 トークン（数字4・演算子3・( 4・) 4・! 8＝各記号の上限）・幅 490px(normal)/443px(compact)、実測 79.2%/88.5% を確認。例の式を `((((5!)!)!)!)!+8!+3!+6!` に差し替え、導出（上限の根拠と式）も併記。③#dv-compact-v を削除（4.0 までは比で算出した compact 値を見る唯一の窓だったが、4.1 で比を廃止して役目が終わった。同じ内容は #dv-copyline の 3 行目が出す）。renderDevMeasured() の代入も削除。空の `<b>` ごと消えた。④GAME-SPEC 4-5 の開発者パネルの記述を現状に（スライダー 6 本→23 本の内訳、SIZE-TRIAL は決定後に撤去・normal 確定/compact 未確定、節の折りたたみ、`#app` 直下で全画面に重なること、2.5 で撤去→3.3 で作り直したという順序）。⑤DESIGN.md 3-5 の参照先「6 章の不揃い」を 7 章に訂正 |
| 4.2 追補 | 2026-09-08 | 文書の訂正のみ（index.html は無変更・**APP_VERSION は 4.2 で据え置き**）。①AGENTS.md の削除を指示されたが、**リポジトリにも Git の索引にも全履歴にも存在しなかった**（find・git ls-files・git log --all で確認）。作った記録も無いので削除はしていない。②CLAUDE.md「バージョン管理」に運用ルールを 2 つ追加 ―― 完了報告に git status も貼る（git diff --stat は新規の未追跡ファイルを出さないので、それだけでは増えたファイルを見落とす）／指示されていないファイルを作らない・消さない・改名しない（必要なら実行せず提案として報告する）。③GAME-SPEC 4-5 末尾の「パネルを開くと問題画面が display:none になる」を訂正。3.4 以降 #devpanel は #app 直下で SCREENS に入らず、#dv-open が goBack() で元の画面へ戻すため、パネルを開いているあいだ問題画面は見えている。ただし設定シートを開き直すと go("settings") が #play を隠すので測れる場面と測れない場面が混ざる ―― devSnap（退避方式）の説明はその理由に付け替えて存置。④DESIGN.md 2-1 の「11 章」に文書名を補って「GAME-SPEC 11 章」に（DESIGN.md は 7 章までしかなく誤読しうる）。文書名なしの他文書参照は grep で全数確認し、この 1 件だけだった。⑤縮小率 79.2%/88.5% に測定条件（画面幅 430px）を明記し、幅ごとの実測表（430/390/360px）を DESIGN.md 3-1 に追加。狭い端末ほど縮むことを両文書に明記 |
