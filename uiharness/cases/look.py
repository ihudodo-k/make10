# -*- coding: utf-8 -*-
"""見た目の決まり（7.3。DESIGN.md 1 章・BRAND.md 7 章）。

色の使い方を、計算後のスタイルで見る:
  - 金（--gold）は 3 か所だけ ―― 正解の「10」・ホームの進捗の線・「つぎへ」の下線
  - 赤（--coral）は注意専用 ―― 注意の文と赤い括弧（と、外へ出して削除の合図）
  - 10 だが使えない記号を使ったときの「10」は 75%（10 でない値の 50% とは別）
  - 丸ボタンの輪は出さない。「全部消す」「ヒント」だけ開発者パネルで出せる（既定は出さない）
  - 囲まない: 背景は単色、ヒントの箱は上下の線だけ、設定は面なし
色はテーマ変数を解決した値と比べる（直値を書かない。値は DESIGN.md 1-1 の表が正）。
"""
import time

NAME = "見た目の決まり（色・面・線）"

NONE = "rgba(0, 0, 0, 0)"
# テーマ変数を解決した色
V = ("(n=>{const e=document.createElement('i');e.style.color='var('+n+')';"
     "document.body.appendChild(e);const c=getComputedStyle(e).color;e.remove();return c})")
# ある色を、文字・地・枠のどこかに使っている要素の一覧（見えていない要素も含めて全部）。
# 文字色は継承するので、親と同じ色の子は数えない（色を「決めている」要素だけを挙げる）
USES = ("(v=>{const col=%s(v),out=[];"
        "for(const e of document.querySelectorAll('#app *,#banner,#banner *,#toast')){"
        "if(e.closest('#devpanel'))continue;const c=getComputedStyle(e),pc=getComputedStyle(e.parentElement).color,"
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
    ui.open({"ci": 137, "cleared": 162, "hintStock": 10, "scoreOn": True})
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
    ui.check("正解: 「10」と「つぎへ」が見えていて、点数のカードの文字は金ではない",
             [ui.visible("eq"), ui.visible("wnext"), ui.visible("win"),
              ui.ev("getComputedStyle($('wpts')).color===%s('--paper')" % V)], [True, True, True, True])
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
