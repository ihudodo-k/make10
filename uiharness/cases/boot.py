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
