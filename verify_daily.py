#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""docs/daily/index.html（デイリー）の回帰検証を headless Chrome で回す。DAILY-SPEC 11 章。

    python verify_daily.py                # 全ケースを 3 画面（430×900・360×690・360×640）で
    python verify_daily.py --case sync    # ケースを絞る（複数可）
    python verify_daily.py --list         # ケースの一覧
    python verify_daily.py --keep-going   # 落ちても最後まで回す

**1 つでも落ちたら赤**（終了コード 1）。本編の `verify_ui.py` と同じ考え方で、入口・道具・ケースは
デイリー用に別に持つ（`uiharness/daily_ui.py`・`uiharness/daily_cases/`）。共用するのは
`uiharness/cdp.py`（Chrome の起動・`docs/` の配信・キャッシュ無効）だけで、本編の検証には触らない。

- **版の照合で止まる。** 起動直後に、ソースの `DAILY_VERSION` と、画面のいちばん下に見えている版を
  突き合わせ、食い違えばケースを 1 つも回さず赤で終わる
- **本編との同期の照合**（ケース `sync`）。デイリーは本編の盤・辞書・CSS を 1 文字も変えずに複製している。
  **本編の `docs/index.html` を変えたら、こちらも流す**（CLAUDE.md「画面の検証」）
- 配る場所は `MAKE10_DOCS` で差し替えられる（わざと壊した複製に当てて、赤くなることを確かめるため）
"""
import argparse
import importlib
import os
import pkgutil
import re
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uiharness import cdp, daily_ui as dui          # noqa: E402

PORT = 8791               # 本編の verify_ui.py（8790）と別にして、同時に流せるようにする
DEBUG_PORT = 9391
VIEWPORTS = [("normal", 430, 900), ("compact", 360, 690), ("small", 360, 640)]
READY = "complete|undefined"      # cdp.Chrome.goto() の待ち合わせ。デイリーに APP_VERSION は無い


def load_cases(only):
    import uiharness.daily_cases as pkg
    mods = []
    for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda x: x.name):
        if only and m.name not in only:
            continue
        mods.append(importlib.import_module("uiharness.daily_cases." + m.name))
    if only:
        missing = set(only) - {m.__name__.rsplit(".", 1)[1] for m in mods}
        if missing:
            raise SystemExit("そんなケースは無い: " + ", ".join(sorted(missing)))
    return mods


def source_version():
    m = re.search(r'const DAILY_VERSION="([^"]+)"', dui.read(dui.DAILY_HTML))
    if not m:
        raise SystemExit("docs/daily/index.html に DAILY_VERSION が見つからない")
    return m.group(1)


def check_version(chrome, url, want):
    """読み込んだページが手元の版かを、画面のいちばん下に見えている版で確かめる"""
    helper = dui.UI(chrome, url, [], "version", (430, 900))
    helper.open()
    shown = helper.visible("dver")
    text = helper.text("dver")
    # 言語に依らないよう、文（「デイリー 0.3」）ではなく版の数字だけを突き合わせる
    nums = re.findall(r"\d+(?:\.\d+)+", text or "")
    return shown and nums == [want], shown, text


def safe_output():
    """出力先の文字コードで出せない文字があっても、結果を最後まで出し切る（本編 7.7 と同じ）"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except Exception:
            pass


def main():
    safe_output()
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", default=[], help="回すケース名（既定は全部）")
    ap.add_argument("--list", action="store_true", help="ケースの一覧を出す")
    ap.add_argument("--keep-going", action="store_true", help="例外が出ても次のケースへ進む")
    ap.add_argument("--viewport", choices=[v[0] for v in VIEWPORTS], help="1 つの画面だけ回す")
    args = ap.parse_args()

    cases = load_cases(args.case)
    if args.list:
        for m in cases:
            print("%-12s %s" % (m.__name__.rsplit(".", 1)[1], m.NAME))
        return 0

    views = [v for v in VIEWPORTS if not args.viewport or v[0] == args.viewport]
    serve = cdp.serve(dui.DOCS, PORT)
    url = "http://127.0.0.1:%d/daily/index.html" % PORT
    profile = tempfile.mkdtemp(prefix="make10-verify-daily-")
    chrome = cdp.Chrome(DEBUG_PORT, profile)
    print("Chrome : %s" % chrome.version)
    print("対象   : %s  (%s)" % (url, dui.DOCS))
    results, broken = [], []
    t0 = time.time()

    def run(mod, name, w, h):
        short = mod.__name__.rsplit(".", 1)[1]
        helper = dui.UI(chrome, url, results, name, (w, h))
        helper.case = short
        start = len(results)
        try:
            mod.run(helper)
        except Exception as e:                      # ケースの事故も赤
            broken.append((name, short, str(e)))
            results.append((False, name, short, "ケースが最後まで走らない",
                            str(e)[:300], "例外なし"))
            if not args.keep_going:
                raise
        ng = [r for r in results[start:] if not r[0]]
        print("  %-12s %-28s %3d 項目  %s"
              % (short, mod.NAME, len(results) - start,
                 "OK" if not ng else "NG %d 件" % len(ng)))
        for r in ng:
            print("      NG %s\n         実測=%r 期待=%r" % (r[3], r[4], r[5]))

    try:
        want = source_version()
        chrome.metrics(*VIEWPORTS[0][1:])
        ok, shown, text = check_version(chrome, url, want)
        print("版     : ソース %s ／ 画面 %r（%s）" % (want, text, "表示あり" if shown else "表示なし"))
        if not ok:
            print("\n版が一致しない。古い版が読まれている。ケースは回さずに止める")
            return 1
        # 画面の大きさに依らないケース（ソースの照合など）は 1 回だけ回す
        static = [m for m in cases if getattr(m, "STATIC", False)]
        if static:
            print("\n===== ソース =====")
            for mod in static:
                run(mod, "-", *VIEWPORTS[0][1:])
        for name, w, h in views:
            print("\n===== %s (%d×%d) =====" % (name, w, h))
            chrome.metrics(w, h)                   # 読み込みより先に画面の大きさを決める
            for mod in cases:
                if not getattr(mod, "STATIC", False):
                    run(mod, name, w, h)
    finally:
        chrome.close()
        serve.shutdown()
        serve.server_close()
        shutil.rmtree(profile, ignore_errors=True)

    ok = sum(1 for r in results if r[0])
    print("\n合計 %d / %d 項目  (%.1f 秒)" % (ok, len(results), time.time() - t0))
    if ok != len(results):
        print("\n落ちた項目:")
        for r in results:
            if not r[0]:
                print("  [%s] %s / %s  実測=%r 期待=%r" % (r[1], r[2], r[3], r[4], r[5]))
        return 1
    if broken:
        return 1
    print("すべて通った")
    return 0


if __name__ == "__main__":
    sys.exit(main())
