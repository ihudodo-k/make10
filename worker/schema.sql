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
-- 別の端末へ移す（DAILY-SPEC 10-1。D0.37）。預かった記録と設定を、受け取られるか期限が来るまで 1 行だけ持つ。
--   c = コード（6 文字）   d = 預かった中身（JSON の文字列）   x = 期限（1970 年からのミリ秒）
-- 受け取ったら、その場で消す。期限を過ぎた行は、次に誰かが預けたときと、受け取ろうとしたときに消す
CREATE TABLE IF NOT EXISTS xfer (
  c TEXT PRIMARY KEY,
  d TEXT NOT NULL,
  x INTEGER NOT NULL
);
-- 期限を過ぎた行を消す文（DELETE FROM xfer WHERE x<=?）が、表を全部読まずに済むように（D0.43 の点検の M1。D0.44）
CREATE INDEX IF NOT EXISTS xfer_x ON xfer (x);
