# -*- coding: utf-8 -*-
"""クリアの確定と挑戦モードの報酬（GAME-SPEC 3-1・7-2・7-3）。

5.4 で chalDone / seen / cleared を advance()（つぎへ）から win()（正解した瞬間）へ
移した。「正解して『つぎへ』を押さずホームへ戻る」でも、記録・報酬・クリア数が
そろって確定することを見る。二重計上しないことも同じだけ大事。

6.5 からは正解したときの表示もここで見る（win_display）―― 「正解」は
読み出し行の 1 か所だけ、正解カードは点数表示オフで「つぎへ」だけ・オンで点数と詳細行、
カードが出ても式・トレイ・.foot が動かないこと、正解の 10 の倍率。
6.6 で星と「お見事」の表示をやめた。読み出し行は段階によらず「正解」、カードに星は
無い。段階（winLevel()）は光り方と振動の強さに残っているので、その違いもここで見る（win_levels）。
"""

import time

NAME = "クリアの確定・挑戦の報酬・正解の表示"

SNAP = ("({chalDone:G.chalDone.length,chalShown:G.chalShown.length,chalRem:G.chalRem,"
        "hint:G.hintStock,seen:G.seen.length,cleared:G.cleared,statsN:G.stats.n,"
        "hist:G.hist.length,ci:G.ci})")


def run(ui):
    ui.open({"ci": 0, "cleared": 120, "hintStock": 10, "chalRem": 0})

    # ── 挑戦: 正解 → 「つぎへ」を押さずホーム ───────────────
    ui.ev("start('chal')")
    ui.check("挑戦の 1 問目を解く（d>=17 でも「正解」。6.6）", ui.solve(), "10|正解")
    s = ui.ev(SNAP)
    ui.check("1問目: クリア数が増える", s["chalDone"], 1)
    ui.check("1問目: seen が増える", s["seen"], 1)
    ui.check("1問目: cleared が増える", s["cleared"], 121)
    ui.check("1問目: 記録も残る", [s["statsN"], s["hist"]], [1, 1])
    ui.check("1問目: 報酬の端数は 1", s["chalRem"], 1)
    ui.check("1問目: まだヒントは増えない", s["hint"], 10)
    ui.ev("go('home')")
    s = ui.ev(SNAP)
    ui.check("つぎへを押さずホームへ戻ってもクリア数は戻らない", s["chalDone"], 1)
    ui.check("ホームの挑戦の表示も増える", ui.text("m-chal-v"),
             "1 / %d" % ui.ev("CHAL.length"))

    ui.ev("start('chal')")
    ui.check("挑戦の 2 問目を解く", ui.solve(1.4), "10|正解")
    s = ui.ev(SNAP)
    ui.check("2問目: クリア数 2", s["chalDone"], 2)
    ui.check("2問目: 2 問ごとの報酬でヒントが 1 個増える", s["hint"], 11)
    ui.check("2問目: 端数は 0 に戻る", s["chalRem"], 0)
    ui.check("2問目: 知らせるトースト",
             ui.ev("__TOASTS.filter(t=>t==='ヒント +1（残り '+G.hintStock+'）').length"), 1)
    ui.ev("go('home')")

    # ── 「つぎへ」を押しても二重に数えない ────────────────
    ui.ev("start('chal')")
    ui.check("挑戦の 3 問目を解く", ui.solve(), "10|正解")
    before = ui.ev(SNAP)
    ui.check("3問目: 正解した時点でクリア数 3", before["chalDone"], 3)
    ui.click("wnext")
    after = ui.ev(SNAP)
    ui.check("つぎへ: クリア数は二重に増えない",
             after["chalDone"] - before["chalDone"], 0)
    ui.check("つぎへ: seen も二重に増えない", after["seen"] - before["seen"], 0)
    ui.check("つぎへ: cleared も二重に増えない",
             after["cleared"] - before["cleared"], 0)
    ui.check("つぎへ: 報酬の端数も動かない",
             after["chalRem"] - before["chalRem"], 0)   # 3 問目ぶんの 1 が残ったまま
    ui.check("つぎへ: 端数は 3 問目の 1 のまま", after["chalRem"], 1)
    ui.check("つぎへ: 次の問題が出る", after["chalShown"] - before["chalShown"], 1)
    ui.check("つぎへ: 2 回目以降は無視する",
             (ui.click("wnext"), ui.ev("G.chalDone.length"))[1], 3)

    # ── 本編: 位置（ci）は「つぎへ」でだけ進む ──────────────
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10})
    ui.ev("start('course')")
    ui.check("本編の 1 問目を解く", ui.solve(), "10|正解")
    s = ui.ev(SNAP)
    ui.check("本編: 正解でクリア数が増える", s["cleared"], 1)
    ui.check("本編: seen も増える", s["seen"], 1)
    ui.check("本編: 位置はまだ進まない", s["ci"], 0)
    ui.ev("go('home')")
    ui.check("ホームの累計も増える", ui.text("ctot"), "累計 1 問")
    ui.check("ホームの位置は 0 のまま", ui.text("cnum"), "0 / 1000 問")
    ui.ev("start('course')")
    ui.check("同じ問題が出る", ui.ev("codeOf(cur)===codeOf(COURSE[0])"), True)
    ui.check("解き直す", ui.solve(), "10|正解")
    s = ui.ev(SNAP)
    ui.check("解き直しても二重に数えない", [s["cleared"], s["seen"]], [1, 1])
    ui.click("wnext")
    s = ui.ev(SNAP)
    ui.check("つぎへで位置が進む", s["ci"], 1)
    ui.check("つぎへではクリア数は増えない", s["cleared"], 1)

    # ── フリー: 報酬は増えない ────────────────────────────
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10, "chalRem": 1})
    ui.ev("start('free')")
    want = ui.solved_text()
    ui.check("フリーの問題を解く", ui.solve(), want)
    s = ui.ev(SNAP)
    ui.check("フリー: クリア数が増える", s["cleared"], 1)
    ui.check("フリー: 挑戦のクリア数には入らない", s["chalDone"], 0)
    ui.check("フリー: 報酬は増えない（端数も動かない）",
             [s["hint"], s["chalRem"]], [10, 1])

    # ── 共有: 5.4 でクリアとして数えるようになった ────────
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10})
    code = ui.ev("codeOf(CHAL[7])")
    ui.ev("$('codein').value=%r" % code)
    ui.click("codego")
    ui.check("共有コードで開く", ui.ev("SCR"), "play")
    ui.check("共有の問題を解く", ui.solve(), "10|正解")   # CHAL[7] は d>=17
    s = ui.ev(SNAP)
    ui.check("共有: クリアとして数える（5.4 の変更）", s["cleared"], 1)
    ui.check("共有: 挑戦のクリア数には入らない", s["chalDone"], 0)

    # ── 挑戦モードの解放（CHAL_AT=100）──────────────────────
    ui.open({"ci": 0, "cleared": 99, "hintStock": 10})
    ui.check("解放条件は 100 問", ui.ev("CHAL_AT"), 100)
    ui.check("99 問ではロック", ui.text("m-chal-v"), "あと 1 問")
    ui.ev("start('free')")
    want = ui.solved_text()
    ui.check("あと 1 問を解く", ui.solve(), want)
    ui.ev("go('home')")
    ui.check("つぎへを押さなくても解放される", ui.text("m-chal-v"),
             "0 / %d" % ui.ev("CHAL.length"))
    ui.check("ロックの class が外れる",
             ui.ev("$('m-chal').classList.contains('lock')"), False)
    ui.click("m-chal")
    ui.check("挑戦モードに入れる", ui.ev("SCR"), "play")
    ui.check("挑戦の問題が出ている", ui.ev("cur.d>=17"), True)
    win_display(ui)
    ui.check_no_errors("一連の流れで JS エラー 0")


# 式・トレイ・.foot・読み出し行の位置と大きさ（6.5: 正解カードが出ても動かない）
RECTS = ("['.readout','#exprwrap','.foot','#tray'].map(q=>{const b=document.querySelector(q)"
         ".getBoundingClientRect();return [b.left,b.top,b.width,b.height].join()}).join('|')")
# 問題画面（#play）に見えている「正解」「お見事」の数。#pcode の「正解 N通り」は正解数の
# 表示なので除く。見えている文字ノードだけを数える（display:none の親を持つものは除く）
WORDS = ("(()=>{const w=document.createTreeWalker($('play'),NodeFilter.SHOW_TEXT);let a=0,b=0,n;"
         "while(n=w.nextNode()){const p=n.parentElement;if(p.closest('#pcode')||!p.getClientRects().length)"
         "continue;a+=(n.data.match(/正解/g)||[]).length;b+=(n.data.match(/お見事/g)||[]).length}"
         "return [a,b]})()")
# 点数表示オンの正解カードの高さ（点数 1 行・詳細行 1 行・枠と余白）。6.6 で
# 星を消す前後で実測して同じだった値（normal / compact とも同じ）
CARD_H = 55.5
# 見えている正解カードの中の要素（display:none でなく大きさがあるもの）の id
CARD_VISIBLE = ("[...$('win').querySelectorAll('[id]')].filter(e=>e.offsetHeight>0).map(e=>e.id)")


# 「つぎへ」#wnext と演算子の箱の色（6.5）。計算後のスタイルで比べる。
# 演算子の記号 .chip は地も枠も持たない（background:none / border:0）ので、見えている箱は
# トレイのパネル .tray。地と枠は .tray と、文字の色はトレイの先頭の記号（+）の .chip と比べる
COLORS = ("(()=>{const b=getComputedStyle($('wnext')),t=getComputedStyle(document.querySelector('.tray')),"
          "c=getComputedStyle(document.querySelector('.tray .chip'));"
          "return [[b.backgroundColor,b.borderTopColor,b.borderTopStyle,b.borderTopWidth,b.color],"
          "[t.backgroundColor,t.borderTopColor,t.borderTopStyle,t.borderTopWidth,c.color]]})()")


def _force_active(ui, selectors, on):
    """CDP で :active を強制する（押している最中の計算後のスタイルを読むため）。
    DOM.getDocument を呼び直すと先に強制した状態が外れるので、1 回で全部に掛ける"""
    ws = ui.c.ws
    ws.call("DOM.enable")
    ws.call("CSS.enable")
    root = ws.call("DOM.getDocument", {"depth": 0})["root"]["nodeId"]
    for sel in selectors:
        node = ws.call("DOM.querySelector", {"nodeId": root, "selector": sel})["nodeId"]
        ws.call("CSS.forcePseudoState",
                {"nodeId": node, "forcedPseudoClasses": ["active"] if on else []})


def check_wnext_colors(ui, label):
    """#wnext の地・枠・文字が演算子の箱と同じ。押したときも .chip:active と同じ変化"""
    got, want = ui.ev(COLORS)
    ui.check(label + ": 「つぎへ」の地・枠・文字の色が演算子の箱と同じ", got, want)
    _force_active(ui, ["#wnext", ".tray .chip"], True)
    pressed = ui.ev("(()=>{const b=getComputedStyle($('wnext')),"
                    "c=getComputedStyle(document.querySelector('.tray .chip'));"
                    "return [[b.backgroundColor,b.opacity],"
                    "[getComputedStyle(document.querySelector('.tray')).backgroundColor,c.opacity]]})()")
    _force_active(ui, ["#wnext", ".tray .chip"], False)
    ui.check(label + ": 押したときも地は変えず、記号と同じだけ薄くなる", pressed[0], pressed[1])
    ui.check(label + ": 押したときの薄さは 0.5", pressed[0][1], "0.5")


# 「10」の見えている倍率（拡大後の高さ ÷ 元の高さ）
TEN_SCALE = ("(()=>{const e=$('eq');return Math.round(e.getBoundingClientRect().height"
             "/parseFloat(getComputedStyle(e).height)*100)/100})()")
# 式の大きさ: 数字・演算子の文字の大きさ、式全体の縮小率、数字 1 つの見えている高さ
# 演算子は正解の前（まだ 1 つも置いていない）には無いので、あるときだけ読む（無ければ CSS 変数の値）
EXPR_SIZE = ("(()=>{const n=document.querySelector('#expr .num'),o=document.querySelector('#expr .tok.op');"
             "return [getComputedStyle(n).fontSize,"
             "o?getComputedStyle(o).fontSize:getComputedStyle(document.documentElement).getPropertyValue('--opF').trim(),"
             "getComputedStyle($('expr')).transform,Math.round(n.getBoundingClientRect().height*10)/10]})()")


# 「つぎへ」が .foot の中央にあるか:
# [#clear と #hint の間の中央か, 縦は #clear と同じ, 高さが #clear と同じ, 幅,
#  #clear との隙間, #hint との隙間]（隙間が正なら当たりは重ならない）
NEXT_IN_FOOT = ("(()=>{const b=$('wnext').getBoundingClientRect(),c=$('clear').getBoundingClientRect(),"
                "h=$('hint').getBoundingClientRect();"
                "return [Math.abs((b.left+b.right)/2-(c.right+h.left)/2)<0.5,"
                "Math.abs(b.top-c.top)<0.5&&Math.abs(b.bottom-c.bottom)<0.5,"
                "Math.round(b.height)===Math.round(c.height),Math.round(b.width),"
                "Math.round(b.left-c.right)>0,Math.round(h.left-b.right)>0]})()")
# 当たり: 「つぎへ」の左右の端の 2px 内側は「つぎへ」、#clear / #hint の内側の端は各自
NEXT_HITS = ("(()=>{const b=$('wnext').getBoundingClientRect(),c=$('clear').getBoundingClientRect(),"
             "h=$('hint').getBoundingClientRect(),y=b.top+b.height/2,"
             "at=(x,id)=>{const e=document.elementFromPoint(x,y);return !!e&&e.closest('#'+id)!==null};"
             "return [at(b.left+2,'wnext'),at(b.right-2,'wnext'),at(c.right-2,'clear'),"
             "at(h.left+2,'hint'),at((b.left+b.right)/2,'wnext')]})()")


def win_display(ui):
    """正解まわりの表示（6.5。GAME-SPEC 8 章）。判定は画面に見える値で取る。"""
    # ── 点数表示オフ（既定）: 「正解」は読み出し行だけ・カードは「つぎへ」だけ ──
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10})
    ui.ev("start('course')")
    before = ui.ev(RECTS)
    size0 = ui.ev(EXPR_SIZE)
    # 「10」は正解した瞬間から拡大後の大きさ（動きは付けない。6.5）。解いた同じ処理の中で測る
    got = ui.ev("(()=>{const r=__solve();return [r,%s]})()" % TEN_SCALE)
    ui.check("オフ: 本編 1 問目（d=3）を解くと「正解」", got[0], "10|正解")
    ui.check("10: 正解した直後（同じフレーム）から倍率どおり 1.8", got[1], 1.8)
    ui.check("10: 大きさに遷移を付けていない",
             ui.ev("getComputedStyle($('eq')).transitionProperty"), "color")
    time.sleep(0.1)
    ui.check("10: 0.1 秒後も 1.8（途中の大きさを経ない）", ui.ev(TEN_SCALE), 1.8)
    size1 = ui.ev(EXPR_SIZE)
    time.sleep(1.0)                          # win() と正解カード（520ms）・跳ねの終わりを待つ
    ui.check("式の大きさ: 正解の直後も正解の前と同じ（文字・縮小率・高さ）", size1, size0)
    ui.check("式の大きさ: 正解カードが出たあとも正解の前と同じ", ui.ev(EXPR_SIZE), size0)
    ui.check("オフ: 「正解」は画面に 1 つだけ・「お見事」は無い", ui.ev(WORDS), [1, 0])
    ui.check("オフ: 「つぎへ」が見えている", ui.visible("wnext"), True)
    ui.check("オフ: 点数のカードは出ない", ui.visible("win"), False)
    ui.check("オフ: 「つぎへ」は .foot の中に置いてある",
             ui.ev("$('wnext').parentElement.classList.contains('foot')"), True)
    ui.check("オフ: 「つぎへ」は #clear と #hint の間の中央・同じ縦位置と高さ・幅 160px・両側に隙間",
             ui.ev(NEXT_IN_FOOT), [True, True, True, 160, True, True])
    ui.check("オフ: 当たりが #clear / #hint と重ならない（端を押しても各自に当たる）",
             ui.ev(NEXT_HITS), [True, True, True, True, True])
    ui.check("オフ: 式・トレイ・.foot・読み出し行が解く前と同じ位置", ui.ev(RECTS), before)
    ui.check("オフ: 問題画面はスクロールしない", ui.scrolls(), False)
    check_wnext_colors(ui, "オフ")
    # テーマは藍（プレイヤー向け）と白（開発用）の 2 つ。どちらでも揃う
    ui.ev("G.theme='paper'; applyTheme()")
    check_wnext_colors(ui, "オフ・白テーマ")
    ui.check("白テーマで本当に色が変わっている（藍と比べる意味がある）",
             ui.ev("getComputedStyle($('wnext')).color"), "rgb(30, 37, 48)")
    ui.ev("G.theme='ai'; applyTheme()")
    ui.check("藍テーマの文字の色", ui.ev("getComputedStyle($('wnext')).color"), "rgb(245, 242, 233)")
    # ── 正解の 10 の大きさ ───────────────────────────────
    scale = TEN_SCALE
    ui.check("10: 既定の倍率は 1.8（devVars.tenScale・実機で決めた値）", ui.ev("DEV_DEFAULT.tenScale"), 1.8)
    ui.check("10: 見えている大きさが倍率どおり", ui.ev(scale), 1.8)
    ui.check("10: 下端は動かず「正解」に重ならない",
             ui.ev("$('eq').getBoundingClientRect().bottom<=$('sub').getBoundingClientRect().top"),
             True)
    ui.check("10: 上のヘッダ（.top）に重ならない",
             ui.ev("$('eq').getBoundingClientRect().top>="
                   "document.querySelector('#play .top').getBoundingClientRect().bottom"), True)
    ui.ev("G.dev=true; devPanelShow(true)")
    ui.check("10: 開発者パネルに倍率のスライダー", ui.text("dv-tenScale-v"), "1.8倍")
    ui.check("つぎへ: 幅のスライダーは外した（固定値 NEXT_BTN.w）",
             ui.ev("[!!$('dv-nextW'),'nextW' in DEV_DEFAULT,NEXT_BTN.w]"), [False, False, 160])
    ui.ev("(()=>{const r=$('dv-tenScale');r.value='2.2';r.dispatchEvent(new Event('input'))})()")
    time.sleep(0.6)
    ui.check("10: スライダーを 2.2 にすると見えている大きさも 2.2", ui.ev(scale), 2.2)
    ui.check("10: 倍率は保存される", ui.ev("G.devVars.tenScale"), 2.2)
    ui.check("10: 読み出し行・式・トレイは倍率を変えても動かない", ui.ev(RECTS), before)
    ui.click("dv-reset")
    time.sleep(0.6)
    ui.check("10: 既定値に戻すと 1.8", ui.ev(scale), 1.8)
    ui.ev("devPanelShow(false); G.dev=false")
    ui.check("10: 崩すと一瞬で元の大きさ（遷移を付けない）",
             ui.ev("(()=>{S.toks=S.toks.filter(t=>t.t==='num');render();"
                   "return getComputedStyle($('eq')).transform})()"), "none")
    ui.check("崩すと「正解」も消える", ui.ev(WORDS), [0, 0])
    ui.check("崩しても「つぎへ」は出たまま（記録は確定済み）", ui.visible("wnext"), True)

    # ── 点数表示オン: 点数・詳細行と「つぎへ」（星は 6.6 で廃止）。「正解」はカードに出さない ──
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10, "scoreOn": True})
    ui.ev("start('course')")
    before = ui.ev(RECTS)
    ui.check("オン: 解くと「正解」", ui.solve(), "10|正解")
    ui.check("オン: 「正解」は画面に 1 つだけ・「お見事」は無い", ui.ev(WORDS), [1, 0])
    ui.check("オン: カードに見えているのは点数・詳細行（「つぎへ」は入れない）",
             ui.ev(CARD_VISIBLE), ["wpts", "wmeta"])
    ui.check("オン: カードの中に「つぎへ」は無い",
             [ui.ev("$('win').contains($('wnext'))"), ui.ev("/つぎへ/.test($('win').innerText)")],
             [False, False])
    ui.check("オン: 「つぎへ」はオフと同じ .foot の中央",
             ui.ev(NEXT_IN_FOOT), [True, True, True, 160, True, True])
    ui.check("オン: 当たりが #clear / #hint と重ならない", ui.ev(NEXT_HITS), [True, True, True, True, True])
    ui.check("オン: 点数だけ（星は出さない）", ui.ev(r"/^\d+ 点$/.test($('wpts').innerText.trim())"), True)
    ui.check("オン: カードのどこにも星（★☆）が無い", ui.ev("/[★☆]/.test($('win').innerText)"), False)
    ui.check("オン: 星を消しても記録の星の段階（G.hist の st）は残る",
             ui.ev("[1,2,3].includes(G.hist[0].st)"), True)
    ui.check("オン: 詳細行", ui.ev(r"/^難易度 3　\d+秒$/.test($('wmeta').innerText)"), True)
    ui.check("オン: カードに「正解」「お見事」は無い",
             ui.ev("/正解|お見事/.test($('win').innerText)"), False)
    ui.check("オン: カードには枠がある", ui.ev("getComputedStyle($('win')).borderTopWidth"), "1px")
    ui.check("オン: カードの高さ（点数・詳細行の 2 行。星を消しても同じ）",
             ui.ev("Math.round($('win').getBoundingClientRect().height*10)/10"), CARD_H)
    ui.check("オン: 式・トレイ・.foot・読み出し行が解く前と同じ位置", ui.ev(RECTS), before)
    ui.check("オン: カードは式（#exprwrap）より下・.foot より上",
             ui.ev("(()=>{const w=$('win').getBoundingClientRect(),"
                   "e=$('exprwrap').getBoundingClientRect(),f=document.querySelector('.foot')"
                   ".getBoundingClientRect();return w.top>=e.bottom&&w.bottom<=f.top})()"), True)
    check_wnext_colors(ui, "オン")
    ui.ev("G.theme='paper'; applyTheme()")
    check_wnext_colors(ui, "オン・白テーマ")
    ui.ev("G.theme='ai'; applyTheme()")
    # 設定を切り替えて戻ると、カードの形もその場で変わる（showWinCard は出すたびに G.scoreOn を見る）
    ui.click("menu")
    ui.click("t-score")
    ui.click("navback")
    ui.check("オン → 設定でオフ → 戻るとカードは消えて「つぎへ」だけ",
             [ui.visible("win"), ui.visible("wnext")], [False, True])
    ui.check("切り替えても「つぎへ」の場所は同じ", ui.ev(NEXT_IN_FOOT), [True, True, True, 160, True, True])
    ui.check("戻っても「正解」は 1 つだけ", ui.ev(WORDS), [1, 0])

    win_levels(ui)


# 正解した瞬間の段階ごとの演出（GAME-SPEC 8 章）。win() が終わったあとに読む:
# [段階 lastWin.lv, 光った演算子・階乗の数 == 演算子・階乗の数, 背景のフラッシュ, 振動の型]
LEVEL_FX = ("(()=>{const t=document.querySelectorAll('#expr .tok.op,#expr .tok.fac').length,"
            "s=document.querySelectorAll('#expr .tok.shine').length;"
            "return [lastWin.lv,t>0&&s===t,s,$('bg').classList.contains('flash'),__VIB.slice()]})()")


def win_levels(ui):
    """段階（winLevel()）は表示から外したが、光り方と振動の強さには残っている（6.6）。
    読み出し行はどの段階でも「正解」。段階の区切りは仕様の値（d>=9 / d>=14、60 秒で 1 段）を直に書く"""
    ui.open({"ci": 0, "cleared": 0, "hintStock": 10, "scoreOn": True})
    ui.ev("window.__VIB=[];Object.defineProperty(navigator,'vibrate',"
          "{value:x=>{__VIB.push(x);return true},configurable:true})")
    # 記号を置く・ボタンの振動は数えない（解いた直後に空にし、win() の 1 回だけを見る）
    cases = [
        ("d=8（段階 1）", "loadPuzzle(ALL().find(p=>p.d===8))", 1, False, False, [16]),
        ("d=13（段階 2）", "loadPuzzle(ALL().find(p=>p.d===13))", 2, True, False, [[16, 36, 18]]),
        ("d=14（段階 3）", "loadPuzzle(ALL().find(p=>p.d===14))", 3, True, True, [[18, 40, 26]]),
        ("d=13 で 60 秒（段階 3）", "loadPuzzle(ALL().find(p=>p.d===13)); t0-=61000",
         3, True, True, [[18, 40, 26]]),
    ]
    for label, load, lv, shine, flash, vib in cases:
        ui.ev("go('home'); start('free'); " + load)
        got = ui.ev("(()=>{const r=__solve();__VIB.length=0;return r})()")
        ui.check(label + ": 読み出し行は「正解」", got, "10|正解")
        time.sleep(1.0)
        ui.check(label + ": 「正解」は画面に 1 つだけ・「お見事」は無い", ui.ev(WORDS), [1, 0])
        ui.check(label + ": カードに星も「正解」「お見事」も無い",
                 ui.ev("/[★☆]|正解|お見事/.test($('win').innerText)"), False)
        fx = ui.ev(LEVEL_FX)
        ui.check(label + ": 段階", fx[0], lv)
        ui.check(label + ": 演算子・階乗が光る（段階 2 以上）",
                 fx[1] if shine else fx[2], True if shine else 0)
        ui.check(label + ": 背景のフラッシュ（段階 3）", fx[3], flash)
        ui.check(label + ": 振動の型", fx[4], vib)
