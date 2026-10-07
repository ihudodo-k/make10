# -*- coding: utf-8 -*-
"""言語の決め方と保存（7.6・GAME-SPEC 13 章）。

  1. 既定は「自動」: navigator.language が ja で始まれば日本語、それ以外は英語
  2. 設定で選んだ値（G.lang = auto / ja / en）が自動より優先し、保存される
  3. ?lang=ja / ?lang=en は保存してある値より優先し、G.lang を書き換えない
  4. <html lang> は表示している言語
  5. 設定の行「言語 / Language」は、押すたびに 自動 → 日本語 → English と回る。右端に今の値
  6. 英語が無いキーは日本語で出る（7.7 で英語を全部入れたので、キーを 1 つ消して見る）
  7. 切り替えたとき、描き済みの文も引き直す（問題画面の状態は保つ）
  8. 「進捗をリセット」では言語を戻さない

ほかのケースは ui.open() の既定（?lang=ja）で日本語に固定して回る。ここだけ lang=None で開く。
"""
import json
import time

NAME = "言語の決め方と保存"

KEY = "make10.progress.v4"
STATE = "[LANG,document.documentElement.lang,G.lang]"


def stored(ui):
    time.sleep(0.3)                     # save() は 150ms 後に書く
    return json.loads(ui.ev("localStorage.getItem(%s)" % json.dumps(KEY)) or "{}")


def run(ui):
    # ── 1. 自動（保存データなし）
    for nav, want in [("ja", "ja"), ("ja-JP", "ja"), ("JA-jp", "ja"),
                      ("en-US", "en"), ("fr-FR", "en"), ("zh-Hans-JP", "en"), ("", "en")]:
        ui.open(lang=None, nav=nav)
        ui.check("自動: 端末の言語 %r なら %s（<html lang> も同じ・G.lang は auto）" % (nav, want),
                 ui.ev(STATE), [want, want, "auto"])

    # ── 2. 選んだ値が自動より優先する
    ui.open({"ci": 0, "lang": "en"}, lang=None, nav="ja-JP")
    ui.check("保存が en なら、端末が日本語でも英語", ui.ev(STATE), ["en", "en", "en"])
    ui.open({"ci": 0, "lang": "ja"}, lang=None, nav="en-US")
    ui.check("保存が ja なら、端末が英語でも日本語", ui.ev(STATE), ["ja", "ja", "ja"])
    ui.open({"ci": 0, "lang": "auto"}, lang=None, nav="en-US")
    ui.check("保存が auto なら端末の言語", ui.ev(STATE), ["en", "en", "auto"])

    # ── 3. ?lang= は保存より優先し、G.lang を書き換えない
    ui.open({"ci": 0, "lang": "ja"}, lang="en", nav="ja-JP")
    ui.check("?lang=en: 保存が ja・端末が日本語でも英語。G.lang は ja のまま",
             ui.ev(STATE), ["en", "en", "ja"])
    ui.ev("G.vib=!G.vib;save()")        # ほかの理由で保存が走っても lang は変わらない
    ui.check("?lang=en のまま保存しても、保存される lang は ja", stored(ui).get("lang"), "ja")
    ui.open({"ci": 0, "lang": "en"}, lang="ja", nav="en-US")
    ui.check("?lang=ja: 保存が en・端末が英語でも日本語。G.lang は en のまま",
             ui.ev(STATE), ["ja", "ja", "en"])
    ui.open(lang="xx", nav="ja-JP")
    ui.check("?lang= が知らない値なら無視する（自動で決まる）", ui.ev(STATE), ["ja", "ja", "auto"])

    # ── 6. 英語が無いキーは日本語で出る
    ui.open(lang="en")
    ui.check("英語の辞書の入れ物がある（共通の塊・本編だけの塊）",
             ui.ev("[typeof STR_CORE.en,typeof STR_APP.en]"), ["object", "object"])
    ui.check("英語にあるキーは、すべて日本語の辞書にもある",
             ui.ev("[...Object.keys(STR_CORE.en).filter(k=>!(k in STR_CORE.ja)),"
                   "...Object.keys(STR_APP.en).filter(k=>!(k in STR_APP.ja))]"), [])
    ui.check("英語のキーがあるうちは英語の文が出る",
             ui.ev('[t("home.free"),t("read.solved")]'), ["Free Play", "Solved!"])
    ui.ev("delete STR_APP.en['home.free'];delete STR_CORE.en['read.solved'];"
          "delete STR_APP.en['home.total'];applyLang(true)")
    ui.check("英語が無いキーは日本語の文で出る（本編だけの塊・共通の塊。キーの数は変わらない）",
             ui.ev('[t("home.free"),t("read.solved"),Object.keys(STR).length===Object.keys({...STR_CORE.ja,...STR_APP.ja}).length]'),
             ["フリープレイ", "正解", True])
    ui.check("英語が無いキーは画面にも日本語で出て、あるキーは英語のまま",
             ui.ev("[$('m-free').querySelector('.mt').textContent,$('m-course').querySelector('.mt').textContent]"),
             ["フリープレイ", "Classic"])
    ui.check("英語でも、英語が無い複数形の文を引ける（日本語の文が出る）",
             ui.ev('[t("home.total",{n:1}),t("home.total",{n:2})]'), ["累計 1 問", "累計 2 問"])

    # ── 5. 設定の行
    ui.open(lang=None, nav="ja-JP")
    ui.click("gear")
    ui.check("設定: 行が見えている", ui.visible("t-lang"), True)
    ui.check("設定: 項目名は「言語 / Language」",
             ui.ev("$('t-lang').firstElementChild.textContent"), "言語 / Language")
    ui.check("設定: 右端の値は「自動（日本語）」（今どちらの言語かを括弧で。7.7）", ui.text("t-lang-v"), "自動（日本語）")
    ui.check("設定:「その他」の節のいちばん上（次が遊び方）",
             ui.ev("[$('t-lang').parentElement===$('go-help').parentElement,"
                   "$('t-lang').nextElementSibling.id,$('t-lang').previousElementSibling]"),
             [True, "go-help", None])
    ui.check("設定: ほかの行と同じ部品（.toggle・高さ 48px・左右の端が同じ）。スイッチも矢印も持たない",
             ui.ev("(()=>{const a=$('t-lang').getBoundingClientRect(),b=$('go-help').getBoundingClientRect();"
                   "return [$('t-lang').className,Math.round(a.height),a.left===b.left,a.right===b.right,"
                   "$('t-lang').querySelectorAll('.sw,.chev').length]})()"),
             ["toggle", 48, True, True, 0])
    ui.check("設定: 値は副次色（矢印と同じ色）・13px・右端が矢印の右端と同じ・行の中で上下の中央",
             ui.ev("(()=>{const v=$('t-lang-v'),c=$('go-help').querySelector('.chev'),s=getComputedStyle(v),"
                   "a=v.getBoundingClientRect(),b=c.getBoundingClientRect(),r=$('t-lang').getBoundingClientRect();"
                   "return [s.color===getComputedStyle(c).color,s.fontSize,Math.abs(a.right-b.right)<0.5,"
                   "Math.abs((a.top+a.bottom)/2-(r.top+r.bottom)/2)<0.5]})()"),
             [True, "13px", True, True])
    ui.check("設定: 項目名と値が重ならず、1 行に収まる",
             ui.ev("(()=>{const l=$('t-lang').firstElementChild.getBoundingClientRect(),"
                   "v=$('t-lang-v').getBoundingClientRect();return [l.right<v.left,l.height<24,v.height<24]})()"),
             [True, True, True])
    before = ui.ev("$('settings').innerText")
    ui.click("t-lang")
    ui.check("1 回押すと「日本語」（G.lang は ja）", [ui.text("t-lang-v")] + ui.ev(STATE),
             ["日本語", "ja", "ja", "ja"])
    ui.click("t-lang")
    ui.check("2 回押すと「English」（G.lang は en・<html lang> も en）",
             [ui.text("t-lang-v")] + ui.ev(STATE), ["English", "en", "en", "en"])
    ui.check("英語のときも項目名は「言語 / Language」",
             ui.ev("$('t-lang').firstElementChild.textContent"), "言語 / Language")
    ui.check("英語にすると、設定のほかの文はその場で英語になる（見出し・スイッチの名前・版）",
             ui.ev("[document.querySelector('#settings h2').textContent,$('t-vib').firstElementChild.textContent,"
                   "$('appver').textContent===t('settings.version',{v:APP_VERSION}),$('appver').textContent.startsWith('Version ')]"),
             ["Settings", "Vibration", True, True])
    ui.check("選んだ値が保存される", stored(ui).get("lang"), "en")
    ui.click("t-lang")
    ui.check("3 回押すと「自動」に戻る（端末の言語になる）",
             [ui.text("t-lang-v")] + ui.ev(STATE), ["自動（日本語）", "ja", "ja", "auto"])
    ui.check("日本語に戻ると、設定の文も元に戻る", ui.ev("$('settings').innerText"), before)
    ui.check("自動に戻したことも保存される", stored(ui).get("lang"), "auto")
    ui.check("行を押すとボタンの振動が 1 回", ui.ev(
        "(()=>{const o=navigator.vibrate,log=[];navigator.vibrate=function(x){log.push(x);return true};"
        "G.vib=true;$('t-lang').click();navigator.vibrate=o;return log.length})()"), 1)
    ui.ev("G.lang='auto';applyLang(true)")

    # ── 8. 進捗をリセットしても言語は戻さない
    ui.ev("G.ci=5;G.cleared=5;G.lang='en';G.scoreOn=true;save();applyLang(true)")
    ui.click("reset")
    ui.click("reset")
    ui.check("リセット: 進捗は消え、言語と設定のスイッチは残る",
             ui.ev("[G.ci,G.cleared,G.lang,G.scoreOn,LANG]"), [0, 0, "en", True, "en"])
    ui.check("リセットのあと、設定の行は「English」のまま", ui.text("t-lang-v"), "English")
    ui.check("リセットのあと保存される lang も en", stored(ui).get("lang"), "en")

    # ── 7. 切り替えたとき、描き済みの文も引き直す
    ui.open(lang=None, nav="ja-JP")
    ui.click("m-course")
    ui.ev("put('+',1);render()")
    ui.click("hint")
    snap = "JSON.stringify([codeOf(cur),S.toks,moves,t0,hintLv,G.hintStock])"
    s0 = ui.ev(snap)
    ui.check("切り替える前: 問題番号とヒントは日本語",
             [ui.text("pmode"), ui.ev("$('hintbox').textContent.includes('使う記号：')")],
             ["本編 1/1000", True])
    ui.click("menu")
    ui.click("t-lang")
    ui.click("t-lang")
    ui.check("英語に切り替えると、設定の外の描き済みの文も英語になる（ホーム）",
             ui.ev("[$('m-free').querySelector('.mt').textContent,$('ctot').textContent]"),
             ["Free Play", "Solved: 0"])
    ui.check("複数形は n で選ぶ（1 のときだけ単数）",
             ui.ev('[t("win.points",{n:1}),t("win.points",{n:2}),t("win.points",{n:0}),'
                   't("unit.puzzle",{n:1}),t("unit.puzzle",{n:1000}),t("unit.times",{n:1}),t("unit.times",{n:94})]'),
             ["1 pt", "2 pts", "0 pts", "puzzle", "puzzles", "hint", "hints"])
    ui.click("navback")
    ui.check("問題画面に戻ると、問題番号とヒントが英語になっている",
             [ui.ev("SCR"), ui.text("pmode"), ui.ev("$('hintbox').textContent.includes('Uses')"),
              ui.ev("$('hintbox').textContent.includes('使う記号：')")],
             ["play", "Classic 1/1000", True, False])
    ui.check("問題・置いた記号・手数・時間・ヒントの段階と残数は切り替える前と同じ", ui.ev(snap), s0)
    ui.click("menu")
    ui.click("t-lang")
    ui.click("t-lang")
    ui.click("navback")
    ui.check("日本語に戻すと、文も元に戻る",
             [ui.ev("LANG"), ui.text("pmode"), ui.ev("$('hintbox').textContent.includes('使う記号：')")],
             ["ja", "本編 1/1000", True])
    ui.check_no_errors()
