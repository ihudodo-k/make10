# -*- coding: utf-8 -*-
"""ヒントと共有（D0.4。DAILY-SPEC 8・9・13-2・13-4・16-4）。

共有の仕組み（`navigator.share`・クリップボード）は、ケースが差し替えて記録する。
ヒントの文と共有文は、列の全問について、Python の側で別に組んだものと突き合わせる。
"""
import datetime
import re

from uiharness import daily_ui as dui

NAME = "ヒントと共有"

TZ = "Asia/Tokyo"
URL = "https://make10.app/daily/"
SLATE = "rgb(85, 104, 138)"
GLYPH = {"+": "+", "-": "−", "*": "×", "/": "÷", "^": "^", "!": "!"}
SEEN = ("(function(){const e=document.querySelector(%r);if(!e)return false;const s=getComputedStyle(e);"
        "return s.display!=='none'&&s.visibility!=='hidden'&&e.offsetHeight>0})()")
# 共有の仕組みの差し替え。__SH = 共有画面に渡された中身、__CP = コピーされた文字
STUB = r"""
window.__SH=[];window.__CP=[];
(function(mode,clip){
  const sh=mode==="none"?undefined:function(d){__SH.push(d);
    if(mode==="ok")return Promise.resolve();
    const e=new Error(mode);e.name=mode==="abort"?"AbortError":"NotAllowedError";return Promise.reject(e)};
  Object.defineProperty(navigator,"share",{value:sh,configurable:true});
  Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:function(s){__CP.push(s);
    return clip?Promise.resolve():Promise.reject(new Error("no clipboard"))}}});
})(%s,%s);
"""
BOX = "(function(){const b=document.getElementById('hintbox');return b.classList.contains('show')?b.textContent:null})()"
BTN = ("(function(){const h=document.getElementById('hint');return [document.getElementById('hintstock').textContent,"
       "h.getAttribute('aria-disabled'),document.getElementById('hintlabel').textContent]})()")


def kinds(sol):
    out = []
    for c in sol:
        if c in "+-*/^!" and c not in out:
            out.append(c)
    return out


def hint_text(sol, n):
    """n 回目のヒントに見える文字（DAILY-SPEC 13-4・16-4。ページの関数は使わない）"""
    k = kinds(sol)
    if n == 1:
        return "使う演算：" + GLYPH[k[0]]
    paren = "括弧：使う" if "(" in sol else "括弧：使わない"
    head = "使う演算：%s %s" % (GLYPH[k[0]], GLYPH[k[1]]) if len(k) > 1 else "ほかの演算は使わない"
    return head + "　" + paren


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def stub(mode="ok", clip=True):
        ui.ev(STUB % ('"%s"' % mode, "true" if clip else "false"))

    def click(el_id, wait=0.25):
        ui.ev("document.getElementById(%r).click()" % el_id)
        import time
        time.sleep(wait)

    two = next(r for r in rows[:60] if len(kinds(r["sol"])) >= 2 and "(" in r["sol"])
    no = two["no"]

    # ══ 全問のヒントの文（1 回目・2 回目）を、別に組んだものと突き合わせる ══
    ui.open(date=day(1).isoformat())
    got = ui.ev("(function(){const d=document.createElement('div');return DAILY_DAYS.map(p=>[1,2].map(n=>{"
                "d.innerHTML=hintHtml(p,n);return d.textContent}))})()")
    bad = [(r["no"], g, [hint_text(r["sol"], 1), hint_text(r["sol"], 2)])
           for r, g in zip(rows, got) if g != [hint_text(r["sol"], 1), hint_text(r["sol"], 2)]]
    ui.check("全 %d 問: ヒントの文（1 回目・2 回目）が、解答例から組んだ文と同じ" % len(rows), bad[:3], [])
    # 確かめが空振りしていないこと（列に、文の型が両方ある）
    ui.check("列に、演算が 1 種類だけの問題と、2 種類以上の問題の両方がある",
             [any(len(kinds(r["sol"])) == 1 for r in rows), any(len(kinds(r["sol"])) > 1 for r in rows)],
             [True, True])
    ui.check("列に、括弧を使う問題と、使わない問題の両方がある",
             [any("(" in r["sol"] for r in rows), any("(" not in r["sol"] for r in rows)], [True, True])
    # 太字は、記号と「使う／使わない」だけ
    ui.check("ヒントの文の太字は、記号と「使う／使わない」だけ",
             ui.ev("(function(){const d=document.createElement('div');d.innerHTML=hintHtml(DAILY_DAYS[%d],2);"
                   "return [...d.querySelectorAll('code')].map(e=>e.textContent)})()" % (no - 1)),
             ["%s %s" % (GLYPH[kinds(two["sol"])[0]], GLYPH[kinds(two["sol"])[1]]), "使う"])

    # ══ 全問の共有文に、答えも演算の記号も入らない ══
    texts = ui.ev("DAILY_DAYS.map(p=>[shareTextOf(p.no),"
                  "shareTextOf(p.no,{r:'s',t:102,h:2,sh:3},7),shareTextOf(p.no,{r:'g',t:null,h:1,sh:1},0)])")
    bad = []
    for r, t3 in zip(rows, texts):
        want = ["Make10 #%d 解ける？" % r["no"], "Make10 #%d ⏱1:42 💡2 🔥7" % r["no"],
                "Make10 #%d ギブアップ" % r["no"]]
        leak = [t for t in t3 if re.search(r"[+\-−×÷*/^!()（）]", t) or r["id"] in t.replace("#%d" % r["no"], "")
                or any(s in t for s in r["sols"])]
        if t3 != want or leak:
            bad.append((r["no"], t3))
    ui.check("全 %d 問: 共有文 3 種類が決まった文で、答え・4 桁・演算の記号・括弧が入らない" % len(rows), bad[:3], [])

    # ══ もらう前 → 知らせ → 共有 → 1 回目 → 2 回目 ══
    ui.open(now=at(no), tz=TZ, perf=True)
    stub("ok")
    ui.check("丸ボタン: 最初は数字が無く、押せる", ui.ev(BTN), ["", None, "ヒント（残り 0 回）"])
    ui.check("ヒントの丸ボタンは右下（「全部消す」と同じ高さ・同じ大きさ）。共有ボタンは統計の真下 8px",
             ui.ev("(function(){const h=hint.getBoundingClientRect(),c=clear.getBoundingClientRect(),"
                   "s=share.getBoundingClientRect(),d=dstats.getBoundingClientRect();"
                   "return [h.top-c.top,h.width-c.width,h.left>c.right,s.left-d.left,s.top-d.bottom,s.width-d.width]})()"),
             [0, 0, True, 0, 8, 0])
    click("hint")
    ui.check("もらう前に押す: 知らせと、共有の入口・閉じる",
             [ui.ev(BOX), ui.ev("[...document.querySelectorAll('#hintbox button')].map(b=>b.getAttribute('aria-label'))")],
             ["友達に出題するとヒントがもらえます", ["共有する", "閉じる"]])
    ui.check("箱は高さ 58px で、丸ボタンの 8px 上。式に重ならない",
             ui.ev("(function(){const g=hintbox.getBoundingClientRect(),f=document.querySelector('.foot')"
                   ".getBoundingClientRect(),e=expr.getBoundingClientRect();"
                   "return [g.height,Math.round((f.top-g.bottom)*10)/10,g.top>=e.bottom]})()"), [58, 8, True])
    ui.check("知らせを出しただけでは、何も数えない", [ui.ev("hintUsed"), ui.ev("shareCount"), ui.saved()], [0, 0, None])
    click("hint-close")
    ui.check("× で閉じる", ui.ev(BOX), None)
    click("hint")
    click("hint")
    ui.check("知らせを出している間にもう一度押すと閉じる", ui.ev(BOX), None)
    click("hint")
    click("hint-share")
    ui.check("知らせの箱から共有: 共有画面に、解く前の文と URL が渡る",
             ui.ev("__SH"), [{"text": "Make10 #%d 解ける？" % no, "url": URL}])
    ui.check("共有した直後に、そのまま 1 回目のヒントが出る", ui.ev(BOX), hint_text(two["sol"], 1))
    ui.check("1 回目を見た: 残りは無い。記録に、使った 1・共有 1",
             [ui.ev(BTN), ui.saved()["cur"]["h"], ui.saved()["cur"]["sh"]],
             [["", None, "ヒント（残り 0 回）"], 1, 1])
    click("hint-close")
    click("hint")
    ui.check("閉じてから押す: 1 回目をもう一度（使わない）", [ui.ev(BOX), ui.ev("hintUsed")], [hint_text(two["sol"], 1), 1])
    click("hint")
    ui.check("1 回目を出している間に押す（残りなし）: 知らせに替わる",
             ui.ev(BOX), "友達に出題するとヒントがもらえます")
    click("share")
    ui.check("上のバーの共有ボタンで共有: 知らせは閉じ、丸ボタンの数字が 1 になる（ヒントは出さない）",
             [ui.ev(BOX), ui.ev(BTN), ui.ev("__SH.length")], [None, ["1", None, "ヒント（残り 1 回）"], 2])
    click("hint")
    ui.check("残りがあっても、閉じた状態で押すと、まず見たヒント（1 回目）をもう一度", [ui.ev(BOX), ui.ev("hintUsed")],
             [hint_text(two["sol"], 1), 1])
    click("hint")
    ui.check("開いている間に押す: 2 回目へ進む", [ui.ev(BOX), ui.ev("hintUsed")], [hint_text(two["sol"], 2), 2])
    ui.check("2 回目を出している間: 丸ボタンは無効の見た目（灰色・半分の濃さ）で、数字は無い",
             [ui.ev(BTN), ui.ev("getComputedStyle(hint).color"), ui.ev("getComputedStyle(hint).opacity")],
             [["", "true", "これ以上のヒントはありません"], SLATE, "0.5"])
    click("hint")
    ui.check("無効の見た目の間は、押しても何も起きない", [ui.ev(BOX), ui.ev("hintUsed")], [hint_text(two["sol"], 2), 2])
    click("hint-close")
    ui.check("閉じると、丸ボタンは普通の見た目に戻る", [ui.ev(BTN)[1], ui.ev("getComputedStyle(hint).opacity")], [None, "1"])
    click("hint")
    ui.check("閉じてから押す: 2 回目をもう一度（読み返せる）", [ui.ev(BOX), ui.ev("hintUsed")], [hint_text(two["sol"], 2), 2])
    click("hint-close")

    # ══ 3 回目以降の共有ではもらえない ══
    click("share")
    click("share")
    ui.check("3 回目・4 回目の共有: 共有の回数は数えるが、ヒントは増えない",
             [ui.ev("shareCount"), ui.ev("hintLeft()"), ui.ev(BTN)[0], ui.saved()["cur"]["sh"]], [4, 0, "", 4])
    click("hint")
    ui.check("そのあと押しても、出るのは 2 回目（3 回目は無い）", ui.ev(BOX), hint_text(two["sol"], 2))
    ui.check_no_errors("ヒント: JS エラー 0")

    # ══ 開き直しても回数が残る ══
    ui.open(now=at(no, 12), tz=TZ, perf=True, store="keep")
    stub("ok")
    ui.check("開き直す: 使った回数と共有の回数が残る。箱は閉じている",
             [ui.ev("hintUsed"), ui.ev("shareCount"), ui.ev(BOX), ui.ev(BTN)[0]], [2, 4, None, ""])
    click("hint")
    ui.check("開き直してから押す: 2 回目を読み返せる", ui.ev(BOX), hint_text(two["sol"], 2))
    ui.tick(61000)
    got = ui.solve(two["sol"], wait=0.9)
    ui.check("解くと、ヒントの箱は閉じる", [got, ui.ev(BOX)], ["10|正解", None])
    ui.check("結果の 3 列のヒントは 2 回", ui.ev("[document.getElementById('r-hints').textContent,"
                                                   "document.getElementById('r-hints-u').textContent]"), ["2", "回"])
    rec = ui.saved()["days"][str(no)]
    ui.check("1 日ぶんの記録に、使ったヒント 2・共有 4", [rec["h"], rec["sh"], ui.saved()["cur"]], [2, 4, None])
    # 解いた後の共有（上のバーと「結果を共有」）
    click("rshare")
    want = "Make10 #%d ⏱%s 💡2 🔥1" % (no, "%d:%02d" % (rec["t"] // 60, rec["t"] % 60))
    ui.check("「結果を共有」: 解いた後の文（時間・ヒント・連続日数）と URL", ui.ev("__SH[__SH.length-1]"),
             {"text": want, "url": URL})
    click("share")
    ui.check("解いた後は、上のバーの共有ボタンも同じ文", ui.ev("__SH[__SH.length-1]"), {"text": want, "url": URL})
    ui.check("解いた後の共有も、共有の回数に数える（ヒントの回数は変わらない）",
             [ui.saved()["days"][str(no)]["sh"], ui.saved()["days"][str(no)]["h"]], [6, 2])
    ui.open(now=at(no, 20), tz=TZ, store="keep")
    ui.check("解いた後に開き直す: ヒント 2 回のまま", ui.text("r-hints"), "2")

    # ══ 共有を 2 回してから押す（数字 2 → 1 → 無し）══
    ui.open(now=at(no), tz=TZ)
    stub("ok")
    click("share")
    click("share")
    ui.check("先に 2 回共有: 丸ボタンの数字は 2", ui.ev(BTN), ["2", None, "ヒント（残り 2 回）"])
    click("hint")
    ui.check("押すと 1 回目、数字は 1", [ui.ev(BOX), ui.ev(BTN)[0]], [hint_text(two["sol"], 1), "1"])
    click("hint")
    ui.check("もう一度押すと 2 回目、数字は無し", [ui.ev(BOX), ui.ev(BTN)[0]], [hint_text(two["sol"], 2), ""])

    # ══ 演算が 1 種類だけの問題 ══
    one = next(r for r in rows if len(kinds(r["sol"])) == 1)
    ui.open(now=at(one["no"]), tz=TZ)
    stub("ok")
    click("share")
    click("share")
    click("hint")
    click("hint")
    ui.check("演算が 1 種類だけの問題の 2 回目（#%d %s）" % (one["no"], one["sol"]), ui.ev(BOX),
             "ほかの演算は使わない　括弧：" + ("使う" if "(" in one["sol"] else "使わない"))
    ui.check("この文は 1 行で箱に収まる",
             ui.ev("(function(){const b=document.querySelector('#hintbox .hbody');"
                   "return b.scrollWidth<=b.clientWidth+0.5&&hintbox.getBoundingClientRect().height===58})()"), True)

    # ══ ギブアップの確認とヒントの箱は、同時に出ない ══
    click("dgiveup")
    ui.check("ギブアップの入口を押すと、ヒントの箱は閉じる", [ui.ev(BOX), ui.ev(SEEN % "#gubox")], [None, True])
    click("hint")
    ui.check("ヒントを押すと、ギブアップの確認は消える", [ui.ev(BOX) is not None, ui.ev(SEEN % "#gubox")], [True, False])
    click("dgiveup")
    click("gu-yes")
    click("share")
    ui.check("ギブアップの後の共有文", ui.ev("__SH[__SH.length-1]"),
             {"text": "Make10 #%d ギブアップ" % one["no"], "url": URL})
    ui.check("ギブアップの記録にも、使ったヒントと共有の回数が入る",
             [ui.saved()["days"][str(one["no"])]["h"], ui.saved()["days"][str(one["no"])]["sh"]], [2, 3])

    # ══ 共有画面が無い・閉じただけ・拒まれた ══
    TOAST = ("(function(){const e=document.getElementById('toast');"
             "return e&&e.classList.contains('show')?e.textContent:null})()")
    # 無い → コピー。もらえる
    ui.open(now=at(no), tz=TZ)
    stub("none")
    click("share")
    ui.check("共有画面が無い: 文と URL をコピーして「コピーしました」。ヒントはもらえる",
             [ui.ev("__CP"), ui.ev(TOAST), ui.ev("shareCount"), ui.ev(BTN)[0]],
             [["Make10 #%d 解ける？\n%s" % (no, URL)], "コピーしました", 1, "1"])
    ui.check("解く前のトーストは、丸ボタン 2 つの間（重ならない）",
             ui.ev("(function(){const t=document.getElementById('toast').getBoundingClientRect(),c=clear.getBoundingClientRect(),"
                   "h=hint.getBoundingClientRect();return [t.left>=c.right,t.right<=h.left,"
                   "Math.abs((t.top+t.bottom)/2-(c.top+c.bottom)/2)<1]})()"), [True, True, True])
    # 共有画面を開いて閉じただけ → もらえる。コピーもしない
    ui.open(now=at(no), tz=TZ)
    stub("abort")
    click("share")
    ui.check("共有画面を閉じただけ: もらえる（送ったかは確かめない）。コピーもトーストも無い",
             [ui.ev("__SH.length"), ui.ev("__CP"), ui.ev(TOAST), ui.ev("shareCount")], [1, [], None, 1])
    # 拒まれた → コピーに切り替え
    ui.open(now=at(no), tz=TZ)
    stub("denied")
    click("share")
    ui.check("共有が拒まれた: コピーに切り替えて「コピーしました」。もらえる",
             [ui.ev("__SH.length"), ui.ev("__CP").__len__(), ui.ev(TOAST), ui.ev("shareCount")],
             [1, 1, "コピーしました", 1])
    # 無くて、コピーもできない → もらえない
    ui.open(now=at(no), tz=TZ)
    stub("none", clip=False)
    click("hint")
    click("hint-share")
    ui.check("共有画面が無く、コピーもできない: 「コピーできません」。もらえない（知らせのまま）",
             [ui.ev(TOAST), ui.ev("shareCount"), ui.ev(BOX), ui.saved()],
             ["コピーできません", 0, "友達に出題するとヒントがもらえます", None])
    # 解いた後のトーストは、版の行のすぐ上
    ui.open(now=at(no), tz=TZ, perf=True)
    stub("none")
    ui.tick(3000)
    ui.solve(two["sol"], wait=0.9)
    click("rshare")
    ui.check("解いた後のトースト: 「コピーしました」が版の行のすぐ上に出る",
             [ui.ev(TOAST), ui.ev("(function(){const t=document.getElementById('toast').getBoundingClientRect(),v=dfoot.getBoundingClientRect();"
                                  "return [Math.round(v.top-t.bottom),t.left>=0&&t.right<=innerWidth]})()")],
             ["コピーしました", [8, True]])
    ui.check("コピーされるのは、解いた後の文と URL",
             ui.ev("__CP[0]"), "Make10 #%d ⏱0:03 💡0 🔥1\n%s" % (no, URL))
    ui.check_no_errors("共有: JS エラー 0")

    # ══ ?date= では保存しない ══
    ui.open(date=day(no).isoformat())
    stub("ok")
    click("share")
    click("hint")
    ui.check("?date=: ヒントも共有も動く", [ui.ev(BOX), ui.ev("shareCount"), ui.ev("hintUsed")],
             [hint_text(two["sol"], 1), 1, 1])
    ui.visibility("hidden")
    ui.check("?date=: 回数も何も保存しない", ui.saved(), None)
    ui.open(tz=None)
