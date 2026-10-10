# -*- coding: utf-8 -*-
"""みんなの結果と、来た人数の計測（D0.8。DAILY-SPEC 17 章・11 章「集計」）。

集計の送り先（api.make10.app）は、ページの fetch を読み込みより先に差し替えて横取りする
（`daily_ui.API`。本物の集計へは 1 回も送らない）。出た要求は `ui.api_calls()` で読む。
"""
import datetime
import json
import time

from uiharness import daily_ui as dui
from uiharness.daily_cases import lang as L

NAME = "みんなの結果と計測"

TZ = "Asia/Tokyo"
URL = "https://api.make10.app/r"
GOLD = "rgb(227, 193, 111)"
AGG = {"s": 412, "g": 96, "s0": 268, "b": [38, 121, 147, 82, 24]}        # 508 件
SEEN = ("(function(){const e=document.getElementById(%r);if(!e)return false;const s=getComputedStyle(e);"
        "return s.display!=='none'&&s.visibility!=='hidden'&&e.offsetHeight>0})()")
# みんなの結果に見えているもの
BOX = ("(function(){const a=document.getElementById('aggbox');if(a.classList.contains('hide'))return null;"
       "const q=s=>[...a.querySelectorAll(s)];"
       "return {title:(a.querySelector('.at')||{}).textContent,pending:(a.querySelector('.ap')||{}).textContent||null,"
       "nums:q('.ac b').map(e=>e.textContent),names:q('.ac span').map(e=>e.textContent),"
       "labels:q('.bar span').map(e=>e.textContent),"
       "bars:q('.bar i').map(e=>Math.round(e.getBoundingClientRect().height)),"
       "me:q('.bar').map((e,i)=>e.classList.contains('me')?i:-1).filter(i=>i>=0),"
       "you:q('.bar[aria-label]').map(e=>e.getAttribute('aria-label')),name:a.getAttribute('aria-label'),"
       "tight:a.classList.contains('tight')}})()")
REST = "[rshare,solbox,applink,document.querySelector('.rcols')].every(e=>e.offsetHeight>0)"
NET = ("performance.getEntriesByType('resource').map(e=>e.name)"
       ".filter(n=>/api\\.make10\\.app|cloudflareinsights/.test(n))")


def run(ui):
    start, rows = dui.page_data()
    day = lambda n: start + datetime.timedelta(days=n - 1)          # noqa: E731
    no = 4
    sol = rows[no - 1]["sol"]
    low = ui.viewport != "normal"

    def at(n, hour=10):
        d = day(n)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    def ok(agg=AGG):
        return {"mode": "ok", "agg": agg}

    def bars(b, h):
        return [max(2, round(h * c / max(b))) for c in b]

    def solve(sec, wait=0.9):
        ui.tick(sec * 1000)
        r = ui.solve(sol, wait=wait)
        return r

    def giveup(wait=0.6):
        ui.ev("dgiveup.click();document.getElementById('gu-yes').click()")
        time.sleep(wait)

    # ══ 解いた瞬間に 1 回だけ送り、返事の集計を出す ══
    ui.open(now=at(no), tz=TZ, perf=True, api=ok())
    ui.check("解く前は、何も送らないし読まない。みんなの結果も出ない", [ui.api_calls(), ui.ev(BOX)], [[], None])
    solve(75)
    calls = ui.api_calls()
    ui.check("解いた瞬間に、1 回だけ送る（POST https://api.make10.app/r）",
             [[c["method"], c["url"]] for c in calls], [["POST", URL]])
    ui.check("中身は、問題番号・結果・時間（秒）・ヒントの回数の 4 つだけ",
             json.loads(calls[0]["body"]) if calls else None, {"n": no, "r": "s", "t": 75, "h": 0})
    ui.check("Content-Type は text/plain だけで、ほかの見出しや項目を足さない（事前確認の OPTIONS が出ない単純な POST）",
             [calls[0]["headers"], calls[0]["keys"]] if calls else None,
             [{"Content-Type": "text/plain"}, ["body", "headers", "method", "signal"]])
    ui.check("送れたら、1 日ぶんの記録に「送った」の印", ui.saved()["days"][str(no)].get("sent"), 1)
    h = 20 if low else 26
    ui.check("みんなの結果: 正解率 81%・ヒントなし 65%・時間の分布（5 本の棒）。自分のいる帯（1:15 → <2:00）だけが目立つ",
             ui.ev(BOX),
             {"title": "みんなの結果", "pending": None, "nums": ["81%", "65%"], "names": ["正解率", "ヒントなし"],
              "labels": ["<0:30", "<1:00", "<2:00", "<5:00", "5:00+"], "bars": bars(AGG["b"], h), "me": [2],
              "you": ["あなた"], "name": "みんなの結果", "tight": low})
    ui.check("自分の帯の棒と文字は明るく（--paper）、ほかは副次色で薄い。平均時間は出さない。金は使わない",
             ui.ev("(function(){const a=aggbox,c=e=>getComputedStyle(e);const me=a.querySelector('.bar.me'),"
                   "ot=a.querySelector('.bar:not(.me)');"
                   "return [c(me.querySelector('i')).backgroundColor,c(me.querySelector('i')).opacity,"
                   "c(me.querySelector('span')).color,c(ot.querySelector('i')).backgroundColor,c(ot.querySelector('i')).opacity,"
                   "[a,...a.querySelectorAll('*')].some(e=>[c(e).color,c(e).backgroundColor,c(e).borderTopColor].includes(%r)),"
                   "/平均|:\\d\\d$/.test(a.querySelector('.ar').firstChild.textContent)]})()" % GOLD),
             ["rgb(244, 241, 232)", "1", "rgb(244, 241, 232)", "rgb(143, 163, 196)", "0.4", False, False])
    ui.check("並びは、全解答 → みんなの結果 → 導線（重ならない・画面の左右に収まる）",
             ui.ev("(function(){const r=e=>e.getBoundingClientRect(),a=r(aggbox),s=r(solbox),l=r(applink),p=r(app);"
                   "return [a.top>=s.bottom-0.5,l.top>=a.bottom-0.5,a.left>=p.left&&a.right<=p.right,"
                   "[...aggbox.querySelectorAll('.ac,.bar')].every(e=>r(e).left>=p.left&&r(e).right<=p.right"
                   "&&e.scrollWidth<=e.clientWidth+1)]})()"), [True, True, True, True])
    # 収まり（13-5）。430×900 は見出しつきで 12px。360×690 は詰めた形（見出しなし・低い棒）で 8px。360×640 だけ縦に動かせる形
    fit = {"normal": ["12px", False, False], "compact": ["8px", True, False], "small": ["8px", True, True]}[ui.viewport]
    ui.check("収まり: 間隔・詰めた形か・縦に動かせる形か（430×900 は 12px／360×690 は詰めて 8px／360×640 だけ縦に動く）",
             ui.ev("[getComputedStyle(result).getPropertyValue('--resGap'),aggbox.classList.contains('tight'),"
                   "app.classList.contains('scrolly')]"), fit)
    if ui.viewport != "small":
        ui.check("導線は、版の行の文字より上に収まる",
                 ui.ev("applink.getBoundingClientRect().bottom<=dver.getBoundingClientRect().top+0.5"), True)
    ui.ev("aggSend(%d);aggSend(%d)" % (no, no))
    time.sleep(0.2)
    ui.check("印が付いた後は、もう送らない", len(ui.api_calls()), 1)

    # ══ 開き直したら、送り直さずに読み直す ══
    again = {"s": 500, "g": 500, "s0": 100, "b": [500, 0, 0, 0, 0]}
    ui.open(now=at(no, 15), tz=TZ, store="keep", api=ok(again))
    time.sleep(0.4)
    ui.check("開き直す: 送り直さず、1 回だけ読む（GET …/r?n=問題番号）",
             [[c["method"], c["url"], c["body"]] for c in ui.api_calls()], [["GET", "%s?n=%d" % (URL, no), None]])
    b = ui.ev(BOX)
    ui.check("開き直す: 読み直した数字を出す（50%・20%。自分の帯は同じ）",
             [b and b["nums"], b and b["me"], b and b["bars"]], [["50%", "20%"], [2], bars(again["b"], h)])

    # ══ 数字の大きさ（D0.12）: 3 列の数字・統計の数字と同じ（26px。詰めた形は 22px）。箱の高さは変わらない ══
    ui.open(now=at(no), tz=TZ, perf=True, api=ok())
    solve(75)
    z = ui.ev("(()=>{const a=document.getElementById('aggbox'),cs=e=>getComputedStyle(e);"
              "return [a.classList.contains('tight'),cs(a.querySelector('.ac b')).fontSize,cs(document.querySelector('.rcol .rv b')).fontSize,"
              "cs(a.querySelector('.ac span')).fontSize,Math.round(a.getBoundingClientRect().height)]})()")
    ui.check("みんなの結果の数字は 26px（詰めた形は 22px）・名前は 11.5px。箱の高さは 62px（詰めた形 34px）のまま",
             z[1:], (["22px", z[2], "11.5px", 34] if z[0] else ["26px", "26px", "11.5px", 62]))

    # ══ 29 件は「集計中」、30 件で数字 ══
    for agg, want in (({"s": 20, "g": 9, "s0": 3, "b": [1, 5, 9, 4, 1]}, [None, "集計中", []]),
                      ({"s": 21, "g": 9, "s0": 3, "b": [1, 5, 10, 4, 1]}, [None, None, ["70%", "14%"]])):
        ui.open(now=at(no), tz=TZ, perf=True, api=ok(agg))
        solve(75)
        b = ui.ev(BOX)
        want[0] = "みんなの結果"
        ui.check("件数が %d: %s" % (agg["s"] + agg["g"], "「集計中」と出し、数字も棒も出さない" if want[1] else "数字を出す"),
                 [b and b["title"], b and b["pending"], b and b["nums"]], want)
        if want[1]:
            # 「集計中」の詰めた形（D0.12）。公開の直後は必ずこの状態なので、360×690 で縦に動かさない
            p = ui.ev("(()=>{const a=document.getElementById('aggbox'),r=e=>e.getBoundingClientRect(),"
                      "t=a.querySelector('.at'),q=a.querySelector('.ap');"
                      "return {tight:a.classList.contains('tight'),h:Math.round(r(a).height),scrolly:app.classList.contains('scrolly'),"
                      "seen:[t.offsetHeight>0,q.offsetHeight>0],row:Math.abs(r(t).top-r(q).top)<3&&r(t).right<=r(q).left,"
                      "in:r(t).left>=r(app).left&&r(q).right<=r(app).right,"
                      "fit:r(applink).bottom<=r(dver).top+0.5}})()")
            if ui.viewport == "compact":
                ui.check("「集計中」: 360×690 は詰めた形（見出しと文を 1 行・20px）で、縦に動かさずに収まる",
                         p, {"tight": True, "h": 20, "scrolly": False, "seen": [True, True], "row": True, "in": True, "fit": True})
            elif ui.viewport == "normal":
                ui.check("「集計中」: 大きい画面は見出しと文の 2 行（39px）のまま",
                         [p["tight"], p["h"], p["scrolly"], p["seen"]], [False, 39, False, [True, True]])
            else:
                ui.check("「集計中」: 360×640 でも、見出しと文は見えている", p["seen"], [True, True])
    ui.open(now=at(no), tz=TZ, perf=True, api=ok({"s": 0, "g": 40, "s0": 0, "b": [0, 0, 0, 0, 0]}))
    giveup()
    b = ui.ev(BOX)
    ui.check("解いた人が 0 のとき: 正解率 0%・ヒントなしは「—」・棒は全部いちばん低い",
             [b and b["nums"], b and b["bars"]], [["0%", "—"], [2, 2, 2, 2, 2]])

    # ══ ギブアップの瞬間にも 1 回だけ送る。目立つ帯は無い ══
    ui.open(now=at(no), tz=TZ, perf=True, api=ok())
    ui.ev("shareCount=2;useHint()")
    ui.tick(50000)
    giveup()
    calls = ui.api_calls()
    ui.check("ギブアップの瞬間に、1 回だけ送る（結果は g・時間は入れない・ヒントは使った回数）",
             [[c["method"], c["url"]] for c in calls] + [json.loads(c["body"]) for c in calls],
             [["POST", URL], {"n": no, "r": "g", "t": None, "h": 1}])
    b = ui.ev(BOX)
    ui.check("ギブアップの後: 数字は出るが、目立つ帯は無い", [b and b["nums"], b and b["me"], b and b["you"]],
             [["81%", "65%"], [], []])
    ui.check("ギブアップの後も、印が付く", ui.saved()["days"][str(no)].get("sent"), 1)

    # ══ ヒントの回数と、時間の上限 ══
    ui.open(now=at(no), tz=TZ, perf=True, api=ok(),
            store={"v": 1, "days": {}, "cur": {"no": no, "ms": 90000000, "h": 2, "sh": 2}})
    solve(1)
    c = ui.api_calls()
    ui.check("ヒントを 2 回使って、25 時間かかった: 時間は上限の 86400 秒で送り、ヒントは 2",
             json.loads(c[0]["body"]) if c else None, {"n": no, "r": "s", "t": 86400, "h": 2})
    ui.check("自分の帯は、いちばん右（5:00+）", (ui.ev(BOX) or {}).get("me"), [4])

    # 帯の境目ちょうどの時間（30 秒は 2 つ目・60 秒は 3 つ目・300 秒は 5 つ目。サーバーと同じ分け方）
    got = []
    for sec in (29, 30, 59, 60, 119, 120, 299, 300):
        ui.open(now=at(no), tz=TZ, perf=True, api=ok())
        solve(sec, wait=0.7)
        got.append((ui.ev(BOX) or {}).get("me"))
    ui.check("自分の帯の境目: 29 秒・30 秒・59 秒・60 秒・119 秒・120 秒・299 秒・300 秒",
             got, [[0], [1], [1], [2], [2], [3], [3], [4]])

    # ══ ?date=（テスト表示）では、送らないし読まない ══
    ui.open(date=day(no).isoformat(), api=ok())
    ui.solve(sol, wait=0.9)
    ui.check("?date=: 解いても、送る要求も読む要求も 1 回も出ない。みんなの結果も出ない",
             [ui.api_calls(), ui.ev(BOX), ui.ev(REST)], [[], None, True])
    ui.open(date=day(no).isoformat(), api=ok())
    giveup()
    ui.check("?date=: ギブアップしても、要求は 1 回も出ない", [ui.api_calls(), ui.ev(BOX)], [[], None])

    # ══ 通信できないとき: 集計の場所を出さず、ほかの並びはそのまま。印を付けず、次に開いたときに送り直す ══
    for mode, what, marked in (("fail", "通信そのものが失敗", None), ("500", "返事がエラー（500）", None),
                               ("value", "返事が 400（値が外れている）", None), ("badjson", "返事が JSON でない", None),
                               ("badshape", "返事の形が違う", 1)):
        ui.open(now=at(no), tz=TZ, perf=True, api={"mode": mode})
        solve(75)
        ui.check("%s: みんなの結果を出さず、ほかの並びはそのまま。JS エラーなし。印は%s" % (
                     what, "付く（届いてはいる）" if marked else "付かない"),
                 [len(ui.api_calls()), ui.ev(BOX), ui.ev(REST), ui.errors(), ui.saved()["days"][str(no)].get("sent")],
                 [1, None, True, [], marked])
    ui.check("通信できないとき、間隔は元のまま（みんなの結果のぶんを詰めない）",
             ui.ev("[getComputedStyle(result).getPropertyValue('--resGap'),app.classList.contains('scrolly')]"),
             {"normal": ["24px", False], "compact": ["16px", False], "small": ["16px", False]}[ui.viewport])
    # 送れなかった日を、次に開いたときに送り直す
    ui.open(now=at(no), tz=TZ, perf=True, api={"mode": "fail"})
    solve(75)
    ui.open(now=at(no, 18), tz=TZ, store="keep", api=ok())
    time.sleep(0.4)
    calls = ui.api_calls()
    ui.check("送れなかった日: 次に開いたときに、1 回だけ送り直す（読む要求は出さない）。印が付き、数字が出る",
             [[c["method"] for c in calls], json.loads(calls[0]["body"]) if calls else None,
              ui.saved()["days"][str(no)].get("sent"), (ui.ev(BOX) or {}).get("nums")],
             [["POST"], {"n": no, "r": "s", "t": 75, "h": 0}, 1, ["81%", "65%"]])
    # 返事が来ないまま打ち切り
    ui.open(now=at(no), tz=TZ, perf=True, api={"mode": "hang"})
    solve(75)
    ui.check("返事が来ない間も、結果の画面はそのまま使える", [ui.ev(REST), ui.ev(BOX), ui.ev("aggBusy.size")], [True, None, 1])
    time.sleep(4.3)
    ui.check("返事が来ないまま 4 秒で打ち切る: みんなの結果を出さず、印も付けず、JS エラーなし",
             [ui.ev("aggBusy.size"), ui.ev(BOX), ui.saved()["days"][str(no)].get("sent"), ui.errors()], [0, None, None, []])

    # ══ サーバーが「もう受け取らない日」と断ったら、印を付けて送り直しをやめる ══
    ui.open(now=at(no), tz=TZ, perf=True, api={"mode": "range"})
    solve(75)
    ui.check("断られた（400 range）: 印を付け、みんなの結果は出さない",
             [ui.saved()["days"][str(no)].get("sent"), ui.ev(BOX), ui.errors()], [1, None, []])
    ui.open(now=at(no, 18), tz=TZ, store="keep", api={"mode": "range"})
    time.sleep(0.3)
    ui.check("断られた後に開き直す: 送り直さない", [c["method"] for c in ui.api_calls()], ["GET"])

    # ══ 前の日の分の送り直し。3 日より前の分は、送らずに印を付ける ══
    # 今日を #10 にして、#1（送った日）・#6・#7（3 日より前）・#8・#9（一昨日と昨日）を仕込む
    t0 = 10
    rec = {"r": "s", "t": 60, "h": 1, "sh": 1, "e": rows[0]["sol"]}
    ui.open(now=at(t0), tz=TZ, api=ok(),
            store={"v": 1, "cur": None, "days": {"1": dict(rec, sent=1), str(t0 - 4): dict(rec), str(t0 - 3): dict(rec),
                                                 str(t0 - 2): dict(rec, r="g", t=None), str(t0 - 1): dict(rec)}})
    time.sleep(0.4)
    calls = ui.api_calls()
    ui.check("送れていない前の日の分を送り直す（一昨日と昨日だけ。3 日より前は送らない。送った日も送らない）",
             sorted([json.loads(c["body"]) for c in calls if c["method"] == "POST"], key=lambda x: x["n"]),
             [{"n": t0 - 2, "r": "g", "t": None, "h": 1}, {"n": t0 - 1, "r": "s", "t": 60, "h": 1}])
    ui.check("読む要求は出さない（今日はまだ遊んでいない）。前の日の集計は画面に出さない",
             [[c["method"] for c in calls if c["method"] != "POST"], ui.ev(BOX), ui.visible("play")], [[], None, True])
    ui.check("どの日にも印が付く（3 日より前の分は、送らずに印だけ）",
             {k: v.get("sent") for k, v in ui.saved()["days"].items()},
             {"1": 1, str(t0 - 4): 1, str(t0 - 3): 1, str(t0 - 2): 1, str(t0 - 1): 1})

    # ══ 保存できない環境でも送る ══
    ui.open(now=at(no), tz=TZ, perf=True, store="blocked", api=ok())
    ui.ev("document.getElementById('dhelp-close').click()")
    solve(75)
    ui.check("保存できない環境: 送って、数字を出す。JS エラーなし",
             [[c["method"] for c in ui.api_calls()], (ui.ev(BOX) or {}).get("nums"), ui.errors()],
             [["POST"], ["81%", "65%"], []])

    # ══ 英語と、両方の言語のはみ出し ══
    for lang, want in (("ja", ["みんなの結果", "正解率", "ヒントなし", "あなた"]),
                       ("en", ["Everyone's results", "Solve rate", "No hints", "You"])):
        ui.open(now=at(no), tz=TZ, perf=True, lang=lang, api=ok({"s": 9999, "g": 1, "s0": 9999, "b": [9999, 0, 0, 0, 0]}))
        solve(5)
        b = ui.ev(BOX) or {}
        a = ui.ev(L.AUDIT)
        ui.check("%s: みんなの結果の文。いちばん長い数字（100%%）でも、はみ出しも折り返しも無い" % lang,
                 [[b.get("name")] + b.get("names", []) + b.get("you", []), b.get("nums"), a["over"],
                  ui.ev("[...aggbox.querySelectorAll('.ac b,.ac span,.bar span')].every(e=>e.getClientRects().length===1"
                        "&&e.scrollWidth<=e.clientWidth+1)")],
                 [want, ["100%", "100%"], [], True])
        if lang == "en":
            ui.check("en: みんなの結果に日本語の文字が無い",
                     [x for x in a["texts"] + a["labels"] if L.JP.search(x)], [])
    ui.open(now=at(no), tz=TZ, perf=True, lang="en", api=ok({"s": 20, "g": 9, "s0": 3, "b": [1, 5, 9, 4, 1]}))
    solve(5)
    ui.check("en: 件数が 29 のときの文", (ui.ev(BOX) or {}).get("pending"), "Collecting results")

    # ══ 来た人数の計測（合い言葉が空なら読み込まない。make10.app でだけ読み込む）══
    src = dui.read(dui.DAILY_HTML)
    ui.open(now=at(no), tz=TZ, api=ok())
    # 合い言葉の値そのものは見ない（人が値を入れた後も、このケースが通るように）
    ui.check("計測: 合い言葉は 1 か所の定数。HTML に計測の印を直に書いていない。127.0.0.1 では読み込まれていない",
             [src.count("const WA_TOKEN="), ui.ev("typeof WA_TOKEN"), src.count("cloudflareinsights"),
              ui.ev("document.querySelectorAll('script[src]').length")], [1, "string", 1, 0])
    ui.check("計測: 合い言葉が空・ホスト名が make10.app でない、のどちらでも読み込まない",
             ui.ev("(function(){const n=document.scripts.length;const r=[waStart('', 'make10.app'),"
                   "waStart('abc', '127.0.0.1'),waStart('abc', 'www.make10.app'),waStart('abc', location.hostname)];"
                   "return [r,document.scripts.length-n]})()"), [[False, False, False, False], 0])
    ui.check("計測: 合い言葉があって make10.app なら、計測の 1 本を足す（合い言葉を付けて・後から読む形で）",
             ui.ev("(function(){const real=document.head.appendChild,got=[];"
                   "document.head.appendChild=function(e){got.push(e);return e};"
                   "let r;try{r=waStart('abc123','make10.app')}finally{document.head.appendChild=real}"
                   "return [r,got.map(e=>[e.tagName,e.src,e.defer,e.getAttribute('data-cf-beacon')])]})()"),
             [True, [["SCRIPT", "https://static.cloudflareinsights.com/beacon.min.js", True, '{"token":"abc123"}']]])
    ui.solve(sol, wait=0.9)
    ui.check("127.0.0.1 で開いて解いても、計測にも本物の集計にも、要求が 1 回も出ていない", ui.ev(NET), [])
    ui.check_no_errors()
