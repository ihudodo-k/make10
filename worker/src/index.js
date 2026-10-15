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
//
// 別の端末へ移す（DAILY-SPEC 10-1。D0.37）。どちらも中身は text/plain の JSON 文字列（事前確認を出さない単純な POST）
//   POST /x       {"days":{…},"set":{…}} を預かり、{"c":"K7P2QX","s":600}（コードと、有効な秒数）を返す
//   POST /x/take  {"c":"K7P2QX"} → 預かった中身 {"d":{…}} を返し、その場で消す（2 回目は 404）
// 断るとき: {"e":"origin"|"body"|"code"（無い・期限切れ・受け取り済み）|"busy"（回数が多すぎる）}
// 預かった行は、期限（10 分）を過ぎるか受け取られたら消す。コードの当てずっぽうに備えて、/x と /x/take は
// 1 つの IP から 1 分に 10 回まで（wrangler.toml の XFER_LIMIT。Cloudflare の回数制限の仕組み。IP はその数えに使うだけで、D1 には残さない）

// 時間の帯の区切り（秒）。30 秒未満・1 分未満・2 分未満・5 分未満・5 分以上（17-4）。
// ページ（docs/daily/index.html の AGG_BANDS）と同じ値にする。食い違いは verify_daily.py のケース server が赤にする
const BANDS = [30, 60, 120, 300];
// 時間（秒）の範囲。1 秒〜24 時間
const T_MIN = 1;
const T_MAX = 86400;
const BODY_MAX = 200;                    // 中身の長さの上限（文字）
const DAY = 86400000;
// 別の端末へ移す（10-1）
const XFER_TTL = 600000;                 // 預かる時間（ミリ秒）。10 分。手元の試しだけ XFER_TTL_MS で縮める
const XFER_MAX = 262144;                 // 預かる中身の長さの上限（文字）。毎日遊んで 3 年分の記録が約 7.7 万文字（DAILY-SPEC 10 章）なので、10 年分ほど
// コードの字。見間違えやすい 0・O・1・I・L を除いた 31 字（ページの MOVE_CHARS と同じ）。6 字で約 8.9 億通り
const CODE_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ";
const CODE_LEN = 6;
const CODE_RE = /^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{6}$/;

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

// 預ける・受け取る（10-1）
const XFER_SWEEP = "DELETE FROM xfer WHERE x<=?1";
const XFER_PUT = "INSERT INTO xfer (c,d,x) VALUES (?1,?2,?3) ON CONFLICT(c) DO NOTHING";
const XFER_TAKE = "DELETE FROM xfer WHERE c=?1 RETURNING d,x";

// ランダムなコード。偏らないよう、31 の倍数（248）以上のバイトは捨てて引き直す
function newCode() {
  let c = "";
  while (c.length < CODE_LEN) {
    for (const b of crypto.getRandomValues(new Uint8Array(16))) {
      if (b < 248 && c.length < CODE_LEN) c += CODE_CHARS[b % 31];
    }
  }
  return c;
}

const agg = (n, row) => row
  ? { n, s: row.s, g: row.g, s0: row.s0, b: [row.b0, row.b1, row.b2, row.b3, row.b4] }
  : { n, s: 0, g: 0, s0: 0, b: [0, 0, 0, 0, 0] };

export default {
  async fetch(req, env) {
    const cors = { "Access-Control-Allow-Origin": env.ALLOW_ORIGIN, "Vary": "Origin", "Cache-Control": "no-store" };
    // 預かった中身は、受け取ったときに JSON の文字列のまま返すので、文字列も受け付ける
    const reply = (status, body) => new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status, headers: { ...cors, "Content-Type": "application/json; charset=utf-8" } });

    const url = new URL(req.url);
    const path = url.pathname;
    if (path !== "/r" && path !== "/x" && path !== "/x/take") return reply(404, { e: "path" });
    // 事前確認は、ページの送り方（text/plain の単純な POST）では出ない。出たら、中身なしで返すだけ
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: {
      ...cors, "Access-Control-Allow-Methods": "GET, POST", "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400" } });
    if (req.method !== "GET" && req.method !== "POST") return reply(405, { e: "method" });
    if (req.headers.get("Origin") !== env.ALLOW_ORIGIN) return reply(403, { e: "origin" });
    if (path !== "/r") return xfer(req, env, path, reply);

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

// 別の端末へ移す（10-1）。Origin はもう確かめてある
async function xfer(req, env, path, reply) {
  if (req.method !== "POST") return reply(405, { e: "method" });
  // 回数の制限。仕組みが付いていない環境（設定を外したとき）では数えない
  if (env.XFER_LIMIT) {
    const { success } = await env.XFER_LIMIT.limit({ key: req.headers.get("CF-Connecting-IP") || "-" });
    if (!success) return reply(429, { e: "busy" });
  }
  const now = Date.now();
  const text = await req.text();
  if (text.length > XFER_MAX) return reply(400, { e: "body" });
  let x;
  try { x = JSON.parse(text); } catch (e) { return reply(400, { e: "body" }); }
  if (!x || typeof x !== "object" || Array.isArray(x)) return reply(400, { e: "body" });

  if (path === "/x/take") {
    if (typeof x.c !== "string" || !CODE_RE.test(x.c)) return reply(400, { e: "body" });
    // 読むのと消すのを 1 文で行う。同じコードで同時に受け取っても、中身を返すのは 1 回だけ
    const row = await env.DB.prepare(XFER_TAKE).bind(x.c).first();
    if (!row || row.x <= now) return reply(404, { e: "code" });
    return reply(200, `{"d":${row.d}}`);
  }

  // 預ける。中身の形は、受け取る側のページが 1 日ずつ確かめる。ここでは記録の入れ物があることだけを見る
  if (!x.days || typeof x.days !== "object" || Array.isArray(x.days)) return reply(400, { e: "body" });
  const ttl = Number(env.XFER_TTL_MS) > 0 ? Number(env.XFER_TTL_MS) : XFER_TTL;
  await env.DB.prepare(XFER_SWEEP).bind(now).run();
  // コードがたまたま使用中なら、引き直す（約 8.9 億通りなので、ほぼ起きない）
  for (let i = 0; i < 5; i++) {
    const c = newCode();
    const r = await env.DB.prepare(XFER_PUT).bind(c, text, now + ttl).run();
    if (r.meta.changes === 1) return reply(200, { c, s: Math.round(ttl / 1000) });
  }
  return reply(503, { e: "busy" });
}
