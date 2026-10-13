# -*- coding: utf-8 -*-
"""遊び方（D0.5。DAILY-SPEC 13-10・16-4）。

- 上のバー左の「?」から開く。× か Esc で閉じる
- 初回だけ自動で出す（保存データの印 help）。?date=（テスト表示）では自動で出さない。
  保存できない環境では、開くたびに出る
- 初回に自動で出た遊び方を読んでいる間は、時間を数えない
"""
import datetime
import time

from uiharness import daily_ui as dui

NAME = "遊び方"

TZ = "Asia/Tokyo"
LINES = {
    "ja": ["4 つの数字を順番どおりに全部使って 10 を作ります。",
           "記号を数字のあいだへドラッグして置きます（設定でタップ配置にもできます）",
           "括弧の中から先に計算します。10 になれば正解です",
           "^ は累乗です（2 ^ 3 = 8）",
           "! は階乗です（3! = 6）",
           "0! は 1 です（0! = 1）",
           "ヒント：共有でもらえます（1 日 2 回まで）",
           "ギブアップ：解答例を見て、その日を終えます",
           "毎日 0 時（端末の時刻）に新しい問題になります。"],
    "en": ["Make 10 using all four numbers in order.",
           "Drag a symbol between the numbers (or turn on Tap to place in Settings)",
           "Parentheses are calculated first. Make 10 and it's solved",
           "^ is power (2 ^ 3 = 8)",
           "! is factorial (3! = 6)",
           "0! is 1 (0! = 1)",
           "Hint · Share to get one (up to 2 a day)",
           "Give up · See a solution and end the day's puzzle",
           "A new puzzle every day at midnight, your local time."],
}
BOLD = {"ja": ["^ は累乗", "! は階乗", "0! は 1", "ヒント", "ギブアップ"],
        "en": ["^ is power", "! is factorial", "0! is 1", "Hint", "Give up"]}
# 見本の図の名前（読み上げ用。D0.16）
ALTS = {"ja": ["見本: 8 7 5 2 の、8 と 7 のあいだに − を置く", "見本: ( 8 − 7 ) × 5 × 2 は、括弧の中から計算して 10。正解"],
        "en": ["Example: placing − between 8 and 7 in 8 7 5 2",
               "Example: ( 8 − 7 ) × 5 × 2 is calculated from the parentheses and makes 10. Solved!"]}
# 見本の動き（名前が hd- で始まる CSS のアニメーション）
HD = "document.getAnimations().filter(a=>(a.animationName||'').startsWith('hd-'))"
FREEZE = HD + ".forEach(a=>{a.pause();a.currentTime=%d})"
# 見本の部品の見た目を、盤の実物と比べる（色・太さ・線は同じ。大きさは盤の寸法 × 倍率 --dk）。食い違った項目の名前を返す
LOOK = r"""(function(){
  const q=s=>document.querySelector(s), cs=e=>getComputedStyle(e), bad=[];
  const dk=parseFloat(cs(q('.hdemo')).getPropertyValue('--dk'));
  const same=(name,a,b,props)=>{if(!a||!b){bad.push(name+': 要素が無い');return}
    for(const p of props)if(cs(a)[p]!==cs(b)[p])bad.push(name+'.'+p+': 盤 '+cs(a)[p]+' / 見本 '+cs(b)[p])};
  const ratio=(name,a,b,props,k)=>{if(!a||!b)return;
    for(const p of props){const x=parseFloat(cs(a)[p]),y=parseFloat(cs(b)[p]);
      if(!(x>0)||Math.abs(y-x*k)>0.06)bad.push(name+'.'+p+': 盤 '+x+' × '+k+' / 見本 '+y)}};
  const d=q('#dhelpbody .hd2');
  same('数字',q('#expr .num'),d.querySelector('.dnum'),['color','fontWeight','fontVariantNumeric']);
  ratio('数字',q('#expr .num'),d.querySelector('.dnum'),['fontSize','width','height','marginLeft'],dk);
  same('演算',q('#expr .tok.op'),d.querySelector('.dtok.op'),['color','fontWeight']);
  ratio('演算',q('#expr .tok.op'),d.querySelector('.dtok.op'),['fontSize','width','height'],dk);
  same('括弧',q('#expr .tok.lp'),d.querySelector('.dtok.par'),['color','fontWeight']);
  ratio('括弧',q('#expr .tok.lp'),d.querySelector('.dtok.par'),['fontSize','width','height'],dk);
  const line=['borderTopColor','borderTopStyle','borderTopWidth','backgroundColor'];
  same('枠',q('#expr .zone.live:not(.hot)'),q('.hd1 .dzone'),line);
  same('吸着した枠',q('#expr .zone.hot'),q('.hd1 .dhot'),line);
  same('トレイの記号',q('#tray .chip:not(.off)'),q('.hd1 .dchip'),['color','fontWeight']);
  ratio('トレイの記号',q('#tray .chip:not(.off)'),q('.hd1 .dchip'),['fontSize'],dk);
  same('トレイの線',q('#tray'),q('.hd1 .dtray'),['borderTopColor','borderTopStyle','borderTopWidth']);
  same('10',q('#eq.hit'),d.querySelector('.deq'),['color','fontWeight','fontVariantNumeric']);
  same('正解',q('#sub.ok'),d.querySelector('.dsub'),['color']);
  {const a=q('#sub.ok'),b=d.querySelector('.dsub');
   if(a&&b&&Math.abs(parseFloat(cs(a).letterSpacing)/parseFloat(cs(a).fontSize)-parseFloat(cs(b).letterSpacing)/parseFloat(cs(b).fontSize))>0.005)
     bad.push('正解.字間')}
  same('運んでいる記号',q('#ghost'),q('.hd1 .dghost'),['color','fontWeight']);
  ratio('運んでいる記号',q('#ghost'),q('.hd1 .dghost'),['fontSize'],dk);
  return {bad,dk,gold:cs(d.querySelector('.deq')).color}})()"""
SHOWN = "!document.getElementById('dhelpsheet').classList.contains('hide')"
ESC = "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))"
RECT = ("(function(){const r=document.getElementById(%r).getBoundingClientRect();"
        "return [r.left,r.top,r.width,r.height].map(Math.round)})()")


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731
    no = 4

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def click(el_id, wait=0.2):
        ui.ev("document.getElementById(%r).click()" % el_id)
        time.sleep(wait)

    # ══ 初めて来た人: 自動で出る ══
    ui.open(now=at(no), tz=TZ, perf=True, first=True)
    ui.check("初回: 遊び方が自動で出る", ui.ev(SHOWN), True)
    ui.check("初回: 出した時点で、保存データに印が付く", ui.saved(raw=True),
             {"v": 1, "days": {}, "cur": None, "help": 1, "set": {"easy": 0, "tap": 0}})
    ui.check("見出しと、9 つの文（最初の 1 行・見本の説明 2 つ・^・!・0!・ヒント・ギブアップ・毎日 0 時）",
             [ui.ev("document.querySelector('#dhelpsheet h2').textContent"),
              ui.ev("[...document.querySelectorAll('#dhelpbody p:not(.hlink)')].map(e=>e.textContent.trim())")],
             ["遊び方", LINES["ja"]])
    ui.check("太字と式（式は 2 ^ 3 = 8・3! = 6・0! = 1）",
             [ui.ev("[...document.querySelectorAll('#dhelpbody b')].map(e=>e.textContent)"),
              ui.ev("[...document.querySelectorAll('#dhelpbody code')].map(e=>e.textContent)")],
             [BOLD["ja"], ["2 ^ 3 = 8", "3! = 6", "0! = 1"]])
    # ── 見本の盤（D0.16）──
    ui.check("見本は 2 組。手順の番号 1・2 と、図（role=img と名前）と、説明の文",
             ui.ev("[...document.querySelectorAll('#dhelpbody .hfig')].map(f=>[f.querySelector('.hstep').textContent,"
                   "f.querySelector('.hdemo').getAttribute('role'),f.querySelector('.hdemo').getAttribute('aria-label'),"
                   "f.querySelector('.hcap').textContent])"),
             [["1", "img", ALTS["ja"][0], LINES["ja"][1]], ["2", "img", ALTS["ja"][1], LINES["ja"][2]]])
    ui.check("図の中身は、読み上げから隠してある（図の名前の文だけが読まれる）",
             ui.ev("[...document.querySelectorAll('#dhelpbody .hdemo')].every(d=>[...d.children].every(c=>c.getAttribute('aria-hidden')==='true'))"), True)
    ui.check("見本に見えている文字（置いた後の 8 − 7 5 2 とトレイの 8 つ／10・正解・( 8 − 7 ) × 5 × 2）",
             ui.ev("[[...document.querySelectorAll('.hd1 .dexpr .dnum,.hd1 .dexpr .dtok')].map(e=>e.textContent).join(' '),"
                   "[...document.querySelectorAll('.hd1 .dchip')].map(e=>e.textContent).join(' '),"
                   "[...document.querySelectorAll('.hd2 .deq,.hd2 .dsub')].map(e=>e.textContent).join(' '),"
                   "[...document.querySelectorAll('.hd2 .dexpr>*')].map(e=>e.textContent).join(' ')]"),
             ["8 − 7 5 2", "+ − × ÷ ^ ! ( )", "10 正解", "( 8 − 7 ) × 5 × 2"])
    ui.check("見本は触れない: 押す場所に見本の部品が当たらず、押しても盤は変わらない",
             ui.ev("(function(){const before=JSON.stringify(S.toks);let hit=0;"
                   "for(const e of document.querySelectorAll('#dhelpbody .dchip,#dhelpbody .dnum,#dhelpbody .dzone')){"
                   "const r=e.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,t=document.elementFromPoint(x,y);"
                   "if(t&&t.closest('.hdemo'))hit++;"
                   "for(const k of ['pointerdown','pointerup','click'])(t||document.body).dispatchEvent(new MouseEvent(k,{bubbles:true,clientX:x,clientY:y}))}"
                   "return [hit,JSON.stringify(S.toks)===before,held,getComputedStyle(document.querySelector('.hdemo')).pointerEvents]})()"),
             [0, True, None, "none"])
    ui.check("ヒントとギブアップの行のアイコンは、本物のボタンの絵柄と同じ",
             ui.ev("(function(){const d=(a,b)=>document.querySelector(a).innerHTML===document.querySelector(b).innerHTML;"
                   "return [d('#hi-hint svg','#hint svg'),d('#hi-giveup svg','#dgiveup svg')]})()"), [True, True])
    # 動き: シートが開いている間だけ動く。動かすのは transform と opacity だけ
    ui.check("開いている間: 見本の動きは 12 個。どれも 5 秒で繰り返し、動かすのは transform と opacity だけ",
             ui.ev("(function(){const a=" + HD + ";const keys=new Set();"
                   "a.forEach(x=>x.effect.getKeyframes().forEach(k=>Object.keys(k).forEach(p=>keys.add(p))));"
                   "['offset','computedOffset','easing','composite'].forEach(p=>keys.delete(p));"
                   "return [a.length,a.every(x=>x.playState==='running'),"
                   "a.every(x=>x.effect.getTiming().duration===5000&&x.effect.getTiming().iterations===Infinity),[...keys].sort()]})()"),
             [12, True, True, ["opacity", "transform"]])
    pos = ("(function(){const c=s=>{const r=document.querySelector(s).getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]};"
           "const o=s=>+getComputedStyle(document.querySelector(s)).opacity;"
           "const g=c('.hd1 .dghost'),a=c('.hd1 .dpick'),z=c('.hd1 .ds1');"
           "return {chip:Math.hypot(g[0]-a[0],g[1]-a[1]),slot:Math.hypot(g[0]-z[0],g[1]-z[1]),"
           "ghost:o('.hd1 .dghost'),zone:o('.hd1 .dzone'),hot:o('.hd1 .dhot'),tok:o('.hd1 .ds1 .dtok'),pick:o('.hd1 .dpick'),"
           "w:document.querySelector('.hd1 .dexpr').getBoundingClientRect().width}})()")
    ui.ev(FREEZE % 700)
    f1 = ui.ev(pos)
    ui.ev(FREEZE % 2200)
    f3 = ui.ev(pos)
    ui.ev(FREEZE % 3000)
    f4 = ui.ev(pos)
    ui.check("動きの途中（0.7 秒）: 運ぶ記号がトレイの「−」の上に出て、トレイの「−」は薄くなり、まだ置かれていない",
             [f1["chip"] < 1.5, f1["ghost"], f1["pick"] < 0.5, f1["tok"]], [True, 1, True, 0])
    ui.check("動きの途中（2.2 秒）: 運ぶ記号が 8 と 7 のあいだの枠に重なり、枠が開いて、その枠だけ明るい",
             [f3["slot"] < 1.5, f3["ghost"], f3["zone"], f3["hot"], f3["tok"]], [True, 1, 1, 1, 0])
    ui.check("置いた後（3 秒）: 記号が置かれ、枠と運ぶ記号は消えている。トレイの「−」は元の濃さ",
             [f4["tok"], f4["zone"], f4["hot"], f4["ghost"], f4["pick"]], [1, 0, 0, 0, 1])
    ui.check("動いている間、並びの幅は変わらない", [abs(f1["w"] - f4["w"]) < 0.01, abs(f3["w"] - f4["w"]) < 0.01], [True, True])
    ui.check("キーボードの一覧は、まだ無い。リンクはプライバシーポリシーの 1 つだけで、いちばん下",
             ui.ev("[document.querySelectorAll('#dhelpbody h3').length,"
                   "[...document.querySelectorAll('#dhelpbody a')].map(a=>a.id).join(' '),"
                   "dhelpbody.lastElementChild.contains(dprivacy)]"), [0, "dprivacy", True])
    ui.check("遊び方は列いっぱいに重なり、盤を覆う",
             [ui.ev(RECT % "dhelpsheet") == ui.ev(RECT % "app"),
              ui.ev("(function(){const r=expr.getBoundingClientRect();"
                    "return !!document.elementFromPoint((r.left+r.right)/2,(r.top+r.bottom)/2).closest('#dhelpsheet')})()")],
             [True, True])
    ui.check("行は画面の中に収まり、横にはみ出さず、式は折り返さない。中を縦に動かす必要も無い",
             ui.ev("(function(){const b=dhelpbody,a=app.getBoundingClientRect();"
                   "const ps=[...b.querySelectorAll('p')],cs=[...b.querySelectorAll('code')];"
                   "return [ps.every(p=>{const r=p.getBoundingClientRect();return r.left>=a.left&&r.right<=a.right"
                   "&&p.scrollWidth<=p.clientWidth+1}),cs.every(c=>c.getClientRects().length===1),"
                   "b.scrollHeight<=b.clientHeight+1,"
                   "ps[ps.length-1].getBoundingClientRect().bottom<=dver.getBoundingClientRect().top]})()"),
             [True, True, True, True])
    ui.check("文の大きさ・行間・明るさは本編の遊び方と同じ（13px・1.75・85%）",
             ui.ev("(function(){const s=getComputedStyle(document.querySelector('#dhelpbody p:not(.hlink)'));"
                   "return [s.fontSize,Math.round(parseFloat(s.lineHeight)*100)/100,s.opacity]})()"),
             ["13px", 22.75, "0.85"])
    ui.check("式は折り返さない指定（white-space:nowrap）で、太字",
             ui.ev("(function(){const s=getComputedStyle(document.querySelector('#dhelpbody code'));"
                   "return [s.whiteSpace,s.fontWeight]})()"), ["nowrap", "700"])
    # 読んでいる間は時間を数えない
    ui.tick(30000)
    ui.check("初回: 読んでいる間は時間を数え始めない（最初に見た時刻が無く、保存もしない）",
             [ui.ev("startAt"), ui.saved(raw=True)["cur"]], [None, None])
    ui.visibility("hidden")
    ui.visibility("visible")
    ui.tick(5000)
    ui.check("初回: 画面を隠して戻しても、閉じるまで数え始めない",
             [ui.ev("startAt"), ui.saved(raw=True)["cur"]], [None, None])
    click("dhelp-close")
    ui.check("× で閉じる", ui.ev(SHOWN), False)
    ui.check("閉じたら、見本の動きは止まる（動いているものが 0 個）", ui.ev(HD + ".length"), 0)
    ui.tick(4000)
    ui.check("閉じた時が「問題を最初に見た時刻」（読んでいた 35 秒は入らない）。その日の分として保存される",
             [ui.ev("startAt"), ui.saved(raw=True)["cur"]],
             [at(no) + 35000, {"no": no, "start": at(no) + 35000, "h": 0, "sh": 0}])
    ui.check("閉じたところから時間を数える", ui.ev("Date.now()-startAt"), 4000)

    # ══ 「?」から開く ══
    ui.check("「?」は上のバーの左端（統計と左右対称・同じ高さ・同じ大きさ）。絵柄は丸で囲んだ ?",
             ui.ev("(function(){const h=dhelp.getBoundingClientRect(),s=dstats.getBoundingClientRect(),"
                   "a=app.getBoundingClientRect();return [Math.round(h.left-a.left)===Math.round(a.right-s.right),"
                   "h.top===s.top,h.width===s.width,h.height===s.height,"
                   "dhelp.querySelectorAll('svg.ic circle').length,dhelp.querySelectorAll('svg.ic path').length]})()"),
             [True, True, True, True, 1, 2])
    ui.check("「?」の名前（title・aria-label）", ui.ev("[dhelp.title,dhelp.getAttribute('aria-label')]"), ["遊び方", "遊び方"])
    click("dhelp")
    ui.check("「?」を押すと出る。見本の動きも、また始まる", [ui.ev(SHOWN), ui.ev(HD + ".length")], [True, 12])
    ui.check("閉じるボタンは統計の入口と同じ場所（右上）で、名前は「閉じる」",
             [ui.ev(RECT % "dhelp-close") == ui.ev(RECT % "dstats"),
              ui.ev("document.getElementById('dhelp-close').getAttribute('aria-label')")], [True, "閉じる"])
    ui.tick(3000)
    ui.check("「?」から開いた遊び方では、時間は止めない（最初に見た時刻も動かない）",
             [ui.ev("Date.now()-startAt"), ui.saved(raw=True)["cur"]["start"]], [7000, at(no) + 35000])
    ui.ev(ESC)
    ui.check("Esc で閉じる。見本の動きも止まる", [ui.ev(SHOWN), ui.ev(HD + ".length")], [False, 0])
    click("dstats")
    click("dstats-close")
    click("dhelp")
    click("dstats-close")
    ui.check("統計の × は、遊び方を閉じない", ui.ev(SHOWN), True)
    ui.ev(ESC)

    # ══ 2 回目からは自動で出ない ══
    ui.open(now=at(no, 12), tz=TZ, store="keep")
    ui.check("開き直す: 自動では出ない", ui.ev(SHOWN), False)
    click("dhelp")
    ui.check("開き直した後も「?」から見られる", ui.ev(SHOWN), True)
    click("dhelp-close")
    ui.open(now=at(no + 1), tz=TZ, store="keep")
    ui.check("次の日: 自動では出ない", ui.ev(SHOWN), False)

    # ══ 解いた後・ギブアップの後も「?」から見られる ══
    ui.open(now=at(no), tz=TZ)
    ui.solve(rows[no - 1]["sol"])
    ui.check("解いた後: 「?」は見えていて、押すと出る",
             [ui.visible("dhelp"), ui.ev("(document.getElementById('dhelp').click(),%s)" % SHOWN)], [True, True])

    # ══ ?date=（テスト表示）では自動で出さない ══
    ui.open(date=day(no).isoformat(), first=True)
    ui.check("?date=: 自動では出ない。保存もしない", [ui.ev(SHOWN), ui.saved(raw=True)], [False, None])
    click("dhelp")
    ui.check("?date=: 「?」からは見られる", ui.ev(SHOWN), True)

    # ══ 保存できない環境では、開くたびに出る ══
    ui.open(now=at(no), tz=TZ, store="blocked")
    first = ui.ev(SHOWN)
    click("dhelp-close")
    ui.open(now=at(no), tz=TZ, store="blocked")
    ui.check("保存できない環境: 開くたびに自動で出る", [first, ui.ev(SHOWN)], [True, True])
    click("dhelp-close")
    ui.check("保存できない環境: 閉じれば、そのまま遊べる", ui.solve(rows[no - 1]["sol"]), "10|正解")
    ui.check_no_errors("保存できない環境で JS エラー 0")

    # ══ 問題が無い日は出さない（「?」も無い）══
    ui.open(now=at(0), tz=TZ, first=True)
    ui.check("問題が無い日: 遊び方を出さず、印も付けない",
             [ui.visible("nopuzzle"), ui.ev(SHOWN), ui.visible("dhelp"), ui.saved(raw=True)],
             [True, False, False, None])

    # ══ 英語 ══
    ui.open(now=at(no), tz=TZ, lang="en", first=True)
    ui.check("英語: 見出しと 9 つの文",
             [ui.ev("document.querySelector('#dhelpsheet h2').textContent"),
              ui.ev("[...document.querySelectorAll('#dhelpbody p:not(.hlink)')].map(e=>e.textContent.trim())"),
              ui.ev("[...document.querySelectorAll('#dhelpbody b')].map(e=>e.textContent)"),
              ui.ev("[dhelp.title,document.getElementById('dhelp-close').getAttribute('aria-label')]")],
             ["How to play", LINES["en"], BOLD["en"], ["How to play", "Close"]])
    ui.check("英語: 行は横にはみ出さず、式は折り返さない。版の行に重ならない",
             ui.ev("(function(){const b=dhelpbody,ps=[...b.querySelectorAll('p')];"
                   "return [ps.every(p=>p.scrollWidth<=p.clientWidth+1),"
                   "[...b.querySelectorAll('code')].every(c=>c.getClientRects().length===1),"
                   "b.scrollHeight<=b.clientHeight+1]})()"), [True, True, True])
    ui.check("英語: 見本の図の名前と、手順の番号",
             ui.ev("[...document.querySelectorAll('#dhelpbody .hfig')].map(f=>[f.querySelector('.hstep').textContent,"
                   "f.querySelector('.hdemo').getAttribute('aria-label')])"), [["1", ALTS["en"][0]], ["2", ALTS["en"][1]]])
    ui.check("英語: 見本の「正解」は Solved!", ui.ev("document.querySelector('.hd2 .dsub').textContent"), "Solved!")
    click("dhelp-close")

    # ══ 収まり: 日本語でも、縦にも横にも動かさずに収まる（文の所が中身より低くない）══
    ui.open(now=at(no), tz=TZ, first=True)
    ui.check("日本語: 遊び方は、縦に動かさずに収まる。横にもはみ出さない",
             ui.ev("[dhelpbody.scrollHeight<=dhelpbody.clientHeight+1,document.documentElement.scrollWidth<=innerWidth,"
                   "[...dhelpbody.querySelectorAll('.hdemo')].every(d=>{const r=d.getBoundingClientRect(),b=dhelpbody.getBoundingClientRect();"
                   "return r.left>=b.left&&r.right<=b.right})]"), [True, True, True])
    click("dhelp-close")

    # ══ 見本の見た目は、盤の実物と同じ（色・太さ・線）。大きさは盤の寸法 × 倍率 ══
    # 盤を解いた形にして（数字・演算・括弧・金の「10」・「正解」がそろう）、枠を開き、1 つを吸着の見た目にしてから比べる
    ui.open(date=day(1).isoformat())
    ui.solve(rows[0]["sol"], wait=0.8)
    ui.ev("showZones('!');document.querySelector('#expr .zone.live').classList.add('hot');"
          "ghost.style.display='block'")
    click("dhelp", 0.6)
    look = ui.ev(LOOK)
    ui.check("#1 の解答例は、括弧・演算・数字がそろう式（比べる相手がある）", rows[0]["sol"], "( 8 - 7 ) * 5 * 2")
    ui.check("見本の数字・演算・括弧・枠・吸着した枠・トレイ・「10」・「正解」・運ぶ記号は、盤の実物と同じ見た目",
             look["bad"], [])
    ui.check("見本の大きさの倍率と、金の色（盤の変数から取れている）", [look["dk"], look["gold"]], [0.55, "rgb(227, 193, 111)"])
    # 金を使うのは「10」だけ（1 章）。遊び方の中では、見本の「10」の 1 つだけ（play・result の金の確かめは、遊び方の外を見ている）
    ui.check("遊び方の中で金を使っているのは、見本の「10」だけ",
             ui.ev("[...document.querySelectorAll('#dhelpsheet *')].filter(e=>getComputedStyle(e).color===%r)"
                   ".map(e=>e.className+':'+e.textContent)" % look["gold"]), ["deq:10"])
    click("dhelp-close")

    # ══ 動きを減らす設定: 動かさず、置いた後の形で止まっている ══
    ui.c.ws.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    try:
        ui.open(date=day(1).isoformat())
        click("dhelp", 0.4)
        ui.check("動きを減らす設定: 見本は動かない（動いているものが 0 個）", ui.ev("document.getAnimations().length"), 0)
        ui.check("動きを減らす設定: 置いた後の形で止まっている（記号は置かれ、枠と運ぶ記号は見えない）",
                 ui.ev("(function(){const o=s=>+getComputedStyle(document.querySelector(s)).opacity;"
                       "const x=s=>document.querySelector(s).getBoundingClientRect().left;"
                       "return [o('.hd1 .ds1 .dtok'),o('.hd1 .dzone'),o('.hd1 .dhot'),o('.hd1 .dghost'),o('.hd1 .dpick'),"
                       "x('.hd1 .dn0')<x('.hd1 .ds1')&&x('.hd1 .ds1')<x('.hd1 .dn1')]})()"), [1, 0, 0, 0, 1, True])
        ui.check("動きを減らす設定: 数字と記号のあいだに、空いた枠のぶんの隙間が残らない（8 − 7 と 5 2 が詰まる）",
                 ui.ev("(function(){const r=s=>document.querySelector(s).getBoundingClientRect();"
                       "const g=(a,b)=>Math.round((r(b).left-r(a).right)*10)/10;const m=2*parseFloat(getComputedStyle(document.querySelector('.hd1 .dn0')).marginLeft);"
                       "return [Math.abs(g('.hd1 .dn1','.hd1 .dn2')-m)<0.1,Math.abs(g('.hd1 .dn2','.hd1 .dn3')-m)<0.1]})()"), [True, True])
    finally:
        ui.c.ws.call("Emulation.setEmulatedMedia", {"features": []})
    ui.check_no_errors()
