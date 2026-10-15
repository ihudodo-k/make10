# -*- coding: utf-8 -*-
"""別の端末へ移す（D0.37。DAILY-SPEC 10-1）。

- 設定の 5 行目に「別の端末へ移す」があり、押すと移す画面が開く（テスト表示 ?date= では出さない）
- 送る: 預ける中身（記録から sent を外したもの・設定。途中の分 cur は入れない）・送り方（text/plain の単純な POST）・
  コードと残りの時間・QR（ここで独立に読み直して、このページの URL ＋ #move=コード になること）・期限が来たら出す前に戻る・
  通信できない／回数が多すぎるときの文
- 受け取る: 入れた字をそろえる（小文字・空白・ハイフン）・形が違えば送らない・記録の合わせ方（同じ日は解いたほうを残す・
  形の違う日は足さない・受け取った日には sent）・設定は送った端末のもの・途中の分は消す・見つからない／回数／通信の文・
  閉じると読み直す・読み直した後は受け取った記録と設定で開き、受け取った日は集計へ送らない
- QR から開く（#move=コード）: コードを入れた状態で開き、URL からコードを消す。自分では受け取らない
- 英語の文・はみ出さない・JS エラー 0

QR の読み直しは、ページの作り方（qrMatrix）を使わず、JIS X 0510 の決まりからここで書いたもの
（形式情報の BCH・機能パターンの場所・マスク・読む順・ブロックの分け方・リード・ソロモンの検査・バイトの形）。
"""
import datetime
import json
import re
import time

from uiharness import daily_ui as dui

NAME = "別の端末へ移す"

TZ = "Asia/Tokyo"
CODE = "K7P2QX"
STATE = ("(function(){const v=id=>{const e=document.getElementById(id);const s=getComputedStyle(e);"
         "return s.display!=='none'&&s.visibility!=='hidden'&&e.offsetHeight>0};"
         "return {pop:popNow,out:v('mv-out'),issue:v('mv-issue'),code:$('mv-code').textContent,left:$('mv-left').textContent,"
         "smsg:$('mv-smsg').textContent,serr:$('mv-smsg').classList.contains('err'),"
         "rmsg:$('mv-rmsg').textContent,rerr:$('mv-rmsg').classList.contains('err'),inp:$('mv-in').value}})()")
QR_DOTS = ("(function(){const s=document.querySelector('#mv-qr svg');if(!s)return null;"
           "const r=s.querySelector('rect'),p=s.querySelector('path'),b=s.getBoundingClientRect();"
           "return {vb:s.getAttribute('viewBox'),d:p.getAttribute('d'),bg:r.getAttribute('fill'),fg:p.getAttribute('fill'),"
           "w:b.width,h:b.height}})()")


# ── QR を読み直す（ページとは別に、決まりから書いたもの）──────────────
_EXP = [0] * 512
_LOG = [0] * 256
_v = 1
for _i in range(255):
    _EXP[_i] = _v
    _LOG[_v] = _i
    _v <<= 1
    if _v & 0x100:
        _v ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]
# 誤り訂正 M の、版ごとの [ブロックの数, データの語数, 誤り訂正の語数]（JIS X 0510 の表 9）
_BLOCKS_M = {1: (1, 16, 10), 2: (1, 28, 16), 3: (1, 44, 26), 4: (2, 32, 18), 5: (2, 43, 24)}
_MASKS = [lambda i, j: (i + j) % 2 == 0, lambda i, j: i % 2 == 0, lambda i, j: j % 3 == 0,
          lambda i, j: (i + j) % 3 == 0, lambda i, j: (i // 2 + j // 3) % 2 == 0,
          lambda i, j: (i * j) % 2 + (i * j) % 3 == 0, lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
          lambda i, j: ((i + j) % 2 + (i * j) % 3) % 2 == 0]        # i = 行・j = 列


def _bch_format(d):
    r = d << 10
    for k in range(14, 9, -1):
        if r & (1 << k):
            r ^= 0x537 << (k - 10)
    return ((d << 10) | r) ^ 0x5412


def qr_read(n, dark):
    """n×n の QR（dark = 黒いマスの (列, 行) の集合）を読む。(文字列, 説明の辞書)。読めなければ (None, 理由)"""
    ver = (n - 17) // 4
    if n != 17 + 4 * ver or ver not in _BLOCKS_M:
        return None, "大きさ %d" % n
    g = lambda x, y: 1 if (x, y) in dark else 0          # noqa: E731
    # 位置検出パターン（7×7 の輪と中の 3×3。周りの 1 マスは白）
    for cx, cy in ((3, 3), (n - 4, 3), (3, n - 4)):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < n and 0 <= y < n:
                    want = 0 if max(abs(dx), abs(dy)) in (2, 4) else 1
                    if g(x, y) != want:
                        return None, "位置検出パターン (%d,%d)" % (x, y)
    for k in range(8, n - 8):
        if g(k, 6) != (k + 1) % 2 or g(6, k) != (k + 1) % 2:
            return None, "タイミング %d" % k
    # 形式情報（2 か所。どちらも有効な BCH の符号語で、同じ値）
    p1 = [(8, i) for i in range(6)] + [(8, 7), (8, 8), (7, 8)] + [(14 - i, 8) for i in range(9, 15)]
    p2 = [(n - 1 - i, 8) for i in range(8)] + [(8, n - 15 + i) for i in range(8, 15)]
    f1 = sum(g(*p1[i]) << i for i in range(15))
    f2 = sum(g(*p2[i]) << i for i in range(15))
    hit = [d for d in range(32) if _bch_format(d) == f1]
    if not hit or f1 != f2:
        return None, "形式情報 %s %s" % (bin(f1), bin(f2))
    ecl, mask = hit[0] >> 3, hit[0] & 7
    if ecl != 0:
        return None, "誤り訂正のレベルが M でない (%d)" % ecl
    if g(8, n - 8) != 1:
        return None, "暗モジュール"

    def func(x, y):
        return ((x < 9 and y < 9) or (x >= n - 8 and y < 9) or (x < 9 and y >= n - 8) or x == 6 or y == 6
                or (ver > 1 and abs(x - (n - 7)) <= 2 and abs(y - (n - 7)) <= 2))
    if ver > 1:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                if g(n - 7 + dx, n - 7 + dy) != (0 if max(abs(dx), abs(dy)) == 1 else 1):
                    return None, "位置合わせパターン"
    bits = []
    right = n - 1
    while right >= 1:
        if right == 6:
            right = 5
        for v in range(n):
            for j in (0, 1):
                x = right - j
                y = n - 1 - v if ((right + 1) & 2) == 0 else v
                if not func(x, y):
                    bits.append(g(x, y) ^ (1 if _MASKS[mask](y, x) else 0))
        right -= 2
    nb, nd, ne = _BLOCKS_M[ver]
    total = nb * (nd + ne)
    words = [int("".join(map(str, bits[k * 8:k * 8 + 8])), 2) for k in range(total)]
    blocks = [[] for _ in range(nb)]
    for k in range(nd * nb):
        blocks[k % nb].append(words[k])
    ecs = [[] for _ in range(nb)]
    for k in range(ne * nb):
        ecs[k % nb].append(words[nd * nb + k])
    for b in range(nb):
        cw = blocks[b] + ecs[b]
        for i in range(ne):
            s = 0
            for k, c in enumerate(cw):
                if c:
                    s ^= _EXP[(_LOG[c] + i * (len(cw) - 1 - k)) % 255]
            if s:
                return None, "リード・ソロモンの検査が 0 でない（ブロック %d）" % b
    data = "".join(format(w, "08b") for blk in blocks for w in blk)
    if data[:4] != "0100":
        return None, "バイトの形でない (%s)" % data[:4]
    length = int(data[4:12], 2)
    body = bytes(int(data[12 + 8 * k:20 + 8 * k], 2) for k in range(length))
    return body.decode("utf-8"), {"ver": ver, "mask": mask}


def qr_of_page(ui):
    q = ui.ev(QR_DOTS)
    if not q:
        return None, None, q
    vb = list(map(int, q["vb"].split()))
    n = vb[2] - 8
    dark = {(int(a), int(b)) for a, b in re.findall(r"M(\d+) (\d+)h1v1h-1z", q["d"])}
    return qr_read(n, dark) + (q,)


def run(ui):
    start, rows = dui.page_data()
    day = lambda k: start + datetime.timedelta(days=k - 1)          # noqa: E731

    def at(k, hour=10):
        d = day(k)
        tz = datetime.timezone(datetime.timedelta(hours=9))
        return int(datetime.datetime(d.year, d.month, d.day, hour, tzinfo=tz).timestamp() * 1000)

    no = 6
    rec = lambda k, r="s", t=40, h=0, sh=0, sent=1: (                   # noqa: E731
        {"r": "s", "t": t, "h": h, "sh": sh, "e": rows[k - 1]["sol"], **({"sent": 1} if sent else {})} if r == "s"
        else {"r": "g", "t": None, "h": h, "sh": sh, **({"sent": 1} if sent else {})})
    # 送る端末: #2 解いた・#3 ギブアップ・#4 ギブアップ（送れていない）・#5 解いた・今日 #6 解いた。設定は全部入れた形
    a_days = {"2": rec(2, t=75, h=1, sh=1), "3": rec(3, "g", h=2, sh=2), "4": rec(4, "g", sent=0), "5": rec(5, t=33),
              "6": rec(6, t=120, h=2, sh=3)}
    a_set = {"easy": 1, "tap": 1, "dark": 1, "lang": "en"}
    store_a = {"v": 1, "days": a_days, "cur": None, "set": a_set}

    # ══ 設定の行と、移す画面を開く ══
    ui.open(now=at(no), tz=TZ)
    ui.ev("dset.click()")
    ui.check("設定の 5 行目に「別の端末へ移す」（スイッチの 4 行とは細い線 1 本で分けた別のまとまり）",
             ui.ev("(function(){const r=[...dsetbody.querySelectorAll('.toggle')].map(b=>b.id);const g=$('t-move-g');"
                   "const l=getComputedStyle(g,'::before'),a=$('t-lang').getBoundingClientRect(),m=$('t-move').getBoundingClientRect();"
                   "return [r,$('t-move').textContent,l.height,l.left,l.right,Math.round(m.top-a.bottom),g.offsetHeight>0]})()"),
             [["t-easy", "t-tap", "t-dark", "t-lang", "t-move"], "別の端末へ移す›", "1px", "14px", "14px", 0, True])
    ui.ev("$('t-move').click()")
    st = ui.ev(STATE)
    ui.check("押すと移す画面が開き（設定は閉じる）、「コードを出す」だけが見える",
             [st["pop"], ui.visible("dsetsheet"), st["issue"], st["out"], st["smsg"], st["rmsg"], st["inp"]],
             ["dmovesheet", False, True, False, "", "", ""])
    ui.check("見出しと 2 つのまとまりの見出し・ボタンの文",
             ui.ev("[$('dmove-title').textContent,...[...dmovebody.querySelectorAll('h3,.mvbtn')].map(e=>e.textContent)]"),
             ["別の端末へ移す", "この端末から送る", "コードを出す", "この端末で受け取る", "受け取る"])
    ui.check("ボタンは面も枠も持たない太字（囲まない）",
             ui.ev("(function(){const s=getComputedStyle($('mv-issue'));"
                   "return [s.backgroundColor,s.borderTopWidth,s.fontWeight]})()"),
             ["rgba(0, 0, 0, 0)", "0px", "700"])

    # 通信できない（既定）・回数が多すぎる
    ui.ev("$('mv-issue').click()")
    time.sleep(0.3)
    st = ui.ev(STATE)
    ui.check("通信できないとき: 「通信できませんでした…」（赤）。コードは出ない",
             [st["smsg"], st["serr"], st["out"], st["issue"]],
             ["通信できませんでした。時間をおいて試してください", True, False, True])
    ui.ev("window.__APIMODE.xput='busy'")
    ui.ev("$('mv-issue').click()")
    time.sleep(0.3)
    ui.check("回数が多すぎるとき（429）: 「試す回数が多すぎます…」", ui.ev(STATE)["smsg"], "試す回数が多すぎます。1 分ほど待ってください")
    ui.check("失敗しても、記録と設定は変わらない（開いただけで残る今日の途中の分 cur のほかは空のまま）",
             {k: v for k, v in (ui.saved(raw=True) or {}).items() if k != "cur"}, {"v": 1, "days": {}, "set": dui.SET_DEFAULT})

    # ══ 送る ══
    ui.open(now=at(no), tz=TZ, store=dict(store_a, cur={"no": 7, "start": 1, "h": 0, "sh": 0}),
            api={"xput": "ok", "xcode": CODE, "xs": 600})
    before = ui.saved(raw=True)
    ui.ev("dset.click();$('t-move').click()")
    ui.ev("$('mv-issue').click()")
    time.sleep(0.3)
    calls = [c for c in ui.api_calls() if "/x" in c["url"]]
    ui.check("預ける要求は 1 回で、https://api.make10.app/x への text/plain の POST（事前確認の出ない形）",
             [[c["url"], c["method"], c["headers"], c["keys"]] for c in calls],
             [["https://api.make10.app/x", "POST", {"Content-Type": "text/plain"}, ["body", "headers", "method", "signal"]]])
    sent = json.loads(calls[0]["body"]) if calls else None
    want_days = {k: {kk: vv for kk, vv in v.items() if kk != "sent"} for k, v in a_days.items()}
    ui.check("預ける中身は、記録（送れたかの印 sent を外す）と設定だけ（途中の分 cur は入れない）",
             sent, {"v": 1, "days": want_days, "set": a_set})
    st = ui.ev(STATE)
    ui.check("コードと残りの時間を出し、「コードを出す」は隠れる",
             [st["code"], st["left"], st["out"], st["issue"], st["smsg"]],
             [CODE, "あと 10:00 有効", True, False, ""])      # ケースは ?lang=ja で開くので、保存の set.lang（英語）より日本語が先
    text, info, q = qr_of_page(ui)
    url = ui.ev("location.origin+location.pathname")
    ui.check("QR を読み直すと、このページの URL ＋ #move=コード（誤り訂正 M・検査が通る）", text, url + "#move=" + CODE)
    ui.check("QR は、どちらの色でも白地に黒・148px 四方（周りの白い余白 4 マスも QR の一部）",
             [q and q["bg"], q and q["fg"], q and round(q["w"]), q and round(q["h"]),
              q and q["vb"].split()[:2]], ["#FFFFFF", "#1A1A1B", 148, 148, ["-4", "-4"]])
    # 本番の URL の長さでも読めること（版 3。37 文字）
    prod = ui.ev("(function(){const t=qrMatrix('https://make10.app/daily/#move=%s');"
                 "const d=[];t.forEach((r,y)=>r.forEach((v,x)=>{if(v)d.push([x,y])}));return [t.length,d]})()" % CODE)
    ui.check("本番の URL（https://make10.app/daily/#move=…）の QR も読み直せる（29 マス・版 3）",
             qr_read(prod[0], {tuple(p) for p in prod[1]})[0] if prod else None,
             "https://make10.app/daily/#move=" + CODE)
    ui.check("コードを出しても、保存は変わらない", ui.saved(raw=True), before)
    ui.tick(61000)
    ui.ev("drawMove()")
    ui.check("1 分たつと、残りの時間が減る", ui.ev(STATE)["left"], "あと 8:59 有効")
    ui.ev("popHide()")
    ui.ev("dset.click();$('t-move').click()")
    ui.check("閉じて開き直しても、同じコードが出ている（期限の中）", [ui.ev(STATE)["code"], ui.ev(STATE)["out"]], [CODE, True])
    ui.tick(540000)
    ui.ev("drawMove()")
    st = ui.ev(STATE)
    ui.check("期限が来たら、出す前に戻り「コードの期限が切れました」（赤）",
             [st["out"], st["issue"], st["smsg"], st["serr"]], [False, True, "コードの期限が切れました", True])
    ui.check_no_errors("送る: JS エラー 0")

    # ══ 受け取る ══
    # 受け取る端末: #1 解いた（こちらだけ）・#2 ギブアップ（送る端末は解いた → 解いたほうに替わる）・
    # #3 解いた（送る端末はギブアップ → こちらを残す）・#5 解いた（両方とも解いた → こちらを残す）・今日 #6 は解いている途中
    b_days = {"1": rec(1, t=50), "2": rec(2, "g", h=1), "3": rec(3, t=99, h=1, sh=1), "5": rec(5, t=200, h=2, sh=2)}
    store_b = {"v": 1, "days": b_days, "cur": {"no": no, "start": at(no) - 30000, "h": 1, "sh": 1},
               "set": {"easy": 0, "tap": 0, "dark": 0, "lang": "auto"}}
    payload = {"v": 1, "days": dict(want_days, **{"7x": rec(1), "8": {"r": "s", "t": 10, "h": 5, "e": "1"},
                                                  "9": {"r": "z", "h": 0}}), "set": a_set}
    ui.open(now=at(no), tz=TZ, store=store_b, dark=False, api={"xtake": "ok", "xstore": {CODE: payload}})
    ui.ev("dset.click();$('t-move').click()")
    for v, key in (("", "6 文字のコードを入れてください"), ("ABC12", "6 文字のコードを入れてください"),
                   ("ABCDE0", "6 文字のコードを入れてください")):
        ui.ev("$('mv-in').value=%s;$('mv-take').click()" % json.dumps(v))
        st = ui.ev(STATE)
        ui.check("形の違うコード「%s」は送らず、「%s」（赤）" % (v, key), [st["rmsg"], st["rerr"]], [key, True])
    ui.check("形の違うコードでは、要求を出さない", [c for c in ui.api_calls() if "/x" in c["url"]], [])
    ui.ev("$('mv-in').value='ZZZZZZ';$('mv-take').click()")
    time.sleep(0.3)
    ui.check("無いコード（404）: 「コードが見つかりません…」", ui.ev(STATE)["rmsg"], "コードが見つかりません（期限切れか、受け取り済み）")
    ui.ev("$('mv-in').value=' k7p-2qx ';$('mv-in').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}))")
    time.sleep(0.3)
    calls = [c for c in ui.api_calls() if "/x" in c["url"]]
    ui.check("小文字・空白・ハイフンをそろえて、Enter でも受け取る（/x/take へ {\"c\":\"K7P2QX\"}）",
             [[c["url"], c["method"], c["headers"], json.loads(c["body"])] for c in calls[-1:]],
             [["https://api.make10.app/x/take", "POST", {"Content-Type": "text/plain"}, {"c": CODE}]])
    st = ui.ev(STATE)
    ui.check("受け取ったら「受け取りました（記録 5 日ぶんと設定）…」（形の違う 3 日は数えない）。もう押せない",
             [st["rmsg"], st["rerr"], ui.ev("[$('mv-take').disabled,$('mv-issue').disabled]")],
             ["受け取りました（記録 5 日ぶんと設定）。閉じると反映されます", False, [True, True]])
    got = ui.saved(raw=True)
    want = {"1": b_days["1"], "2": dict(want_days["2"], sent=1), "3": b_days["3"], "4": dict(want_days["4"], sent=1),
            "5": b_days["5"], "6": dict(want_days["6"], sent=1)}
    ui.check("記録の合わせ方: こちらだけの日は残す・ギブアップは解いたほうに替わる・解いた日は残す・"
             "無い日は足す・受け取った日には sent・形の違う日は足さない", got and got["days"], want)
    ui.check("設定は送った端末のもの・今日を受け取ったので途中の分は消す", got and [got["set"], got["cur"]], [a_set, None])
    ui.ev("$('mv-take').click()")
    time.sleep(0.2)
    ui.check("受け取った後は、もう 1 度押しても要求を出さない", len([c for c in ui.api_calls() if "/x" in c["url"]]), 2)
    # 閉じると読み直す（読み直すと、仕込みが保存を戻すので、ここでは読み直したことだけを見る）
    ui.ev("window.__mark=1;popHide()")
    time.sleep(1.0)
    ui.ev("0")
    ui.check("閉じると、ページを読み直す", ui.ev("window.__mark===undefined"), True)

    # 読み直した後（受け取った保存のまま開く）
    ui.open(now=at(no), tz=TZ, store=dict(got), dark=False, lang=None, api={"mode": "ok", "agg": {"s": 40, "g": 3, "s0": 20, "b": [5, 10, 15, 8, 2]}})
    time.sleep(0.3)
    ui.check("開き直すと、受け取った設定（ダークモード・英語・途中の値・タップ配置）",
             ui.ev("[document.documentElement.classList.contains('dark'),document.documentElement.lang,G.easy,tapMode]"),
             [True, "en", True, True])
    ui.check("今日を受け取ったので、解いた後の画面で開く", ui.ev("!!dayRecord()&&dayRecord().r"), "s")
    ui.check("受け取った日は、集計へ送らない（読むだけ）",
             [c["method"] for c in ui.api_calls() if c["url"].startswith("https://api.make10.app/r")], ["GET"])
    ui.check_no_errors("受け取る: JS エラー 0")

    # 受け取りの失敗の文（回数・通信）
    ui.open(now=at(no), tz=TZ, api={"xtake": "busy"})
    ui.ev("dset.click();$('t-move').click();$('mv-in').value='K7P2QX';$('mv-take').click()")
    time.sleep(0.3)
    ui.check("受け取り: 回数が多すぎるとき（429）", ui.ev(STATE)["rmsg"], "試す回数が多すぎます。1 分ほど待ってください")
    ui.ev("window.__APIMODE.xtake='fail';$('mv-take').click()")
    time.sleep(0.3)
    st = ui.ev(STATE)
    ui.check("受け取り: 通信できないとき（赤）・記録と設定は変わらない",
             [st["rmsg"], st["rerr"], {k: v for k, v in (ui.saved(raw=True) or {}).items() if k != "cur"}],
             ["通信できませんでした。時間をおいて試してください", True, {"v": 1, "days": {}, "set": dui.SET_DEFAULT}])

    # ══ QR から開く ══（前のページと URL を変えて、読み込みからやり直す。#move= だけの違いだと、同じページの中の移動になる）
    ui.open(now=at(no), tz=TZ, extra="&from=qr#move=k7p2qx", api={"xtake": "ok", "xstore": {CODE: payload}})
    time.sleep(0.2)
    st = ui.ev(STATE)
    ui.check("#move=コード で開くと、コードを入れた状態で移す画面が開き、URL からコードを消す",
             [st["pop"], st["inp"], ui.ev("location.hash")], ["dmovesheet", CODE, ""])
    ui.check("QR から開いても、自分では受け取らない（押すのは人）",
             [[c for c in ui.api_calls() if "/x" in c["url"]], (ui.saved(raw=True) or {}).get("days")], [[], {}])
    ui.ev("$('mv-take').click()")
    time.sleep(0.3)
    ui.check("押せば受け取る", ui.ev(STATE)["rmsg"], "受け取りました（記録 5 日ぶんと設定）。閉じると反映されます")
    # 開いたままのページの URL に #move= が付いたとき（読み直さない）も、移す画面を開く
    ui.open(now=at(no), tz=TZ)
    ui.ev("window.__mark=1;location.hash='#move=ABCDEF'")
    time.sleep(0.2)
    st = ui.ev(STATE)
    ui.check("開いたままのページに #move=コード が付いても、コードを入れて開く（読み直さない）",
             [st["pop"], st["inp"], ui.ev("location.hash"), ui.ev("window.__mark")], ["dmovesheet", "ABCDEF", "", 1])

    # ══ テスト表示では出さない ══
    ui.open(date=day(no).isoformat())
    ui.ev("dset.click()")
    ui.check("テスト表示（?date=）では、設定に「別の端末へ移す」を出さない", ui.visible("t-move"), False)

    # ══ 英語・はみ出し ══
    ui.open(now=at(no), tz=TZ, lang="en", api={"xput": "ok", "xcode": CODE})
    ui.ev("dset.click();$('t-move').click();$('mv-issue').click()")
    time.sleep(0.3)
    ui.check("英語の文", ui.ev("[$('t-move').textContent,$('dmove-title').textContent,"
                               "...[...dmovebody.querySelectorAll('h3,.mvbtn')].map(e=>e.textContent),$('mv-in').placeholder]"),
             ["Move to another device›", "Move to another device", "Send from this device", "Get a code",
              "Receive on this device", "Receive", "Code"])
    ui.check("英語の移す画面に、日本語の字が無い",
             re.findall(r"[぀-ヿ㐀-鿿＀-￯]", ui.ev("dmovebody.innerText+$('dmove-title').textContent"))[:5], [])
    ui.check("移す画面は横にはみ出さず、ページにスクロールが出ない（高さが足りなければカードの中だけが動く）",
             ui.ev("(function(){const c=popCard('dmovesheet').getBoundingClientRect();"
                   "const out=[...dmovebody.querySelectorAll('*')].filter(e=>{const r=e.getBoundingClientRect();"
                   "return r.width>0&&(r.left<c.left-0.5||r.right>c.right+0.5)}).length;"
                   "return [out,c.top>=0,c.bottom<=innerHeight+0.5]})()") + [ui.scrolls()],
             [0, True, True, False])
    ui.check_no_errors()
