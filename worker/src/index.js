// Make10 デイリーの集計（DAILY-SPEC 17-2・17-3）。
//
//   POST /r   中身は text/plain の JSON 文字列 {"n":問題番号,"r":"s"|"g","t":秒,"h":ヒントの回数}
//             → その日の行に足して、足した後の集計を返す
//   GET  /r?n=問題番号 → その日の集計を返す
//
// 返す集計: {"n":23,"s":解いた数,"g":ギブアップの数,"s0":ヒント 0 回で解いた数,"b":[帯ごとの数 5 つ]}
// 断るとき: {"e":"origin"|"range"|"value"|"body"|"path"|"method"}
//   range（問題番号が今日の前後 1 日に無い）は、ページが「送り直しをやめる」合図に使う。
//
// ズルへの備えは、値の範囲と Origin を確かめるだけ（17-3）。人や端末を見分けるものは受け取らないし、残さない。

// 時間の帯の区切り（秒）。30 秒未満・1 分未満・2 分未満・5 分未満・5 分以上（17-4）。
// ページ（docs/daily/index.html の AGG_BANDS）と同じ値にする。食い違いは verify_daily.py のケース server が赤にする
const BANDS = [30, 60, 120, 300];
// 時間（秒）の範囲。1 秒〜24 時間
const T_MIN = 1;
const T_MAX = 86400;
const BODY_MAX = 200;                    // 中身の長さの上限（文字）
const DAY = 86400000;

// 問題番号 = 起点日（#1）から、その瞬間の UTC の日付までの日数 + 1
function dayNo(start, ms) {
  const [y, m, d] = start.split("-").map(Number);
  return Math.floor((Math.floor(ms / DAY) * DAY - Date.UTC(y, m - 1, d)) / DAY) + 1;
}
const bandOf = (t) => { let i = 0; while (i < BANDS.length && t >= BANDS[i]) i++; return i; };

const UPSERT =
  "INSERT INTO days (n,s,g,s0,b0,b1,b2,b3,b4) VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9) " +
  "ON CONFLICT(n) DO UPDATE SET s=s+excluded.s, g=g+excluded.g, s0=s0+excluded.s0, " +
  "b0=b0+excluded.b0, b1=b1+excluded.b1, b2=b2+excluded.b2, b3=b3+excluded.b3, b4=b4+excluded.b4";
const SELECT = "SELECT n,s,g,s0,b0,b1,b2,b3,b4 FROM days WHERE n=?1";

const agg = (n, row) => row
  ? { n, s: row.s, g: row.g, s0: row.s0, b: [row.b0, row.b1, row.b2, row.b3, row.b4] }
  : { n, s: 0, g: 0, s0: 0, b: [0, 0, 0, 0, 0] };

export default {
  async fetch(req, env) {
    const cors = { "Access-Control-Allow-Origin": env.ALLOW_ORIGIN, "Vary": "Origin", "Cache-Control": "no-store" };
    const reply = (status, body) => new Response(JSON.stringify(body), {
      status, headers: { ...cors, "Content-Type": "application/json; charset=utf-8" } });

    const url = new URL(req.url);
    if (url.pathname !== "/r") return reply(404, { e: "path" });
    // 事前確認は、ページの送り方（text/plain の単純な POST）では出ない。出たら、中身なしで返すだけ
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: {
      ...cors, "Access-Control-Allow-Methods": "GET, POST", "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400" } });
    if (req.method !== "GET" && req.method !== "POST") return reply(405, { e: "method" });
    if (req.headers.get("Origin") !== env.ALLOW_ORIGIN) return reply(403, { e: "origin" });

    // 問題番号は、サーバーの今の日付（UTC）から見て、前後 1 日の範囲（時間帯の差のぶん）
    const today = dayNo(env.DAILY_START, Date.now());
    const inRange = (n) => Number.isInteger(n) && n >= 1 && n >= today - 1 && n <= today + 1;

    if (req.method === "GET") {
      const raw = url.searchParams.get("n") || "";
      if (!/^[0-9]{1,6}$/.test(raw)) return reply(400, { e: "value" });
      const n = Number(raw);
      if (!inRange(n)) return reply(400, { e: "range" });
      return reply(200, agg(n, await env.DB.prepare(SELECT).bind(n).first()));
    }

    const text = await req.text();
    if (text.length > BODY_MAX) return reply(400, { e: "body" });
    let x;
    try { x = JSON.parse(text); } catch (e) { return reply(400, { e: "body" }); }
    if (!x || typeof x !== "object" || Array.isArray(x)) return reply(400, { e: "body" });
    const { n, r, t, h } = x;
    if (!Number.isInteger(n) || n < 1) return reply(400, { e: "value" });
    if (r !== "s" && r !== "g") return reply(400, { e: "value" });
    if (!Number.isInteger(h) || h < 0 || h > 2) return reply(400, { e: "value" });
    // ギブアップのときの時間は集計に使わないので、見ない（17-2）
    if (r === "s" && !(Number.isInteger(t) && t >= T_MIN && t <= T_MAX)) return reply(400, { e: "value" });
    if (!inRange(n)) return reply(400, { e: "range" });

    // 足すのは 1 文（読んでから書く形にしない）。同時に届いても数がずれない
    const solved = r === "s" ? 1 : 0;
    const b = [0, 0, 0, 0, 0];
    if (solved) b[bandOf(t)] = 1;
    const out = await env.DB.batch([
      env.DB.prepare(UPSERT).bind(n, solved, 1 - solved, solved && h === 0 ? 1 : 0, ...b),
      env.DB.prepare(SELECT).bind(n),
    ]);
    return reply(200, agg(n, out[1].results[0]));
  },
};
