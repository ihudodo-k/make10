-- Make10 デイリーの集計（DAILY-SPEC 17-3）。1 日（問題番号）を 1 行に足していく。1 件ごとの行は持たない。
--   n  = 問題番号
--   s  = 解いた数          g = ギブアップの数        s0 = ヒント 0 回で解いた数
--   b0〜b4 = 解いた人の時間の帯ごとの数（30 秒未満・1 分未満・2 分未満・5 分未満・5 分以上）
CREATE TABLE IF NOT EXISTS days (
  n  INTEGER PRIMARY KEY,
  s  INTEGER NOT NULL DEFAULT 0,
  g  INTEGER NOT NULL DEFAULT 0,
  s0 INTEGER NOT NULL DEFAULT 0,
  b0 INTEGER NOT NULL DEFAULT 0,
  b1 INTEGER NOT NULL DEFAULT 0,
  b2 INTEGER NOT NULL DEFAULT 0,
  b3 INTEGER NOT NULL DEFAULT 0,
  b4 INTEGER NOT NULL DEFAULT 0
);
