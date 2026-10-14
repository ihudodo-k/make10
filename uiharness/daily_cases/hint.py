# -*- coding: utf-8 -*-
"""ヒントと共有（D0.4。DAILY-SPEC 8・9・13-2・13-4・16-4）。

共有の仕組み（`navigator.share`・クリップボード）は、ケースが差し替えて記録する。
ヒントの文と共有文は、列の全問について、Python の側で別に組んだものと突き合わせる。
"""
import datetime
import json
import re
import time

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
window.__SH=[];window.__CP=[];window.__MQ=[];
(function(mode,clip,pc){
  if(!window.__realMM)window.__realMM=window.matchMedia.bind(window);
  window.matchMedia=function(q){
    if(/pointer|hover/.test(q)){__MQ.push(q);return {matches:pc,media:q}}
    return window.__realMM(q)};
  const sh=mode==="none"?undefined:function(d){__SH.push(d);
    if(mode==="ok")return Promise.resolve();
    const e=new Error(mode);e.name=mode==="abort"?"AbortError":"NotAllowedError";return Promise.reject(e)};
  Object.defineProperty(navigator,"share",{value:sh,configurable:true});
  Object.defineProperty(navigator,"clipboard",{configurable:true,value:{writeText:function(s){__CP.push(s);
    return clip?Promise.resolve():Promise.reject(new Error("no clipboard"))}}});
})(%s,%s,%s);
"""
BOX = "(function(){const b=document.getElementById('hintbox');return b.classList.contains('show')?b.textContent:null})()"
TOAST_JS = ("(function(){const e=document.getElementById('toast');"
            "return e&&e.classList.contains('show')?e.textContent:null})()")
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

    def stub(mode="ok", clip=True, pc=False):
        """共有の仕組みを差し替える。pc … パソコン扱い（指す道具が細かい）にするか。既定はスマホ扱い"""
        ui.ev(STUB % ('"%s"' % mode, "true" if clip else "false", "true" if pc else "false"))

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
    # 文は 3 つの状態 × みんなの結果のある・なしの 5 通り（D0.21。その日の 4 つの数字は入れる。ヒントの回数と連続日数は入れない）
    AGG = {"s": 412, "g": 96, "s0": 268, "b": [38, 121, 147, 82, 24]}
    AJS = json.dumps(AGG)
    texts = ui.ev("DAILY_DAYS.map(p=>{const s={r:'s',t:102,h:2,sh:3},g={r:'g',t:null,h:1,sh:1},a=Object.assign({n:p.no},%s);"
                  "return [shareTextOf(p),shareTextOf(p,s),shareTextOf(p,g),shareTextOf(p,s,a),shareTextOf(p,g,a)]})" % AJS)
    bad = []
    for r, t5 in zip(rows, texts):
        want = [dui.share_text(r), dui.share_text(r, "s", 102), dui.share_text(r, "g"),
                dui.share_text(r, "s", 102, AGG), dui.share_text(r, "g", agg=AGG)]
        if t5 != want or any(dui.share_leak(r, t) for t in t5):
            bad.append((r["no"], t5))
    ui.check("全 %d 問: 共有文 5 通りが決まった文で、4 つの数字が入り、答え・演算の記号・括弧が入らない" % len(rows), bad[:3], [])
    ui.check("例（#1）: 解く前・解いた後・ギブアップの後の文",
             texts[0][:3],
             ["Make10 DAILY #1\n%s\nこの 4 つの数字で 10 を作れる？" % " ".join(rows[0]["id"]),
              "Make10 DAILY #1\n%s → 10  ⏱ 1:42\nあなたは何秒？" % " ".join(rows[0]["id"]),
              "Make10 DAILY #1\n%s → 10\nギブアップ…\nあなたは解ける？" % " ".join(rows[0]["id"])])
    ui.check("例（#1）: みんなの結果があるとき（1:42 は 25%・正解率は 81%）",
             texts[0][3:],
             ["Make10 DAILY #1\n%s → 10  ⏱ 1:42\n解いた人の 25%% より速い\nあなたは何秒？" % " ".join(rows[0]["id"]),
              "Make10 DAILY #1\n%s → 10\nギブアップ…（正解率 81%%）\nあなたは解ける？" % " ".join(rows[0]["id"])])
    # 時間は「→ 10」と同じ行（D0.23。間は半角の空白 2 つ）。ギブアップの後・解く前の文には時間が無い
    d1 = " ".join(rows[0]["id"])
    ui.check("解いた後の文の 2 行目は「数字 → 10  ⏱ 時間」（位置あり・なしとも。行の数は 3 と 4）",
             [[t.split("\n")[1], len(t.split("\n"))] for t in (texts[0][1], texts[0][3])],
             [[d1 + " → 10  ⏱ 1:42", 3], [d1 + " → 10  ⏱ 1:42", 4]])
    ui.check("解く前とギブアップの後の文は、時間を持たず、2 行目は今までどおり",
             [[t.split("\n")[1], "⏱" in t] for t in (texts[0][0], texts[0][2], texts[0][4])],
             [[d1, False], [d1 + " → 10", False], [d1 + " → 10", False]])
    ui.check("どの文にも、ヒントの回数と連続日数（💡・🔥・ヒント・連続）が入らない",
             [t for t in texts[0] if re.search("💡|🔥|ヒント|連続", t)], [])
    # 位置（%）: 自分より遅い帯にいる人 ÷ 解いた人（切り捨て）。帯の境目・集計中・0%・形の合わない返事
    SP = "sharePct({r:'s',t:%d},Object.assign({n:1},%s))"
    secs = [1, 29, 30, 59, 60, 119, 120, 299, 300, 3599]
    ui.check("位置は、時間の帯ごとに「自分より遅い帯の人 ÷ 解いた人」の切り捨て（境目の秒は遅い側の帯）",
             [ui.ev(SP % (s, AJS)) for s in secs], [dui.share_pct("s", s, AGG) for s in secs])
    ui.check("…その値は 90・90・61・61・25・25・5・5・無し・無し", [dui.share_pct("s", s, AGG) for s in secs],
             [90, 90, 61, 61, 25, 25, 5, 5, None, None])
    slow = dui.share_text(rows[0], "s", 400)
    ui.check("いちばん遅い帯（0%）のときは、位置の行を出さない",
             [ui.ev("shareTextOf(DAILY_DAYS[0],{r:'s',t:400},Object.assign({n:1},%s))" % AJS), "より速い" in slow], [slow, False])
    PEND = {"s": 20, "g": 9, "s0": 3, "b": [1, 5, 9, 4, 1]}
    ui.check("集計中（30 件未満）は、解いた後もギブアップの後も、位置を出さない",
             ui.ev("[{r:'s',t:10},{r:'g',t:null}].map(x=>shareTextOf(DAILY_DAYS[0],x,Object.assign({n:1},%s)))" % json.dumps(PEND)),
             [dui.share_text(rows[0], "s", 10), dui.share_text(rows[0], "g")])
    ui.check("みんなの結果が無い（通信できない・まだ届いていない）ときは、位置を出さない",
             ui.ev("[null,undefined].map(a=>sharePct({r:'s',t:10},a))"), [None, None])
    ui.check("解く前の文は、みんなの結果があっても変わらない",
             ui.ev("shareTextOf(DAILY_DAYS[0],undefined,Object.assign({n:1},%s))" % AJS), dui.share_text(rows[0]))
    ui.check("解いた人が 0 のギブアップの後は、正解率 0%",
             ui.ev("shareTextOf(DAILY_DAYS[0],{r:'g',t:null},{n:1,s:0,g:40,s0:0,b:[0,0,0,0,0]})"),
             "Make10 DAILY #1\n%s → 10\nギブアップ…（正解率 0%%）\nあなたは解ける？" % " ".join(rows[0]["id"]))
    # 1 時間を超えた時間（D0.24）は h:mm:ss。位置はいちばん遅い帯なので出ない
    ui.check("1 時間を超えた時間の共有文は「⏱ 1:02:05」「⏱ 23:59:59」（みんなの結果があっても、位置の行は出ない）",
             [ui.ev("shareTextOf(DAILY_DAYS[0],{r:'s',t:%d},Object.assign({n:1},%s))" % (s, AJS)) for s in (3725, 86399)],
             ["Make10 DAILY #1\n%s → 10  ⏱ %s\nあなたは何秒？" % (d1, x) for x in ("1:02:05", "23:59:59")])
    # X の文字数（重み 280。かな・漢字・全角・絵文字は 2、ほかは 1、URL は 23）。いちばん長くなる場合でも収まる
    def xlen(s):
        n = 0
        for ch in s:
            c = ord(ch)
            n += 1 if (c <= 0x10FF or 0x2000 <= c <= 0x200D or 0x2010 <= c <= 0x201F or 0x2032 <= c <= 0x2037) else 2
        return n + 1 + 23
    longest = max([xlen(t) for t5 in texts for t in t5]
                  + [xlen(dui.share_text(rows[-1], "s", s, AGG)) for s in (299, 3725, 86399, 359999)])
    ui.check("全問の共有文が、URL を含めて X の文字数（重み 280）に収まる", longest <= 280, True)

    # ══ もらう前 → 知らせ → 共有 → 1 回目 → 2 回目 ══
    ui.open(now=at(no), tz=TZ, perf=True)
    ui.tick(9000)                        # 時計を進めておく（ヒントや共有で、最初に見た時刻が動かないことを見るため）
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
    # 保存にあるのは、問題を見た瞬間に残した「最初に見た時刻」だけ（D0.24）
    START = {"v": 1, "days": {}, "cur": {"no": no, "start": at(no), "h": 0, "sh": 0}}
    ui.check("知らせを出しただけでは、何も数えない", [ui.ev("hintUsed"), ui.ev("shareCount"), ui.saved()], [0, 0, START])
    click("hint-close")
    ui.check("× で閉じる", ui.ev(BOX), None)
    click("hint")
    click("hint")
    ui.check("知らせを出している間にもう一度押すと閉じる", ui.ev(BOX), None)
    click("hint")
    click("hint-share")
    ui.check("知らせの箱から共有: 共有画面に、解く前の文と URL が渡る",
             ui.ev("__SH"), [{"text": dui.share_text(two) + "\n" + URL}])
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
    ui.check("ヒントを使っても共有しても、最初に見た時刻は動かない（回数だけが変わる。D0.24）",
             ui.saved()["cur"], {"no": no, "start": at(no), "h": 2, "sh": 4})
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
    want = dui.share_text(two, "s", rec["t"])
    ui.check("「結果を共有」: 解いた後の文（4 つの数字と時間。ヒントの回数と連続日数は入らない）と URL", ui.ev("__SH[__SH.length-1]"),
             {"text": want + "\n" + URL})
    click("share")
    ui.check("解いた後は、上のバーの共有ボタンも同じ文", ui.ev("__SH[__SH.length-1]"), {"text": want + "\n" + URL})
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
    ui.check("ギブアップの入口を押すと、ヒントの箱は閉じる", [ui.ev(BOX), ui.ev(SEEN % "#dgusheet")], [None, True])
    ui.check("確認が出ている間は、後ろ（ヒントの丸ボタン）は押せない（D0.28 からポップアップ。ケース giveup）",
             ui.ev("play.inert"), True)
    click("gu-yes")
    click("share")
    ui.check("ギブアップの後の共有文", ui.ev("__SH[__SH.length-1]"),
             {"text": dui.share_text(one, "g") + "\n" + URL})
    ui.check("ギブアップの記録にも、使ったヒントと共有の回数が入る",
             [ui.saved()["days"][str(one["no"])]["h"], ui.saved()["days"][str(one["no"])]["sh"]], [2, 3])

    # ══ スマホ扱い: 文と URL を 1 つの text にまとめて渡す（url を別にしない。D0.22）══
    ui.open(now=at(no), tz=TZ)
    stub("ok")
    click("share")
    ui.check("スマホ扱い: 共有画面に渡すのは text の 1 つだけ（title も url も無い）。text の最後の行が URL",
             ui.ev("[__SH.length,Object.keys(__SH[0]),__SH[0].text.split('\\n').pop(),__CP]"), [1, ["text"], URL, []])
    ui.check("スマホ扱い: 共有 1 回に数える。トーストは出ない", [ui.ev("shareCount"), ui.ev(BTN)[0], ui.ev(TOAST_JS)], [1, "1", None])
    ui.check("パソコンかどうかは、指す道具の問い合わせ 1 つで決める（押すたびに見る）",
             [ui.ev("__MQ"), ui.ev("SHARE_PC_MQ")], [["(hover: hover) and (pointer: fine)"]] + ["(hover: hover) and (pointer: fine)"])
    # ══ パソコン扱い: 共有画面を使わず、文と URL をコピーする（D0.22）══
    ui.open(now=at(no), tz=TZ, perf=True)
    stub("ok", pc=True)
    click("share")
    ui.check("パソコン扱い: 共有画面を呼ばない。クリップボードに「文＋改行＋URL」。「コピーしました」",
             [ui.ev("__SH"), ui.ev("__CP"), ui.ev(TOAST_JS)], [[], [dui.share_text(two) + "\n" + URL], "コピーしました"])
    ui.check("パソコン扱い: 共有 1 回に数え、ヒントがもらえる", [ui.ev("shareCount"), ui.ev(BTN)], [1, ["1", None, "ヒント（残り 1 回）"]])
    click("hint")
    ui.check("パソコン扱い: もらったヒントを使える", ui.ev(BOX), hint_text(two["sol"], 1))
    click("hint")
    click("hint-share")
    ui.check("パソコン扱い: 知らせの箱から共有しても、コピーして、そのまま 2 回目のヒントが出る",
             [ui.ev("__SH"), len(ui.ev("__CP")), ui.ev("shareCount"), ui.ev(BOX)], [[], 2, 2, hint_text(two["sol"], 2)])
    ui.tick(3000)
    ui.solve(two["sol"], wait=0.9)
    click("rshare")
    click("share")
    rec = ui.saved()["days"][str(no)]
    ui.check("パソコン扱い: 解いた後も、共有ボタン 2 つともコピー（解いた後の文＋URL）。共有の回数は 2 → 4",
             [ui.ev("__SH"), ui.ev("__CP.slice(2)"), rec["sh"]],
             [[], [dui.share_text(two, "s", rec["t"]) + "\n" + URL] * 2, 4])
    ui.open(now=at(no), tz=TZ)
    stub("ok", clip=False, pc=True)
    click("hint")
    click("hint-share")
    ui.check("パソコン扱いでコピーできない: 共有画面には切り替えず、「コピーできません」。数えない・もらえない",
             [ui.ev("__SH"), ui.ev(TOAST_JS), ui.ev("shareCount"), ui.ev(BOX), ui.saved()],
             [[], "コピーできません", 0, "友達に出題するとヒントがもらえます", START])
    ui.open(now=at(no), tz=TZ)
    stub("none", pc=True)
    click("share")
    ui.check("パソコン扱いで共有画面が無い（Firefox など）: 同じくコピー",
             [ui.ev("__CP"), ui.ev(TOAST_JS), ui.ev("shareCount")], [[dui.share_text(two) + "\n" + URL], "コピーしました", 1])
    # 差し替えない本物の問い合わせ: 検証の Chrome（スマホの画面として開いている）の答えと、ページの判定が同じ
    ui.open(now=at(no), tz=TZ)
    ui.check("差し替えないとき、ページの判定は、ブラウザーの本物の答えと同じ",
             ui.ev("sharePc()===matchMedia('(hover: hover) and (pointer: fine)').matches"), True)
    # ══ 共有画面が無い・閉じただけ・拒まれた ══
    TOAST = TOAST_JS
    # 無い → コピー。もらえる
    ui.open(now=at(no), tz=TZ)
    stub("none")
    click("share")
    ui.check("共有画面が無い: 文と URL をコピーして「コピーしました」。ヒントはもらえる",
             [ui.ev("__CP"), ui.ev(TOAST), ui.ev("shareCount"), ui.ev(BTN)[0]],
             [[dui.share_text(two) + "\n" + URL], "コピーしました", 1, "1"])
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
             ["コピーできません", 0, "友達に出題するとヒントがもらえます", START])
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
             ui.ev("__CP[0]"), dui.share_text(two, "s", 3) + "\n" + URL)
    # ══ みんなの結果を受け取れているときは、共有する文に位置が入る（テスト表示の見本の数字で、押して確かめる）══
    for extra, kind in (("&agg=demo", "s"), ("&agg=pending", "s"), ("", "s"), ("&agg=demo", "g"), ("&agg=pending", "g")):
        ui.open(date=day(no).isoformat(), extra=extra)
        stub("ok")
        if kind == "s":
            ui.solve(two["sol"], wait=0.9)
        else:
            ui.ev("dgiveup.click();document.getElementById('gu-yes').click()")
            time.sleep(0.6)
        click("rshare")
        sec = ui.ev("dayRecord().t")
        agg = {"&agg=demo": AGG, "&agg=pending": PEND}.get(extra)
        want = dui.share_text(two, kind, sec, agg)
        ui.check("押して共有（%s・%s）: 共有画面に渡る文" % ("解いた後" if kind == "s" else "ギブアップの後", extra[1:] or "みんなの結果なし"),
                 [ui.ev("__SH[__SH.length-1]"), ("より速い" in want or "正解率" in want)],
                 [{"text": want + "\n" + URL}, extra == "&agg=demo"])
        click("share")
        ui.check("…上のバーの共有ボタンも同じ文", ui.ev("__SH[__SH.length-1]"), {"text": want + "\n" + URL})
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
