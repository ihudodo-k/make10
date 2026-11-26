# -*- coding: utf-8 -*-
"""見た目の決まり（7.3。DESIGN.md 1 章・BRAND.md 7 章）。

色の使い方を、計算後のスタイルで見る:
  - 金（--gold）は 3 か所だけ ―― 正解の「10」・ホームの進捗の線・「つぎへ」の下線
  - 赤（--coral）は注意専用 ―― 注意の文と赤い括弧（と、外へ出して削除の合図）
  - 10 だが使えない記号を使ったときの「10」は 75%（10 でない値の 50% とは別）
  - 丸ボタンの輪は出さない。「全部消す」「ヒント」だけ開発者パネルで出せる（既定は出さない）
  - 囲まない: 背景は単色、ヒントの箱は上下の線だけ、設定は面なし
  - 遊び方（9.5）: 並びと文・見本の盤（Web のデイリーと同じ部品。盤の実物と同じ見た目・動き）・アイコン・はみ出し
色はテーマ変数を解決した値と比べる（直値を書かない。値は DESIGN.md 1-1 の表が正）。
"""
import time

NAME = "見た目の決まり（色・面・線）"

NONE = "rgba(0, 0, 0, 0)"
# テーマ変数を解決した色
V = ("(n=>{const e=document.createElement('i');e.style.color='var('+n+')';"
     "document.body.appendChild(e);const c=getComputedStyle(e).color;e.remove();return c})")
# ある色を、文字・地・枠のどこかに使っている要素の一覧（見えていない要素も含めて全部）。
# 遊び方の見本の盤（9.5）は数えない ―― 見本の金の「10」は正解の「10」の見本（Web の遊び方と同じ）。遊び方の中は help_sheet() が見る。
# 文字色は継承するので、親と同じ色の子は数えない（色を「決めている」要素だけを挙げる）
USES = ("(v=>{const col=%s(v),out=[];"
        "for(const e of document.querySelectorAll('#app *,#banner,#banner *,#toast')){"
        "if(e.closest('#devpanel,#help .hdemo'))continue;const c=getComputedStyle(e),pc=getComputedStyle(e.parentElement).color,"
        "name=e.id?('#'+e.id):(e.tagName.toLowerCase()+'.'+[...e.classList].join('.'));"
        "if(c.color===col&&pc!==col)out.push(name+':文字');"
        "if(c.backgroundColor===col)out.push(name+':地');"
        "for(const s of ['Top','Right','Bottom','Left'])"
        "if(c['border'+s+'Color']===col&&c.color!==col&&parseFloat(c['border'+s+'Width'])>0)out.push(name+':枠'+s)}"
        "return [...new Set(out)].sort()})" % V)


def uses(ui, var):
    return ui.ev("%s(%r)" % (USES, var))


def run(ui):
    # ── 1. 金は 3 か所だけ ────────────────────────────────
    ui.open({"ci": 137, "cleared": 162, "hintStock": 10})
    ui.check("金と赤と文字の色は別の色", ui.ev("new Set(['--gold','--coral','--paper','--dim','--slate','--ink'].map(%s)).size" % V), 6)
    gold_idle = ["#cbar:地", "#wnext:枠Bottom"]
    ui.check("ホーム: 金は進捗の線（と、まだ出ていない「つぎへ」の下線）だけ", uses(ui, "--gold"), gold_idle)
    ui.check("ホーム: 進捗の線が見えている・統計の棒は金ではない",
             ui.ev("[$('cbar').getBoundingClientRect().width>0,getComputedStyle($('cbar')).backgroundColor===%s('--gold')]" % V),
             [True, True])
    ui.ev("start('course')")
    ui.check("問題画面（解く前）: 金は増えない", uses(ui, "--gold"), gold_idle)
    ui.ev("loadPuzzle(COURSE[0]);put('+',1);put('+',3);put('+',5);render()")     # 8 + 8 + 4 + 2 = 22
    ui.check("10 でない値（22）: 金にならない", [ui.text("eq"), uses(ui, "--gold")], ["22", gold_idle])
    ui.ev("clearAll()")
    ui.check("解くと「正解」", ui.solve(), "10|正解")
    ui.check("正解: 金は「10」・進捗の線・「つぎへ」の下線の 3 か所だけ",
             uses(ui, "--gold"), ["#cbar:地", "#eq:文字", "#wnext:枠Bottom"])
    ui.check("正解: 「10」と「つぎへ」が見えていて、点数のカードは無い（8.7）",
             [ui.visible("eq"), ui.visible("wnext"), ui.ev("$('win')===null")], [True, True, True])
    ui.check("正解: 「正解」の字は字間 24%・中央のまま",
             ui.ev("(()=>{const s=$('sub'),c=getComputedStyle(s),r=document.createRange();r.selectNodeContents(s);"
                   "const b=r.getBoundingClientRect(),q=$('eq').getBoundingClientRect(),f=parseFloat(c.fontSize);"
                   "return [Math.round(parseFloat(c.letterSpacing)/f*100),"
                   "Math.abs((b.left+b.right-f*0.24)/2-(q.left+q.right)/2)<1]})()"), [24, True])
    ui.ev("go('stats')")
    ui.check("統計: 金は増えない（棒は --paper のまま）",
             [uses(ui, "--gold"), ui.ev("[...document.querySelectorAll('#statbars .bar i')].every(e=>getComputedStyle(e).backgroundColor===%s('--paper'))" % V)],
             [["#cbar:地", "#eq:文字", "#wnext:枠Bottom"], True])
    ui.ev("go('settings')")
    ui.check("設定: 金は増えない", uses(ui, "--gold"), ["#cbar:地", "#eq:文字", "#wnext:枠Bottom"])

    # ── 2. 赤は注意専用 ───────────────────────────────────
    ui.open({"ci": 0, "cleared": 0, "hintStock": 0})
    red_idle = ["div.trashmsg:文字"]            # 外へ出して削除の合図（ドラッグ中だけ見える注意の文）
    ui.check("ホーム: 赤は使っていない（隠れている「ここで離すと外れます」だけ）", uses(ui, "--coral"), red_idle)
    ui.ev("start('course')")
    ui.check("問題画面（何も置いていない）: 赤は増えない", uses(ui, "--coral"), red_idle)
    ui.check("「ここで離すと外れます」は普段は見えない",
             ui.ev("getComputedStyle(document.querySelector('.trashmsg')).opacity"), "0")
    ui.ev("put('+',1);put('-',3);put('-',5);put('lp',0);render()")
    ui.check("括弧が合わない: 赤は注意の文と赤い括弧だけ",
             [ui.text("eq"), ui.text("sub"), uses(ui, "--coral")],
             ["括弧が対応していません", "赤い括弧が余っています", ["#sub:文字", "div.tok.lp.lone:文字", "div.trashmsg:文字"]])
    ui.check("括弧が合わない: メッセージの本文は赤ではなく副次色",
             ui.ev("getComputedStyle($('eq')).color===%s('--dim')" % V), True)
    ui.ev("clearAll()")
    ui.click("hint")
    ui.check("ヒントの残りが無い: 注意の文だけ赤",
             [ui.text("sub"), uses(ui, "--coral")], ["ヒントの残りがありません", ["#sub:文字", "div.trashmsg:文字"]])
    ui.ev("go('settings')")
    ui.check("設定: 赤は増えない", uses(ui, "--coral"), ["#sub:文字", "div.trashmsg:文字"])

    # ── 3. 10 だが使えない記号（75%）と、10 でない値（50%） ──────────
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10})
    ui.ev("start('course');loadPuzzle(COURSE.find(p=>p.rc==='S0'))")
    sol = ui.ev("cur.id")
    # − 禁止の問題で、− を使って 10 を作る（4 つの数字と − を含む式を探して置く）
    made = ui.ev(
        "(()=>{const d=cur.id.split('').map(Number),ops=['+','-','*','/'];"
        "for(const a of ops)for(const b of ops)for(const c of ops){if(![a,b,c].includes('-'))continue;"
        "let v;try{v=eval(d[0]+a+d[1]+b+d[2]+c+d[3])}catch(e){continue}"
        "if(v===10){put(a,1);put(b,3);put(c,5);render();return a+b+c}}return ''})()")
    if made:
        ui.check("%s（− 禁止）で − を使って 10: 値は「10」・注意の文・不正解のまま" % sol,
                 [ui.text("eq"), ui.text("sub"), ui.ev("solved"), ui.visible("wnext")],
                 ["10", "− は使えません", False, False])
        time.sleep(0.3)                      # 文字の色の遷移（.eq の color .18s）が終わるのを待つ
        ui.check("10 だが使えない記号: 「10」は 75%・文字の色（金ではない）・拡大しない",
                 ui.ev("(()=>{const e=$('eq'),c=getComputedStyle(e);return [c.opacity,c.color===%s('--paper'),"
                       "c.transform,e.classList.contains('ban'),e.classList.contains('miss'),e.classList.contains('hit')]})()" % V),
                 ["0.75", True, "none", True, False, False])
    else:
        ui.check("− 禁止の問題で − を使って 10 にできる式が見つかる（%s）" % sol, made, "見つかること")
    ui.ev("clearAll();put('+',1);put('+',3);put('+',5);render()")
    notten = ui.ev("$('eq').textContent!=='10'")
    ui.check("10 でない値: 50%（.miss）のまま",
             ui.ev("[getComputedStyle($('eq')).opacity,$('eq').classList.contains('miss'),$('eq').classList.contains('ban')]")
             if notten else "10 になった", ["0.5", True, False])

    # ── 4. 丸ボタンの輪 ───────────────────────────────────
    RING = ("(()=>{const c=getComputedStyle($('clear')),h=getComputedStyle($('hint'),'::before'),b=getComputedStyle($('back')),"
            "R=e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.width,r.height].join()};"
            "return {clear:c.borderTopColor,hint:h.borderTopColor,back:b.borderTopColor,"
            "w:[c.borderTopWidth,h.borderTopWidth,b.borderTopWidth],rect:[R($('clear')),R($('hint')),R($('back'))],"
            "ring:%s('--ring'),on:document.body.classList.contains('rings')}})()" % V)
    ui.open({"ci": 0, "cleared": 0, "dev": True})
    ui.ev("start('course')")
    r0 = ui.ev(RING)
    # 太さは CSS では 1.5px。この検証の画面（倍率 1）では計算後の値が 1px に丸まる（7.2 の輪も同じ）
    ui.check("既定: 輪は出さない（全部消す・ヒント・ホームとも透明。枠の太さは残す）",
             [r0["on"], r0["clear"], r0["hint"], r0["back"], r0["w"]],
             [False, NONE, NONE, NONE, ["1px", "1px", "1px"]])
    ui.check("既定値は輪なし", ui.ev("DEV_DEFAULT.btnRing"), 0)
    ui.ev("G.dev=true; devPanelShow(true)")
    ui.check("開発者パネルに切り替えがある", ui.text("dv-btnRing"), "輪なし（既定）")
    ui.click("dv-btnRing")
    r1 = ui.ev(RING)
    ui.check("切り替えると「全部消す」「ヒント」に薄い輪が出る（ホームには出ない）",
             [r1["on"], r1["clear"] == r1["ring"], r1["hint"] == r1["ring"], r1["back"], r1["ring"] != NONE],
             [True, True, True, NONE, True])
    ui.check("輪を出しても、ボタンの位置と大きさは変わらない", r1["rect"], r0["rect"])
    time.sleep(1.0)                          # save() はまとめて遅らせて書くので待つ
    ui.check("切り替えは保存される・表示が変わる",
             [ui.ev("G.devVars.btnRing"), ui.ev("JSON.parse(localStorage.getItem('make10.progress.v4')).devVars.btnRing"),
              ui.text("dv-btnRing")], [1, 1, "輪あり"])
    ui.click("dv-reset")
    r2 = ui.ev(RING)
    ui.check("既定値に戻すと輪なし", [r2["on"], r2["clear"], r2["hint"], ui.text("dv-btnRing")],
             [False, NONE, NONE, "輪なし（既定）"])
    ui.ev("devPanelShow(false)")
    # 古い保存データ（btnRing が無い devVars）は既定の 0 が補われ、ほかのキーはそのまま読める
    ui.open({"ci": 0, "cleared": 0, "devVars": {"dur": 250, "tenScale": 2}, "devSecs": {"basic": 0}})
    ui.ev("start('course')")
    r3 = ui.ev(RING)
    ui.check("古い保存データ: 輪のキーが補われる（0）・ほかのキーは読める・節「丸ボタンの輪」は既定で開",
             [ui.ev("G.devVars.btnRing"), ui.ev("G.devVars.dur"), ui.ev("G.devVars.tenScale"), r3["on"], r3["clear"],
              ui.ev("({...DEV_SEC_DEFAULT,...G.devSecs}).ring"), ui.ev("G.devSecs.basic")],
             [0, 250, 2, False, NONE, 1, 0])
    ui.open({"ci": 0, "cleared": 0, "devVars": {"btnRing": 1}})
    ui.ev("start('course')")
    ui.check("保存してある輪ありは、開き直しても輪あり", ui.ev(RING)["on"], True)

    # ── 5. 囲まない（背景・上のバー・ヒントの箱・設定） ──────────────
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10})
    ui.check("背景は単色（グラデーションなし）・地の色",
             ui.ev("(()=>{const c=getComputedStyle(document.body);return [c.backgroundImage,c.backgroundColor===%s('--ink')]})()" % V),
             ["none", True])
    ui.check("バナーは地の色に上の線 1 本・文字は変数の色",
             ui.ev("(()=>{const c=getComputedStyle($('banner'));return [c.backgroundColor===%s('--ink'),c.borderTopColor===%s('--edge'),"
                   "c.borderTopWidth,c.color===%s('--bannerText')]})()" % (V, V, V)), [True, True, "1px", True])
    ui.ev("start('course')")
    ui.check("上のバーの情報は画面の中央・色は副次色（--slate ではない）",
             ui.ev("(()=>{const r=document.createRange();r.selectNodeContents($('pmode'));const b=r.getBoundingClientRect(),"
                   "c=getComputedStyle($('pcode')).color;return [Math.abs((b.left+b.right)/2-innerWidth/2)<1,"
                   "c===%s('--dim'),c!==%s('--slate')]})()" % (V, V)), [True, True, True])
    ui.check("共有ボタンは三本線の真下のまま",
             ui.ev("(()=>{const s=$('share').getBoundingClientRect(),m=$('menu').getBoundingClientRect();"
                   "return [Math.abs(s.left-m.left)<0.5,Math.round(s.top-m.bottom)]})()"), [True, 8])
    ui.check("括弧の残数は副次色（無効の色ではない）",
             ui.ev("getComputedStyle(document.querySelector('.chip .stock')).color===%s('--dim')" % V), True)
    ui.click("hint")
    ui.check("ヒントの箱: 地の色（不透明）・上下の線だけ・左右は透明の枠 1px・影と角丸なし・高さ 58px",
             ui.ev("(()=>{const b=$('hintbox'),c=getComputedStyle(b);return [c.backgroundColor===%s('--ink'),"
                   "c.borderTopColor===%s('--edge'),c.borderBottomColor===%s('--edge'),c.borderLeftColor,c.borderRightColor,"
                   "c.borderLeftWidth,c.boxShadow,c.borderTopLeftRadius,Math.round(b.getBoundingClientRect().height*10)/10]})()"
                   % (V, V, V)), [True, True, True, NONE, NONE, "1px", "none", "0px", 58])
    ui.ev("toast('（見た目の確認）')")
    time.sleep(0.4)
    ui.check("トーストは面（--panel）と枠を持つ",
             ui.ev("(()=>{const c=getComputedStyle($('toast'));return [c.backgroundColor===%s('--panel'),c.borderTopColor===%s('--edge')]})()"
                   % (V, V)), [True, True])
    ui.ev("go('settings')")
    ui.check("設定: 面と枠は見えない（透明の枠 1px を残す）・節の見出しは 12px・副次色・字間 8%・行の文字と左端が揃う",
             ui.ev("(()=>{const g=getComputedStyle(document.querySelector('#settings .group')),"
                   "h=document.querySelector('#settings h3'),hc=getComputedStyle(h),r=document.createRange();"
                   "r.selectNodeContents(h);const hx=r.getBoundingClientRect().left;"
                   "r.selectNodeContents(document.querySelector('#settings .toggle span'));const tx=r.getBoundingClientRect().left;"
                   "return [g.backgroundColor,g.borderTopColor,g.borderTopWidth,hc.fontSize,hc.color===%s('--dim'),"
                   "Math.round(parseFloat(hc.letterSpacing)/12*100),Math.abs(hx-tx)<0.6]})()" % V),
             [NONE, NONE, "1px", "12px", True, 8, True])
    ui.check("設定: バージョン表記は副次色・11.5px・行の文字と左端が揃う",
             ui.ev("(()=>{const a=$('appver'),c=getComputedStyle(a),r=document.createRange();r.selectNodeContents(a);"
                   "const ax=r.getBoundingClientRect().left;r.selectNodeContents(document.querySelector('#settings .toggle span'));"
                   "return [c.color===%s('--dim'),c.fontSize,Math.abs(ax-r.getBoundingClientRect().left)<0.6]})()" % V),
             [True, "11.5px", True])
    ui.ev("go('help')")
    ui.check("遊び方: 節の見出しは 12px・副次色",
             ui.ev("(()=>{const c=getComputedStyle(document.querySelector('#help h3'));return [c.fontSize,c.color===%s('--dim')]})()" % V),
             ["12px", True])
    # 白テーマ（開発用）でも同じ決まりが成り立つ
    ui.ev("G.theme='paper';applyTheme();go('home');start('course')")
    ui.check("白テーマ: 色が 6 つとも別・輪の色も決まっている",
             ui.ev("[new Set(['--gold','--coral','--paper','--dim','--slate','--ink'].map(%s)).size,%s('--ring')!==%s('--nothing')]"
                   % (V, V, V)), [6, True])
    ui.solve()
    ui.check("白テーマ: 正解の金も 3 か所だけ", uses(ui, "--gold"), ["#cbar:地", "#eq:文字", "#wnext:枠Bottom"])
    ui.ev("G.theme='ai';applyTheme()")
    ui.check_no_errors("見た目の決まりで JS エラー 0")
    help_sheet(ui)


# ── 遊び方（9.5）。Web のデイリーの遊び方（DAILY-SPEC 13-10）を手本に作り直した ──
HELP_LINES = {
    "ja": [["P", "4 つの数字を順番どおりに全部使って 10 を作ります。"],
           ["H3", "計算のきまり"],
           ["P", "^ は累乗です（2 ^ 3 = 8）"], ["P", "0 ^ 0 は 1 です（0 ^ 0 = 1）"],
           ["P", "^ は右から計算します。2 ^ 3 ^ 2 は 2 ^ ( 3 ^ 2 )"], ["P", "! は階乗です（4! = 4 × 3 × 2 × 1 = 24）"],
           ["P", "0! は 1 です（0! = 1）"], ["P", "階乗は 12! まで。3!! とは書けません。( 3! )! と書きます"],
           ["P", "0 で割る式は正解になりません"],
           ["H3", "操作"],
           ["P", "置いた記号を式の外へ出すと外れます"], ["P", "置いた記号は、つまんで別の場所へ運べます"],
           ["P", "演算子は、置いてある演算子の上に重ねると差し替わります"],
           ["P", "括弧は ( と ) を別々に置きます。相手がいない括弧は赤くなります"],
           ["P", "タップで置く：設定でオンにすると、記号を押して選び、置き場所を押します。置いた記号は押すと外れます"],
           ["P", "全部消す：置いた記号をまとめて外します"],
           ["H3", "ヒント"],
           ["P", "ヒント：3 段階です。押すたびに少しずつ答えに近づきます"],
           ["P", "3段階目の式を押すと、ほかの解き方も見られます。"],
           ["P", "ヒントの数には限りがあります。挑戦モードで 2 問解くごとに 1 つ増えます"],
           ["H3", "モード"],
           ["P", "クラシック … 1000問。だんだん難しくなります"], ["P", "フリープレイ … ランダムに出題。何問でも遊べます"],
           ["P", "挑戦モード … 100問クリアで解放。かなりの難問です"], ["P", "デイリー … 1 日 1 問。みんなが同じ問題を解きます"],
           ["H3", "デイリー"],
           ["P", "1 日 1 回だけ解けます"], ["P", "ヒント：共有でもらえます（1 日 2 回まで）"],
           ["P", "ギブアップ：解答例を見て、その日を終えます"], ["P", "統計：解いた日数・連続日数とカレンダー"],
           ["P", "毎日 0 時（端末の時刻）に新しい問題になります。"],
           ["P", "記録はクラシックとは別に数えます。クラシックのヒントは減りません"],
           ["H3", "共有コード"],
           ["P", "問題ごとにコードがあります。友達に送ると同じ問題が開きます。"],
           ["P", "共有：問題の画面の右上から、コードを送れます"],
           ["P", "問題の画面の上のコードを押すと、コピーできます"],
           ["P", "もらったコードは、ホームの欄に入れてひらくを押します"]],
    "en": [["P", "Make 10 using all four numbers in order."],
           ["H3", "Rules"],
           ["P", "^ is power (2 ^ 3 = 8)"], ["P", "0 ^ 0 is 1 (0 ^ 0 = 1)"],
           ["P", "^ is evaluated right to left. 2 ^ 3 ^ 2 means 2 ^ ( 3 ^ 2 )"],
           ["P", "! is factorial (4! = 4 × 3 × 2 × 1 = 24)"], ["P", "0! is 1 (0! = 1)"],
           ["P", "Factorials go up to 12!. You can't write 3!!; write ( 3! )!"], ["P", "Dividing by 0 never counts as correct"],
           ["H3", "Controls"],
           ["P", "Drag a placed symbol out to remove it."], ["P", "Drag a placed symbol to move it to another spot."],
           ["P", "Drop an operation on top of another to replace it."],
           ["P", "Place ( and ) separately. Unmatched parentheses turn red."],
           ["P", "Tap to place · Turn it on in Settings, tap a symbol, then tap a spot. Tap a placed symbol to remove it."],
           ["P", "Clear all · Removes every placed symbol"],
           ["H3", "Hints"],
           ["P", "Hint · 3 steps, each a little closer to the answer"],
           ["P", "In step 3, tap the expression to see other solutions."],
           ["P", "Hints are limited. You get one for every 2 Challenge puzzles you solve."],
           ["H3", "Modes"],
           ["P", "Classic … 1000 puzzles that get harder as you go"], ["P", "Free Play … random puzzles, as many as you like"],
           ["P", "Challenge … unlocks after 100 clears. Very tough puzzles"],
           ["P", "Daily … one puzzle a day, the same for everyone"],
           ["H3", "Daily"],
           ["P", "One try a day."], ["P", "Hint · Share to get one (up to 2 a day)"],
           ["P", "Give up · See a solution and end the day's puzzle"], ["P", "Stats · Days solved, streaks and a calendar"],
           ["P", "A new puzzle every day at midnight, your local time."],
           ["P", "Daily results are counted separately from Classic. Your Classic hints are not used."],
           ["H3", "Share codes"],
           ["P", "Every puzzle has a code. Send it to a friend to open the same puzzle."],
           ["P", "Share · Send the code from the top right of the puzzle screen"],
           ["P", "Tap the code at the top of the puzzle screen to copy it"],
           ["P", "To open a code you got, enter it on Home and tap Open"]],
}
# 見本の 2 組 [手順の番号, 図の名前, 説明]（Web と同じ文）
HELP_FIGS = {"ja": [["1", "見本: 8 7 5 2 の、8 と 7 のあいだに − を置く", "記号を数字のあいだへドラッグして置きます\n（設定でタップ配置にもできます）"],
                    ["2", "見本: ( 8 − 7 ) × 5 × 2 は、括弧の中から計算して 10。正解", "括弧の中から先に計算します。10 になれば正解です"]],
             "en": [["1", "Example: placing − between 8 and 7 in 8 7 5 2", "Drag a symbol between the numbers\n(or turn on Tap to place in Settings)"],
                    ["2", "Example: ( 8 − 7 ) × 5 × 2 is calculated from the parentheses and makes 10. Solved!",
                     "Parentheses are calculated first. Make 10 and it's solved"]]}
# 遊び方の並び: 見出し（H3）と文（P。見本の説明は .hfig の中なので入らない）
HELP_SEQ = "[...$('help').children].filter(e=>e.tagName==='P'||e.tagName==='H3').map(e=>[e.tagName,e.textContent.trim()])"
HD = "document.getAnimations().filter(a=>(a.animationName||'').startsWith('hd-'))"
# 見本の部品の見た目を、盤の実物と比べる（Web のケース help と同じ比べ方。色・太さ・線は同じ、大きさは盤の寸法 × 倍率 --dk）
HELP_LOOK = r"""(function(){
  const q=s=>document.querySelector(s), cs=e=>getComputedStyle(e), bad=[];
  const dk=parseFloat(cs(q('#help .hdemo')).getPropertyValue('--dk'));
  const same=(name,a,b,props)=>{if(!a||!b){bad.push(name+': 要素が無い');return}
    for(const p of props)if(cs(a)[p]!==cs(b)[p])bad.push(name+'.'+p+': 盤 '+cs(a)[p]+' / 見本 '+cs(b)[p])};
  const ratio=(name,a,b,props,k)=>{if(!a||!b)return;
    for(const p of props){const x=parseFloat(cs(a)[p]),y=parseFloat(cs(b)[p]);
      if(!(x>0)||Math.abs(y-x*k)>0.06)bad.push(name+'.'+p+': 盤 '+x+' × '+k+' / 見本 '+y)}};
  const d=q('#help .hd2');
  same('数字',q('#expr .num'),d.querySelector('.dnum'),['color','fontWeight','fontVariantNumeric']);
  ratio('数字',q('#expr .num'),d.querySelector('.dnum'),['fontSize','width','height','marginLeft'],dk);
  same('演算',q('#expr .tok.op'),d.querySelector('.dtok.op'),['color','fontWeight']);
  ratio('演算',q('#expr .tok.op'),d.querySelector('.dtok.op'),['fontSize','width','height'],dk);
  same('括弧',q('#expr .tok.lp'),d.querySelector('.dtok.par'),['color','fontWeight']);
  ratio('括弧',q('#expr .tok.lp'),d.querySelector('.dtok.par'),['fontSize','width','height'],dk);
  const line=['borderTopColor','borderTopStyle','borderTopWidth','backgroundColor'];
  same('枠',q('#expr .zone.live:not(.hot)'),q('#help .hd1 .dzone'),line);
  same('吸着した枠',q('#expr .zone.hot'),q('#help .hd1 .dhot'),line);
  same('トレイの記号',q('#tray .chip:not(.off)'),q('#help .hd1 .dchip'),['color','fontWeight']);
  ratio('トレイの記号',q('#tray .chip:not(.off)'),q('#help .hd1 .dchip'),['fontSize'],dk);
  same('トレイの線',q('#tray'),q('#help .hd1 .dtray'),['borderTopColor','borderTopStyle','borderTopWidth']);
  same('10',q('#eq.hit'),d.querySelector('.deq'),['color','fontWeight','fontVariantNumeric']);
  same('正解',q('#sub.ok'),d.querySelector('.dsub'),['color']);
  same('運んでいる記号',q('#ghost'),q('#help .hd1 .dghost'),['color','fontWeight']);
  ratio('運んでいる記号',q('#ghost'),q('#help .hd1 .dghost'),['fontSize'],dk);
  return {bad,dk}})()"""
# 遊び方のシートの中で、横にはみ出す要素・はみ出す段落・折り返した式・横の動き・画面全体の縦の動き
HELP_FIT = ("(()=>{const h=$('help'),hb=h.getBoundingClientRect(),bad=[];"
            "for(const e of h.querySelectorAll('*')){const r=e.getBoundingClientRect();if(!r.width)continue;"
            "if(r.left<hb.left-0.5||r.right>hb.right+0.5)bad.push(e.className||e.tagName)}"
            "for(const p of h.querySelectorAll('p'))if(p.scrollWidth>p.clientWidth+1)bad.push('p:'+p.textContent.slice(0,12));"
            "return [bad,[...h.querySelectorAll('code')].filter(c=>c.getClientRects().length!==1).map(c=>c.textContent),"
            "h.scrollWidth>h.clientWidth,document.documentElement.scrollWidth>innerWidth,"
            "document.documentElement.scrollHeight>innerHeight+1]})()")


def help_sheet(ui):
    """遊び方（9.5）。並び・文・見本の盤（Web と同じ部品・同じ動き・盤と同じ見た目）・アイコン・はみ出し"""
    for lang in ("ja", "en"):
        ui.open(lang=lang)
        ui.ev("go('help')")
        time.sleep(0.3)
        ui.check("遊び方（%s）: 見出しと、節の見出し・文の並び（9.5）" % lang,
                 [ui.ev("document.querySelector('#help h2').textContent"), ui.ev(HELP_SEQ)],
                 [{"ja": "遊び方", "en": "How to play"}[lang], HELP_LINES[lang]])
        ui.check("遊び方（%s）: 見本は 2 組で、最初の文のすぐ後。手順の番号・図の名前・説明（Web と同じ文）" % lang,
                 [ui.ev("[...document.querySelectorAll('#help .hfig')].map(f=>[f.querySelector('.hstep').textContent,"
                        "f.querySelector('.hdemo').getAttribute('aria-label'),f.querySelector('.hcap').textContent])"),
                  ui.ev("[1,2,3].map(i=>$('help').children[i].tagName+'.'+$('help').children[i].className).join('|')")],
                 [HELP_FIGS[lang], "P.|DIV.hfig|DIV.hfig"])
        ui.check("遊び方（%s）: 手順 1 の説明は、文の区切りで改行して、ちょうど 2 行" % lang,
                 ui.ev("(function(){const p=document.querySelector('#help .hd1').parentElement.querySelector('.hcap');"
                       "return [getComputedStyle(p).whiteSpace,Math.round(p.getBoundingClientRect().height/parseFloat(getComputedStyle(p).lineHeight))]})()"),
                 ["pre-line", 2])
        ui.check("遊び方（%s）: 見本の「正解」は辞書の文" % lang, ui.ev("document.querySelector('#help .hd2 .dsub').textContent"),
                 {"ja": "正解", "en": "Solved!"}[lang])
        # はみ出し: 今の画面と、compact のときは 360×640 も。いちばん下へ送った後も見る
        for size in ([None] if ui.viewport == "normal" else [None, (360, 640)]):
            if size:
                ui.c.metrics(*size)
            try:
                if size:
                    ui.open(lang=lang)
                    ui.ev("go('help')")
                    time.sleep(0.3)
                a = ui.ev(HELP_FIT)
                ui.ev("$('help').scrollTop=99999")
                b = ui.ev(HELP_FIT)
                ui.ev("$('help').scrollTop=0")
                ui.check("遊び方（%s%s）: 横にはみ出さない・式は折り返さない・画面は縦に動かない（シートの中だけ動く）"
                         % (lang, "・360×640" if size else ""), [a, b], [[[], [], False, False, False]] * 2)
            finally:
                if size:
                    ui.c.metrics(360, 690)
    ui.open()
    ui.ev("go('help')")
    ui.check("式（Web と同じ 4 つと、^ は右から・12! の式）",
             ui.ev("[...document.querySelectorAll('#help code')].map(e=>e.textContent)"),
             ["2 ^ 3 = 8", "0 ^ 0 = 1", "2 ^ 3 ^ 2", "2 ^ ( 3 ^ 2 )", "4! = 4 × 3 × 2 × 1 = 24", "0! = 1", "3!!", "( 3! )!"])
    ui.check("式は本文と同じ書体の太字で、折り返さない（Web と同じ）",
             ui.ev("(function(){const c=getComputedStyle(document.querySelector('#help code')),p=getComputedStyle(document.querySelector('#help p'));"
                   "return [c.whiteSpace,c.fontWeight,c.fontFamily===p.fontFamily]})()"), ["nowrap", "700", True])
    ui.check("文は 13px・行間 1.75・明るさ 85%（Web の遊び方と同じ）・段落の間は 6px",
             ui.ev("(function(){const s=getComputedStyle(document.querySelector('#help p'));"
                   "return [s.fontSize,Math.round(parseFloat(s.lineHeight)*100)/100,s.opacity,s.marginBottom]})()"),
             ["13px", 22.75, "0.85", "6px"])
    ui.check("アイコン付きの行の絵柄は、本物のボタンと同じ（全部消す・ヒント・デイリーのヒント・ギブアップ・統計・共有）",
             ui.ev("[['hi-clear','clear'],['hi-hint','hint'],['hi-dhint','hint'],['hi-giveup','dgiveup'],['hi-dstats','dstats'],['hi-share','share']]"
                   ".map(([a,b])=>$(a).innerHTML===$(b).querySelector('svg').outerHTML)"), [True] * 6)
    ui.check("図の中身は読み上げから隠してある・見本は触れない（pointer-events:none）",
             ui.ev("[[...document.querySelectorAll('#help .hdemo')].every(d=>d.getAttribute('role')==='img'&&[...d.children].every(c=>c.getAttribute('aria-hidden')==='true')),"
                   "getComputedStyle(document.querySelector('#help .hdemo')).pointerEvents]"), [True, "none"])
    ui.check("見本に見えている文字（置いた後の 8 − 7 5 2 とトレイの 8 つ／10・正解・( 8 − 7 ) × 5 × 2）",
             ui.ev("[[...document.querySelectorAll('#help .hd1 .dexpr .dnum,#help .hd1 .dexpr .dtok')].map(e=>e.textContent).join(' '),"
                   "[...document.querySelectorAll('#help .hd1 .dchip')].map(e=>e.textContent).join(' '),"
                   "[...document.querySelectorAll('#help .hd2 .deq,#help .hd2 .dsub')].map(e=>e.textContent).join(' '),"
                   "[...document.querySelectorAll('#help .hd2 .dexpr>*')].map(e=>e.textContent).join(' ')]"),
             ["8 − 7 5 2", "+ − × ÷ ^ ! ( )", "10 正解", "( 8 − 7 ) × 5 × 2"])
    ui.check("開いている間: 見本の動きは 12 個。どれも 5 秒で繰り返し、動かすのは transform と opacity だけ",
             ui.ev("(function(){const a=" + HD + ";const keys=new Set();"
                   "a.forEach(x=>x.effect.getKeyframes().forEach(k=>Object.keys(k).forEach(p=>keys.add(p))));"
                   "['offset','computedOffset','easing','composite'].forEach(p=>keys.delete(p));"
                   "return [a.length,a.every(x=>x.playState==='running'),"
                   "a.every(x=>x.effect.getTiming().duration===5000&&x.effect.getTiming().iterations===Infinity),[...keys].sort()]})()"),
             [12, True, True, ["opacity", "transform"]])
    pos = ("(function(){const c=s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]};"
           "const o=s=>+getComputedStyle(document.querySelector(s)).opacity;"
           "const g=c('#help .hd1 .dghost'),z=c('#help .hd1 .ds1');"
           "return {slot:Math.hypot(g[0]-z[0],g[1]-z[1]),ghost:o('#help .hd1 .dghost'),hot:o('#help .hd1 .dhot'),tok:o('#help .hd1 .ds1 .dtok')}})()")
    ui.ev(HD + ".forEach(a=>{a.pause();a.currentTime=2200})")
    f = ui.ev(pos)
    ui.check("動きの途中（2.2 秒）: 運ぶ記号が 8 と 7 のあいだの枠に重なり、その枠が明るい",
             [f["slot"] < 1.5, f["ghost"], f["hot"], f["tok"]], [True, 1, 1, 0])
    ui.ev("go('settings')")
    ui.check("遊び方を閉じると、見本の動きは止まる（動いているものが 0 個）", ui.ev(HD + ".length"), 0)
    # 見本の見た目は、盤の実物と同じ（盤を解いた形にして、枠を開き、1 つを吸着の見た目にしてから比べる）
    # 本編 11 問目（4205）の解答例は ( 4 - 2 + 0 ) * 5 で、括弧・演算・数字がそろう。枠の色は遷移するので、待ってから比べる
    ui.open({"ci": 10})
    ui.ev("start('course')")
    ui.solve(wait=0.8)
    ui.ev("showZones('!');document.querySelector('#expr .zone.live').classList.add('hot');ghost.style.display='block'")
    ui.ev("$('help').classList.remove('hide')")
    time.sleep(0.6)
    look = ui.ev(HELP_LOOK)
    ui.ev("$('help').classList.add('hide');ghost.style.display='none'")
    ui.check("比べる相手がある（盤に括弧と演算がある）",
             ui.ev("document.querySelectorAll('#expr .tok.lp').length>0&&document.querySelectorAll('#expr .tok.op').length>0"), True)
    ui.check("見本の数字・演算・括弧・枠・吸着した枠・トレイ・「10」・「正解」・運ぶ記号は、盤の実物と同じ見た目（大きさは × 0.55）",
             [look["bad"], look["dk"]], [[], 0.55])
    ui.check("遊び方の中で金を使っているのは、見本の「10」だけ（正解の「10」の見本。Web の遊び方と同じ）",
             ui.ev("(()=>{const g=%s('--gold');return [...document.querySelectorAll('#help *')].filter(e=>getComputedStyle(e).color===g"
                   "&&getComputedStyle(e.parentElement).color!==g).map(e=>e.className+':'+e.textContent)})()" % V), ["deq:10"])
    # 動きを減らす設定: 動かさず、置いた後の形で止まっている
    ui.c.ws.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    try:
        ui.open()
        ui.ev("go('help')")
        time.sleep(0.3)
        ui.check("動きを減らす設定: 見本は動かず、置いた後の形（記号は置かれ、枠と運ぶ記号は見えない）",
                 [ui.ev(HD + ".length"),
                  ui.ev("(function(){const o=s=>+getComputedStyle(document.querySelector(s)).opacity;"
                        "return [o('#help .hd1 .ds1 .dtok'),o('#help .hd1 .dzone'),o('#help .hd1 .dhot'),o('#help .hd1 .dghost')]})()")],
                 [0, [1, 0, 0, 0]])
    finally:
        ui.c.ws.call("Emulation.setEmulatedMedia", {"features": []})
    ui.check_no_errors("遊び方で JS エラー 0")
