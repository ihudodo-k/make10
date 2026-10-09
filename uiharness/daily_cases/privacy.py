# -*- coding: utf-8 -*-
"""プライバシーポリシー（D0.6。DAILY-SPEC 17-6）。

- デイリーの遊び方のいちばん下に、プライバシーポリシーへのリンクがあること（両方の言語）
- リンクの先（docs/privacy/index.html）が開けて、日本語と英語の両方・書く内容・問い合わせ先がそろっていること
- スクリプトを持たないこと・3 画面で横にはみ出さないこと
"""
import re
import time

from uiharness import daily_ui as dui

NAME = "プライバシーポリシー"

MAIL = "make10alfa@gmail.com"
READY = "complete|undefined"


def run(ui):
    start, rows = dui.page_data()

    # ══ 遊び方のいちばん下のリンク ══
    for lang, text in (("ja", "プライバシーポリシー"), ("en", "Privacy Policy")):
        ui.open(date=start.isoformat(), lang=lang)
        ui.ev("dhelp.click()")
        time.sleep(0.2)
        ui.check("%s: 遊び方のいちばん下に、プライバシーポリシーへのリンク" % lang,
                 ui.ev("(function(){const a=document.getElementById('dprivacy');const r=a.getBoundingClientRect(),"
                       "b=dhelpbody.getBoundingClientRect(),ps=[...dhelpbody.querySelectorAll('p:not(.hlink)')];"
                       "return [a.textContent,new URL(a.href).pathname,a.target,a.rel,"
                       "r.top>=ps[ps.length-1].getBoundingClientRect().bottom,r.bottom<=b.bottom+0.5&&r.right<=b.right,"
                       "dhelpbody.scrollHeight<=dhelpbody.clientHeight+1]})()"),
                 [text, "/privacy/", "_blank", "noopener", True, True, True])
    ui.check("リンクは副次色の小さい字で、下線がある",
             ui.ev("(function(){const s=getComputedStyle(dprivacy);"
                   "return [s.color,s.fontSize,s.textDecorationLine]})()"),
             ["rgb(143, 163, 196)", "12px", "underline"])
    href = ui.ev("dprivacy.href")
    ui.check_no_errors("遊び方を開いて JS エラー 0")

    # ══ リンクの先のページ ══
    ui.c.goto(href, ready=READY)
    src = dui.read(dui.DOCS + "/privacy/index.html")
    ui.check("リンクの先が開ける（題に「プライバシーポリシー」と Privacy Policy と Make10）",
             ui.ev("document.title"), "プライバシーポリシー / Privacy Policy — Make10")
    ui.check("日本語と英語の節が 1 ページに並ぶ（切り替えは持たない）",
             ui.ev("[...document.querySelectorAll('main section')].map(s=>[s.id,s.lang,s.querySelector('h1').textContent])"),
             [["ja", "ja", "プライバシーポリシー"], ["en", "en", "Privacy Policy"]])
    ui.check("どちらの節も、見出しが 10 個で同じ数",
             ui.ev("[...document.querySelectorAll('main section')].map(s=>s.querySelectorAll('h2').length)"), [10, 10])
    ui.check("どちらの節にも、問い合わせ先のアドレス（mailto のリンク）",
             ui.ev("[...document.querySelectorAll('main section')].map(s=>[...s.querySelectorAll('a[href^=\"mailto:\"]')]"
                   ".map(a=>a.getAttribute('href')+'|'+a.textContent).join(' '))"),
             ["mailto:%s|%s" % (MAIL, MAIL)] * 2)
    ja = ui.ev("document.getElementById('ja').textContent")
    en = ui.ev("document.getElementById('en').textContent")
    # 書く内容（17-6）。送る 4 つ・足した数だけを保存・見分ける番号を付けない・Cloudflare に IP・クッキーなし・端末の中の記録と消し方
    need_ja = ["問題番号", "結果（解いた／ギブアップ）", "かかった時間（秒）", "使ったヒントの回数", "足し合わせた数だけ",
               "人や端末を見分ける番号も付けません", "Cloudflare", "IP アドレス", "クッキーは使いません",
               "localStorage", "サイトデータ", "期限を決めずに保存", "GitHub", "Google", "最終更新"]
    need_en = ["Puzzle number", "Result (solved / gave up)", "Time taken (seconds)", "Number of hints used",
               "only running totals", "No identifier for you or your device", "Cloudflare", "IP address",
               "does not use cookies", "localStorage", "site data", "no set time limit", "GitHub", "Google", "Last updated"]
    ui.check("日本語の節に、書く内容がそろっている", [w for w in need_ja if w not in ja], [])
    ui.check("英語の節に、書く内容がそろっている", [w for w in need_en if w not in en], [])
    ui.check("英語の節に、日本語の文字が無い",
             re.findall(r"[　-ヿ㐀-鿿＀-￯]", en)[:5], [])
    ui.check("ページはスクリプトを持たず、外から読むのはフォントだけ",
             [len(re.findall(r"<script", src)),
              sorted(set(re.findall(r'(?:src|href)="(https?://[^/"]+)', src)) - {"https://make10.app"})],
             [0, ["https://fonts.googleapis.com", "https://fonts.gstatic.com"]])
    # 画面の幅は、決めた値（ui.size）と比べる。innerWidth は、中身が広いと Chrome が合わせて広げてしまう
    ui.check("横にはみ出さない。文字は 12px 以上",
             ui.ev("(function(){const w=document.documentElement;const m=document.querySelector('main').getBoundingClientRect();"
                   "const small=[...document.querySelectorAll('main *')].filter(e=>e.children.length===0&&e.textContent.trim()"
                   "&&parseFloat(getComputedStyle(e).fontSize)<12).length;"
                   "const out=[...document.querySelectorAll('main *')].filter(e=>{const r=e.getBoundingClientRect();"
                   "return r.width>0&&(r.left<-0.5||r.right>__W__+0.5)}).length;"
                   "return [w.scrollWidth<=__W__+1&&out===0,m.left>=0&&m.right<=__W__+0.5,small]})()".replace("__W__", str(ui.size[0]))),
             [True, True, 0])
    ui.check("デイリーへ戻るリンクがある", ui.ev("new URL(document.querySelector('.brand a').href).pathname"), "/daily/")
