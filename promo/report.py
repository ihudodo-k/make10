# -*- coding: utf-8 -*-
"""型ごとのまとめを出す（promo/README.md）。人が読むための表で、**勝ち負けは決めない**（型を決めるのは人）。

  python promo/report.py                 Markdown の表を画面に出す
  python promo/report.py --out report.md ファイルに書く（GitHub Actions は collect の後に promo-data へ書く）

- 型ごと: 投稿の数・表示の平均・表示 1,000 回あたりの反応（いいね ＋ 返信 ＋ リポスト）とプロフィールのクリック・
  X から来た人（その日の t.co ＋ x.com の訪問）の平均・その日の遊んだ人数（解いた ＋ ギブアップ）の平均
- **文の版（posts.csv の tmpl）ごとに分けて出す。** 版が違えば同じ型の名前でも別の文なので混ぜない（版 1 は #1・#2 の短い文）
- 比べるのは投稿から約 24 時間の値（m24_*）。まだ無い日は数えず、数えた日数を並べて出す
- 偏りを見るために、型ごとの曜日の内訳と、何日目に出たか（日がたつとフォロワーが増えるので後の型ほど有利）、
  日ごとの表（フォロワーの増減つき）も出す
"""
import argparse
import datetime
import sys

import common as c

WD = "月火水木金土日"


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def fmt(x, nd=0):
    if x is None:
        return "—"
    return ("{:,.%df}" % nd).format(x)


def per1000(a, imp):
    return a * 1000 / imp if a is not None and imp else None


def build(ddir):
    posts = c.read_table(ddir, "posts.csv")
    visits = c.read_table(ddir, "visits.csv")
    agg = c.read_table(ddir, "agg.csv")
    days = []
    prev_f = None
    for k in sorted(posts):
        p = posts[k]
        if not p["tweet_id"]:
            continue
        d = datetime.date.fromisoformat(k)
        imp = num(p["m24_impressions"])
        parts = [num(p["m24_" + m]) for m in ("likes", "replies", "reposts")]
        react = sum(parts) if p["m24_at"] and None not in parts else None
        f = num(p["followers"])
        v = visits.get(k, {})
        fx = (num(v.get("from_tco")) or 0) + (num(v.get("from_x")) or 0) if v else None
        a = agg.get(p["n"], {})
        days.append({"date": k, "wd": WD[d.weekday()], "n": int(p["n"]), "type": p["type"], "tmpl": p["tmpl"],
                     "followers": f, "df": f - prev_f if f is not None and prev_f is not None else None,
                     "imp": imp, "react": react, "prof": num(p["m24_profile_clicks"]),
                     "imp_last": num(p["last_impressions"]), "from_x": fx,
                     "visits": num(v.get("visits")) if v else None,
                     "players": num(a.get("players")) if a else None, "c_note": p["c_note"]})
        if f is not None:
            prev_f = f
    return days


def render(days):
    out = ["# 型ごとのまとめ", "",
           "人が読むための表。勝ち負けは決めない。曜日と、何日目か（フォロワーの増え方）で偏るので、曜日の内訳と日ごとの表と合わせて読む。文の版ごとに分けてある（版が違う文を混ぜない）。",
           "比べる数は投稿から約 24 時間の値（まだ無い日は「24 時間の値がある日」に入らない）。", ""]
    if not days:
        out.append("まだ投稿が無い。")
        return "\n".join(out) + "\n"
    # 文の版ごとに分ける（新しい版を上に）。版が違えば同じ型の名前でも別の文なので、混ぜない
    for v in sorted({d["tmpl"] for d in days}, key=int, reverse=True):
        out += by_type([d for d in days if d["tmpl"] == v], v)
    out += ["## 日ごと", "",
            "| 日付（UTC） | 曜日 | # | 文の版 | 型 | フォロワー | 増減 | 表示（24 時間） | 反応 | プロフィール | 表示（最新） | 訪問 | X から | 遊んだ人 | C の昨日の行 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for d in days:
        out.append("| %s | %s | %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            d["date"], d["wd"], d["n"], d["tmpl"], d["type"], fmt(d["followers"]),
            "—" if d["df"] is None else "%+d" % d["df"], fmt(d["imp"]), fmt(d["react"]), fmt(d["prof"]),
            fmt(d["imp_last"]), fmt(d["visits"]), fmt(d["from_x"]), fmt(d["players"]), d["c_note"] or ""))
    return "\n".join(out) + "\n"


def by_type(days, v):
    """1 つの文の版の、型ごとの表と曜日の内訳"""
    out = ["## 文の版 %s" % v, "",
           "| 型 | 投稿 | 24 時間の値がある日 | 表示の平均 | 反応 / 表示 1,000 | プロフィール / 表示 1,000 | X から来た人の平均 | 遊んだ人の平均 | 何日目（平均） | フォロワーの増え（平均） |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for t in sorted({d["type"] for d in days}):
        ds = [d for d in days if d["type"] == t]
        m = [d for d in ds if d["imp"] is not None and d["react"] is not None]
        imp = sum(d["imp"] for d in m)
        out.append("| %s | %d | %d | %s | %s | %s | %s | %s | %s | %s |" % (
            t, len(ds), len(m), fmt(avg([d["imp"] for d in m])),
            fmt(per1000(sum(d["react"] for d in m), imp) if m else None, 1),
            fmt(per1000(sum(d["prof"] or 0 for d in m), imp) if m else None, 1),
            fmt(avg([d["from_x"] for d in ds]), 1), fmt(avg([d["players"] for d in ds]), 1),
            fmt(avg([d["n"] for d in ds]), 1), fmt(avg([d["df"] for d in ds]), 1)))
    out += ["", "### 曜日の内訳（投稿の数。文の版 %s）" % v, "", "| 型 | " + " | ".join(WD) + " |", "|---|" + "---|" * 7]
    for t in sorted({d["type"] for d in days}):
        out.append("| %s | " % t + " | ".join(str(sum(1 for d in days if d["type"] == t and d["wd"] == w)) for w in WD) + " |")
    return out + [""]


def main(argv=None):
    ap = argparse.ArgumentParser(description="型ごとのまとめを出す（勝ち負けは決めない）")
    ap.add_argument("--data", help="CSV の置き場所（既定は promo/data。環境変数 PROMO_DATA でも）")
    ap.add_argument("--out", help="書き出すファイル（省くと画面に出す）")
    a = ap.parse_args(argv)
    text = render(build(c.data_dir(a.data)))
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("書いた: %s" % a.out)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
