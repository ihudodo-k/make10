# -*- coding: utf-8 -*-
"""正解したとき、数字は動かず、左から順に一瞬ほのかに光る。「10」が式へ寄る動きは行き過ぎない
（D0.18。本編 8.3 の直しを写した。GAME-SPEC 8 章・DESIGN.md 4 章・DAILY-SPEC 13-5）。

数字の規則（@keyframes numglow・.num.shine）は本編と同じ文字列（同期の照合の対象）。本編のケース win_glow と同じ見方で、
描画のたび（requestAnimationFrame）に数字の位置と影を記録して、
- 正解の後、数字の位置が上下にも左右にも動かないこと
- 光が左から順に付くこと（間隔は約 0.07 秒）。終わったら消えること
- 動きを減らす設定（prefers-reduced-motion）では、何も動かず、光らないこと
を見る。デイリーだけの確かめとして、
- 解いた後に「10」と「正解」（読み出し行）が式へ寄る動きが、行き過ぎないこと（減速して止まる曲線）
も見る。
"""
import json
import re
import time

from uiharness import daily_ui as dui

NAME = "正解の光と、10 が寄る動き"

PREP = r"""(function(expr){
  const steps=[];let p=0;
  for(const tk of expr.split(' ')){let x=tk,fac=0;while(x.endsWith('!')){fac++;x=x.slice(0,-1)}
    if(/^[0-9]$/.test(x))p++;
    else if(x==='('){steps.push(['lp',p]);p++}else if(x===')'){steps.push(['rp',p]);p++}else if(x!==''){steps.push([x,p]);p++}
    for(let k=0;k<fac;k++){steps.push(['!',p]);p++}}
  clearAll();for(const s of steps.slice(0,-1))put(s[0],s[1]);render();
  window.__last=steps[steps.length-1];return steps.length})"""
# 最後の 1 手を置いて、描画のたびに、数字の位置・影・transform と、読み出し行の寄った量（translateY）を記録する
FIRE = r"""(function(){
  put(__last[0],__last[1]);render();
  const t0=performance.now();window.__gl={on:true,f:[]};
  const ro=document.querySelector('#play .readout');
  (function loop(){if(!__gl.on)return;
    const r=e=>{const b=e.getBoundingClientRect(),c=getComputedStyle(e);
      return [Math.round(b.left*100)/100,Math.round(b.top*100)/100,c.textShadow!=='none',c.transform,c.animationName]};
    const tf=getComputedStyle(ro).transform;
    __gl.f.push([performance.now()-t0,[...document.querySelectorAll('#expr .num')].map(r),
      tf==='none'?0:Math.round(new DOMMatrix(tf).m42*100)/100,
      document.getAnimations().filter(a=>!(a.animationName||'').startsWith('hd-')).length]);
    requestAnimationFrame(loop)})();
  return curExprScale})()"""
STOP = "(function(){__gl.on=false;return __gl.f})()"
RULES = r"""(function(){const out={kf:{},ease:getComputedStyle(document.documentElement).getPropertyValue('--ease').trim()};
  for(const sh of document.styleSheets){let rs;try{rs=sh.cssRules}catch(e){continue}
    for(const r of rs)if(r.type===CSSRule.KEYFRAMES_RULE)out.kf[r.name]=[...r.cssRules].map(k=>[k.keyText,k.style.textShadow,k.style.transform])}
  const probe=cls=>{const e=document.createElement('div');e.className=cls;document.getElementById('expr').appendChild(e);
    const c=getComputedStyle(e),v=[c.animationName,c.animationDuration,c.animationTimingFunction,c.animationIterationCount];e.remove();return v};
  out.num=probe('num shine');out.tok=probe('tok op shine');return out})()"""
# 読み出し行の寄る動きの決まり（計算後の値）と、式の縮小（盤の減速の曲線 --zoneEase）の曲線
RO = ("(function(){const a=getComputedStyle(document.querySelector('#play .readout')),b=getComputedStyle(document.getElementById('expr'));"
      "return [a.transitionProperty,a.transitionDuration,a.transitionTimingFunction,b.transitionTimingFunction,"
      "parseFloat(getComputedStyle(document.querySelector('#play .readout')).getPropertyValue('--roShift'))]})()")


def analyze(frames, n_num):
    after = [f for f in frames if f[0] >= 60 and len(f[1]) == n_num]
    moved = []
    for i in range(n_num):
        xs = {f[1][i][0] for f in after}
        ys = {f[1][i][1] for f in after}
        if len(xs) > 1 or len(ys) > 1:
            moved.append((i, sorted(xs), sorted(ys)))
    first = []
    for i in range(n_num):
        ts = [f[0] for f in after if f[1][i][2]]
        first.append(round(ts[0]) if ts else None)
    not_none = sum(1 for f in after for x in f[1] if x[3] != "none")
    lit = sum(1 for f in after for x in f[1] if x[2])
    return moved, first, not_none, lit, after


def run(ui):
    start, rows = dui.page_data()
    src = dui.read(dui.DAILY_HTML)
    sol = rows[0]["sol"]
    n_num = 4

    def begin():
        ui.open(date=start.isoformat())
        ui.ev(PREP + "(%s)" % json.dumps(sol))
        time.sleep(0.5)

    def solve_and_record(wait=1.3):
        scale = ui.ev(FIRE)
        time.sleep(wait)
        return scale, ui.ev(STOP)

    # ══ CSS の決まり ══
    begin()
    r = ui.ev(RULES)
    ng = r["kf"].get("numglow", [])
    ui.check("数字の光の規則: 影だけを変える（位置は変えない）。山の影は、演算子の光（glow）の山と同じ値",
             [[k[0] for k in ng], [k[2] for k in ng],
              [k[1] for k in ng if k[0] == "50%"] == [k[1] for k in r["kf"].get("glow", []) if k[0] == "50%"],
              ([k[1] for k in ng if k[0] == "50%"] or [""])[0] not in ("", "none")],
             [["0%, 100%", "50%"], ["", ""], True, True])
    ui.check("数字の光の長さ・曲線・回数は、演算子の光（.tok.shine）と同じ（0.5 秒・1 回）",
             [r["num"][0], r["num"][1:], r["tok"][0]], ["numglow", r["tok"][1:], "glow"])
    ui.check("跳ねる動き（pop）の規則は無い。行き過ぎて戻る曲線 --ease も無い",
             ["pop" in r["kf"], r["ease"], "var(--ease)" in src, "--ease:" in src], [False, "", False, False])
    curves = [tuple(float(x) for x in m.groups()) for m in
              re.finditer(r"cubic-bezier\(\s*([\d.-]+)\s*,\s*([\d.-]+)\s*,\s*([\d.-]+)\s*,\s*([\d.-]+)\s*\)", src[:src.index("</style>")])]
    ui.check("CSS の曲線は、どれも行き過ぎない（cubic-bezier の y が 0〜1 の中。1 つ以上ある）",
             [len(curves) >= 1, [c for c in curves if not (0 <= c[1] <= 1 and 0 <= c[3] <= 1)]], [True, []])

    # ══ 正解: 数字は動かず、左から順に光る ══
    scale, frames = solve_and_record()
    moved, first, not_none, lit, after = analyze(frames, n_num)
    ui.check("正解になり、結果の画面へ移る。式は縮めていない（位置を素直に比べられる）",
             [ui.text("eq") + "|" + ui.text("sub"), ui.ev("play.classList.contains('done')"), scale, len(after) >= 40, sol],
             ["10|正解", True, 1, True, "( 8 - 7 ) * 5 * 2"])
    ui.check("正解の後、数字の位置は上下にも左右にも動かない（transform も付かない。結果の並びが出ても同じ）", [moved, not_none], [[], 0])
    got = [x for x in first if x is not None]
    ui.check("数字は 4 つとも光り、左から順に付く", [len(got), got == sorted(got), len(set(got)) >= 3], [n_num, True, True])
    gaps = [b - a for a, b in zip(first, first[1:])] if len(got) == n_num else []
    ui.check("光り始めは置いてから約 0.26 秒後。隣との間隔は約 0.07 秒（描画の刻みぶんの幅を見る）",
             [200 <= (first[0] or 0) <= 340, len(gaps) == n_num - 1 and all(30 <= g <= 115 for g in gaps), 150 <= sum(gaps) <= 270],
             [True, True, True])
    ui.check("光は 0.5 秒で消える（1.3 秒後には、影も、動いているアニメーションも無い）",
             [any(x[2] for x in after[-1][1]), after[-1][3], ui.ev("document.querySelectorAll('#expr .num.shine').length")],
             [False, 0, n_num])

    # ══ 「10」と「正解」が式へ寄る動き: 行き過ぎない ══
    ro = ui.ev(RO)
    ys = [f[2] for f in frames]
    final = ro[4]
    ui.check("読み出し行の寄る動きは、0.3 秒・減速して止まる曲線（式の縮小と同じ --zoneEase）",
             [ro[0], ro[1], ro[2], ro[2] == ro[3]], ["transform", "0.3s", "cubic-bezier(0.22, 0.72, 0.3, 1)", True])
    ui.check("読み出し行は、式のほうへ（下へ）寄って止まる。寄る量は 1px より大きい", [final > 1, abs(ys[-1] - final) < 0.02], [True, True])
    mid = sorted({y for y in ys if 0.02 < y < final - 0.02})
    ui.check("寄る動きは、途中のコマがある（一瞬で飛ばない）。戻らずに進み、行き先を 1 度も通り過ぎない",
             [len(mid) >= 4, all(b >= a - 0.02 for a, b in zip(ys, ys[1:])), max(ys) <= final + 0.02, min(ys) >= -0.02],
             [True, True, True, True])
    ui.check_no_errors("JS エラー 0")

    # ══ 動きを減らす設定: 何も動かず、光らない ══
    ui.c.ws.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]})
    try:
        begin()
        scale, frames = solve_and_record()
        moved, first, not_none, lit, after = analyze(frames, n_num)
        ro = ui.ev(RO)
        ys = sorted({f[2] for f in frames})
        ui.check("動きを減らす設定: 正解になる（金の「10」と「正解」は出る）",
                 [ui.text("eq") + "|" + ui.text("sub"), ui.ev("getComputedStyle(eq).color"), ui.ev("play.classList.contains('done')")],
                 ["10|正解", "rgb(227, 193, 111)", True])
        ui.check("動きを減らす設定: 数字は動かず、1 コマも光らない。動いているアニメーションは 0",
                 [moved, not_none, lit, max(f[3] for f in after)], [[], 0, 0, 0])
        ui.check("動きを減らす設定: 読み出し行は、途中のコマ無しで行き先に着く（寄る前か、寄った後のどちらかだけ）",
                 [[y for y in ys if 0.02 < y < ro[4] - 0.02], abs(ys[-1] - ro[4]) < 0.02], [[], True])
    finally:
        ui.c.ws.call("Emulation.setEmulatedMedia", {"features": []})
    ui.check_no_errors("動きを減らす設定: JS エラー 0")
