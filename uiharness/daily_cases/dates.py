# -*- coding: utf-8 -*-
"""日付から問題番号（DAILY-SPEC 5 章）。

「今日」は端末のローカル時刻の日付。問題番号は、起点日（#1）から今日までの日数 + 1。
端末の時計と時間帯を差し替えて、0 時の前後・時間帯の違い・夏時間の切り替え日を見る。
`?date=` は付けない（付けると端末の時計を見ないので、この確かめにならない）。

期待値は、その時間帯での暦の日付から Python で数える。
"""
import datetime

from uiharness import daily_ui as dui

NAME = "日付から問題番号"


def ms(y, mo, d, h, mi, offset_hours):
    """その時間帯の「y 年 mo 月 d 日 h 時 mi 分」の UTC のミリ秒"""
    tz = datetime.timezone(datetime.timedelta(hours=offset_hours))
    return int(datetime.datetime(y, mo, d, h, mi, tzinfo=tz).timestamp() * 1000)


def run(ui):
    start, rows = dui.page_data()
    y = start.year

    def shown():
        """見えているもの。問題が出ていれば上のバーの文字、出ていなければ「問題がありません」"""
        return ui.text("dinfo") if ui.visible("play") else ui.text("nopuzzle")

    def want(day):
        no = (day - start).days + 1
        return dui.top_text(no, day) if 1 <= no <= len(rows) else "問題がありません"

    d1 = start + datetime.timedelta(days=1)
    before = start - datetime.timedelta(days=1)

    # ── 日本（UTC+9）。0 時の前後 ──
    for name, day, hh, mi in (("起点日の前日 23:59", before, 23, 59), ("起点日 0:00", start, 0, 0),
                              ("起点日 23:59", start, 23, 59), ("2 日目 0:00", d1, 0, 0)):
        ui.open(now=ms(day.year, day.month, day.day, hh, mi, 9), tz="Asia/Tokyo")
        ui.check("日本・%s" % name, shown(), want(day))
    ui.check("?date= が無いのでテスト表示は出ない", ui.visible("dtest"), False)

    # ── 同じ瞬間でも、時間帯で日付が違う ──
    # 日本の 2 日目 0:30 ＝ ハワイ（UTC-10）では起点日の 5:30
    t = ms(d1.year, d1.month, d1.day, 0, 30, 9)
    ui.open(now=t, tz="Asia/Tokyo")
    ui.check("同じ瞬間: 日本は 2 日目", shown(), want(d1))
    ui.open(now=t, tz="Pacific/Honolulu")
    ui.check("同じ瞬間: ハワイは起点日（#1）", shown(), want(start))
    # 日本の起点日 19:30 ＝ キリバス（ライン諸島・UTC+14）では 2 日目の 0:30
    t = ms(start.year, start.month, start.day, 19, 30, 9)
    ui.open(now=t, tz="Asia/Tokyo")
    ui.check("同じ瞬間: 日本は起点日（#1）", shown(), want(start))
    ui.open(now=t, tz="Pacific/Kiritimati")
    ui.check("同じ瞬間: キリバスは 2 日目", shown(), want(d1))
    # 日本の起点日 0:30 ＝ ハワイではまだ前日 → 問題がありません
    ui.open(now=ms(start.year, start.month, start.day, 0, 30, 9), tz="Pacific/Honolulu")
    ui.check("日本が起点日になった直後、ハワイはまだ前日", shown(), want(before))

    # ── 夏時間の切り替え日（ニューヨーク）。1 日が 23 時間・25 時間になる日でも、1 日に 1 つ進む ──
    # 3 月の第 2 日曜に始まり（その日は 23 時間）、11 月の第 1 日曜に終わる（その日は 25 時間）
    def nth_sunday(month, n):
        d = datetime.date(y, month, 1)
        d += datetime.timedelta(days=(6 - d.weekday()) % 7)
        return d + datetime.timedelta(days=7 * (n - 1))

    spring, fall = nth_sunday(3, 2), nth_sunday(11, 1)
    one = datetime.timedelta(days=1)
    for name, day, hh, mi, off in (
            ("始まる前日 23:30（冬時間）", spring - one, 23, 30, -5),
            ("始まる日 0:30（冬時間）", spring, 0, 30, -5),
            ("始まる日 23:30（夏時間）", spring, 23, 30, -4),
            ("始まった翌日 0:30（夏時間）", spring + one, 0, 30, -4),
            ("終わる日 0:30（夏時間）", fall, 0, 30, -4),
            ("終わる日 23:30（冬時間）", fall, 23, 30, -5),
            ("終わった翌日 0:30（冬時間）", fall + one, 0, 30, -5)):
        ui.open(now=ms(day.year, day.month, day.day, hh, mi, off), tz="America/New_York")
        # 差し替えた時計が、その時間帯で狙った日付になっていること（期待値の前提）
        ui.check("夏時間・%s: 端末の日付" % name,
                 ui.ev("(function(){const n=new Date();"
                       "return [n.getFullYear(),n.getMonth()+1,n.getDate(),n.getHours()]})()"),
                 [day.year, day.month, day.day, hh])
        ui.check("夏時間・%s: 問題番号" % name, shown(), want(day))
    ui.check_no_errors()
    ui.open(tz=None)                    # 時間帯の差し替えを戻す
