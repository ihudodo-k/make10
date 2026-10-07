# -*- coding: utf-8 -*-
"""英語の画面（7.7・GAME-SPEC 13-8）。?lang=en で開いて見る。

  1. 画面を巡っても、日本語の文字が出ない
     （例外は設定の行の項目名「言語 / Language」と、値の「日本語」だけ）
  2. 文字のはみ出しが無い（要素の幅より文字が長い・画面の外に出る・途中で切れる）。
     上のバー・トースト・読み出し行・入力欄の薄い字・統計の名前は、個別にも測る
  3. ヒントのラベル: 英語はコロンを持たず、中身との間を CSS の余白で空ける（日本語は「：」のまま・余白 0）。
     縮小の計算が持つ幅と空き（HINT_TEXT.labelEm / labelGap）が、言語ごとの実際の値と合っている
  4. 遊び方の「計算のきまり」の先頭 2 行（^ は累乗・! は階乗。日本語の画面にも出る）。式は折り返さない
  5. 設定の「自動」の値は、今どちらの言語かを括弧で出す
  6. 英語の区切りは「 · 」（正解カードの詳細行。日本語は全角の空白のまま）

画面の大きさは normal 430×900・compact 360×690 に加えて、compact の回で 360×640 も見る。
"""
import json
import time

NAME = "英語の画面"

JA = "/[\\u3040-\\u30ff\\u3400-\\u9fff\\uff01-\\uff60\\u3005\\u3006]/"

HELPERS = r"""
window.__skip=e=>e.closest('#devpanel,#banner,#dv-open-row');
/* 日本語の文字が入っている文字・属性（見えていない画面も含めて DOM 全体。言語の行は別に見る） */
window.__ja=function(){const re=%s,out=[];
  const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  for(let n=w.nextNode();n;n=w.nextNode()){const e=n.parentElement;
    if(!e||e.closest('script,style')||__skip(e)||e.closest('#t-lang'))continue;
    if(re.test(n.textContent))out.push((e.id||e.className||e.tagName)+': '+n.textContent.trim().slice(0,24))}
  for(const e of document.querySelectorAll('[title],[aria-label],[placeholder]')){if(__skip(e))continue;
    for(const a of ['title','aria-label','placeholder']){const v=e.getAttribute(a)||'';
      if(re.test(v))out.push((e.id||e.tagName)+'@'+a+': '+v.slice(0,24))}}
  return out};
window.__vis=e=>{const s=getComputedStyle(e);if(s.display==='none'||s.visibility==='hidden')return false;
  const r=e.getBoundingClientRect();return r.width>0&&r.height>0};
/* 見えている文字のはみ出し。読み上げ専用の .btnlabel は画面の外に置いてあるので見ない */
window.__over=function(){const out=[],vw=innerWidth;
  for(const e of document.querySelectorAll('#app *')){
    if(__skip(e)||e.closest('.btnlabel,.hide')||!__vis(e))continue;
    let a=e.parentElement,ok=true;while(a&&a.id!=='app'){if(!__vis(a)){ok=false;break}a=a.parentElement}if(!ok)continue;
    const tn=[...e.childNodes].filter(n=>n.nodeType===3&&n.textContent.trim());if(!tn.length)continue;
    const r=document.createRange();r.setStartBefore(tn[0]);r.setEndAfter(tn[tn.length-1]);
    const t=r.getBoundingClientRect(),b=e.getBoundingClientRect(),
      name=(e.id?'#'+e.id:e.tagName.toLowerCase()+'.'+e.className)+' "'+e.textContent.trim().slice(0,24)+'"';
    if(t.left<-0.5||t.right>vw+0.5)out.push('画面の外: '+name);
    else if(t.right>b.right+0.6||t.left<b.left-0.6)out.push('要素より長い: '+name);
    if(getComputedStyle(e).overflowX!=='visible'&&e.scrollWidth>e.clientWidth+1)out.push('切れている: '+name)}
  return out};
/* 要素の文字の箱 [左, 右, 行数]。行数は、文字の上下の広がりが文字 2 つぶんより小さければ 1 */
window.__tx=function(e){const r=document.createRange();r.selectNodeContents(e);
  const rs=[...r.getClientRects()].filter(x=>x.width>0);if(!rs.length)return [0,0,0];
  const top=Math.min(...rs.map(x=>x.top)),bot=Math.max(...rs.map(x=>x.bottom)),
    fs=parseFloat(getComputedStyle(e).fontSize);
  return [Math.min(...rs.map(x=>x.left)),Math.max(...rs.map(x=>x.right)),(bot-top)<fs*2?1:2]};
1""" % JA

TOASTS = [("toast.copied", "{}", True), ("toast.share_copied", "{}", True),
          ("toast.copy_failed", "{code:'WWHMT'}", True), ("toast.hint_reward", "{stock:1000}", True),
          ("toast.chal_end", "{done:CHAL.length,total:CHAL.length}", False), ("toast.reset", "{}", False),
          ("toast.exit_confirm", "{}", False), ("toast.exit_app", "{}", False), ("play.alt_none", "{}", False)]


def tour(ui, tag):
    """英語で主な画面を巡り、(日本語の文字の残り, はみ出し) を集める"""
    ja, over = [], []

    def look(name):
        time.sleep(0.12)
        ja.extend("%s / %s" % (name, x) for x in ui.ev("__ja()"))
        over.extend("%s / %s" % (name, x) for x in ui.ev("__over()"))

    ui.open(lang="en")
    codes = ui.ev("[codeOf(COURSE[3]),codeOf(CHAL[0]),codeOf(FREE.find(p=>p.rc!=='N')),codeOf(COURSE[900])]")
    save = {"ci": 137, "cleared": 152, "scoreOn": True, "hintStock": 97, "seen": codes,
            "stats": {"n": 152, "sec": 6100, "best": 7, "band": {"3-8": 60, "9-13": 70, "14-16": 15, "17+": 7}},
            "hist": [{"c": c, "d": 17, "s": 123, "m": "chal", "p": 300, "st": 3} for c in codes]}
    ui.open(save, lang="en")
    ui.ev(HELPERS)
    look("ホーム")
    ui.ev("G.cleared=3;renderHome()"); look("ホーム（挑戦がロック中）")
    ui.ev("G.cleared=152;G.chalDone=CHAL.map(codeOf);renderHome()"); look("ホーム（全問クリア）")
    ui.ev("G.chalDone=[];renderHome();$('codein').placeholder=t('home.code_bad')"); look("ホーム（コードが違う）")
    ui.click("m-course"); look("問題画面")
    for i in (1, 2, 3):
        ui.click("hint"); look("ヒント %d" % i)
    ui.click("hint-close")
    ui.solve(); look("正解（点数表示オン）")
    ui.ev("go('home');go('stats')"); look("統計")
    ui.ev("G.hist=[];G.stats={n:0,sec:0,best:0,band:{}};renderStats()"); look("統計（記録なし）")
    ui.ev("go('home')"); ui.click("gear"); look("設定（自動）")
    ui.click("t-lang"); look("設定（日本語）")
    ui.click("t-lang"); look("設定（English）")
    ui.click("reset"); look("設定（リセットの確認）")
    ui.click("go-help"); look("遊び方")
    ui.ev("go('home');G.chalShown=CHAL.slice(0,CHAL.length-1).map(codeOf);G.cleared=152;start('chal')")
    look("問題画面（挑戦の最大桁）")
    ui.ev("go('home');start('free')"); look("問題画面（フリー）")
    return ja, over


def measure(ui, width):
    """個別に測る所。戻り値は {名前: 実測} で、呼ぶ側が期待値と比べる"""
    out = {}
    # ── 上のバー: 問題番号とコードの行が 1 行で、左右のボタンに食い込まない・.top の高さは変わらない
    ui.ev("go('home');G.chalShown=CHAL.slice(0,CHAL.length-1).map(codeOf);G.cleared=152;start('chal')")
    out["top"] = ui.ev(
        "(()=>{const a=__tx($('pmode')),b=__tx($('pcode')),l=$('back').getBoundingClientRect().right,"
        "r=$('menu').getBoundingClientRect().left,h=document.querySelector('.top').getBoundingClientRect().height;"
        "return [$('pmode').textContent,a[2],b[2],a[0]>=l,a[1]<=r,b[0]>=l,b[1]<=r,h===$('back').getBoundingClientRect().height]})()")
    # ── 読み出し行: どの文も 1 行で、行の幅に収まる
    bad = []
    for k, vars_ in [("read.paren_mismatch", "{}"), ("read.paren_extra", "{}"), ("read.no_calc", "{}"),
                     ("read.no_calc_why", "{}"), ("read.solved", "{}"), ("read.banned", "{op:'×'}"),
                     ("read.dead_paren", "{}"), ("read.no_hint", "{}")]:
        el = "eq" if k in ("read.paren_mismatch", "read.no_calc") else "sub"
        r = ui.ev("(()=>{const e=$(%s);e.className=%s;e.textContent=t(%s,%s);"
                  "const x=__tx(e),p=e.parentElement.getBoundingClientRect();"
                  "return [x[2]===1,x[0]>=p.left,x[1]<=p.right]})()"
                  % (json.dumps(el), json.dumps("eq idle" if el == "eq" else "sub warn"), json.dumps(k), vars_))
        if r != [True, True, True]:
            bad.append(k)
    out["read"] = bad
    ui.ev("render()")
    # ── トースト: 1 行で画面の中。.foot の中央に出すものは「全部消す」と「ヒント」の間
    bad = []
    for k, vars_, foot in TOASTS:
        ui.ev("toast(t(%s,%s),%s)" % (json.dumps(k), vars_, "{at:'foot'}" if foot else "{}"))
        time.sleep(0.3)                 # 出る動き（0.2 秒）が終わってから測る
        r = ui.ev("(()=>{const t=$('toast').getBoundingClientRect(),c=$('clear').getBoundingClientRect().right,"
                  "h=$('hint').getBoundingClientRect().left,x=__tx($('toast'));"
                  "return [x[2]===1,t.left>=0,t.right<=innerWidth,%s]})()"
                  % ("t.left>=c&&t.right<=h" if foot else "true"))
        if r != [True, True, True, True]:
            bad.append(k)
    out["toast"] = bad
    # ── 入力欄の薄い字: ::placeholder の書体で測った幅が、欄の中に収まる
    ui.ev("go('home')")
    out["ph"] = ui.ev(
        "(()=>{const i=$('codein'),s=getComputedStyle(i),p=getComputedStyle(i,'::placeholder'),"
        "sp=document.createElement('span');sp.style.cssText='position:absolute;visibility:hidden;white-space:nowrap';"
        "for(const k of ['fontFamily','fontSize','fontWeight','letterSpacing','textTransform'])sp.style[k]=p[k];"
        "document.body.appendChild(sp);const av=i.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight),bad=[];"
        "for(const k of ['home.code_placeholder','home.code_bad']){sp.textContent=t(k);"
        "if(sp.getBoundingClientRect().width>av)bad.push(k)}sp.remove();return bad})()")
    # ── 統計: 6 項目の名前と数字が 1 行で、自分の列に収まる。帯の名前と履歴の行も 1 行
    ui.ev("G.ci=1000;G.seen=Array.from({length:12345},(_,i)=>'X'+i);G.chalDone=CHAL.map(codeOf);"
          "G.stats={n:9,sec:8991,best:999,band:{'3-8':1000,'9-13':1000,'14-16':1000,'17+':CHAL.length}};"
          "G.hist=[{c:codeOf(FREE.find(p=>p.rc!=='N')),d:44,s:9999,m:'free',p:1,st:1}];go('stats')")
    out["stats"] = ui.ev(
        "(()=>{const bad=[];for(const s of document.querySelectorAll('#statlist .stat')){const b=s.getBoundingClientRect();"
        "const n=s.querySelector('.sv b'),u=s.querySelector('.sv .su');"
        "for(const e of [s.querySelector('.sk'),n,u]){if(!e)continue;const x=__tx(e);"
        "if(x[2]!==1||x[0]<b.left-0.5||x[1]>b.right+0.5)bad.push(e.textContent)}"
        "if(n&&u){const a=n.getBoundingClientRect(),c=u.getBoundingClientRect();"
        "if(c.top<a.top-1||c.bottom>a.bottom+1||c.left<a.right)bad.push('単位が別の行: '+s.textContent)}}"
        "for(const e of document.querySelectorAll('#statbars .row span,#stathist .toggle>span')){const x=__tx(e),"
        "b=e.closest('.row,.toggle').getBoundingClientRect();if(x[2]!==1||x[1]>b.right+0.5)bad.push(e.textContent)}"
        "return bad})()")
    # ── 設定: 行の名前が、右端のスイッチ・矢印・値に重ならず 1 行
    ui.ev("go('home')"); ui.click("gear")
    out["settings"] = ui.ev(
        "(()=>{const bad=[];for(const b of document.querySelectorAll('#settings .toggle')){"
        "const x=__tx(b.firstElementChild),r=b.lastElementChild.getBoundingClientRect();"
        "if(x[2]!==1||x[1]>r.left-4)bad.push(b.id)}return bad})()")
    # ── ホーム: モードの名前と値が行の中に収まり、矢印に重ならない
    ui.ev("go('home');G.cleared=3;renderHome()")
    out["home"] = ui.ev(
        "(()=>{const bad=[];for(const m of document.querySelectorAll('#home .mode')){const c=m.querySelector('.chev').getBoundingClientRect();"
        "for(const e of m.querySelectorAll('.mt,.mv')){if(!e.textContent)continue;const x=__tx(e),b=m.getBoundingClientRect();"
        "if(x[2]!==1||x[0]<b.left||x[1]>c.left)bad.push(e.textContent)}}"
        "for(const e of [$('chero'),$('cden'),$('ctot').parentElement]){const x=__tx(e);"
        "if(x[2]!==1||x[0]<0||x[1]>innerWidth)bad.push(e.id||e.className)}"
        "return bad})()")
    return out


def run(ui):
    width = ui.ev("innerWidth") or 0
    sizes = [None] if ui.viewport == "normal" else [None, (360, 640)]
    for size in sizes:
        tag = "" if size is None else "（360×640）"
        if size:
            ui.c.metrics(*size)
        try:
            ja, over = tour(ui, tag)
            width = ui.ev("innerWidth")
            ui.check("英語で画面を巡っても、日本語の文字が出ない" + tag, ja, [])
            ui.check("英語で画面を巡っても、文字のはみ出しが無い" + tag, over, [])
            ui.check("設定の行の項目名だけは、英語でも「言語 / Language」" + tag,
                     ui.ev("$('t-lang').firstElementChild.textContent"), "言語 / Language")
            m = measure(ui, width)
            ui.check("上のバー: いちばん長い問題番号とコードの行が 1 行で、左右のボタンに食い込まない・高さは同じ" + tag,
                     m["top"], ["Challenge %d/%d" % ((ui.ev("CHAL.length"),) * 2), 1, 1, True, True, True, True, True])
            ui.check("読み出し行: どの文も 1 行で幅に収まる" + tag, m["read"], [])
            ui.check("トースト: どれも 1 行で画面の中・.foot の中央に出すものはボタンの間" + tag, m["toast"], [])
            ui.check("入力欄の薄い字が欄に収まる" + tag, m["ph"], [])
            ui.check("統計: いちばん長い値でも、名前・数字・帯・履歴が 1 行で収まる" + tag, m["stats"], [])
            ui.check("設定: 行の名前が右端の部品に重ならない" + tag, m["settings"], [])
            ui.check("ホーム: モードの名前と値・進み具合の行が 1 行で収まる" + tag, m["home"], [])
            ui.check_no_errors("JS エラー 0" + tag)
        finally:
            if size:
                ui.c.metrics(360, 690)

    # ── 設定の値（7.7）: 言語の名前は自分の言葉、自動は今の言語を括弧で
    ui.open(lang=None, nav="en-US")
    ui.click("gear")
    vals = [ui.text("t-lang-v")]
    for _ in range(2):
        ui.click("t-lang"); vals.append(ui.text("t-lang-v"))
    ui.check("設定の値: 端末が英語のとき Auto (English) → 日本語 → English", vals,
             ["Auto (English)", "日本語", "English"])
    ui.open(lang=None, nav="ja-JP")
    ui.click("gear")
    vals = [ui.text("t-lang-v")]
    for _ in range(2):
        ui.click("t-lang"); vals.append(ui.text("t-lang-v"))
    ui.check("設定の値: 端末が日本語のとき 自動（日本語）→ 日本語 → English", vals,
             ["自動（日本語）", "日本語", "English"])
    ui.check("設定の値: いちばん長い値でも項目名に重ならず 1 行", ui.ev(
        "(()=>{const bad=[];for(const v of ['auto','ja','en']){G.lang=v;applyLang(true);"
        "const l=$('t-lang').firstElementChild.getBoundingClientRect(),r=$('t-lang-v').getBoundingClientRect();"
        "if(l.right>r.left-4||r.height>24)bad.push(v)}G.lang='auto';applyLang(true);return bad})()"), [])

    # ── 遊び方の 2 行（7.7。日本語にも出る）
    for lang, want in [("ja", ["^ は累乗です（2 ^ 3 = 8）", "! は階乗です（3! = 6）"]),
                       ("en", ["^ is power (2 ^ 3 = 8)", "! is factorial (3! = 6)"])]:
        ui.open(lang=lang)
        ui.ev("go('help')")
        ui.check("遊び方（%s）:「計算のきまり」の先頭 2 行が ^ と ! の意味" % lang, ui.ev(
            "(()=>{const h=[...document.querySelectorAll('#help h3')].find(x=>x.textContent===t('help.sec_rules'));"
            "return [...h.nextElementSibling.children].slice(0,2).map(x=>x.textContent)})()"), want)
        ui.check("遊び方（%s）:「計算のきまり」は 6 行で、3 行目は今までの先頭（^ は右から）" % lang, ui.ev(
            "(()=>{const h=[...document.querySelectorAll('#help h3')].find(x=>x.textContent===t('help.sec_rules'));"
            "const li=[...h.nextElementSibling.children];return [li.length,li[2].innerHTML===t('help.r1_html')]})()"),
            [6, True])
        # 式（<code>）は行の途中で折り返さない。折り返さなくしても、行からはみ出さない
        for size in ([None] if ui.viewport == "normal" else [None, (360, 640)]):
            tag = "" if size is None else "・360×640"
            if size:
                ui.c.metrics(*size)
            try:
                ui.open(lang=lang)
                ui.ev(HELPERS)
                ui.ev("go('help')")
                r = ui.ev(
                    "(()=>{const h=$('help'),hb=h.getBoundingClientRect(),cs=[...h.querySelectorAll('code')];"
                    "const wrap=cs.filter(c=>c.getClientRects().length!==1).map(c=>c.textContent),"
                    "out=cs.filter(c=>{const li=c.closest('li,p').getBoundingClientRect(),b=c.getBoundingClientRect();"
                    "return b.left<li.left-0.5||b.right>li.right+0.5||b.right>hb.right}).map(c=>c.textContent);"
                    "const a=__over();h.scrollTop=9999;const b=__over();h.scrollTop=0;"
                    "return [cs.length,wrap,out,a.concat(b),h.scrollWidth>h.clientWidth,"
                    "document.documentElement.scrollWidth>innerWidth]})()")
                ui.check("遊び方（%s%s）: 式 7 つがどれも折り返さず、行からも画面からもはみ出さない・横に動かない"
                         % (lang, tag), r, [7, [], [], [], False, False])
            finally:
                if size:
                    ui.c.metrics(360, 690)

    # ── ヒントのラベル（7.7）: 英語はコロンなし・中身との間は CSS の余白。日本語は「：」のまま・余白 0。
    #    縮小の計算が持つ幅と空きが、実際のラベルの幅・空きと合っている
    for lang, labels, gap in [("ja", ["使う記号：", "形：", "解答例："], 0), ("en", ["Uses", "Shape", "Solution"], 6)]:
        ui.open(lang=lang)
        ui.click("m-course")
        got = []
        for _ in range(3):
            ui.click("hint")
            got.append(ui.ev(
                "(()=>{const bin=document.querySelector('#hintbox .hbin'),c=bin.querySelector('code'),x=document.createRange();"
                "x.setStart(bin,0);x.setEndBefore(c);const t=x.getBoundingClientRect();"
                "return [bin.firstChild.textContent,Math.round((c.getBoundingClientRect().left-t.right)*100)/100,t.width]})()"))
        ui.check("ヒントのラベル（%s）: 段階 1〜3 の文字（英語はコロンなし）" % lang, [g[0] for g in got], labels)
        ui.check("ヒントのラベル（%s）: ラベルと中身の間の空きは %dpx（段階 1〜3 とも）" % (lang, gap),
                 [g[1] for g in got], [gap] * 3)
        ui.check("ヒント 3 のラベル（%s）: 計算が持つ幅は実際の文字の幅以上で差は 0.5px 未満・空きは CSS と同じ値" % lang,
                 ui.ev("(()=>{const have=HINT_TEXT.labelEm[LANG]*HINT_ROW.font,real=%s;"
                       "return [have>=real,have-real<0.5,HINT_TEXT.labelGap[LANG],"
                       "getComputedStyle(document.documentElement).getPropertyValue('--hintLabelGap').trim()]})()"
                       % json.dumps(got[2][2])), [True, True, gap, "%dpx" % gap])
    # 英語で、いちばん長い式の行（幅 360px では縮む）が 1 行に収まる
    ui.open(lang="en")
    ui.ev("MODE='share';loadPuzzle(INDEX.get('5333|M0'));go('play')")
    for _ in range(3):
        ui.click("hint")
    ui.ev("hintSolAt=43;showHint()")
    r = ui.ev("(()=>{const b=document.querySelector('#hintbox .hbody'),i=b.querySelector('.hbin'),"
              "c=i.querySelector('code');return [b.scrollWidth<=b.clientWidth,i.getBoundingClientRect().width<=b.clientWidth,"
              "Math.round($('hintbox').getBoundingClientRect().height),c.style.fontSize]})()")
    ui.check("英語のヒント 3: いちばん長い式の行が 1 行に収まり、箱は 58px"
             "（幅 360px では 80% に縮む・430px では縮まない）", r,
             [True, True, 58, "80%" if ui.ev("innerWidth") == 360 else ""])
    # ヒント 3 を開いたまま設定で言語を切り替えて戻っても、その言語のラベル幅で縮め直してある
    ui.open(lang=None, nav="ja-JP")
    ui.ev("MODE='share';loadPuzzle(INDEX.get('5333|M0'));go('play')")
    for _ in range(3):
        ui.click("hint")
    ui.ev("hintSolAt=43;showHint()")
    look = ("(()=>{const b=document.querySelector('#hintbox .hbody'),i=b.querySelector('.hbin'),"
            "c=i.querySelector('code');return [i.firstChild.textContent,b.scrollWidth<=b.clientWidth,c.style.fontSize]})()")
    narrow = ui.ev("innerWidth") == 360
    ui.check("日本語のヒント 3: いちばん長い式の行（幅 360px では 80.7%）", ui.ev(look),
             ["解答例：", True, "80.7%" if narrow else ""])
    ui.click("menu"); ui.click("t-lang"); ui.click("t-lang"); ui.click("navback")
    ui.check("設定で英語に切り替えて戻ると、英語のラベル幅で縮め直してある（80%）・見ていた解答のまま",
             ui.ev(look) + [ui.ev("hintSolAt")], ["Solution", True, "80%" if narrow else "", 43])

    # ── 英語の区切りは「 · 」（7.7）。日本語は全角の空白のまま
    for lang, pat in [("en", r"^Difficulty \d+ · \d+s · Hint 1( · New best!)?$"),
                      ("ja", r"^難易度 \d+　\d+秒　ヒント1(　自己ベスト更新)?$")]:
        ui.open({"ci": 0, "scoreOn": True}, lang=lang)
        ui.click("m-course")
        ui.click("hint")
        ui.solve()
        ui.check("正解カードの詳細行（%s）の区切り" % lang,
                 ui.ev("[new RegExp(%s).test($('wmeta').textContent),$('wmeta').textContent.includes('　')]"
                       % json.dumps(pat)), [True, lang == "ja"])
    ui.check_no_errors("JS エラー 0（設定・遊び方・ヒント）")
