#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""docs/index.html の回帰検証を headless Chrome で回す。

    python verify_ui.py                 # 全ケースを normal / compact の両方で
    python verify_ui.py --case reward    # ケースを絞る（複数可）
    python verify_ui.py --list           # ケースの一覧
    python verify_ui.py --keep-going     # 落ちても最後まで回す

**1 つでも落ちたら赤**（終了コード 1）。`make10.py blob` の 12 項目と同じ思想で、
「通ったこと」ではなく「1 つも落ちなかったこと」を成果とする。

## 何を入れて、何を入れないか

入れるのは**回帰**だけ ―― 起動と画面の巡回・保存データの移行・3 モードの出題と
件数・ヒントの消費規則・クリアの確定と挑戦の報酬・JS エラー 0。
寸法の詰め（SIZE-TRIAL のような）や縮小率の実測のような**計測もの**は入れない。
あれは答えが出たら TOKEN_METRICS に焼き付けて終わるもので、
毎回回す価値が無いうえ、実機の値と食い違って赤くなるだけになる。
計測の手順と条件は DESIGN.md に文章で残す。

## つまずいた点（作り直すたびに踏んだので、実装に入れてある）

1. **Chrome の実行パスは `MAKE10_CHROME` で上書きできる。** 環境に直書きしない
2. **`file://` ではなく 127.0.0.1 の HTTP で開く。** file:// では localStorage が
   使えず、保存データの検証がそのままでは成立しない
3. **画面の大きさは読み込みより先に決める。** applyMetrics() は読み込み時の幅で
   normal / compact を決めるので、後から変えても反映されない（5.1 でこれに騙され、
   「normal」と書いた測定が実は compact だった）
4. **判定はできるだけ DOM の見える値で取る。** 変数が正しくても画面に出ていない
   ことがある（4.5 で #pmode に値を入れたのに親が display:none だった）
5. **キャッシュを使わず、読んだ版を照合する。** 5.4 の検証は、実際には 5.3 の
   ページに 5.4 のテストを当てていた。Chrome のプロファイルが `%TEMP%` の固定パスに
   残り、そこに worktree から配った 5.3（更新時刻が手元の 5.4 より新しい）が
   キャッシュされていた。次の実行で Chrome が `If-Modified-Since` を送ると、
   標準の `SimpleHTTPRequestHandler` は手元のファイルのほうが古いので 304 を返し、
   キャッシュの 5.3 がそのまま動いた。3 層で塞いである ――
   配信は条件付き要求を無視して常に 200・`Cache-Control: no-store`（cdp.serve）／
   ブラウザは `Network.setCacheDisabled`（cdp.Chrome）／プロファイルは実行ごとに
   `tempfile.mkdtemp()` で作って終了時に消す。さらに起動直後に
   `docs/index.html` のソースの `APP_VERSION` と、設定画面に**見えている**
   `#appver` を突き合わせ、食い違えばケースを回さずに赤で止まる
   （キャッシュ以外の原因で古い版が読まれた場合もここで止まる）
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
from uiharness import cdp, ui as uilib          # noqa: E402

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
PORT = 8790
DEBUG_PORT = 9390
# 実機（Android）が normal、幅の狭い端末が compact。両方を必ず回す（DESIGN.md 2-2）
VIEWPORTS = [("normal", 430, 900), ("compact", 360, 690)]


def load_cases(only):
    import uiharness.cases as pkg
    mods = []
    for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda x: x.name):
        if only and m.name not in only:
            continue
        mods.append(importlib.import_module("uiharness.cases." + m.name))
    if only:
        missing = set(only) - {m.__name__.rsplit(".", 1)[1] for m in mods}
        if missing:
            raise SystemExit("そんなケースは無い: " + ", ".join(sorted(missing)))
    return mods


def source_version():
    """docs/index.html のソースに書いてある APP_VERSION"""
    with open(os.path.join(DOCS, "index.html"), encoding="utf-8") as f:
        m = re.search(r'const APP_VERSION="([^"]+)"', f.read())
    if not m:
        raise SystemExit("docs/index.html に APP_VERSION が見つからない")
    return m.group(1)


def check_version(chrome, url, want):
    """読み込んだページが手元の版かを、設定画面に見えている #appver で確かめる
    （つまずき 4・5）。#appver は設定画面にしか無いので、開いてから読む。"""
    helper = uilib.UI(chrome, url, [], "version")
    helper.open()
    helper.click("gear")
    shown = helper.visible("appver")
    text = helper.text("appver")
    ok = shown and text == "バージョン " + want + "（試作）"
    return ok, shown, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", action="append", default=[],
                    help="回すケース名（既定は全部）")
    ap.add_argument("--list", action="store_true", help="ケースの一覧を出す")
    ap.add_argument("--keep-going", action="store_true",
                    help="例外が出ても次のケースへ進む")
    ap.add_argument("--viewport", choices=[v[0] for v in VIEWPORTS],
                    help="片方だけ回す（既定は両方）")
    args = ap.parse_args()

    cases = load_cases(args.case)
    if args.list:
        for m in cases:
            print("%-16s %s" % (m.__name__.rsplit(".", 1)[1], m.NAME))
        return 0

    views = [v for v in VIEWPORTS if not args.viewport or v[0] == args.viewport]
    serve = cdp.serve(DOCS, PORT)
    url = "http://127.0.0.1:%d/index.html" % PORT
    # プロファイルは実行ごとに作って消す。前回の実行のキャッシュや localStorage を
    # 持ち越さない（つまずき 5）
    profile = tempfile.mkdtemp(prefix="make10-verify-ui-")
    chrome = cdp.Chrome(DEBUG_PORT, profile)
    print("Chrome : %s" % chrome.version)
    print("対象   : %s" % url)
    results = []
    broken = []
    t0 = time.time()
    try:
        # 版の照合。食い違ったらケースは 1 つも回さない
        want = source_version()
        chrome.metrics(*VIEWPORTS[0][1:])
        ok, shown, text = check_version(chrome, url, want)
        print("版     : ソース %s ／ 画面 %r（%s）"
              % (want, text, "表示あり" if shown else "表示なし"))
        if not ok:
            print("\n版が一致しない。古い版が読まれている。ケースは回さずに止める")
            return 1
        for name, w, h in views:
            print("\n===== %s (%d×%d) =====" % (name, w, h))
            # 読み込みより先に画面の大きさを決める（つまずき 3）
            chrome.metrics(w, h)
            for mod in cases:
                short = mod.__name__.rsplit(".", 1)[1]
                helper = uilib.UI(chrome, url, results, name)
                helper.case = short
                start = len(results)
                try:
                    mod.run(helper)
                except Exception as e:                      # ケースの事故も赤
                    broken.append((name, short, str(e)))
                    results.append((False, name, short, "ケースが最後まで走らない",
                                    str(e)[:200], "例外なし"))
                    if not args.keep_going:
                        raise
                ng = [r for r in results[start:] if not r[0]]
                print("  %-16s %-24s %3d 項目  %s"
                      % (short, mod.NAME, len(results) - start,
                         "OK" if not ng else "NG %d 件" % len(ng)))
                for r in ng:
                    print("      NG %s\n         実測=%r 期待=%r" % (r[3], r[4], r[5]))
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
                print("  [%s] %s / %s  実測=%r 期待=%r"
                      % (r[1], r[2], r[3], r[4], r[5]))
        return 1
    if broken:
        return 1
    print("すべて通った")
    return 0


if __name__ == "__main__":
    sys.exit(main())
