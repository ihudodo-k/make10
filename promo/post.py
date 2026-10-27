# -*- coding: utf-8 -*-
"""その日の投稿を作って X へ送る（promo/README.md）。毎日 1 本。GitHub Actions が UTC 8:30（日本の 17:30）に流す。

  python promo/post.py --dry-run     送らずに、送る文と型を出すだけ（鍵は要らない）
  python promo/post.py               送る（鍵 4 つが環境変数に要る）。送ったら promo/data/posts.csv に 1 行足す

- 問題番号と 4 つの数字は、docs/daily/index.html の起点日と列から、UTC の日付で出す。**答えは載せない**（送る前に確かめる）
- 文の版は TMPL（posts.csv の tmpl に残す。今は 2。版 1 は #1・#2 の短い文。tmpl が空の行は版 1 として読む）
- 型は 3 つを、問題番号で順に回す（(番号 - 1) を 3 で割った余り。#1 が A・#2 が B・#3 が C）。
  1 つに決めたら、環境変数 PROMO_TYPE（GitHub の Variables）に A・B・C のどれかを入れる。型を自動で選ぶ処理は無い
- リンクは付けない（リンク付きの投稿は API の料金が高い。リンクはプロフィールに置く）
- 同じ日に 2 回流しても、posts.csv にその日の行があれば送らない
"""
import argparse
import os
import re
import sys

import common as c

TYPES = "ABC"
TMPL = "2"                 # 文の版（posts.csv の tmpl）。文を変えたら上げる。report.py は版ごとに分けて集計する
SEP = " · "                # 4 つの数字の間
RULE_B = "Keep the order. + − × ÷ ^ ! ( ) allowed."
TAGS = {"A": "#Make10 #DailyPuzzle #MathPuzzle", "B": "#Make10 #DailyPuzzle #BrainTeaser",
        "C": "#Make10 #DailyPuzzle #MathPuzzle"}
TEXT_MAX = 280             # X の重みつきの字数（x_len）


def type_of(n):
    """その番号の型。PROMO_TYPE があればそれ（人が 1 つに決めた後）"""
    fixed = os.environ.get("PROMO_TYPE", "").strip().upper()
    if fixed:
        if fixed not in TYPES:
            raise c.Fail("PROMO_TYPE は A・B・C のどれか（今は %r）" % fixed)
        return fixed
    return TYPES[(n - 1) % 3]


def c_line(n):
    """C の 2 行目（昨日の結果）と、記録に残す一言。出さないときは ("", 理由)"""
    if n <= 1:
        return "", "昨日の問題が無い"
    try:
        j = c.agg_get(n - 1)
    except c.Fail as e:
        return "", "取れない（%s）" % e
    total = j["s"] + j["g"]
    if total < c.AGG_MIN:
        return "", "%d 件未満（%d 件）" % (c.AGG_MIN, total)
    line = "Yesterday's puzzle: %d%% solved" % c.pct(j["s"], total)
    if j["s"]:
        line += ", %d%% with no hints" % c.pct(j["s0"], j["s"])
    return line + ".", "出した（s=%d g=%d s0=%d）" % (j["s"], j["g"], j["s0"])


def compose(n, digits, typ, line=""):
    """その型の文（版 TMPL）。line は C の 2 行目（空なら、その行を除く）"""
    d = SEP.join(digits)
    if typ == "A":
        lines = ["Make10 Daily #%d" % n, "Today's numbers: %s" % d, "Use all four, in order, to make 10.",
                 "Play free — link in profile."]
    elif typ == "B":
        lines = ["Can you make 10 from %s?" % d, RULE_B, "Make10 Daily #%d — link in profile." % n]
    else:
        lines = ["Make10 Daily #%d: %s" % (n, d)] + ([line] if line else []) + ["Your turn — make 10. Link in profile."]
    return "\n".join(lines + [TAGS[typ]])


_D = r"(?P<d1>\d) · (?P<d2>\d) · (?P<d3>\d) · (?P<d4>\d)"
SHAPES = [re.compile(x) for x in (
    r"Make10 Daily #(?P<n>\d+)\nToday's numbers: " + _D + r"\nUse all four, in order, to make 10\.\n"
    r"Play free — link in profile\.\n#Make10 #DailyPuzzle #MathPuzzle",
    r"Can you make 10 from " + _D + r"\?\n" + re.escape(RULE_B) + r"\nMake10 Daily #(?P<n>\d+) — link in profile\.\n"
    r"#Make10 #DailyPuzzle #BrainTeaser",
    r"Make10 Daily #(?P<n>\d+): " + _D + r"\n(?:Yesterday's puzzle: \d{1,3}% solved(?:, \d{1,3}% with no hints)?\.\n)?"
    r"Your turn — make 10\. Link in profile\.\n#Make10 #DailyPuzzle #MathPuzzle")]


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
    elif int(m.group("n")) != row["no"] or "".join(m.group("d1", "d2", "d3", "d4")) != row["digits"]:
        out.append("番号か数字がその日の問題と違う")
    flat = text.replace(" ", "")
    for s in row["sols"]:
        if s in text or s.replace(" ", "") in flat:
            out.append("答えが入っている")
            break
    # B の決まりの行（使える記号の一覧）だけは記号を書く。その行を除いた残りに記号が無いこと
    if re.search(r"[+\-*/^!=()×÷−]", text.replace(RULE_B, "")):
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


def main(argv=None):
    ap = argparse.ArgumentParser(description="その日の投稿を作って X へ送る")
    ap.add_argument("--dry-run", action="store_true", help="送らずに、送る文と型を出すだけ")
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
        ddir = c.data_dir(a.data)
        posts = c.read_table(ddir, "posts.csv")
        if posts.get(day.isoformat(), {}).get("tweet_id") and not a.dry_run:
            print("%s（#%d）は送ってある（tweet %s）。送らない" % (day, n, posts[day.isoformat()]["tweet_id"]))
            return 0
        line, note = c_line(n) if typ == "C" else ("", "")
        text = compose(n, row["digits"], typ, line)
        bad = problems(text, row)
        if bad:
            raise c.Fail("この文は送らない: " + "・".join(bad))
        print("%s（UTC） #%d  型 %s  文の版 %s%s" % (day, n, typ, TMPL, "  C の 2 行目: " + note if typ == "C" else ""))
        print("----")
        print(text)
        print("----  %d 字（X の数え方）" % x_len(text))
        if a.dry_run:
            print("dry-run なので送らない")
            return 0
        keys = c.x_keys()
        followers = ""
        st, j, txt = c.x_call("GET", "/2/users/me", keys, query={"user.fields": "public_metrics"})
        if st == 200 and isinstance(j, dict) and "data" in j:
            followers = str(j["data"].get("public_metrics", {}).get("followers_count", ""))
        else:
            print("注意: フォロワーの数が読めない（%s）。投稿は続ける" % c.x_error(st, j, txt))
        st, j, txt = c.x_call("POST", "/2/tweets", keys, body={"text": text})
        tid = (j or {}).get("data", {}).get("id") if isinstance(j, dict) else None
        if st not in (200, 201) or not tid:
            raise c.Fail("X が投稿を断った: " + c.x_error(st, j, txt))
        posts[day.isoformat()] = {"date": day.isoformat(), "n": str(n), "type": typ, "tmpl": TMPL, "digits": row["digits"],
                                  "text": text, "c_note": note, "tweet_id": str(tid), "posted_at": c.iso(now),
                                  "followers": followers}
        c.write_table(ddir, "posts.csv", posts)
        print("送った: tweet %s（フォロワー %s）" % (tid, followers or "?"))
        return 0
    except c.Fail as e:
        print("失敗: %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
