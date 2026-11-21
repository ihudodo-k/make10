# -*- coding: utf-8 -*-
"""その日の投稿を作って X へ送る（promo/README.md）。毎日 1 本。GitHub Actions が UTC 8:30（日本の 17:30）に流す。

  python promo/post.py --dry-run     送らずに、送る文と型を出し、画像を作るだけ（鍵は要らない）
  python promo/post.py               送る（鍵 4 つが環境変数に要る）。送ったら promo/data/posts.csv に 1 行足す
  python promo/post.py --media-test  画像を作って X に上げ、代わりの文も入れて、状態を出すだけ（投稿しない・CSV に書かない）

- 問題番号と 4 つの数字は、docs/daily/index.html の起点日と列から、UTC の日付で出す。**答えは載せない**（送る前に確かめる）
- 文の版は TMPL（posts.csv の tmpl に残す。今は 4。版 1 は #1・#2 の短い文。tmpl が空の行は版 1 として読む）
- 文は短い 1〜2 行 ＋ #Make10。4 本（A〜D）を問題番号で順に回す（(番号 - 1) を 4 で割った余り。#1 が A・#5 も A）。
  画像の型（image.style_of。3 つ）と周期がずれるので、12 日で文と画像の全部の組み合わせが出る。
  文を 1 つに決めたら、環境変数 PROMO_TYPE（GitHub の Variables）に A〜D のどれかを入れる。型を自動で選ぶ処理は無い
- 根拠の無い数字（「1% しか解けない」など）・リンクの案内は入れない。ハッシュタグは #Make10 だけ
- 画像を付ける（promo/image.py。紙の型は JPEG・ほかは PNG。上げるときの形式は中身から決める）。
  作れない・上げられないときは、その日は文字だけで送り、ログに理由を出す（posts.csv の image が 0・style が空）。
  代わりの文が入らないだけなら画像は付ける。画像付きが 4xx で断られたら、文字だけで 1 回送り直す
- リンクは付けない（リンク付きの投稿は API の料金が高い。リンクはプロフィールに置く）
- 同じ日に 2 回流しても、posts.csv にその日の行があれば送らない
"""
import argparse
import os
import re
import sys
import tempfile

import common as c

TYPES = "ABCD"
TMPL = "4"                 # 文の版（posts.csv の tmpl）。文を変えたら上げる。report.py は版ごとに分けて集計する
SEP = ", "                 # 4 つの数字の間
TAG = "#Make10"
TEXTS = {                  # {d} は「6, 8, 2, 3」
    "A": "Make 10 with {d} — in this order. Can you?",
    "B": "Looks easy. Is it?\n{d} → 10. Reply with your answer.",
    "C": "Four digits, one target: 10.\n{d} — in this order.",
    "D": "Today's digits: {d}.\nKeep the order. Make 10.",
}
TEXT_MAX = 280             # X の重みつきの字数（x_len）


def type_of(n):
    """その番号の文の型。PROMO_TYPE があればそれ（人が 1 つに決めた後）"""
    fixed = os.environ.get("PROMO_TYPE", "").strip().upper()
    if fixed:
        if fixed not in TYPES:
            raise c.Fail("PROMO_TYPE は %s のどれか（今は %r）" % ("・".join(TYPES), fixed))
        return fixed
    return TYPES[(n - 1) % len(TYPES)]


def compose(digits, typ):
    """その型の文（版 TMPL）"""
    return TEXTS[typ].format(d=SEP.join(digits)) + "\n" + TAG


_D = r"(?P<d1>\d), (?P<d2>\d), (?P<d3>\d), (?P<d4>\d)"
SHAPES = [re.compile(re.escape(TEXTS[t]).replace(re.escape("{d}"), _D) + r"\n" + re.escape(TAG)) for t in TYPES]


def x_len(text):
    """X の重みつきの字数（twitter-text の版 3: この範囲の字は 1、ほかは 2。URL は文に入れないので扱わない）"""
    one = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
    return sum(1 if any(a <= ord(ch) <= b for a, b in one) else 2 for ch in text)


def problems(text, row):
    """送ってはいけない理由のリスト（空なら送ってよい）。答え（列の解答のどれか）が入っていないこと・形・長さ"""
    out = []
    if x_len(text) > TEXT_MAX:
        out.append("%d 字（%d 字まで）" % (x_len(text), TEXT_MAX))
    m = next((m for m in (sh.fullmatch(text) for sh in SHAPES) if m), None)
    if not m:
        out.append("決まった形でない")
    elif "".join(m.group("d1", "d2", "d3", "d4")) != row["digits"]:
        out.append("数字がその日の問題と違う")
    flat = text.replace(" ", "")
    for s in row["sols"]:
        if s in text or s.replace(" ", "") in flat:
            out.append("答えが入っている")
            break
    if re.search(r"[+\-*/^!=()×÷−]", text):
        out.append("演算の記号が入っている")
    return out


def plan(day, page=None):
    """その日（UTC の日付）の (番号, 行, 型)。起点日より前は (番号, None, None)"""
    start, rows = c.load_page(page)
    n = c.puzzle_no(start, day)
    if n < 1:
        return n, None, None
    if n > len(rows):
        raise c.Fail("#%d の問題が列に無い（列は %d 日ぶん。python make10.py daily で延ばす）" % (n, len(rows)))
    return n, rows[n - 1], type_of(n)


def alt_text(n, digits, rc):
    """画像の代わりの文。記号の並びは画像の「Use」の行と同じ（使えない記号は抜く）"""
    return "Make10 #%d. Digits: %s. Use all four, in order, to make 10. Use %s." % (
        n, ", ".join(digits), " ".join(c.allowed_syms(rc)))


def make_image(n, row):
    """その日の (画像のバイト列, 画像の型)。作れないときは Fail（文字だけの投稿に落とす）"""
    try:
        import image
    except ImportError as e:
        raise c.Fail("画像の部品を読めない: %s" % e)
    style = image.style_of(n)
    return image.make(n, row["digits"], row["rc"], style), style


def save_image(data, n, out_dir):
    """画像を out_dir に書いて、パスを返す（既定は一時フォルダー。拡張子は中身の形式から）"""
    _, ext = c.image_format(data)
    out_dir = out_dir or os.path.join(tempfile.gettempdir(), "make10-promo-image")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "make10-%d%s" % (n, ext))
    with open(path, "wb") as f:
        f.write(data)
    return path


def upload(keys, data, n, row):
    """画像を上げて代わりの文を入れる。(media_id, 上げたときの状態, 代わりの文の状態か理由)。上げられないときは Fail"""
    mime, ext = c.image_format(data)
    st, j, txt = c.x_upload_image(keys, data, mime, "make10" + ext)
    mid = (j or {}).get("data", {}).get("id") if isinstance(j, dict) else None
    if st not in (200, 201) or not isinstance(mid, str) or not re.fullmatch(r"[0-9]{1,19}", mid):
        raise c.Fail("X が画像を断った: " + c.x_error(st, j, txt))
    alt = alt_text(n, row["digits"], row["rc"])
    try:
        st2, j2, txt2 = c.x_call("POST", "/2/media/metadata", keys,
                                 body={"id": mid, "metadata": {"alt_text": {"text": alt}}})
    except c.Fail as e:
        return mid, st, str(e)
    return mid, st, st2 if st2 in (200, 201) else c.x_error(st2, j2, txt2)


def media_test(n, row, out_dir):
    """画像を作って上げるだけ（手で流す確かめ。投稿しない・CSV に書かない）。上げられなければ Fail"""
    data, style = make_image(n, row)
    print("画像: %s（型 %s・%d バイト）" % (save_image(data, n, out_dir), style, len(data)))
    mid, st, alt = upload(c.x_keys(), data, n, row)
    print("media_id: %s  上げたときの状態: HTTP %s  代わりの文の状態: %s" % (mid, st, alt))
    if alt not in (200, 201):
        raise c.Fail("代わりの文が入らなかった: %s" % alt)
    print("投稿はしていない")


def main(argv=None):
    ap = argparse.ArgumentParser(description="その日の投稿を作って X へ送る")
    ap.add_argument("--dry-run", action="store_true", help="送らずに、送る文と型を出し、画像を作るだけ")
    ap.add_argument("--media-test", action="store_true", help="画像を作って X に上げるだけ（投稿しない・CSV に書かない）")
    ap.add_argument("--image-dir", help="画像を書き出す場所（--dry-run・--media-test。既定は一時フォルダー）")
    ap.add_argument("--data", help="CSV の置き場所（既定は promo/data。環境変数 PROMO_DATA でも）")
    ap.add_argument("--page", help="問題の列を読むページ（既定は docs/daily/index.html）")
    ap.add_argument("--now", help="今の時刻を決める（試しのため。2026-10-26T08:30:00Z の形）")
    a = ap.parse_args(argv)
    try:
        now = c.now_utc(a.now)
        day = now.date()
        n, row, typ = plan(day, a.page)
        if row is None:
            print("%s（UTC）は起点日より前（#%d）。送らない" % (day, n))
            return 0
        if a.media_test:
            media_test(n, row, a.image_dir)
            return 0
        ddir = c.data_dir(a.data)
        posts = c.read_table(ddir, "posts.csv")
        if posts.get(day.isoformat(), {}).get("tweet_id") and not a.dry_run:
            print("%s（#%d）は送ってある（tweet %s）。送らない" % (day, n, posts[day.isoformat()]["tweet_id"]))
            return 0
        text = compose(row["digits"], typ)
        bad = problems(text, row)
        if bad:
            raise c.Fail("この文は送らない: " + "・".join(bad))
        print("%s（UTC） #%d  文の型 %s  文の版 %s" % (day, n, typ, TMPL))
        print("----")
        print(text)
        print("----  %d 字（X の数え方）" % x_len(text))
        if a.dry_run:
            try:
                data, style = make_image(n, row)
                print("画像: %s（型 %s・%d バイト）" % (save_image(data, n, a.image_dir), style, len(data)))
            except c.Fail as e:
                print("注意: 画像を作れない（本番なら文字だけで送る）: %s" % e)
            print("代わりの文: %s" % alt_text(n, row["digits"], row["rc"]))
            print("dry-run なので送らない")
            return 0
        keys = c.x_keys()
        followers = ""
        st, j, txt = c.x_call("GET", "/2/users/me", keys, query={"user.fields": "public_metrics"})
        if st == 200 and isinstance(j, dict) and "data" in j:
            followers = str(j["data"].get("public_metrics", {}).get("followers_count", ""))
        else:
            print("注意: フォロワーの数が読めない（%s）。投稿は続ける" % c.x_error(st, j, txt))
        mid = style = None
        try:
            data, style = make_image(n, row)
            mid, st, alt = upload(keys, data, n, row)
            print("画像を上げた: media_id %s（型 %s）" % (mid, style))
            if alt not in (200, 201):
                print("注意: 代わりの文が入らない（画像は付ける）: %s" % alt)
        except c.Fail as e:
            print("注意: 画像なしで投稿する: %s" % e)
        body = {"text": text}
        if mid:
            body["media"] = {"media_ids": [mid]}
        st, j, txt = c.x_call("POST", "/2/tweets", keys, body=body)
        if mid and 400 <= st < 500:     # 届いて断られた。5xx や通信の失敗は、出ているかもしれないので送り直さない
            print("注意: 画像付きを断られたので、文字だけで送り直す: " + c.x_error(st, j, txt))
            mid = None
            st, j, txt = c.x_call("POST", "/2/tweets", keys, body={"text": text})
        tid = (j or {}).get("data", {}).get("id") if isinstance(j, dict) else None
        if st not in (200, 201) or not tid:
            raise c.Fail("X が投稿を断った: " + c.x_error(st, j, txt))
        posts[day.isoformat()] = {"date": day.isoformat(), "n": str(n), "type": typ, "tmpl": TMPL, "digits": row["digits"],
                                  "text": text, "c_note": "", "image": "1" if mid else "0",
                                  "style": str(style) if mid else "", "tweet_id": str(tid), "posted_at": c.iso(now),
                                  "followers": followers}
        c.write_table(ddir, "posts.csv", posts)
        print("送った: tweet %s（フォロワー %s・画像 %s）" % (tid, followers or "?", "型 %s" % style if mid else "なし"))
        return 0
    except c.Fail as e:
        print("失敗: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
