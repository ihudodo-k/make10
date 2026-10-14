# -*- coding: utf-8 -*-
"""正解したとき、式の下に細い線が引かれて消える。数字は動かず、光らない（8.4。GAME-SPEC 8 章・DESIGN.md 4 章）。

正解の演出の移り変わり: 8.2 までは数字が 13px 跳ねる → 8.3 は数字が順に光る → 8.4 は、式の下に細い線が中央から
左右へ引かれ、少し見せて消える（答えに下線を引く）。数字には何もしない。動きの曲線は「減速して止まる」だけ。

描画のたび（requestAnimationFrame）に、数字の位置と影、線の伸び（scaleX）と濃さ（opacity）を記録して、
- 正解の後、数字の位置が上下にも左右にも動かず、光らないこと
- 線が、正解が決まった瞬間に引かれ始め、戻らずに伸び切り、行き過ぎず、消えること
- 線の幅が式の幅と同じで、式のすぐ下にあること（式を縮めた長い式でも）
- 動きを減らす設定（prefers-reduced-motion）では、何も動かず、線も出ないこと
を見る。
"""
import json
import os
import re
import time

NAME = "正解の線（数字は動かない）"

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
  (function loop(){if(!__gl.on)return;
    const r=e=>{const b=e.getBoundingClientRect(),c=getComputedStyle(e);
      return [Math.round(b.left*100)/100,Math.round(b.top*100)/100,c.textShadow!=='none',c.transform,c.animationName]};
    const a=getComputedStyle(line);
    __gl.f.push([performance.now()-t0,[...document.querySelectorAll('#expr .num')].map(r),
      [...document.querySelectorAll('#expr .tok.op,#expr .tok.fac')].map(e=>getComputedStyle(e).textShadow!=='none'),
      document.getAnimations().length,
      a.transform==='none'?1:Math.round(new DOMMatrix(a.transform).a*1000)/1000,Math.round(+a.opacity*1000)/1000,a.animationName]);
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


def run(ui):
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "docs", "index.html"),
               encoding="utf-8").read()
    picks = [(1, "COURSE[0]"),
             (2, "ALL().find(p=>p.d>=9&&p.d<=13&&p.rc==='N'&&p.sol.length<=13&&!p.sol.includes('('))"),
             (3, "ALL().find(p=>p.d>=14&&p.rc==='N'&&p.sol.length<=17)")]

    def start(pick):
        ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
        ui.ev('MODE="free";loadPuzzle(%s);go("play")' % pick)
        sol = ui.ev("cur.sol")
        ui.ev(PREP + "(%s)" % json.dumps(sol))
        time.sleep(0.5)
        return sol

    def solve_and_record(wait=1.6):
        scale = ui.ev(FIRE)
        time.sleep(wait)
        return scale, ui.ev(STOP)

    # ══ CSS の決まり ══
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
    ui.click("m-course")
    r = ui.ev(RULES)
    draw, fade = r["kf"].get("ruledraw", []), r["kf"].get("rulefade", [])       # 規則が無ければ空（下の項目が落ちる）
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

    # ══ 段階 1〜3: 線が引かれて消える。数字は動かず、光らない ══
    for lv, pick in picks:
        sol = start(pick)
        n_num = 4
        scale, frames = solve_and_record()
        moved, not_none, lit, after = analyze(frames, n_num)
        pre = "段階 %d（%s）: " % (lv, sol)
        ui.check(pre + "正解になり、演出の段階は %d。式は縮めていない" % lv,
                 [ui.ev("$('eq').textContent+'|'+$('sub').textContent"), ui.ev("hitLv"), scale, len(after) >= 60],
                 [ui.solved_text(), lv, 1, True])
        ui.check(pre + "正解の後、数字の位置は上下にも左右にも動かない（transform も付かない）。数字は 1 コマも光らない",
                 [moved, not_none, lit, ui.ev("document.querySelectorAll('#expr .num.shine').length")], [[], 0, 0, 0])
        line_checks(ui, pre, frames)
        g = ui.ev(LINE)
        ui.check(pre + "線は、式と同じ幅・式の下 8px・式の左右の中央。太さ 1px・白の 50%。伸びるのは 0.5 秒・減速（--zoneEase）、消えるのは 0.85 秒後から 0.5 秒。押す邪魔をしない",
                 [abs(g["w"] - g["exw"]) < 0.6, abs(g["gap"] - 8) < 0.6, abs(g["center"]) < 0.6, g["h"], g["color"], g["dur"], g["count"], g["pe"],
                  g["ease"], g["delay"]],
                 [True, True, True, "1px", True, "0.5s, 0.5s", "1, 1", "none", "cubic-bezier(0.22, 0.72, 0.3, 1), ease-in-out", "0s, 0.85s"])
        ops = [f[2] for f in after]
        n_ops = len(ops[-1])
        lit_ops = [any(f[i] for f in ops if len(f) == n_ops) for i in range(n_ops)]
        ui.check(pre + "演算子が光るのは段階 2 から（今までどおり）", lit_ops, [lv >= 2] * n_ops)
    ui.check_no_errors("JS エラー 0")

    # ══ 縮めた長い式でも、線は式の幅・式のすぐ下 ══
    sol = start("ALL().filter(p=>p.rc==='N').sort((a,b)=>b.sol.length-a.sol.length)[0]")
    scale, frames = solve_and_record()
    g = ui.ev(LINE)
    ui.check("長い式（%s）: 式を縮めている（縮小率 %.3f）。線は、縮めた式と同じ幅で、その下 8px・中央" % (sol, scale),
             [scale < 0.98, abs(g["scale"] - scale) < 0.001, abs(g["w"] - g["exw"]) < 0.8, abs(g["gap"] - 8) < 0.8, abs(g["center"]) < 0.8,
              ui.ev("$('eq').textContent")], [True, True, True, True, True, "10"])
    ui.check("長い式: 線は画面からはみ出さない",
             g["w"] <= ui.ev("document.getElementById('exprwrap').clientWidth") + 0.5, True)

    # ══ 1 度だけ: 正解の後に盤を崩して組み直しても、設定から戻っても、線は引き直さない ══
    start(picks[0][1])
    ui.ev(FIRE)
    time.sleep(1.6)
    ui.ev(STOP)
    ui.click("menu")
    ui.click("navback")
    time.sleep(0.4)
    ui.check("正解の後に設定を開いて戻っても、線は引き直さない（動いているアニメーションなし・濃さ 0）",
             ui.ev("[document.getAnimations().length,getComputedStyle(document.getElementById('ruleline')).opacity,"
                   "document.getElementById('ruleline').classList.contains('on')]"), [0, "0", False])
    ui.ev("render()")
    time.sleep(0.2)
    ui.check("正解の後に盤を描き直しても（render()）、線は引き直さない",
             ui.ev("[document.getAnimations().length,getComputedStyle(document.getElementById('ruleline')).opacity,"
                   "document.getElementById('ruleline').classList.contains('on')]"), [0, "0", False])
    ui.ev("loadPuzzle(COURSE[1])")
    time.sleep(0.3)
    ui.check("次の問題へ移ると、線は見えない", ui.ev("getComputedStyle(document.getElementById('ruleline')).opacity"), "0")

    # ══ 動きを減らす設定: 何も動かず、線も出ない ══
    ui.c.ws.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    try:
        for lv, pick in (picks[0], picks[2]):
            sol = start(pick)
            scale, frames = solve_and_record(1.2)
            moved, not_none, lit, after = analyze(frames, 4)
            pre = "動きを減らす設定・段階 %d: " % lv
            ui.check(pre + "正解になる（金の「10」と「正解」は出る）",
                     [ui.ev("$('eq').textContent+'|'+$('sub').textContent"), ui.ev("getComputedStyle($('eq')).color"), ui.ev("hitLv")],
                     ["10|正解", "rgb(220, 189, 110)", lv])
            ui.check(pre + "数字は動かず、光らない。演算子も光らない。線は 1 コマも見えない。動いているアニメーションは 0",
                     [moved, not_none, lit, sum(1 for f in after for x in f[2] if x), max(f[5] for f in frames), max(f[3] for f in after)],
                     [[], 0, 0, 0, 0, 0])
    finally:
        ui.c.ws.call("Emulation.setEmulatedMedia", {"features": []})
    ui.check_no_errors("動きを減らす設定: JS エラー 0")
