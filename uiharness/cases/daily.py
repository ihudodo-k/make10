# -*- coding: utf-8 -*-
"""本編の中のデイリー（8.9。DAILY-SPEC 21 章）。

ホームの 4 行目・デイリーの 1 問・ギブアップ・解いた後の並び・保存（Web と同じキー make10.daily.v1）。
- デイリーで解いても、本編の進み・累計・挑戦の解放・ヒントの残数・統計が変わらない（21-2）
- Web のデイリー（/daily/）で解いた日は、本編から解き直せない（同じキーを読む）
- 本編が書くのは days と cur だけ。set は保存にあるものをそのまま書き戻し、書く前に保存にある日を足す（21-3）
- 「進捗をリセット」はデイリーの記録を消さない

端末の時計は ui.open(now=…) で固定の時刻から進める（2026-11-25（水）12:00 は #31）。
"""
import json
import time

NAME = "デイリー（本編の中）"


def ms(y, m, d, h=12, mi=0):
    """端末のローカル時刻の y-m-d h:mi（ミリ秒）。ブラウザも同じ時間帯で動く"""
    return int(time.mktime((y, m, d, h, mi, 0, 0, 0, -1)) * 1000)


NOW = ms(2026, 11, 25)          # 水曜。起点日 2026-10-26（月）から 31 日目
PROG = {"ci": 137, "cleared": 162, "hintStock": 57, "chalDone": [], "chalShown": [],
        "stats": {"n": 5, "sec": 300, "best": 20, "band": {"3-8": 5}}, "hist": [], "seen": []}
# 本編の記録のうち、デイリーで解いても動いてはいけないもの
G_SNAP = ("JSON.stringify({ci:G.ci,cleared:G.cleared,seen:G.seen,stats:G.stats,hist:G.hist,"
          "chalDone:G.chalDone,chalShown:G.chalShown,chalRem:G.chalRem,hintStock:G.hintStock,hints:G.hints})")
STORE = "JSON.parse(localStorage.getItem('make10.daily.v1')||'null')"
MODES = "[...document.querySelectorAll('.modes .mode')].map(b=>b.id)"
FITS = ("(()=>{const a=$('app'),lim=a.getBoundingClientRect().top+a.clientHeight-parseFloat(getComputedStyle(a).paddingBottom);"
        "const n=document.querySelector('.share').getBoundingClientRect().bottom;"
        "return n<=lim+.5&&document.documentElement.scrollHeight<=innerHeight+1&&$('home').scrollHeight<=$('home').clientHeight+1})()")


# 英語の画面（9.3）: [見えている文字に日本語があるか, 画面の幅からはみ出す要素の数]。%s は画面の id
EN_OK = ("(()=>{const r=$('%s');const ja=/[\\u3040-\\u30ff\\u3400-\\u9fff\\uff01-\\uff60]/.test(r.innerText);"
         "const over=[...r.querySelectorAll('*')].filter(e=>{const b=e.getBoundingClientRect();"
         "return b.width>0&&getComputedStyle(e).visibility!=='hidden'&&(b.left<-0.5||b.right>innerWidth+0.5)}).length;"
         "return [ja,over]})()")
# 遊び方のデイリーの節（9.3。9.5 で行を p にした）: [見出し, 次の見出しまでの行]
HELP_DAILY = ("(()=>{const h=[...document.querySelectorAll('#help h3')].find(x=>x.textContent===t('help.sec_daily'));"
              "const out=[h.textContent];for(let e=h.nextElementSibling;e&&e.tagName!=='H3';e=e.nextElementSibling)"
              "if(e.tagName==='P')out.push(e.textContent.trim());return out})()")


def value(ui):
    return ui.text("m-daily-v")


def run(ui):
    # ── ホームの 4 行目（解く前）──────────────────────────────
    ui.open(PROG, now=NOW)
    ui.check("今日は #31", ui.ev("dlyToday().no"), 31)
    ui.check("本編とデイリーのページの起点日が同じ", ui.ev("DAILY_START"), "2026-10-26")
    ui.check("モードの行は 4 つで、デイリーはいちばん下", ui.ev(MODES), ["m-course", "m-free", "m-chal", "m-daily"])
    ui.check("行の名前", ui.ev("$('m-daily').querySelector('.mt').textContent"), "デイリー")
    # 9.4: 解く前は名前だけ（値を出さない。ほかの行と同じ見た目）
    ui.check("解く前は値を出さない（名前だけ・値の要素は見えない）", [value(ui), ui.visible("m-daily-v")], ["", False])
    ui.check("解く前のデイリーの行は、フリープレイの行と同じ形（名前の位置が同じ）",
             ui.ev("(()=>{const f=e=>{const b=$(e).getBoundingClientRect(),t=$(e).querySelector('.mt').getBoundingClientRect();"
                   "return [Math.round(b.height),Math.round(t.top-b.top)]};return JSON.stringify(f('m-daily'))===JSON.stringify(f('m-free'))})()"),
             True)
    ui.check("押せる（ロックの見た目ではない）", ui.ev("$('m-daily').classList.contains('lock')"), False)
    ui.check("ホームは縦にも横にもはみ出さない（広告の枠の上に収まる）", ui.ev(FITS), True)
    ui.check("デイリーの保存は、まだ無い", ui.ev(STORE), None)

    # ── デイリーの 1 問 ─────────────────────────────────────
    g0 = ui.ev(G_SNAP)
    ui.click("m-daily")
    ui.check("問題の画面に入る", ui.ev("SCR+'|'+MODE"), "play|daily")
    pz = ui.ev("DAILY_DAYS[30]")
    ui.check("問題は列の #31", ui.ev("cur.id+','+cur.rc"), pz["id"] + "," + pz["rc"])
    ui.check("上のバーの 1 行目", ui.text("pmode"), "デイリー")
    ui.check("上のバーの 2 行目", ui.text("pday"), "#31　11月25日（水）")
    ui.check("問題のコードと難易度の言葉は出さない", ui.visible("pcode"), False)
    ui.check("ギブアップの入口が見える", ui.visible("dgiveup"), True)
    ui.check("共有とヒントの丸ボタンが見える（9.1）", [ui.visible("share"), ui.visible("hint")], [True, True])
    ui.check("「べつの問題」は出さない", ui.visible("alt"), False)
    ui.check("式が出来るまで、薄い目標の「10」", ui.ev("$('eq').className+'|'+$('eq').textContent"), "eq goal|10")
    st = ui.ev(STORE)
    ui.check("見た瞬間に、その日の途中の分（cur）を保存する",
             [st["cur"]["no"], isinstance(st["cur"]["start"], int), st["days"]] if st else None, [31, True, {}])
    ui.check("問題の画面はスクロールしない", ui.scrolls(), False)
    time.sleep(1.2)
    ui.check("解くと「10」と「正解」", ui.solve(wait=1.0), ui.solved_text())
    rec = ui.ev(STORE)["days"].get("31")
    ui.check("解いた日の記録（結果・式・ヒント 0 回・共有 0 回）",
             rec and [rec["r"], rec["e"], rec["h"], rec["sh"]], ["s", pz["sol"], 0, 0])
    ui.check("時間は 1 秒以上・60 分未満の整数", bool(rec) and isinstance(rec["t"], int) and 1 <= rec["t"] < 3600, True)
    ui.check("途中の分は消える", ui.ev(STORE)["cur"], None)
    ui.check("本編の記録は 1 つも変わらない（進み・累計・挑戦・ヒントの残数・統計・履歴）", ui.ev(G_SNAP), g0)
    time.sleep(0.4)
    ui.check("本編の保存も変わらない", ui.ev("(()=>{const s=JSON.parse(localStorage.getItem('make10.progress.v4')||'null');"
                                         "return s?[s.ci,s.cleared,s.hintStock,s.stats.n,s.seen.length]:null})()"),
             [137, 162, 57, 5, 0])
    ui.check("「つぎへ」は出ない", ui.visible("wnext"), False)
    ui.check("結果の並びが出る", ui.visible("result"), True)
    ui.check("3 列（時間・ヒント・連続日数）",
             [ui.text("r-time"), ui.text("r-hints"), ui.text("r-hints-u"), ui.text("r-streak"), ui.text("r-streak-u")],
             [ui.ev("fmtTime(%d)" % rec["t"]), "0", "回", "1", "日"])
    ui.check("全解答の箱（解答例：）", ui.ev("$('solbox').classList.contains('show')&&$('solbox').textContent.startsWith('解答例：')"), True)
    ui.check("トレイと丸ボタンは消える（場所は残す）", ui.ev("getComputedStyle(document.querySelector('#play .bottom')).visibility"), "hidden")
    ui.check("解いた後は式を動かせない", ui.ev("getComputedStyle($('expr')).pointerEvents"), "none")
    ui.check("ギブアップの入口は消える", ui.visible("dgiveup"), False)
    ui.check("結果の並びは、広告の枠の上に収まるか、列の中だけが縦に動く",
             ui.ev("(()=>{const a=$('app'),lim=a.getBoundingClientRect().top+a.clientHeight-parseFloat(getComputedStyle(a).paddingBottom);"
                   "return $('result').getBoundingClientRect().bottom<=lim+.5||a.classList.contains('dscroll')})()"), True)

    # ── ホームの値（解いた後）・入り直し・開き直し ──────────────
    ui.click("back")
    ui.check("解いた後の値", value(ui), "解いた %s　連続 1 日" % ui.ev("fmtTime(%d)" % rec["t"]))
    ui.click("m-daily")
    ui.check("入り直すと結果の画面（解き直せない）",
             ui.ev("$('play').classList.contains('done')&&!$('result').classList.contains('hide')"), True)
    ui.check("盤は自分の式", ui.ev("exprOf()"), pz["sol"])
    ui.open(PROG, now=NOW, keep_daily=True)
    ui.check("開き直しても、解いた後の値", value(ui), "解いた %s　連続 1 日" % ui.ev("fmtTime(%d)" % rec["t"]))
    # 「進捗をリセット」はデイリーの記録を消さない
    ui.ev("go('settings')")
    ui.click("reset")
    ui.click("reset")
    ui.check("本編の進捗をリセットしても、デイリーの記録は残る", ui.ev(STORE)["days"].get("31", {}).get("r"), "s")
    ui.ev("go('home')")
    ui.check("リセットの後も、ホームのデイリーは解いた後", (value(ui) or "").startswith("解いた "), True)

    # ── Web のデイリー（/daily/）で解いた日は、本編から解き直せない（同じキー）──
    web_set = {"easy": 1, "tap": 0, "dark": 1, "lang": "en"}
    web = {"v": 1, "days": {"30": {"r": "s", "t": 50, "h": 0, "sh": 1, "sent": 1},
                            "31": {"r": "s", "t": 102, "h": 1, "sh": 1, "e": pz["sol"], "sent": 1}},
           "cur": None, "set": web_set}
    ui.open(PROG, now=NOW, daily=web)
    ui.check("Web で解いた日: ホームは解いた後", value(ui), "解いた 1:42　連続 2 日")
    ui.click("m-daily")
    ui.check("Web で解いた日: 入ると結果の画面", ui.ev("$('play').classList.contains('done')"), True)
    ui.check("Web で解いた日: 3 列", [ui.text("r-time"), ui.text("r-hints"), ui.text("r-streak")], ["1:42", "1", "2"])
    ui.check("Web で解いた日: トレイは出ない", ui.ev("getComputedStyle(document.querySelector('#play .bottom')).visibility"), "hidden")
    ui.check("Web で解いた日: 本編は何も書かない（保存は Web のまま）", ui.ev(STORE), web)

    # ── 統計とカレンダー（9.0）──────────────────────────────
    ui.check("統計の入口（棒 3 本）が見える", ui.visible("dstats"), True)
    ui.check("上のバーの中央の文字は、統計の入口に重ならない",
             ui.ev("$('pday').getBoundingClientRect().right<=$('dstats').getBoundingClientRect().left"), True)
    g1 = ui.ev(G_SNAP)
    ui.click("dstats")
    ui.check("統計の画面（シート）が開く", ui.ev("SCR"), "dailystats")
    ui.check("見出し", ui.ev("document.querySelector('#dailystats h2').textContent"), "デイリーの統計")
    ui.check("3 つの数字（解いた日数・連続日数・最長）",
             ui.ev("[...document.querySelectorAll('#dstatlist .stat')].map(e=>e.querySelector('.sv').textContent+'|'+e.querySelector('.sk').textContent)"),
             ["2日|解いた日数", "2日|連続日数", "2日|最長"])
    ui.check("カレンダーは今月", ui.text("dcal-title"), "2026年11月")
    ui.check("今日（25 日）は解いた印・今日の枠・選んでいる",
             ui.ev("document.querySelector('#dcal-grid .dc[data-no=\"31\"]').className"), "dc s today sel")
    ui.check("24 日も解いた印・23 日は遊ばなかった印・26 日は押せない",
             ui.ev("['30','29'].map(n=>document.querySelector('#dcal-grid .dc[data-no=\"'+n+'\"]').className)"
                   ".concat([document.querySelectorAll('#dcal-grid .dc.x').length])"), ["dc s", "dc n", 5])
    ui.check("下の 1 行は今日の結果", ui.ev("$('dcal-line').textContent"), "#31　11月25日（水）　1:42　ヒント 1 回")
    ui.check("次の月へは行けない・前の月へは行ける", ui.ev("[$('dcal-next').disabled,$('dcal-prev').disabled]"), [True, False])
    ui.click("dcal-prev")
    ui.check("前の月（起点日の月）", [ui.text("dcal-title"), ui.ev("$('dcal-prev').disabled"),
                                 ui.ev("document.querySelectorAll('#dcal-grid .dc.x').length")], ["2026年10月", True, 25])
    ui.ev("document.querySelector('#dcal-grid .dc[data-no=\"1\"]').click()")
    ui.check("日を押すと、その日の 1 行", ui.ev("$('dcal-line').textContent"), "#1　10月26日（月）　遊んでいません")
    ui.check("統計の画面ははみ出さない", ui.ev("(()=>{const h=$('dailystats');return h.scrollWidth<=h.clientWidth})()"), True)
    ui.click("navback")
    ui.check("戻ると問題の画面（解いた後のまま）", ui.ev("SCR+'|'+$('play').classList.contains('done')"), "play|true")
    ui.check("統計を開いても本編の記録は変わらない", ui.ev(G_SNAP), g1)

    # ── 書くとき: set はそのまま・保存にある日を足す（keepOthers と同じ）──
    ui.open(PROG, now=NOW, daily={"v": 1, "days": {"29": {"r": "g", "t": None, "h": 0, "sh": 0}}, "cur": None,
                                  "set": web_set})
    ui.click("m-daily")
    # 別のタブ（Web のデイリー）が、28 日の記録を書いた
    ui.ev("(()=>{const x=%s;x.days['28']={r:'s',t:40,h:2,sh:2,sent:1};localStorage.setItem('make10.daily.v1',JSON.stringify(x))})()" % STORE)
    ui.solve(wait=1.0)
    st = ui.ev(STORE)
    ui.check("書いた後も set は Web のデイリーのまま", st.get("set"), web_set)
    ui.check("別のところで書かれた日も残る（28・29・31）", sorted(st["days"].keys()), ["28", "29", "31"])
    ui.check("足した日の送った印 sent はそのまま", st["days"]["28"].get("sent"), 1)
    ui.check("本編は Web の設定を使わない（途中の値・タップは本編の設定のまま）", ui.ev("[G.easy,tapMode]"), [False, False])
    # set の無い保存には set を書かない
    ui.open(PROG, now=NOW, daily={"v": 1, "days": {}, "cur": None})
    ui.click("m-daily")
    ui.check("set の無い保存には set を足さない", "set" in ui.ev(STORE), False)
    # 壊れた保存（形の違う日・null）は捨てて遊べる
    ui.open(PROG, now=NOW, daily={"v": 1, "days": {"31": None, "abc": {"r": "s"}, "30": {"r": "x", "h": 0}}, "cur": 5})
    ui.check("壊れた保存でも、解く前（値を出さない）", value(ui), "")
    ui.click("m-daily")
    ui.check("壊れた保存でも、問題の画面", ui.ev("SCR+'|'+$('play').classList.contains('done')"), "play|false")

    # ── ギブアップ ─────────────────────────────────────────
    ui.open(PROG, now=NOW)
    ui.click("m-daily")
    ui.click("dgiveup")
    ui.check("確認が出る", [ui.visible("gubox"), ui.ev("$('gubox').textContent")], [True, "ギブアップしますか？はいいいえ"])
    ui.click("gu-no")
    ui.check("「いいえ」で閉じて、そのまま解ける", [ui.visible("gubox"), ui.ev(STORE)["days"]], [False, {}])
    ui.click("dgiveup")
    ui.click("gu-yes")
    time.sleep(0.3)
    st = ui.ev(STORE)
    ui.check("「はい」でギブアップの記録", st["days"].get("31"), {"r": "g", "t": None, "h": 0, "sh": 0})
    ui.check("「10」の場所に「ギブアップ」", ui.ev("$('eq').className+'|'+$('eq').textContent"), "eq gaveup|ギブアップ")
    ui.check("盤は解答例", ui.ev("exprOf()"), pz["sol"])
    ui.check("時間は「—」・連続日数は 0", [ui.text("r-time"), ui.text("r-streak")], ["—", "0"])
    n_sols = len(pz["sols"])
    ui.check("全解答の箱（ほかの解き方：）は 2 本目から（無ければ出さない）",
             ui.ev("$('solbox').classList.contains('show')"), n_sols > 1)
    ui.check("ギブアップでも本編の記録は変わらない", ui.ev(G_SNAP), g0)
    ui.click("back")
    ui.check("ギブアップの後の値（9.4 で番号を外した）", value(ui), "ギブアップ")

    # ── 時間: ホームへ戻っても・開き直しても数え続ける／60 分で数え直す ──
    ui.open(PROG, now=NOW)
    ui.click("m-daily")
    s0 = ui.ev(STORE)["cur"]["start"]
    ui.click("back")
    ui.open(PROG, now=NOW + 5000, keep_daily=True)
    ui.click("m-daily")
    ui.check("開き直しても、最初に見た時刻から数える", ui.ev("startAt"), s0)
    ui.open(PROG, now=NOW, daily={"v": 1, "days": {}, "cur": {"no": 31, "start": NOW - 2 * 3600 * 1000, "h": 0, "sh": 0}})
    ui.click("m-daily")
    ui.check("60 分を過ぎた途中の分は、入った時から数え直す", ui.ev("startAt>=%d" % (NOW - 1000)), True)
    ui.check("数え直した時刻を保存する", ui.ev(STORE)["cur"]["start"] >= NOW - 1000, True)
    ui.open(PROG, now=NOW, daily={"v": 1, "days": {}, "cur": {"no": 30, "start": NOW - 60000, "h": 1, "sh": 1}})
    ui.click("m-daily")
    ui.check("前の日の途中の分は引き継がない", ui.ev("[hintUsed,shareCount,startAt>=%d]" % (NOW - 1000)), [0, 0, True])

    # ── 問題が無い日・日付が変わったとき ──────────────────────
    ui.open(PROG, now=ms(2026, 10, 20))
    ui.check("起点日より前: 問題がありません", value(ui), "問題がありません")
    ui.check("起点日より前: ロックの見た目", ui.ev("$('m-daily').classList.contains('lock')"), True)
    ui.click("m-daily")
    ui.check("起点日より前: 押しても入らない", ui.ev("SCR"), "home")
    ui.open(PROG, now=ms(2029, 10, 29))
    ui.check("列の終わりの後: 問題がありません", value(ui), "問題がありません")
    ui.open(PROG, now=ms(2026, 11, 25, 23, 59),
            daily={"v": 1, "days": {"31": {"r": "s", "t": 102, "h": 0, "sh": 0, "e": pz["sol"]}}, "cur": None})
    ui.check("23:59 は #31（解いた後）", [ui.ev("dlyToday().no"), value(ui)], [31, "解いた 1:42　連続 1 日"])
    # 開いたまま日付が変わった（アプリは閉じずに置かれる）。ホームを描き直すと次の日
    ui.ev("(()=>{const D=Date,off=%d-D.now();class FD extends D{constructor(...a){if(a.length)super(...a);else super(D.now()+off)}"
          "static now(){return D.now()+off}};window.Date=FD})()" % ms(2026, 11, 26, 0, 1))
    ui.ev("go('settings');go('home')")
    ui.check("日付が変わってからホームを描くと #32（解く前なので値を出さない）", [ui.ev("dlyToday().no"), value(ui)], [32, ""])

    # ── 英語 ───────────────────────────────────────────────
    ui.open(PROG, now=NOW, lang="en")
    ui.check("英語: 行の名前と解く前の値",
             [ui.ev("$('m-daily').querySelector('.mt').textContent"), value(ui)], ["Daily", ""])
    ui.check("英語: ホームははみ出さない", ui.ev(FITS), True)
    ui.open(PROG, now=NOW, lang="en", daily={"v": 1, "days": {"31": {"r": "g", "t": None, "h": 0, "sh": 0}}, "cur": None})
    ui.check("英語: ギブアップの後の値（9.4）", value(ui), "Gave up")
    ui.open(PROG, now=NOW, lang="en")
    ui.click("m-daily")
    ui.check("英語: 上のバー", [ui.text("pmode"), ui.text("pday")], ["Daily", "#31 · Wed, Nov 25"])
    time.sleep(1.2)
    ui.solve(wait=1.0)
    t_en = ui.ev(STORE)["days"]["31"]["t"]
    ui.check("英語: 3 列の名前と単位",
             [ui.ev("[...document.querySelectorAll('.rcol .rn')].map(e=>e.textContent).join('|')"),
              ui.text("r-hints-u"), ui.text("r-streak-u")], ["Time|Hints|Streak", "", "day"])
    # 英語の確かめ（9.3）: デイリーの画面に日本語の文字が出ない・画面の幅からはみ出す要素が無い
    ui.check("英語: 解いた後の画面に日本語が出ない・はみ出さない", ui.ev(EN_OK % "play"), [False, 0])
    ui.click("dstats")
    ui.check("英語: 統計の画面", [ui.ev("document.querySelector('#dailystats h2').textContent"),
                               ui.ev("$('dcal-line').textContent")],
             ["Daily stats", "#31 · Wed, Nov 25 · %s · 0 hints" % ui.ev("fmtTime(%d)" % t_en)])
    ui.check("英語: 統計の画面に日本語が出ない・はみ出さない", ui.ev(EN_OK % "dailystats"), [False, 0])
    ui.click("navback")
    ui.click("back")
    ui.check("英語: 解いた後の値", value(ui), "Solved %s · 1-day streak" % ui.ev("fmtTime(%d)" % t_en))
    ui.ev("go('help')")
    ui.check("英語: 遊び方のデイリーの節（9.5）", ui.ev(HELP_DAILY),
             ["Daily", "One try a day.", "Hint · Share to get one (up to 2 a day)",
              "Give up · See a solution and end the day's puzzle", "Stats · Days solved, streaks and a calendar",
              "A new puzzle every day at midnight, your local time.",
              "Daily results are counted separately from Classic. Your Classic hints are not used."])
    ui.check("英語: 遊び方のモードに 4 行目", ui.ev("document.querySelector('#help [data-i18n-html$=m4_html]').textContent"),
             "Daily — one puzzle a day, the same for everyone")
    ui.check("英語: 遊び方に日本語が出ない・はみ出さない", ui.ev(EN_OK % "help"), [False, 0])

    # ── ヒントと共有（9.1）。本編のヒントの残数（G）は減らさない ──────
    ui.open(PROG, now=NOW)
    ui.click("m-daily")
    # 共有は、共有画面を使わずクリップボードへ（ハーネスで差し替えて中身を取る）
    ui.ev("Object.defineProperty(navigator,'share',{value:undefined,configurable:true});"
          "Object.defineProperty(navigator,'clipboard',{value:{writeText:async s=>{window.__CP=s}},configurable:true})")
    g2 = ui.ev(G_SNAP)
    ui.check("ヒントの丸ボタンと共有ボタンが見える", [ui.visible("hint"), ui.visible("share")], [True, True])
    ui.check("もらう前は残り回数を出さない", [ui.text("hintstock"), ui.text("hintlabel")], ["", "ヒント（残り 0 回）"])
    ui.click("hint")
    ui.check("もらう前に押すと知らせ", ui.ev("$('hintbox').textContent"), "友達に出題するとヒントがもらえます")
    ui.click("hint-share")
    time.sleep(0.3)
    ui.check("知らせから共有すると、そのまま 1 回目のヒント",
             ui.ev("$('hintbox').textContent.startsWith('使う演算：')"), True)
    ui.check("共有文は 4 つの数字と URL（答えは入れない）",
             ui.ev("__CP"), "Make10 DAILY #31\n%s\nこの 4 つの数字で 10 を作れる？\nhttps://make10.app/daily/" % " ".join(pz["id"]))
    ui.check("コピーしたら知らせる", ui.toasts()[-1:], ["コピーしました"])
    st = ui.ev(STORE)["cur"]
    ui.check("途中の分にヒント 1 回・共有 1 回を保存", [st["h"], st["sh"]], [1, 1])
    ui.click("share")
    time.sleep(0.3)
    ui.check("上のバーの共有でもう 1 回もらえる（残り 1）", ui.text("hintstock"), "1")
    ui.click("hint")
    ui.check("2 回目のヒント（括弧を使うか）", ui.ev("/括弧：/.test($('hintbox').textContent)"), True)
    ui.check("2 回目を出している間は無効の見た目", ui.ev("$('hint').getAttribute('aria-disabled')"), "true")
    ui.check("デイリーのヒントを使っても、本編のヒントの残数・段階は変わらない", ui.ev(G_SNAP), g2)
    ui.check("本編のヒントの残数は 57 のまま", ui.ev("G.hintStock"), 57)
    time.sleep(1.2)
    ui.solve(wait=1.0)
    rec = ui.ev(STORE)["days"]["31"]
    ui.check("記録にヒント 2 回・共有 2 回", [rec["h"], rec["sh"]], [2, 2])
    ui.check("3 列のヒントは 2 回", [ui.text("r-hints"), ui.text("r-hints-u")], ["2", "回"])
    ui.check("解いた後はヒントの箱を閉じる", ui.visible("hintbox"), False)
    ui.check("結果を共有のボタンが見える", ui.visible("rshare"), True)
    ui.click("rshare")
    time.sleep(0.3)
    ui.check("解いた後の共有文（時間。ヒントの回数と連続日数は入れない）",
             ui.ev("__CP"), "Make10 DAILY #31\n%s → 10  ⏱ %s\nあなたは何秒？\nhttps://make10.app/daily/"
             % (" ".join(pz["id"]), ui.ev("fmtTime(%d)" % rec["t"])))
    ui.check("解いた後の共有は記録の共有の回数に足す", ui.ev(STORE)["days"]["31"]["sh"], 3)
    ui.check("解いても本編のヒントの残数は変わらない", ui.ev("G.hintStock"), 57)
    # 本編へ戻ると、丸ボタンは本編の残数に描き直される・本編のヒントは本編の決まりで減る
    ui.ev("start('course')")
    ui.check("本編へ戻ると、丸ボタンの数字は本編の残数・無効の見た目ではない",
             [ui.text("hintstock"), ui.ev("$('hint').getAttribute('aria-disabled')==='true'")], ["57", False])
    ui.check("本編へ戻ると、デイリーのヒントの箱は出ていない", ui.ev("$('hintbox').textContent.includes('使う演算')"), False)
    ui.click("hint")
    ui.check("本編の丸ボタンは本編の決まり（1 つ使う）", ui.ev("G.hintStock"), 56)
    ui.ev("window.__CP=''")
    ui.click("share")
    time.sleep(0.3)
    ui.check("本編の共有ボタンは本編の共有（デイリーの共有文ではない）", [ui.ev("__CP.includes('DAILY')"), ui.ev("__CP.length>0")],
             [False, True])

    # ── みんなの結果（9.2）。送り先は本物でなく、ハーネスが受け取る（ui.open(agg=…)）──
    demo = {"status": 200, "body": {"n": 31, "s": 412, "g": 96, "s0": 268, "b": [38, 121, 147, 82, 24]}}
    ui.open(PROG, now=NOW, agg=demo)
    ui.click("m-daily")
    ui.check("解く前は何も送らない", ui.ev("__AGG"), [])
    g3 = ui.ev(G_SNAP)
    time.sleep(1.2)
    ui.solve(wait=1.2)
    rec = ui.ev(STORE)["days"]["31"]
    ui.check("解いた瞬間に 1 回だけ送る（POST・4 つだけ）",
             ui.ev("__AGG.map(x=>x.method+' '+x.url+' '+x.body)"),
             ['POST https://api.make10.app/r {"n":31,"r":"s","t":%d,"h":0}' % rec["t"]])
    ui.check("送れたら送った印", rec.get("sent"), 1)
    ui.check("みんなの結果が出る（正解率・ヒントなし）", [ui.visible("aggbox"),
             ui.ev("[...document.querySelectorAll('#aggbox .ac b')].map(e=>e.textContent)")], [True, ["81%", "65%"]])
    ui.check("棒に本編の進捗の棒（.bar）の様式が掛からない: 面なし・はみ出しを隠さない・帯の名前が 1 列にそろい箱の中（9.3）",
             ui.ev("(()=>{const box=$('aggbox').getBoundingClientRect(),bs=[...document.querySelectorAll('#aggbox .bar')],"
                   "sp=bs.map(b=>b.querySelector('span').getBoundingClientRect());"
                   "return [bs.every(b=>{const c=getComputedStyle(b);return c.backgroundColor==='rgba(0, 0, 0, 0)'&&c.overflow==='visible'}),"
                   "new Set(sp.map(r=>Math.round(r.bottom))).size,sp.every(r=>r.bottom<=box.bottom+.5&&r.height>0),"
                   "bs.map(b=>b.querySelector('span').textContent).join(' ')]})()"),
             [True, 1, True, "<0:30 <1:00 <2:00 <5:00 5:00+"])
    ui.check("いちばん多い帯（<2:00）の棒が、いちばん高い",
             ui.ev("(()=>{const h=[...document.querySelectorAll('#aggbox .bar i')].map(i=>i.getBoundingClientRect().height);"
                   "return h.indexOf(Math.max(...h))})()"), 2)
    ui.check("自分のいる帯は 1 つ（30 秒未満）", ui.ev("[...document.querySelectorAll('#aggbox .bar')].findIndex(e=>e.classList.contains('me'))"), 0)
    ui.check("結果の並びは、広告の枠の上に収まるか、列の中だけが縦に動く",
             ui.ev("(()=>{const a=$('app'),lim=a.getBoundingClientRect().top+a.clientHeight-parseFloat(getComputedStyle(a).paddingBottom);"
                   "return $('result').getBoundingClientRect().bottom<=lim+.5||a.classList.contains('dscroll')})()"), True)
    ui.check("集計を送っても本編の記録は変わらない", ui.ev(G_SNAP), g3)
    ui.ev("Object.defineProperty(navigator,'share',{value:undefined,configurable:true});"
          "Object.defineProperty(navigator,'clipboard',{value:{writeText:async s=>{window.__CP=s}},configurable:true})")
    ui.click("rshare")
    time.sleep(0.3)
    ui.check("共有文に、みんなの中の位置（自分より遅い帯の人 ÷ 解いた人）", ui.ev("__CP.split('\\n')[2]"), "解いた人の 90% より速い")
    # 入り直す・開き直す: 送った日は読み直す（GET。送り直さない）
    ui.open(PROG, now=NOW, agg=demo, keep_daily=True)
    ui.click("m-daily")
    time.sleep(0.5)
    ui.check("開き直すと読み直す（GET だけ）", ui.ev("__AGG.map(x=>x.method+' '+x.url)"), ["GET https://api.make10.app/r?n=31"])
    ui.check("開き直してもみんなの結果が出る", ui.visible("aggbox"), True)
    # 30 件未満は「集計中」
    ui.open(PROG, now=NOW, agg={"status": 200, "body": {"n": 31, "s": 20, "g": 9, "s0": 3, "b": [1, 5, 9, 4, 1]}}, keep_daily=True)
    ui.click("m-daily")
    time.sleep(0.5)
    ui.check("30 件未満は「集計中」", ui.ev("$('aggbox').querySelector('.ap')&&$('aggbox').querySelector('.ap').textContent"), "集計中")
    # 形の違う返事は出さない
    ui.open(PROG, now=NOW, agg={"status": 200, "body": {"n": 31, "s": -1, "g": 0, "s0": 0, "b": [0, 0, 0, 0, 0]}}, keep_daily=True)
    ui.click("m-daily")
    time.sleep(0.5)
    ui.check("形の違う返事は出さない", ui.visible("aggbox"), False)
    # 通信できない: 印を付けない → 次に入ったときに送り直す
    ui.open(PROG, now=NOW)
    ui.click("m-daily")
    time.sleep(1.2)
    ui.solve(wait=1.2)
    ui.check("通信できないとき: みんなの結果は出さない・送った印を付けない",
             [ui.visible("aggbox"), ui.ev(STORE)["days"]["31"].get("sent"), len(ui.ev("__AGG"))], [False, None, 1])
    ui.open(PROG, now=NOW, agg=demo, keep_daily=True)
    ui.click("m-daily")
    time.sleep(0.5)
    ui.check("次に入ったときに送り直す", [ui.ev("__AGG.map(x=>x.method)"), ui.ev(STORE)["days"]["31"].get("sent")], [["POST"], 1])
    # 3 日より前の送れていない日は、送らずに印を付ける。昨日の分は送り直す
    ui.open(PROG, now=NOW, agg=demo, daily={"v": 1, "cur": None, "days": {
        "27": {"r": "s", "t": 40, "h": 0, "sh": 0}, "30": {"r": "g", "t": None, "h": 1, "sh": 1}}})
    ui.click("m-daily")
    time.sleep(0.5)
    st = ui.ev(STORE)["days"]
    ui.check("3 日より前（#27）は送らずに印・昨日（#30）は送る（ギブアップは時間 null）",
             [st["27"].get("sent"), st["30"].get("sent"), ui.ev("__AGG.map(x=>x.body)")],
             [1, 1, ['{"n":30,"r":"g","t":null,"h":1}']])
    # サーバーが「もう受け取らない日」（400 range）と断ったら、印を付けて送り直さない
    ui.open(PROG, now=NOW, agg={"status": 400, "body": {"e": "range"}})
    ui.click("m-daily")
    ui.click("dgiveup")
    ui.click("gu-yes")
    time.sleep(0.5)
    ui.check("400 range で断られたら印を付ける・みんなの結果は出さない",
             [ui.ev(STORE)["days"]["31"].get("sent"), ui.visible("aggbox")], [1, False])

    # ── ほかのモードへ移ると、デイリーの部品は片付く ──────────────
    ui.ev("start('course')")
    ui.check("本編に戻ると、結果の並び・ギブアップの入口・日付の行は出ない",
             [ui.visible("result"), ui.visible("dgiveup"), ui.visible("pday"), ui.visible("pcode"),
              ui.ev("$('play').classList.contains('done')||$('play').classList.contains('dplay')")],
             [False, False, False, True, False])
    ui.check("本編に戻ると、共有とヒントの丸ボタンが見える", [ui.visible("share"), ui.visible("hint")], [True, True])
    ui.check("本編の問題番号（画面の呼び名はクラシック。9.4）", ui.text("pmode"), "クラシック 138/1000")
    # 遊び方（9.3）
    ui.ev("go('help')")
    ui.check("遊び方のデイリーの節（9.5 で Web の行を写して作り直した）", ui.ev(HELP_DAILY),
             ["デイリー", "1 日 1 回だけ解けます", "ヒント：共有でもらえます（1 日 2 回まで）",
              "ギブアップ：解答例を見て、その日を終えます", "統計：解いた日数・連続日数とカレンダー",
              "毎日 0 時（端末の時刻）に新しい問題になります。",
              "記録はクラシックとは別に数えます。クラシックのヒントは減りません"])
    ui.check("遊び方のモードに 4 行目", ui.ev("document.querySelector('#help [data-i18n-html$=m4_html]').textContent"),
             "デイリー ・・・ 1 日 1 問。みんなが同じ問題を解きます")
    ui.check_no_errors("デイリーを回しても JS エラー 0")
