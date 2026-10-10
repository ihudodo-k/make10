# -*- coding: utf-8 -*-
"""吸着した枠が、ドラッグ中に震えない（8.1。GAME-SPEC 4-1）。

8.0 までの onMove() は、pointermove のたびに「全部の .hot を外す → tgt() で行き先を決める → 同じ枠に .hot を
付け直す」の順で動いていた。tgt() の中の elementFromPoint と getBoundingClientRect がスタイルの再計算を起こすので、
「.hot が外れた状態」が一瞬確定し、幅の遷移が縮む方向に始まっては戻る ―― これが動くたびに繰り返されて、
吸着して膨らんだ枠が細かく震えて見えた（スマホの Firefox で報告）。

ここでは、本物のマウスで枠に吸着させたまま、同じ枠の中で pointermove を 100 回送り、その間に
盤のどの要素の class も 1 回も変わらないこと（MutationObserver で数える）と、幅の遷移が 1 回も始まらないことを見る。
行き先が変わったときは今までどおり .hot が移ること、差し替えの相手（置いてある演算）でも同じであることも見る。
"""
import time

NAME = "吸着した枠が震えない"

STUB = """
window.__VIB=[];
Object.defineProperty(navigator,'vibrate',
  {value:function(x){__VIB.push(x);return true},configurable:true});
"""
# その要素を見張る。盤の中の class の変化と、その要素の幅の遷移の始まりを数える
WATCH = """(function(){
  const z=document.querySelector(%r);
  window.__HOT={n:0,tr:0,z};
  __HOT.ob=new MutationObserver(rs=>{__HOT.n+=rs.length});
  __HOT.ob.observe($('expr'),{attributes:true,attributeFilter:['class'],subtree:true});
  z.addEventListener('transitionrun',e=>{if(e.propertyName==='width')__HOT.tr++});
  __VIB.splice(0);
  return [z.classList.contains('hot'),lastHot===z]})()"""
# [class の変化の回数, 幅の遷移が始まった回数, まだ .hot か, lastHot がその要素か, .hot の数, 振動の回数]
READ = """(function(){
  __HOT.n+=__HOT.ob.takeRecords().length;
  return [__HOT.n,__HOT.tr,__HOT.z.classList.contains('hot'),lastHot===__HOT.z,
          document.querySelectorAll('.hot').length,__VIB.length]})()"""
TOKS = "T().map(x=>x.t==='num'?String(x.v):x.t==='op'?x.v:x.t==='fac'?'!':x.t==='lp'?'(':')').join(' ')"
HOTS = "[...document.querySelectorAll('.hot')].map(e=>e.classList.contains('zone')?'zone'+e.dataset.p:'tok')"
N = 100


def mouse(ui, typ, x, y):
    ui.c.ws.call("Input.dispatchMouseEvent",
                 {"type": typ, "x": x, "y": y, "button": "left",
                  "buttons": 1 if typ != "mouseReleased" else 0, "clickCount": 1})


def center(ui, sel):
    return ui.ev("(()=>{const b=document.querySelector(%r).getBoundingClientRect();"
                 "return [b.left+b.width/2,b.top+b.height/2]})()" % sel)


def glide(ui, x0, y0, x1, y1, steps=6):
    for i in range(1, steps + 1):
        mouse(ui, "mouseMoved", x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        time.sleep(0.03)
    time.sleep(0.4)                         # 膨らむ動きが終わるのを待つ


def wiggle(ui, sel, n=N):
    """その要素の中だけで、pointermove を n 回送る（中心から上下左右 3px 以内）"""
    x, y = center(ui, sel)
    for i in range(n):
        mouse(ui, "mouseMoved", x + (i % 7) - 3, y + (i * 3 % 7) - 3)
    time.sleep(0.15)


def steady(ui, pre):
    """ページを開いて問題画面にした後の、確かめの本体"""
    ui.ev(STUB)
    z1, z2 = ".zone[data-p='1']", ".zone[data-p='2']"
    x0, y0 = center(ui, '.chip[data-op="+"]')
    mouse(ui, "mousePressed", x0, y0)
    mouse(ui, "mouseMoved", x0, y0 - 6)
    time.sleep(0.45)                        # 枠が開くのを待つ
    x1, y1 = center(ui, z1)
    glide(ui, x0, y0 - 6, x1, y1)
    ui.check(pre + "枠に吸着している（.hot。lastHot もその枠）", ui.ev(WATCH % z1), [True, True])
    w0 = ui.ev("__HOT.z.getBoundingClientRect().width")
    ui.check(pre + "吸着した枠は、開いた枠より広い（膨らんでいる）",
             w0 > ui.ev("document.querySelector(%r).getBoundingClientRect().width" % z2) + 1, True)
    wiggle(ui, z1)
    ui.check(pre + "同じ枠の中で pointermove を %d 回: 盤の class は 1 回も変わらず、幅の遷移も始まらない。枠は .hot のまま・振動もしない" % N,
             ui.ev(READ), [0, 0, True, True, 1, 0])
    ui.check(pre + "その間、枠の幅は変わらない", abs(ui.ev("__HOT.z.getBoundingClientRect().width") - w0) < 0.01, True)

    # ほかの場所が .hot を外したら、次の pointermove で付け直す（lastHot と食い違わない）
    ui.ev("showZones(drag.op)")
    ui.check(pre + "枠を開き直すと .hot が外れ、lastHot も外れる", [ui.ev(HOTS), ui.ev("lastHot")], [[], None])
    mouse(ui, "mouseMoved", x1 + 1, y1)
    time.sleep(0.3)
    ui.check(pre + "次の pointermove で、同じ枠に .hot が付き直す", ui.ev(HOTS), ["zone1"])

    # 行き先が変わったら、今までどおり .hot が移る（振動は 1 回）
    ui.ev("__VIB.splice(0)")
    x2, y2 = center(ui, z2)
    glide(ui, x1, y1, x2, y2)
    ui.check(pre + "隣の枠へ動かすと、.hot は隣の枠だけに移る。振動は 1 回", [ui.ev(HOTS), ui.ev("__VIB.length")], [["zone2"], 1])
    fx, fy = ui.ev("(()=>{const r=$('field').getBoundingClientRect();return [r.left+r.width/2,r.top-60]})()")
    glide(ui, x2, y2, fx, fy)
    ui.check(pre + "式エリアの外へ出すと、.hot は 1 つも無く、lastHot も外れる", [ui.ev(HOTS), ui.ev("lastHot")], [[], None])
    x1, y1 = center(ui, z1)
    glide(ui, fx, fy, x1, y1)
    ui.check(pre + "戻すと、また吸着する", ui.ev(HOTS), ["zone1"])
    mouse(ui, "mouseReleased", x1, y1)
    time.sleep(0.5)
    toks = ui.ev(TOKS).split(" ")
    ui.check(pre + "離すと、その枠に置かれる（.hot は残らない）", [toks[1], ui.ev(HOTS)], ["+", []])

    # 差し替えの相手（置いてある演算）でも同じ
    x0, y0 = center(ui, '.chip[data-op="*"]')
    mouse(ui, "mousePressed", x0, y0)
    mouse(ui, "mouseMoved", x0, y0 - 6)
    time.sleep(0.45)
    tx, ty = center(ui, "#expr .tok.op")
    glide(ui, x0, y0 - 6, tx, ty)
    ui.check(pre + "置いてある演算の上: 差し替えの相手が .hot になる", [ui.ev(WATCH % "#expr .tok.op"), ui.ev(HOTS)], [[True, True], ["tok"]])
    wiggle(ui, "#expr .tok.op")
    ui.check(pre + "差し替えの相手の上で pointermove を %d 回: 盤の class は 1 回も変わらない" % N,
             ui.ev(READ)[0::2], [0, True, 1])
    mouse(ui, "mouseReleased", tx, ty)
    time.sleep(0.5)
    ui.check(pre + "離すと、演算が差し替わる", ui.ev(TOKS).split(" ")[1], "*")
    ui.check_no_errors(pre + "JS エラー 0")


def run(ui):
    ui.open({"ci": 0, "cleared": 0, "hintStock": 50})
    ui.click("m-course")
    time.sleep(0.3)
    steady(ui, "")
