# -*- coding: utf-8 -*-
"""問題コードのコピー・共有ボタン・難易度の言葉（6.4。GAME-SPEC 5-3・5-5）。

クリップボードと共有メニューは headless Chrome では本物を確かめられないので、
navigator.clipboard / navigator.share を差し替えて「何が渡されたか」を記録する。
判定は #pcodev / #pdiff / トーストなど、画面に見える値で取る。
"""

import time

NAME = "コピー・共有・難易度の言葉"

# 差し替え。__CLIP に書き込まれた文字、__SHARE に共有メニューへ渡したものを溜める。
# mode: "ok"（両方ある）/ "noshare"（共有が無い）/ "none"（両方無い）/
#       "abort"（共有メニューを閉じた）/ "deny"（共有が拒まれた）
STUB = """
(function(mode){
  window.__CLIP=[]; window.__SHARE=[];
  const clip = mode==="none" ? undefined
    : {writeText: async t=>{__CLIP.push(t)}};
  Object.defineProperty(navigator,'clipboard',{value:clip,configurable:true});
  let share;
  if(mode==="ok") share=async d=>{__SHARE.push(d)};
  else if(mode==="abort") share=async d=>{__SHARE.push(d);
    throw new DOMException('closed','AbortError')};
  else if(mode==="deny") share=async d=>{__SHARE.push(d);
    throw new DOMException('denied','NotAllowedError')};
  Object.defineProperty(navigator,'share',{value:share,configurable:true});
  window.__TOASTS.length=0;
  getSelection().removeAllRanges();
})(%s)
"""


def toast_at_foot(ui):
    """トーストの中心が #clear と #hint の間の中央・.foot の高さの中央にあり、隙間に収まる"""
    return ui.ev("(()=>{const t=$('toast').getBoundingClientRect(),"
                 "c=$('clear').getBoundingClientRect(),h=$('hint').getBoundingClientRect();"
                 "return $('toast').classList.contains('atfoot')"
                 "&&Math.abs((t.left+t.right)/2-(c.right+h.left)/2)<1"
                 "&&Math.abs((t.top+t.bottom)/2-(c.top+c.bottom)/2)<1"
                 "&&t.left>=c.right&&t.right<=h.left})()")


def toast_above_next(ui):
    """「つぎへ」が出ているとき（6.5）: トーストは #clear と #hint の間の中央・下端が .foot の
    上端の TOAST_FOOT_GAP 上で、「つぎへ」と重ならない。戻り値は [中央, 下端, 重ならない]"""
    return ui.ev("(()=>{const t=$('toast').getBoundingClientRect(),n=$('wnext').getBoundingClientRect(),"
                 "c=$('clear').getBoundingClientRect(),h=$('hint').getBoundingClientRect(),"
                 "f=document.querySelector('.foot').getBoundingClientRect();"
                 "return [Math.abs((t.left+t.right)/2-(c.right+h.left)/2)<1,"
                 "Math.abs(t.bottom-(f.top-TOAST_FOOT_GAP))<1,"
                 "!(t.left<n.right&&n.left<t.right&&t.top<n.bottom&&n.top<t.bottom)]})()")


def toast_in_gap(ui):
    """点数表示オンで点数のカードが出ているとき（6.5）: トーストは読み出し行（#sub の下端）と
    式（#exprwrap の上端）のあいだの空きの中央。戻り値は
    [横は #clear と #hint の間の中央, 縦は空きの中央, #eq・#sub・式・カード・「つぎへ」のどれとも重ならない]"""
    return ui.ev("(()=>{const r=q=>document.querySelector(q).getBoundingClientRect(),t=r('#toast'),"
                 "c=r('#clear'),h=r('#hint'),sb=r('#sub'),ew=r('#exprwrap');"
                 "const ov=b=>t.left<b.right&&b.left<t.right&&t.top<b.bottom&&b.top<t.bottom;"
                 "return [Math.abs((t.left+t.right)/2-(c.right+h.left)/2)<1,"
                 "Math.abs((t.top+t.bottom)/2-(sb.bottom+ew.top)/2)<1,"
                 "!['#eq','#sub','#expr','#win','#wnext'].some(q=>ov(r(q)))]})()")


def stub(ui, mode):
    ui.ev(STUB % ('"%s"' % mode))


def run(ui):
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
    ui.ev("start('course')")
    code = ui.ev("codeOf(cur)")
    url = ui.ev("SHARE_URL")
    # ── コードの見た目 ────────────────────────────────────
    ui.check("コードが #pcodev に出る", ui.text("pcodev"), code)
    ui.check("コード欄の並び",
             ui.text("pcode"),
             "コード %s　%s　正解 %d通り" % (code, ui.text("pdiff"), ui.ev("cur.n")))
    ui.check("コードに点線の下線（タップできる印）",
             ui.ev("getComputedStyle($('pcodev')).textDecorationStyle"), "dotted")
    ui.check("コードの当たりは文字より上下に広い（上 10px を押してもコード）",
             ui.ev("(()=>{const b=$('pcodev').getBoundingClientRect();"
                   "const e=document.elementFromPoint(b.left+b.width/2,b.top-10);"
                   "return !!e&&e.closest('#pcodev')!==null})()"), True)
    ui.check("当たりが #menu に食い込まない",
             ui.ev("(()=>{const b=$('menu').getBoundingClientRect();"
                   "const e=document.elementFromPoint(b.left+2,b.top+b.height/2);"
                   "return !!e&&e.closest('#menu')!==null})()"), True)
    ui.check("コードはボタンとして読み上げられる",
             ui.ev("$('pcodev').getAttribute('role')"), "button")
    # ── タップでコピー ────────────────────────────────────
    stub(ui, "ok")
    ui.click("pcodev")
    ui.check("コピー: クリップボードにコード", ui.ev("__CLIP"), [code])
    ui.check("コピー: トースト", ui.toasts(), ["コピーしました"])
    stub(ui, "none")
    ui.click("pcodev")
    ui.check("クリップボードが無い: コードが選択状態になる",
             ui.ev("getSelection().toString()"), code)
    ui.check("クリップボードが無い: トーストは出さない", ui.toasts(), [])
    # ── 共有ボタンの置き場所（6.4 で実機で決めた: 三本線 #menu の真下・枠なし）──
    ui.check("共有ボタンは .foot に無い（中央は #clear と #hint だけ）",
             ui.ev("[...document.querySelector('.foot').children]"
                   ".filter(e=>getComputedStyle(e).display!=='none').map(e=>e.id)"),
             ["clear", "hint"])
    ui.check("共有ボタンが見えている", ui.visible("share"), True)
    ui.check("見た目は #menu と同じ枠なし（.plainbtn）", ui.ev("$('share').className"), "plainbtn")
    ui.check("#menu と同じ大きさ・同じ列・間隔 SHARE_BTN.gap の真下",
             ui.ev("(()=>{const a=$('share').getBoundingClientRect(),"
                   "b=$('menu').getBoundingClientRect();"
                   "return [a.width===b.width,a.height===b.height,"
                   "Math.abs(a.left-b.left)<0.5,Math.abs(a.top-(b.bottom+SHARE_BTN.gap))<0.5]})()"),
             [True, True, True, True])
    ui.check("真ん中を押すと共有ボタンに当たる",
             ui.ev("(()=>{const b=$('share').getBoundingClientRect();"
                   "const e=document.elementFromPoint(b.left+b.width/2,b.top+b.height/2);"
                   "return !!e&&e.closest('#share')!==null})()"), True)
    # 文字は .info がいちばん長い場合（挑戦 1474/1474・HARD）でも見る
    for label, js in [("本編 1 問目", ""),
                      ("いちばん長い .info",
                       "loadPuzzle(CHAL.reduce((a,b)=>b.n>a.n?b:a));"
                       "$('pmode').textContent='挑戦 '+CHAL.length+'/'+CHAL.length;")]:
        if js:
            ui.ev(js)
        ui.check(label + ": 文字（#pmode・#pcode・#eq）とコードの当たりに重ならない",
                 ui.ev("(()=>{const a=$('share').getBoundingClientRect();"
                       "const ink=el=>{const r=document.createRange();r.selectNodeContents(el);"
                       "return r.getBoundingClientRect()};"
                       "const v=$('pcodev').getBoundingClientRect();"
                       "const hit={left:v.left-6,right:v.right+6,top:v.top-14,bottom:v.bottom+14};"
                       "const ov=b=>a.left<b.right&&b.left<a.right&&a.top<b.bottom&&b.top<a.bottom;"
                       "return [ink($('pmode')),ink($('pcode')),ink($('eq')),hit].map(ov)})()"),
                 [False, False, False, False])
    ui.ev("go('home'); start('course')")
    code = ui.ev("codeOf(cur)")
    # 式・トレイ・.foot の位置は、共有ボタンが有っても無くても 1px も変わらない
    ui.check("式・トレイ・.foot の位置は共有ボタンの有無で変わらない",
             ui.ev("(()=>{const m=()=>['exprwrap','clear','hint'].map(i=>$(i).getBoundingClientRect())"
                   ".concat([document.querySelector('.tray').getBoundingClientRect()])"
                   ".map(b=>[b.left,b.top,b.width,b.height].join());"
                   "const a=m();$('share').style.display='none';const b=m();"
                   "$('share').style.display='';return a.join('|')===b.join('|')})()"), True)
    stub(ui, "ok")
    ui.click("share")
    ui.check("押すと共有メニューが開く", len(ui.ev("__SHARE")), 1)
    # 切り替えの仕組みは外した。開発者パネルにも devVars にも残っていない
    ui.check("開発者パネルに共有ボタンの切り替えが無い",
             ui.ev("[!!$('dv-shareSide'),!!$('dv-shareFrame'),'shareSide' in DEV_DEFAULT,"
                   "'shareFrame' in DEV_DEFAULT,'share' in DEV_SEC_DEFAULT]"),
             [False, False, False, False, False])
    ui.check("共有ボタンの絵柄は ICON_SHARE",
             ui.ev("(()=>{const t=document.createElement('div');t.innerHTML=ICON_SHARE;"
                   "return $('share').innerHTML===t.innerHTML})()"), True)
    ui.check("問題画面はスクロールしない", ui.scrolls(), False)
    # 切り替えを試していた端末の保存データ（shareSide / shareFrame 入り）も、読まずに無視される
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50,
             "devVars": {"shareSide": 2, "shareFrame": 1, "vibBtn": 30},
             "devSecs": {"share": 1, "vib": 0}})
    ui.ev("start('course')")
    ui.check("古い保存データ: shareSide / shareFrame は読まれず、ボタンは #menu の真下・枠なし",
             [ui.ev("'shareSide' in G.devVars"), ui.ev("'shareFrame' in G.devVars"),
              ui.ev("'share' in G.devSecs"), ui.ev("$('share').className"),
              ui.ev("Math.abs($('share').getBoundingClientRect().left-$('menu').getBoundingClientRect().left)<0.5")],
             [False, False, False, "plainbtn", True])
    ui.check("古い保存データ: ほかの devVars（振動の長さ）はそのまま読める",
             [ui.ev("G.devVars.vibBtn"), ui.ev("G.devVars.vibPick"), ui.ev("G.devSecs.vib")],
             [30, 16, 0])
    ui.check_no_errors("古い保存データを読んでも JS エラー 0")
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
    ui.ev("start('course')")
    # ── 共有 ──────────────────────────────────────────────
    text = "Make10 のこの問題、解ける？ コード " + code
    stub(ui, "ok")
    ui.click("share")
    ui.check("共有: 共有メニューに渡す文面",
             ui.ev("__SHARE"), [{"title": "Make10", "text": text, "url": url}])
    ui.check("共有: 文面に問題の 4 桁が入っていない",
             ui.ev("__SHARE[0].text.includes(cur.id)"), False)
    ui.check("共有: 開けたらコピーもトーストもしない",
             [ui.ev("__CLIP"), ui.toasts()], [[], []])
    stub(ui, "noshare")
    ui.click("share")
    ui.check("共有が無い: 同じ文面と URL をコピー", ui.ev("__CLIP"), [text + "\n" + url])
    ui.check("共有が無い: トースト", ui.toasts(), ["共有の文面をコピーしました"])
    stub(ui, "abort")
    ui.click("share")
    ui.check("共有メニューを閉じた: 何もしない",
             [len(ui.ev("__SHARE")), ui.ev("__CLIP"), ui.toasts()], [1, [], []])
    stub(ui, "deny")
    ui.click("share")
    ui.check("共有が拒まれた: コピーに切り替える",
             [ui.ev("__CLIP"), ui.toasts()], [[text + "\n" + url], ["共有の文面をコピーしました"]])
    stub(ui, "none")
    ui.click("share")
    ui.check("共有もクリップボードも無い: コードをトーストで見せる",
             ui.toasts(), ["コピーできません　%s" % code])
    # ── コピーと共有のトースト: .foot の中央・1 秒 ───────────────
    for label, how, msg in [("コードのコピー", "ok", "コピーしました"),
                            ("共有の代替", "noshare", "共有の文面をコピーしました"),
                            ("コピーできない", "none", "コピーできません　" + code)]:
        stub(ui, how)
        ui.click("pcodev" if label == "コードのコピー" else "share")
        time.sleep(0.4)                     # 出るときの動き（0.2 秒）が終わるまで
        ui.check(label + ": 文面", ui.text("toast"), msg)
        ui.check(label + ": 見えている", ui.ev("getComputedStyle($('toast')).opacity"), "1")
        ui.check(label + ": .foot の中央（#clear と #hint の間）に出る", toast_at_foot(ui), True)
        time.sleep(1.1)                     # 1 秒＋消える動き 0.2 秒を過ぎた
        ui.check(label + ": 1 秒で消える", ui.ev("getComputedStyle($('toast')).opacity"), "0")
    ui.ev("toast('（既定）')")
    time.sleep(0.4)
    ui.check("指定の無いトーストは今までの位置（画面下から 78px）",
             [ui.ev("$('toast').classList.contains('atfoot')"),
              ui.ev("getComputedStyle($('toast')).bottom")], [False, "78px"])
    ui.ev("go('home'); toast('（ホーム）',{at:'foot'})")
    time.sleep(0.4)
    ui.check("問題画面でなければ .foot の指定があっても今までの位置",
             ui.ev("$('toast').classList.contains('atfoot')"), False)
    # ── 挑戦の報酬のトースト: 「つぎへ」の上・2.4 秒 ────────────────
    # 正解の直後に出るので「つぎへ」（.foot の中央。6.5）が出ている。その上に出す
    ui.open({"ci": 0, "cleared": 200, "hintStock": 5, "chalRem": 1})
    ui.ev("start('chal')")
    t0 = time.time()
    ui.solve(wait=0)
    time.sleep(max(0, 1.6 - (time.time() - t0)))    # win() の 260ms ＋ 900ms 後に出る
    ui.check("報酬: 文面", ui.text("toast"), "ヒント +1（残り 6）")
    ui.check("報酬: 見えている", ui.ev("getComputedStyle($('toast')).opacity"), "1")
    ui.check("報酬: 「つぎへ」が出ている", ui.visible("wnext"), True)
    ui.check("報酬: 「つぎへ」の上（.foot の 8px 上）に出て「つぎへ」に重ならない",
             toast_above_next(ui), [True, True, True])
    time.sleep(max(0, 3.3 - (time.time() - t0)))
    ui.check("報酬: 2 秒を過ぎてもまだ見えている（2.4 秒）",
             ui.ev("getComputedStyle($('toast')).opacity"), "1")
    time.sleep(max(0, 4.1 - (time.time() - t0)))
    ui.check("報酬: 2.4 秒で消える", ui.ev("getComputedStyle($('toast')).opacity"), "0")
    # ── 正解のあとにコードをコピー: トーストは「つぎへ」の上（6.5）──────
    stub(ui, "ok")
    ui.click("pcodev")
    time.sleep(0.4)
    ui.check("正解後のコピー: 文面", ui.toasts(), ["コピーしました"])
    ui.check("正解後のコピー: 「つぎへ」の上に出て「つぎへ」に重ならない",
             toast_above_next(ui), [True, True, True])
    time.sleep(1.1)
    ui.click("wnext")
    stub(ui, "ok")
    ui.click("pcodev")
    time.sleep(0.4)
    ui.check("「つぎへ」で次の問題へ進むと、コピーのトーストは .foot の中央に戻る",
             [ui.visible("wnext"), toast_at_foot(ui)], [False, True])
    # ── 点数表示オン: 点数のカードが .foot の上にあるので、トーストは読み出し行と式のあいだ（6.5）──
    ui.open({"ci": 0, "cleared": 200, "hintStock": 5, "chalRem": 1, "scoreOn": True})
    ui.ev("start('chal')")
    t0 = time.time()
    ui.solve(wait=0)
    time.sleep(max(0, 1.6 - (time.time() - t0)))
    ui.check("オン・報酬: 文面", ui.text("toast"), "ヒント +1（残り 6）")
    ui.check("オン・報酬: 点数のカードと「つぎへ」が出ている",
             [ui.visible("win"), ui.visible("wnext")], [True, True])
    ui.check("オン・報酬: 読み出し行と式のあいだに出て、カード・「つぎへ」・式・読み出し行に重ならない",
             toast_in_gap(ui), [True, True, True])
    time.sleep(max(0, 4.1 - (time.time() - t0)))
    stub(ui, "ok")
    ui.click("pcodev")
    time.sleep(0.4)
    ui.check("オン・正解後のコピー: 同じ空きに出て何にも重ならない", toast_in_gap(ui), [True, True, True])
    time.sleep(1.1)
    ui.click("wnext")
    stub(ui, "ok")
    ui.click("pcodev")
    time.sleep(0.4)
    ui.check("オン: 次の問題へ進むと .foot の中央に戻る",
             [ui.visible("win"), toast_at_foot(ui)], [False, True])
    # ── 難易度の言葉（区切りは星と同じ）─────────────────────
    # 6.5 で英語に（6.4 は かんたん／ふつう／むずかしい）。区切り TIER_AT は変えていない
    for d, word in [(3, "EASY"), (8, "EASY"), (9, "NORMAL"), (13, "NORMAL"),
                    (14, "HARD"), (16, "HARD")]:
        ui.ev("go('home'); start('free'); loadPuzzle(ALL().find(p=>p.d===%d))" % d)
        ui.check("難易度 %d は「%s」" % (d, word), ui.text("pdiff"), word)
        ui.check("難易度 %d: 数値は出さない" % d,
                 ui.ev("/難易度/.test($('pcode').textContent)"), False)
    ui.ev("go('home'); start('chal')")
    ui.check("挑戦は「HARD」", ui.text("pdiff"), "HARD")
    # 正解の段階と同じ区切り。d=13 は「正解」、d=14 は「お見事」（すぐ解くので苦戦の加算なし）。
    # 6.5 から「正解」「お見事」は読み出し行（#sub）だけに出る
    for d, word, big in [(8, "EASY", "正解"), (13, "NORMAL", "正解"),
                         (14, "HARD", "お見事")]:
        ui.ev("go('home'); start('free'); loadPuzzle(ALL().find(p=>p.d===%d))" % d)
        ui.solve()
        ui.check("難易度 %d の読み出し行" % d, ui.text("sub"), big)
        ui.check("難易度 %d の星の段階は言葉の段階と同じ" % d,
                 ui.ev("lastWin.lv"), {"EASY": 1, "NORMAL": 2, "HARD": 3}[word])
    # 区切りを 1 か所で持っていること: TIER_AT を動かすと言葉と星が一緒に動く
    ui.ev("TIER_AT[0]=10; go('home'); start('free'); loadPuzzle(ALL().find(p=>p.d===9))")
    ui.check("区切りを 10 にずらすと d=9 は「EASY」", ui.text("pdiff"), "EASY")
    ui.solve()
    ui.check("同じく星の段階も 1 に下がる", ui.ev("lastWin.lv"), 1)
    ui.ev("TIER_AT[0]=9")
    # ── #pcode が 1 行に収まる（6.5。各段階でいちばん幅を取る組み合わせを全問から探す）──
    ui.ev("go('home'); start('chal')")
    top_h = ui.ev("document.querySelector('#play .top').getBoundingClientRect().height")
    longest = ui.ev(
        "(()=>{const pc=$('pcode');pc.style.whiteSpace='nowrap';const best={};"
        "for(const p of ALL()){const k=TIER_NAME[tierOf(p.d)];"
        "$('pcodev').textContent=codeOf(p);$('pdiff').textContent=k;$('pcount').textContent=p.n;"
        "const r=document.createRange();r.selectNodeContents(pc);const w=r.getBoundingClientRect().width;"
        "if(!best[k]||w>best[k].w)best[k]={w,code:codeOf(p)}}"
        "pc.style.whiteSpace='';return Object.entries(best).map(([k,v])=>[k,v.code])})()")
    ui.check("3 段階とも見つかる", sorted(k for k, _ in longest), ["EASY", "HARD", "NORMAL"])
    for word, code in longest:
        ui.ev("loadPuzzle(ALL().find(p=>codeOf(p)===%r));"
              "$('pmode').textContent='挑戦 '+CHAL.length+'/'+CHAL.length" % code)
        ui.check("%s でいちばん長い #pcode（%s）が 1 行に収まる" % (word, code),
                 ui.ev("(()=>{const pc=$('pcode'),i=document.querySelector('#play .info');"
                       "const r=document.createRange();r.selectNodeContents(pc);"
                       "return [new Set([...r.getClientRects()].map(b=>Math.round(b.bottom))).size===1,"
                       "i.scrollWidth<=i.clientWidth,"
                       "i.getBoundingClientRect().right<=$('menu').getBoundingClientRect().left]})()"),
                 [True, True, True])
        ui.check("%s: ヘッダの高さが変わらない" % word,
                 ui.ev("document.querySelector('#play .top').getBoundingClientRect().height"), top_h)
    ui.check_no_errors()
