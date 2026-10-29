# -*- coding: utf-8 -*-
"""リンクを貼ったときの見た目（OGP。D0.20。D1.1 で英語にした。DAILY-SPEC 9 章）。

- head に、og と twitter のタグが決めた名前で 1 つずつ揃っていること・中身が空でないこと
- URL（og:url・og:image・twitter:image）が https://make10.app/daily/ で始まる絶対パスであること
- 画像 og.png が docs/daily/ にあり、1200×630 の PNG で、300KB 以下であること（タグの寸法とも合う）
- 貼られた先はスクリプトを動かさないので、タグはソースに直に書いてあること（JS が後から書く形ではない）
- 検索（D1.2。DAILY-SPEC 2 章）: ソースの <title> が英語の題（og:title と同じ）・<meta name="description">（og:description と同じ）・
  canonical（https://make10.app/daily/）が 1 つずつあること。robots の meta はソースに無く、?date=（テスト表示）で開いたときだけ
  noindex が 1 つ付くこと（?date= の無いふつうの表示には付かない）
"""
import os
import re
import struct
import time

from uiharness import daily_ui as dui

NAME = "リンクを貼ったときの見た目（OGP）"

BASE = "https://make10.app/daily/"
OG = ["og:type", "og:site_name", "og:locale", "og:url", "og:title", "og:description", "og:image",
      "og:image:type", "og:image:width", "og:image:height", "og:image:alt"]
TW = ["twitter:card", "twitter:title", "twitter:description", "twitter:image"]
MAX_BYTES = 300 * 1024


def _metas(head):
    """head のソースから、(属性の名前, キー, 中身) の並びを作る"""
    out = []
    for tag in re.findall(r"<meta\b[^>]*>", head):
        k = re.search(r'\b(property|name)="([^"]*)"', tag)
        c = re.search(r'\bcontent="([^"]*)"', tag)
        if k and c:
            out.append((k.group(1), k.group(2), c.group(1)))
    return out


def _png_size(path):
    """PNG の先頭（署名と IHDR）だけを読んで、(幅, 高さ) を返す。PNG でなければ None"""
    with open(path, "rb") as f:
        b = f.read(24)
    if len(b) < 24 or b[:8] != b"\x89PNG\r\n\x1a\n" or b[12:16] != b"IHDR":
        return None
    return list(struct.unpack(">II", b[16:24]))


def run(ui):
    src = dui.read(dui.DAILY_HTML)
    head = src[src.index("<head>"):src.index("</head>")]
    metas = _metas(head)
    og = {k: c for a, k, c in metas if a == "property" and k.startswith("og:")}
    tw = {k: c for a, k, c in metas if a == "name" and k.startswith("twitter:")}

    # ══ ソースのタグ ══
    ui.check("og のタグが、決めた名前で揃っている（property で書く）", sorted(og), sorted(OG))
    ui.check("twitter のタグが、決めた名前で揃っている（name で書く）", sorted(tw), sorted(TW))
    keys = [k for a, k, c in metas if k.startswith(("og:", "twitter:"))]
    ui.check("同じ名前のタグが 2 つ無い", sorted(k for k in set(keys) if keys.count(k) > 1), [])
    ui.check("中身が空のタグが無い", sorted(k for a, k, c in metas if k.startswith(("og:", "twitter:")) and not c.strip()), [])
    ui.check("og:type・og:site_name・og:locale・twitter:card",
             [og.get("og:type"), og.get("og:site_name"), og.get("og:locale"), tw.get("twitter:card")],
             ["website", "Make10", "en_US", "summary_large_image"])
    ui.check("og:url はデイリーの公開 URL（絶対パス）", og.get("og:url"), BASE)
    ui.check("画像の URL は絶対パスで、og と twitter で同じ",
             [og.get("og:image"), tw.get("twitter:image")], [BASE + "og.png"] * 2)
    ui.check("og と twitter の URL に、相対パスや http:// が無い",
             [(k, c) for a, k, c in metas if k in ("og:url", "og:image", "twitter:image") and not c.startswith(BASE)], [])
    ui.check("タイトルに「Make10 Daily」が入り、og と twitter で同じ",
             ["Make10 Daily" in og.get("og:title", ""), og.get("og:title") == tw.get("twitter:title")], [True, True])
    ui.check("説明に「four digits」と「10」が入り、og と twitter で同じ。80 字以内",
             ["four digits" in og.get("og:description", ""), "10" in og.get("og:description", ""),
              og.get("og:description") == tw.get("twitter:description"), len(og.get("og:description", "")) <= 80],
             [True, True, True, True])
    ui.check("別の言語の og（og:locale:alternate）は付けない", [k for k in og if "alternate" in k], [])

    # ══ 検索（D1.2）══
    titles = re.findall(r"<title\b[^>]*>(.*?)</title>", head, re.S)
    ui.check("<title> が 1 つで、中身は英語の題（og:title と同じ）",
             titles, ["Make10 Daily — one number puzzle a day"])
    ui.check("og:title も同じ題", og.get("og:title"), "Make10 Daily — one number puzzle a day")
    desc = [c for a, k, c in metas if a == "name" and k == "description"]
    ui.check("<meta name=\"description\"> が 1 つで、og:description と同じ文", desc, [og.get("og:description")])
    canon = re.findall(r'<link\b[^>]*\brel="canonical"[^>]*>', head)
    ui.check("canonical が 1 つで、https://make10.app/daily/ を指す",
             [re.search(r'\bhref="([^"]*)"', c).group(1) for c in canon], [BASE])
    ui.check("robots の meta はソースに無い（ふつうの表示は検索に出す）",
             [k for a, k, c in metas if a == "name" and k == "robots"], [])

    # ══ 画像 ══
    path = os.path.join(dui.DOCS, "daily", "og.png")
    there = os.path.isfile(path)
    ui.check("og.png が docs/daily/ にある", there, True)
    size = _png_size(path) if there else None
    ui.check("og.png は 1200×630 の PNG", size, [1200, 630])
    ui.check("タグの寸法と種類が、画像と合っている",
             [og.get("og:image:width"), og.get("og:image:height"), og.get("og:image:type")], ["1200", "630", "image/png"])
    ui.check("og.png は 300KB 以下", there and os.path.getsize(path) <= MAX_BYTES, True)

    # ══ 開いたページ ══
    start, rows = dui.page_data()
    for lang in ("ja", "en"):
        ui.open(date=start.isoformat(), lang=lang)
        # 言語を切り替えても、タグは書き換わらない（英語だけを付ける。D1.1）
        ui.check("%s: 開いたページの head のタグが、ソースと同じ（スクリプトが書き換えない）" % lang,
                 ui.ev("[...document.head.querySelectorAll('meta[property^=\"og:\"],meta[name^=\"twitter:\"]')]"
                       ".map(m=>[m.getAttribute('property')?'property':'name',"
                       "m.getAttribute('property')||m.getAttribute('name'),m.getAttribute('content')])"),
                 [list(m) for m in metas if m[1].startswith(("og:", "twitter:"))])
    # ui.ev は Promise を待たないので、読み込ませてから、結果を後で読む
    ui.ev("(function(){window.__og='wait';const i=new Image();i.onload=()=>{window.__og=[i.naturalWidth,i.naturalHeight]};"
          "i.onerror=()=>{window.__og='error'};i.src=new URL('og.png',location.href.split('?')[0]).href})()")
    for _ in range(50):
        if ui.ev("window.__og") != "wait":
            break
        time.sleep(0.1)
    ui.check("画像がページと同じ場所から読める（1200×630）", ui.ev("window.__og"), [1200, 630])

    # ══ 開いたページの検索のタグ（D1.2）══
    robots = ("[...document.head.querySelectorAll('meta[name=\"robots\"]')].map(m=>m.getAttribute('content'))")
    seo = ("[document.querySelectorAll('title').length,"
           "document.head.querySelector('meta[name=\"description\"]')?.content,"
           "[...document.head.querySelectorAll('link[rel=\"canonical\"]')].map(l=>l.getAttribute('href'))]")
    for lang, title in (("ja", "Make10 デイリー"), ("en", "Make10 Daily")):
        ui.open(date=start.isoformat(), lang=lang)
        ui.check("%s: ?date=（テスト表示）では robots の noindex が 1 つだけ付く" % lang, ui.ev(robots), ["noindex"])
        ui.check("%s: 開いた後の題は今までどおり言語に合わせて書き換わる（daily.page_title）" % lang,
                 ui.ev("document.title"), title)
        ui.check("%s: 開いた後も、説明と canonical は 1 つずつのまま" % lang, ui.ev(seo),
                 [1, og.get("og:description"), [BASE]])
    for lang in ("ja", "en"):
        ui.open(date=None, lang=lang)
        ui.check("%s: ?date= の無いふつうの表示には robots の meta が付かない" % lang, ui.ev(robots), [])
    ui.open(date=None, lang="en", extra="&date=bad")
    ui.check("?date= の日付が読めない（テスト表示にならない）ときは付けない", ui.ev(robots), [])
    ui.check_no_errors()
