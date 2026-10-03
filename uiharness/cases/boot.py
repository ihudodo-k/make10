# -*- coding: utf-8 -*-
"""起動と 5 画面の巡回。左上＝戻る／右上＝設定の出し分け（GAME-SPEC 5-0）も見る。"""

NAME = "起動と画面の巡回"


def run(ui):
    ui.open()                                   # 保存データ無しで起動
    ui.check_no_errors("起動で JS エラーが出ない")
    ui.check("ホームで始まる", ui.ev("SCR"), "home")
    ui.check("本編の件数がホームに出る", ui.text("cnum"), "0 / 1000 問")
    ui.check("進捗 0%", ui.text("cpct"), "0.0")
    ui.check("ホームに NaN / undefined が出ない",
             ui.ev("/NaN|undefined/.test($('home').textContent)"), False)
    # ── 左上・右上の出し分け ───────────────────────────────
    ui.check("ホーム: 左上の戻るは出ない", ui.visible("navback"), False)
    ui.check("ホーム: 右上の三本線が出る", ui.visible("gear"), True)
    ui.click("gear")
    ui.check("設定が開く", ui.ev("SCR"), "settings")
    ui.check("設定: 左上に戻るが出る", ui.visible("navback"), True)
    ui.check("設定: 右上は空", ui.visible("gear"), False)
    ui.check("バージョン表示", ui.text("appver"),
             "バージョン " + ui.ev("APP_VERSION") + "（試作）")
    # ── 設定 → 遊び方 → 戻る → 統計 → 戻る → 戻る ─────────
    ui.ev("go('help')")
    ui.check("遊び方が開く", ui.ev("SCR"), "help")
    ui.check("遊び方: 左上に戻るが出る", ui.visible("navback"), True)
    ui.click("navback")
    ui.check("遊び方から戻ると設定", ui.ev("SCR"), "settings")
    ui.ev("go('stats')")
    ui.check("統計が開く", ui.ev("SCR"), "stats")
    ui.check("統計に NaN が出ない",
             ui.ev("/NaN/.test($('stats').textContent)"), False)
    ui.check("履歴が空なら案内が出る",
             ui.ev("$('stathist').textContent.indexOf('まだありません')>=0"), True)
    ui.click("navback")
    ui.check("統計から戻ると設定", ui.ev("SCR"), "settings")
    ui.click("navback")
    ui.check("設定から戻るとホーム", ui.ev("SCR"), "home")
    # ── 問題画面のナビ ────────────────────────────────────
    ui.ev("start('course')")
    ui.check("本編が始まる", ui.ev("SCR"), "play")
    ui.check("問題画面: 左上の戻るは出ない", ui.visible("navback"), False)
    ui.check("問題画面: 右上の三本線（#gear）は出ない", ui.visible("gear"), False)
    ui.check("問題画面: ヘッダの #back が出る", ui.visible("back"), True)
    ui.check("問題画面: ヘッダの #menu が出る", ui.visible("menu"), True)
    ui.check("問題画面はスクロールしない", ui.scrolls(), False)
    # 6.5: 何も置いていないときの案内文「演算子を式の中へ」は出さない（#eq も #sub も空）
    ui.check("問題画面: 読み出し行は空（案内文を出さない）",
             [ui.text("eq"), ui.text("sub")], ["", ""])
    ui.check("問題画面: 「演算子を式の中へ」がどこにも見えない",
             ui.ev("$('play').innerText.includes('演算子を式の中へ')"), False)
    ui.check("トレイの見出しは今のまま", ui.text("trayhead"), "つまんで式の中へ")
    ui.ev("G.easy=true; render()")
    ui.check("途中の値を表示する設定でも #sub に案内文を出さない", ui.text("sub"), "")
    ui.ev("G.easy=false; render()")
    # 設定へ出入りしても問題が保たれる（3.1 の回帰）
    code = ui.ev("codeOf(cur)")
    ui.click("menu")
    ui.check("問題画面から設定へ", ui.ev("SCR"), "settings")
    ui.click("navback")
    ui.check("設定から戻ると問題画面", ui.ev("SCR"), "play")
    ui.check("問題が変わっていない", ui.ev("codeOf(cur)"), code)
    ui.check("問題画面はスクロールしない（戻った後）", ui.scrolls(), False)
    ui.click("back")
    ui.check("#back でホームへ", ui.ev("SCR"), "home")
    ui.check_no_errors("巡回のあとも JS エラー 0")
    home_total(ui)


# ホームの本編カードと各行の位置・大きさ（累計点数を消してもレイアウトが崩れない）
HOME_RECTS = ("(()=>{const r=q=>document.querySelector(q).getBoundingClientRect(),"
              "f=v=>Math.round(v*10)/10,c=r('#ctot');"
              "return ['#home .card','#cnum','#m-course','#m-chal','#m-free'].map(q=>{const b=r(q);"
              "return [b.left,b.top,b.width,b.height].map(f).join()}).concat([[c.top,c.height].map(f).join()])"
              ".join('|')})()")


def home_total(ui):
    """ホームの累計（6.6）: 累計点数は出さない。クリア数は残す。
    点数の記録（G.best）は保存データに残る（あとで表示を戻せるように）"""
    ui.open({"ci": 0, "cleared": 0})
    off = ui.ev(HOME_RECTS)
    code = ui.ev("codeOf(COURSE[0])")
    ui.open({"ci": 0, "cleared": 5, "scoreOn": True, "best": {code: 1234}})
    ui.check("ホームの累計はクリア数だけ（点数表示オンでも）", ui.text("ctot"), "累計 5 問")
    ui.check("ホームに累計点数が出ない",
             ui.ev(r"/\d[\d,]* 点/.test($('home').innerText)"), False)
    ui.check("累計は 1 行のまま・本編カードとモードの行の位置と大きさが点数表示オフと同じ",
             ui.ev(HOME_RECTS), off)
    ui.check("ホームはスクロールしない（横）",
             ui.ev("$('home').scrollWidth<=$('home').clientWidth"), True)
    ui.check("点数の記録は残っている（G.best）", ui.ev("G.best[%r]" % code), 1234)
    ui.check("累計点数の計算も残っている（totalScore）", ui.ev("totalScore()"), 1234)
    # 解くと点数は今までどおり記録され、保存データにも入る
    ui.ev("start('course'); loadPuzzle(COURSE[1])")
    ui.solve()
    code2 = ui.ev("codeOf(cur)")
    ui.ev("go('home')")
    ui.check("解いた問題の点数も記録される", ui.ev("G.best[%r]>0" % code2), True)
    ui.check("保存データ（localStorage）に点数が残っている",
             ui.ev("(()=>{const b=JSON.parse(localStorage.getItem(%r)).best;"
                   "return [b[%r],b[%r]>0]})()" % ("make10.progress.v4", code, code2)),
             [1234, True])
    ui.check("解いたあともホームの累計はクリア数だけ", ui.text("ctot"), "累計 6 問")
    ui.check_no_errors("ホームの累計で JS エラー 0")
    stats_scores(ui)


# 統計画面の行: [一覧の行の見出し, 一覧の各行の高さ, 履歴の各行の高さ, 履歴の右端の文字]
STATS_ROWS = ("(()=>{const f=v=>Math.round(v*10)/10,"
              "kv=[...$('statlist').querySelectorAll('.kv')],h=[...$('stathist').querySelectorAll('.toggle')];"
              "return [kv.map(e=>e.firstElementChild.textContent),kv.map(e=>f(e.getBoundingClientRect().height)),"
              "h.map(e=>f(e.getBoundingClientRect().height)),h.map(e=>e.children.length>1?e.lastElementChild.textContent:'')]})()")


def stats_scores(ui):
    """統計画面（6.6。GAME-SPEC 9-2）: 星・累計スコア・履歴の「N 点」を出さない
    （点数を出すのは点数表示オンの正解カードだけ）。
    点数と星の記録（best / hist の p・st）は保存データに残る"""
    code = ui.ev("codeOf(COURSE[0])")
    code2 = ui.ev("codeOf(COURSE[1])")
    hist = [{"c": code, "d": 3, "s": 12, "m": "course", "p": 75, "st": 3},
            {"c": code2, "d": 4, "s": 40, "m": "course", "p": 60, "st": 1}]
    base = {"ci": 2, "cleared": 2, "best": {code: 75, code2: 60}, "hist": hist,
            "stats": {"n": 2, "sec": 52, "best": 12, "band": {"3-8": 2}}}
    ui.open(dict(base, scoreOn=False))
    ui.ev("go('stats')")
    off = ui.ev(STATS_ROWS)
    ui.open(dict(base, scoreOn=True))
    ui.ev("go('stats')")
    on = ui.ev(STATS_ROWS)
    ui.check("統計: 一覧に「累計スコア」の行が無い（点数表示オンでも）",
             "累計スコア" in on[0] or "累計スコア" in ui.ev("$('stats').innerText"), False)
    ui.check("統計: 一覧の行は点数表示オフと同じ 6 行", [on[0], len(on[0])], [off[0], 6])
    ui.check("統計: 一覧の各行の高さが点数表示オフと同じ", on[1], off[1])
    ui.check("統計: 画面のどこにも星（★☆）が無い", ui.ev("/[★☆]/.test($('stats').innerText)"), False)
    ui.check("統計: 履歴の右端に何も出さない（子は左の 1 つだけ）", on[3], ["", ""])
    ui.check("統計: 履歴のどこにも点数（「N 点」）が出ない",
             ui.ev(r"/\d+ 点/.test($('stathist').innerText)"), False)
    ui.check("統計: 履歴の左の並び（番号・難易度・秒）は今までどおり",
             ui.ev("[...$('stathist').querySelectorAll('.toggle')].map(e=>e.textContent)"),
             [ui.ev("COURSE[0].id") + "　難易度 3・12秒", ui.ev("COURSE[1].id") + "　難易度 4・40秒"])
    ui.check("統計: 履歴の各行が横にはみ出さない",
             ui.ev("[...$('stathist').querySelectorAll('.toggle')].every(e=>e.scrollWidth<=e.clientWidth)"),
             True)
    ui.check("統計: 履歴の行の高さが点数表示オフと同じ", on[2], off[2])
    ui.check("統計: 横にはみ出さない",
             ui.ev("$('stats').scrollWidth<=$('stats').clientWidth"), True)
    ui.check("統計: 点数・星の記録は G に残っている",
             ui.ev("[G.best[%r],G.hist[0].p,G.hist[0].st,G.hist[1].st,totalScore()]" % code),
             [75, 75, 3, 1, 135])
    # 問題を解いても点数と星は今までどおり記録され、保存データに入る
    ui.ev("start('course'); loadPuzzle(COURSE[2])")
    ui.solve()
    ui.ev("go('stats')")
    ui.check("統計: 解いたあとも星は出ない", ui.ev("/[★☆]/.test($('stats').innerText)"), False)
    ui.check("統計: 保存データ（localStorage）に点数と星が残っている",
             ui.ev("(()=>{const s=JSON.parse(localStorage.getItem(%r)),h=s.hist[0];"
                   "return [s.best[%r],h.p>0,[1,2,3].includes(h.st),s.hist.length]})()"
                   % ("make10.progress.v4", code)),
             [75, True, True, 3])
    ui.check_no_errors("統計画面で JS エラー 0")
