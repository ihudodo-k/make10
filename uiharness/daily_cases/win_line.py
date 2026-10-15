# -*- coding: utf-8 -*-
"""正解したとき、式の下に細い線が引かれて消える。数字は動かず、光らない。「10」が式へ寄る動きは行き過ぎない
（D0.19。本編 8.4 の直しを写した。GAME-SPEC 8 章・DESIGN.md 4 章・DAILY-SPEC 13-5）。

線の規則（.ruleline・@keyframes ruledraw / rulefade）と ruleLine() は本編と同じ文字列（同期の照合の対象）。
本編のケース win_line と同じ見方に、デイリーだけの確かめ（結果の並びと重ならない・開き直しやギブアップでは引かない・
「10」と「正解」が式へ寄る動きが行き過ぎない）を足してある。

正解の演出の移り変わり: 8.2 までは数字が 13px 跳ねる → 8.3 は数字が順に光る → 8.4 は、式の下に細い線が中央から
左右へ引かれ、少し見せて消える（答えに下線を引く）。数字には何もしない。動きの曲線は「減速して止まる」だけ。

描画のたび（requestAnimationFrame）に、数字の位置と影、線の伸び（scaleX）と濃さ（opacity）を記録して、
- 正解の後、数字の位置が上下にも左右にも動かず、光らないこと
- 線が、正解が決まった瞬間に引かれ始め、戻らずに伸び切り、行き過ぎず、消えること
- 線の幅が式の幅と同じで、式のすぐ下にあること（式を縮めた長い式でも）
- 動きを減らす設定（prefers-reduced-motion）では、何も動かず、線も出ないこと
を見る。
"""
import datetime
import json
import re
import time

from uiharness import daily_ui as dui

NAME = "正解の線と、10 が寄る動き"

# 最後の 1 手の手前まで置く（ここでは正解にならない）
PREP = r"""(function(expr){
  const steps=[];let p=0;
  for(const tk of expr.split(' ')){let x=tk,fac=0;while(x.endsWith('!')){fac++;x=x.slice(0,-1)}
    if(/^[0-9]$/.test(x))p++;
    else if(x==='('){steps.push(['lp',p]);p++}else if(x===')'){steps.push(['rp',p]);p++}else if(x!==''){steps.push([x,p]);p++}
    for(let k=0;k<fac;k++){steps.push(['!',p]);p++}}
  clearAll();for(const s of steps.slice(0,-1))put(s[0],s[1]);render();
  window.__last=steps[steps.length-1];return steps.length})"""
# 最後の 1 手を置いて、描画のたびに、数字の位置・影・transform、演算子の影、線の伸びと濃さを記録する
FIRE = r"""(function(){
  put(__last[0],__last[1]);render();
  const t0=performance.now();window.__gl={on:true,f:[]};const line=document.getElementById('ruleline');
  const ro=document.querySelector('#play .readout');
  (function loop(){if(!__gl.on)return;
    const r=e=>{const b=e.getBoundingClientRect(),c=getComputedStyle(e);
      return [Math.round(b.left*100)/100,Math.round(b.top*100)/100,c.textShadow!=='none',c.transform,c.animationName]};
    const a=getComputedStyle(line);
    __gl.f.push([performance.now()-t0,[...document.querySelectorAll('#expr .num')].map(r),
      [...document.querySelectorAll('#expr .tok.op,#expr .tok.fac')].map(e=>getComputedStyle(e).textShadow!=='none'),
      document.getAnimations().filter(x=>!(x.animationName||'').startsWith('hd-')).length,
      a.transform==='none'?1:Math.round(new DOMMatrix(a.transform).a*1000)/1000,Math.round(+a.opacity*1000)/1000,a.animationName,
      (function(){const tf=getComputedStyle(ro).transform;return tf==='none'?0:Math.round(new DOMMatrix(tf).m42*100)/100})()]);
    requestAnimationFrame(loop)})();
  return scaleFor(tokensWidth())})()"""
STOP = "(function(){__gl.on=false;return __gl.f})()"
# 線の決まり（計算後の値）と、式の箱との位置の関係
LINE = r"""(function(){const l=document.getElementById('ruleline'),a=getComputedStyle(l),lr=l.getBoundingClientRect(),
  ex=document.getElementById('expr').getBoundingClientRect();
  const p=document.createElement('i');document.body.appendChild(p);p.style.color='color-mix(in srgb,var(--paper) 50%,transparent)';
  const want=getComputedStyle(p).color;p.remove();
  l.classList.add('on');const c2=getComputedStyle(l),dur=c2.animationDuration,count=c2.animationIterationCount,ease=c2.animationTimingFunction,delay=c2.animationDelay;l.classList.remove('on');
  return {w:lr.width,exw:ex.width,gap:lr.top-ex.bottom,h:a.height,center:(lr.left+lr.right)/2-(ex.left+ex.right)/2,color:a.backgroundColor===want,
    dur,count,ease,delay,pe:a.pointerEvents,cls:l.classList.contains('on'),inField:l.parentNode.id,hidden:l.getAttribute('aria-hidden'),scale:curExprScale}})()"""
RULES = r"""(function(){const out={kf:{},ease:getComputedStyle(document.documentElement).getPropertyValue('--ease').trim()};
  for(const sh of document.styleSheets){let rs;try{rs=sh.cssRules}catch(e){continue}
    for(const r of rs)if(r.type===CSSRule.KEYFRAMES_RULE)out.kf[r.name]=[...r.cssRules].map(k=>[k.keyText,k.style.transform,k.style.opacity,k.style.width])}
  return out})()"""


def analyze(frames, n_num):
    """(位置が動いた数字, transform が none でない数, 影が付いたコマの数, 置いた後のコマ)"""
    after = [f for f in frames if f[0] >= 60 and len(f[1]) == n_num]      # 置いた直後の組み直しが済んでから
    moved = []
    for i in range(n_num):
        xs = {f[1][i][0] for f in after}
        ys = {f[1][i][1] for f in after}
        if len(xs) > 1 or len(ys) > 1:
            moved.append((i, sorted(xs), sorted(ys)))
    not_none = sum(1 for f in after for x in f[1] if x[3] != "none")
    lit = sum(1 for f in after for x in f[1] if x[2])
    return moved, not_none, lit, after


def line_checks(ui, pre, frames):
    """線の動き: 正解が決まった瞬間に始まり、戻らずに伸び切り、行き過ぎず、消える"""
    sx = [(f[0], f[4], f[5], f[6]) for f in frames]
    grow = [x for x in sx if x[0] <= 520]
    ui.check(pre + "線は、正解が決まった瞬間に引かれ始める（最初のコマでは、まだ伸び切っていない）",
             [sx[0][3], sx[0][1] < 0.5, sx[0][2]], ["ruledraw, rulefade", True, 1])
    ui.check(pre + "線は、戻らずに伸び、0.5 秒で伸び切る。1 度も行き過ぎない（伸びは 0〜1 の中）",
             [all(b[1] >= a[1] - 0.002 for a, b in zip(grow, grow[1:])), max(x[1] for x in sx) <= 1.0005, min(x[1] for x in sx) >= 0,
              [x[1] for x in sx if 540 <= x[0] <= 620][:1]], [True, True, True, [1]])
    half = [x[1] for x in grow if x[0] >= 250][:1]
    ui.check(pre + "伸びている間は減速する（伸びる時間の半分で、7 割を超えている）", [len(half), (half or [0])[0] > 0.7], [1, True])
    ui.check(pre + "線は、0.84 秒までは濃いまま見えていて、そのあと薄くなり、1.35 秒で消える",
             [all(x[2] == 1 for x in sx if x[0] <= 800), any(0.05 < x[2] < 0.95 for x in sx if 880 <= x[0] <= 1300),
              [x[2] for x in sx if x[0] >= 1400][:1], sx[-1][2], frames[-1][3], sx[-1][3]], [True, True, [0], 0, 0, "none"])


# 読み出し行の寄る動きの決まり（計算後の値）と、式の縮小（盤の減速の曲線 --zoneEase）の曲線
RO = ("(function(){const a=getComputedStyle(document.querySelector('#play .readout')),b=getComputedStyle(document.getElementById('expr'));"
      "return [a.transitionProperty,a.transitionDuration,a.transitionTimingFunction,b.transitionTimingFunction,"
      "parseFloat(a.getPropertyValue('--roShift'))]})()")
LINE_OFF = ("(function(){const l=document.getElementById('ruleline');"
            "return [getComputedStyle(l).opacity,l.classList.contains('on'),"
            "document.getAnimations().filter(x=>(x.animationName||'').startsWith('rule')).length]})()")


def run(ui):
    start, rows = dui.page_data()
    src = dui.read(dui.DAILY_HTML)
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731
    n_num = 4

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def begin(no=1):
        ui.open(date=day(no).isoformat())
        ui.ev(PREP + "(%s)" % json.dumps(rows[no - 1]["sol"]))
        time.sleep(0.5)

    def solve_and_record(wait=1.6):
        scale = ui.ev(FIRE)
        time.sleep(wait)
        return scale, ui.ev(STOP)

    # ══ CSS の決まり ══
    begin()
    r = ui.ev(RULES)
    draw, fade = r["kf"].get("ruledraw", []), r["kf"].get("rulefade", [])
    ui.check("線の規則: 伸びる動きは transform（scaleX 0 → 1）だけ、消える動きは opacity（1 → 0）だけ。幅は動かさない",
             [[k[:2] for k in draw], [[k[0], k[2]] for k in fade], [k[3] for k in draw + fade], [k[2] for k in draw], [k[1] for k in fade]],
             [[["0%", "scaleX(0)"], ["100%", "scaleX(1)"]], [["0%", "1"], ["100%", "0"]], ["", "", "", ""], ["", ""], ["", ""]])
    ui.check("数字を光らせる規則（numglow）も、跳ねる規則（pop）も無い。行き過ぎて戻る曲線 --ease も無い",
             ["numglow" in r["kf"], "pop" in r["kf"], r["ease"], "var(--ease)" in src, ".num.shine{" in src], [False, False, "", False, False])
    curves = [tuple(float(x) for x in m.groups()) for m in
              re.finditer(r"cubic-bezier\(\s*([\d.-]+)\s*,\s*([\d.-]+)\s*,\s*([\d.-]+)\s*,\s*([\d.-]+)\s*\)", src[:src.index("</style>")])]
    ui.check("CSS の曲線は、どれも行き過ぎない（cubic-bezier の y が 0〜1 の中。1 つ以上ある）",
             [len(curves) >= 1, [c for c in curves if not (0 <= c[1] <= 1 and 0 <= c[3] <= 1)]], [True, []])
    ui.check("解く前は、線は見えない（濃さ 0・印の class なし）。線は式エリアの中にあり、読み上げから隠してある",
             ui.ev("(function(){const l=document.getElementById('ruleline');"
                   "return [getComputedStyle(l).opacity,l.classList.contains('on'),l.parentNode.id,l.getAttribute('aria-hidden')]})()"),
             ["0", False, "field", "true"])

    # ══ 正解: 線が引かれて消える。数字は動かず、光らない ══
    sol = rows[0]["sol"]
    scale, frames = solve_and_record()
    moved, not_none, lit, after = analyze(frames, n_num)
    ui.check("正解になり、結果の画面へ移る。式は縮めていない",
             [ui.text("eq") + "|" + ui.text("sub"), ui.ev("play.classList.contains('done')"), scale, len(after) >= 60, sol],
             ["10|正解", True, 1, True, "( 8 - 7 ) * 5 * 2"])
    ui.check("正解の後、数字の位置は上下にも左右にも動かない（transform も付かない。結果の並びが出ても同じ）。数字は 1 コマも光らない",
             [moved, not_none, lit, ui.ev("document.querySelectorAll('#expr .num.shine').length")], [[], 0, 0, 0])
    line_checks(ui, "", frames)
    g = ui.ev(LINE)
    ui.check("線は、式と同じ幅・式の下 8px・式の左右の中央。太さ 1px・白の 50%。伸びるのは 0.5 秒・減速（--zoneEase）、消えるのは 0.85 秒後から 0.5 秒。押す邪魔をしない",
             [abs(g["w"] - g["exw"]) < 0.6, abs(g["gap"] - 8) < 0.6, abs(g["center"]) < 0.6, g["h"], g["color"], g["dur"], g["count"], g["pe"],
              g["ease"], g["delay"]],
             [True, True, True, "1px", True, "0.5s, 0.5s", "1, 1", "none", "cubic-bezier(0.22, 0.72, 0.3, 1), ease-in-out", "0s, 0.85s"])
    ui.check("線は、結果の並び（時間・ヒント・連続日数）に重ならない（線のほうが上）",
             ui.ev("document.getElementById('ruleline').getBoundingClientRect().bottom<=document.querySelector('.rcols').getBoundingClientRect().top"), True)

    # ══ 「10」と「正解」が式へ寄る動き: 行き過ぎない ══
    ro = ui.ev(RO)
    ys = [f[7] for f in frames]
    final = ro[4]
    ui.check("読み出し行の寄る動きは、0.3 秒・減速して止まる曲線（式の縮小と同じ --zoneEase）",
             [ro[0], ro[1], ro[2], ro[2] == ro[3]], ["transform", "0.3s", "cubic-bezier(0.22, 0.72, 0.3, 1)", True])
    mid = sorted({y for y in ys if 0.02 < y < final - 0.02})
    ui.check("読み出し行は、式のほうへ（下へ）寄って止まる。途中のコマがあり、戻らずに進み、行き先を 1 度も通り過ぎない",
             [final > 1, abs(ys[-1] - final) < 0.02, len(mid) >= 4, all(b >= a - 0.02 for a, b in zip(ys, ys[1:])),
              max(ys) <= final + 0.02, min(ys) >= -0.02], [True, True, True, True, True, True])
    ui.check_no_errors("JS エラー 0")

    # ══ いちばん長い解答例の日でも、線は式の幅・式のすぐ下 ══
    longest = max(rows, key=lambda r: len(r["sol"]))
    begin(longest["no"])
    scale, frames = solve_and_record()
    g = ui.ev(LINE)
    ui.check("いちばん長い解答例（#%d %s・縮小率 %.3f）: 線は、式と同じ幅で、その下 8px・中央。画面からはみ出さない" % (longest["no"], longest["sol"], scale),
             [ui.text("eq"), abs(g["scale"] - scale) < 0.001, abs(g["w"] - g["exw"]) < 0.8, abs(g["gap"] - 8) < 0.8, abs(g["center"]) < 0.8,
              g["w"] <= ui.ev("document.getElementById('exprwrap').clientWidth") + 0.5], ["10", True, True, True, True, True])

    # ══ 式を縮める長い式: 線は、縮めた式と同じ幅・その下 8px（列には縮める日が無いので、長い式を直に組んで ruleLine() を呼ぶ）══
    begin()
    ui.ev(PREP + "(%s)" % json.dumps("( ( ( ( 8! )! )! )! )! + 7! + 5! + 2!"))
    ui.ev("put(__last[0],__last[1]);render()")
    time.sleep(0.6)
    ui.ev("ruleLine()")
    time.sleep(1.6)                     # 伸び切って消えてから測る（伸びている途中は、見えている幅が狭い）
    g = ui.ev(LINE)
    k = ui.ev("scaleFor(tokensWidth())")
    ui.check("長い式（縮小率 %.3f）: 式を縮めている。線は、縮めた式と同じ幅で、その下 8px・中央。画面からはみ出さない" % k,
             [k < 0.95, abs(g["scale"] - k) < 0.001, abs(g["w"] - g["exw"]) < 0.8, abs(g["gap"] - 8) < 0.8, abs(g["center"]) < 0.8,
              g["w"] <= ui.ev("document.getElementById('exprwrap').clientWidth") + 0.5], [True, True, True, True, True, True])

    # ══ 線を引くのは、解いた瞬間の 1 度だけ ══
    ui.open(now=at(1), tz="Asia/Tokyo", store={"v": 1, "days": {"1": {"r": "s", "t": 30, "h": 0, "sh": 0, "e": rows[0]["sol"], "sent": 1}}, "cur": None})
    time.sleep(0.4)
    ui.check("解いた後に開き直す: 結果の画面。線は引かない", [ui.ev("play.classList.contains('done')"), ui.ev(LINE_OFF)], [True, ["0", False, 0]])
    ui.open(date=day(1).isoformat())
    ui.ev("dgiveup.click();document.getElementById('gu-yes').click()")
    time.sleep(0.4)
    ui.check("ギブアップ: 解答例が盤に出るが、線は引かない", [ui.text("eq"), ui.ev(LINE_OFF)], ["ギブアップ", ["0", False, 0]])
    begin()
    ui.ev(FIRE)
    time.sleep(0.25)
    ui.ev("document.getElementById('dset').click()")
    time.sleep(0.3)
    ui.ev("document.getElementById('dset-close').click()")
    time.sleep(1.5)
    ui.ev(STOP)
    ui.check("線が引かれている途中で設定のシートを開いて閉じても、線は 1 度で終わる（印が外れ、濃さ 0）", ui.ev(LINE_OFF), ["0", False, 0])

    # ══ 動きを減らす設定: 何も動かず、線も出ない ══
    ui.media(reduce=True)
    try:
        begin()
        scale, frames = solve_and_record(1.2)
        moved, not_none, lit, after = analyze(frames, n_num)
        ro = ui.ev(RO)
        ys = sorted({f[7] for f in frames})
        ui.check("動きを減らす設定: 正解になる（金の「10」と「正解」は出る）",
                 [ui.text("eq") + "|" + ui.text("sub"), ui.ev("getComputedStyle(eq).color"), ui.ev("play.classList.contains('done')")],
                 ["10|正解", "rgb(220, 189, 110)", True])
        ui.check("動きを減らす設定: 数字は動かず、光らない。線は 1 コマも見えない。動いているアニメーションは 0",
                 [moved, not_none, lit, max(f[5] for f in frames), max(f[3] for f in after)], [[], 0, 0, 0, 0])
        ui.check("動きを減らす設定: 読み出し行は、途中のコマ無しで行き先に着く（寄る前か、寄った後のどちらかだけ）",
                 [[y for y in ys if 0.02 < y < ro[4] - 0.02], abs(ys[-1] - ro[4]) < 0.02], [[], True])
    finally:
        ui.media()
    ui.check_no_errors("動きを減らす設定: JS エラー 0")
