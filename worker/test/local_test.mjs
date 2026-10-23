// Make10 デイリーの集計: 手元の試し（DAILY-SPEC 11 章「サーバーの側」・17-3）。
//
//   npm test            （worker/ の中で。Node が要る）
//
// wrangler を手元で立ち上げ（wrangler dev --local と、手元の D1）、
//   1. 範囲の外の値と、Origin が違う要求を、足さずに断ること
//   2. 100 件を同時に送って、数が合うこと（2 回ぶん＝200 件）
//   3. 別の端末へ移す（D0.37。DAILY-SPEC 10-1）: 預けて受け取れる・2 回目は受け取れない・期限・断る値・同時に受け取っても 1 回・回数の制限
//   4. 中身の上限（D0.43）: Content-Length が上限より大きければ読まずに断る・無いときも上限を超えた時点で打ち切る
// を確かめる。データは毎回、一時フォルダに作って終わったら消す（本番にも、手元の .wrangler にも残さない）。
// 1 つでも落ちたら終了コード 1。
//
// 起点日は、試しのあいだだけ「今日が #11」になる日に差し替える（wrangler.toml の値は遠い未来なので、
// そのままだと受け付ける問題番号が 1 つも無い）。預かる時間も、試しのあいだだけ XFER_TTL_SEC 秒に縮める。
// MAKE10_WORKER_MAIN に別のファイルを入れると、そちらを Worker の本体として試す（わざと壊して赤くなることの確かめ用）。
import { spawn, spawnSync } from "node:child_process";
import { request as httpRequest } from "node:http";
import { pathToFileURL } from "node:url";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { statements } from "../schema_each.mjs";

const HERE = dirname(dirname(fileURLToPath(import.meta.url)));        // worker/
const WRANGLER = join(HERE, "node_modules", "wrangler", "bin", "wrangler.js");
const PORT = Number(process.env.MAKE10_WORKER_PORT || 8799);
const BASE = `http://127.0.0.1:${PORT}`;
const ORIGIN = "https://make10.app";
const TODAY = 11;                                                     // 試しのあいだの「今日」の問題番号
const start = new Date(Math.floor(Date.now() / 86400000) * 86400000 - (TODAY - 1) * 86400000)
  .toISOString().slice(0, 10);
const dir = mkdtempSync(join(tmpdir(), "make10-worker-"));
const main = process.env.MAKE10_WORKER_MAIN;
const XFER_TTL_SEC = 3;                                               // 試しのあいだの、預かる時間（秒）

let ok = 0, ng = 0;
function check(name, got, want) {
  const same = JSON.stringify(got) === JSON.stringify(want);
  if (same) ok++; else ng++;
  console.log(`  ${same ? "OK" : "NG"}  ${name}` + (same ? "" : `\n        実測=${JSON.stringify(got)}\n        期待=${JSON.stringify(want)}`));
}
const post = (body, headers = { Origin: ORIGIN }) => fetch(BASE + "/r", {
  method: "POST", headers: { "Content-Type": "text/plain", ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body) });
const get = (n, headers = { Origin: ORIGIN }) => fetch(`${BASE}/r?n=${n}`, { headers });
const body = async (r) => [r.status, await r.json()];
const zero = (n) => ({ n, s: 0, g: 0, s0: 0, b: [0, 0, 0, 0, 0] });

function stop(child) {
  if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"]);
  else child.kill("SIGKILL");
}

async function run() {
  // ── 表を作る文の分け方（公開前の総点検の H2）: Windows の Git が CRLF で取り出した schema.sql でも、LF と同じ文に分ける ──
  const sql = readFileSync(join(HERE, "schema.sql"), "utf8").replace(/\r\n/g, "\n");
  const lf = statements(sql), crlf = statements(sql.replace(/\n/g, "\r\n"));
  check("schema.sql の文の分け方は、改行が CRLF でも LF と同じ（3 文・注釈が残らない）",
    [crlf, lf.length, crlf.some((s) => s.includes("--"))], [lf, 3, false]);

  // ── 一覧にある値を 1 つずつ変えた、断られるはずの要求 ──
  const good = { n: TODAY, r: "s", t: 42, h: 0 };
  check("最初は 0（GET）", await body(await get(TODAY)), [200, zero(TODAY)]);
  const r0 = await get(TODAY);
  check("返事に Access-Control-Allow-Origin: https://make10.app と no-store",
    [r0.headers.get("access-control-allow-origin"), r0.headers.get("cache-control")], [ORIGIN, "no-store"]);
  const bad = [
    ["Origin が無い", () => post(good, {}), 403, "origin"],
    ["Origin が違う", () => post(good, { Origin: "https://example.com" }), 403, "origin"],
    ["Origin が http", () => post(good, { Origin: "http://make10.app" }), 403, "origin"],
    ["GET: Origin が違う", () => get(TODAY, { Origin: "https://example.com" }), 403, "origin"],
    ["問題番号が 2 日前", () => post({ ...good, n: TODAY - 2 }), 400, "range"],
    ["問題番号が 2 日後", () => post({ ...good, n: TODAY + 2 }), 400, "range"],
    ["GET: 問題番号が 2 日前", () => get(TODAY - 2), 400, "range"],
    ["問題番号が 0", () => post({ ...good, n: 0 }), 400, "value"],
    ["問題番号が小数", () => post({ ...good, n: TODAY + 0.5 }), 400, "value"],
    ["問題番号が文字", () => post({ ...good, n: String(TODAY) }), 400, "value"],
    ["GET: 問題番号が無い", () => fetch(BASE + "/r", { headers: { Origin: ORIGIN } }), 400, "value"],
    ["GET: 問題番号が数字でない", () => get("1e1"), 400, "value"],
    ["結果が知らない値", () => post({ ...good, r: "x" }), 400, "value"],
    ["時間が 0", () => post({ ...good, t: 0 }), 400, "value"],
    ["時間が 24 時間より長い", () => post({ ...good, t: 86401 }), 400, "value"],
    ["時間が小数", () => post({ ...good, t: 1.5 }), 400, "value"],
    ["解いたのに時間が無い", () => post({ n: TODAY, r: "s", h: 0 }), 400, "value"],
    ["ヒントが 3 回", () => post({ ...good, h: 3 }), 400, "value"],
    ["ヒントが -1 回", () => post({ ...good, h: -1 }), 400, "value"],
    ["ヒントが無い", () => post({ n: TODAY, r: "s", t: 42 }), 400, "value"],
    ["中身が JSON でない", () => post("hello"), 400, "body"],
    ["中身が配列", () => post("[1,2,3]"), 400, "body"],
    ["中身が長すぎる", () => post(JSON.stringify({ ...good, x: "a".repeat(300) })), 400, "body"],
    ["パスが違う", () => fetch(BASE + "/nope", { method: "POST", headers: { Origin: ORIGIN }, body: JSON.stringify(good) }), 404, "path"],
    ["PUT", () => fetch(BASE + "/r", { method: "PUT", headers: { Origin: ORIGIN }, body: JSON.stringify(good) }), 405, "method"],
  ];
  const got = [];
  for (const [name, f, status, e] of bad) {
    const r = await f();
    const j = await r.json().catch(() => null);
    if (r.status !== status || !j || j.e !== e) got.push([name, r.status, j]);
  }
  check(`範囲の外・Origin 違いの ${bad.length} 通りを、決めた返事で断る`, got, []);
  check("断った後も、どの日も 0 のまま（足していない）",
    [await body(await get(TODAY - 1)), await body(await get(TODAY)), await body(await get(TODAY + 1))],
    [[200, zero(TODAY - 1)], [200, zero(TODAY)], [200, zero(TODAY + 1)]]);
  const opt = await fetch(BASE + "/r", { method: "OPTIONS", headers: { Origin: ORIGIN } });
  check("事前確認（OPTIONS）は 204 で、足さない", opt.status, 204);

  // ── 100 件を同時に送る ──
  // 解いた 70 件（時間の帯ごとに 10・20・25・10・5 件。ヒント 0 回は 3 件に 1 件が 1 回以上）、ギブアップ 30 件
  const times = [[5, 10], [45, 20], [90, 25], [200, 10], [900, 5]];
  const batch = [];
  let k = 0, s0 = 0;
  for (const [t, c] of times) for (let i = 0; i < c; i++) {
    const h = k++ % 3 === 0 ? 1 + (k % 2) : 0;
    if (h === 0) s0++;
    batch.push({ n: TODAY, r: "s", t, h });
  }
  for (let i = 0; i < 30; i++) batch.push(i % 2 ? { n: TODAY, r: "g", t: null, h: i % 3 } : { n: TODAY, r: "g", h: i % 3 });
  for (let i = batch.length - 1; i > 0; i--) { const j = (i * 7919) % (i + 1); [batch[i], batch[j]] = [batch[j], batch[i]]; }
  const want1 = { n: TODAY, s: 70, g: 30, s0, b: [10, 20, 25, 10, 5] };

  let res = await Promise.all(batch.map((b) => post(b).then(body)));
  check("100 件を同時に送る: 全部 200", res.filter(([st]) => st !== 200).length, 0);
  check("100 件のどの返事も、その時点の集計（合計は 1〜100）",
    res.filter(([, j]) => !(j && j.n === TODAY && j.s + j.g >= 1 && j.s + j.g <= 100
      && j.b.reduce((a, c) => a + c, 0) === j.s && j.s0 <= j.s)).length, 0);
  check("返事の合計は、1〜100 が 1 つずつ（同じ数が 2 回返らない）",
    res.map(([, j]) => j.s + j.g).sort((a, b) => a - b).join(), Array.from({ length: 100 }, (_, i) => i + 1).join());
  check("100 件のあと、数が合う（解いた 70・ギブアップ 30・ヒントなし・時間の帯）", await body(await get(TODAY)), [200, want1]);

  res = await Promise.all(batch.map((b) => post(b).then(body)));
  check("もう 100 件を同時に送る: 全部 200", res.filter(([st]) => st !== 200).length, 0);
  check("200 件のあと、数がちょうど 2 倍", await body(await get(TODAY)),
    [200, { n: TODAY, s: 140, g: 60, s0: s0 * 2, b: want1.b.map((x) => x * 2) }]);

  // ── 前後 1 日は受け付け、別の行に足す。帯の境目 ──
  check("昨日の問題番号は受け付ける（時間帯の差）", await body(await post({ n: TODAY - 1, r: "s", t: 30, h: 2 })),
    [200, { n: TODAY - 1, s: 1, g: 0, s0: 0, b: [0, 1, 0, 0, 0] }]);
  check("明日の問題番号は受け付ける（時間帯の差）", await body(await post({ n: TODAY + 1, r: "g", h: 0 })),
    [200, { n: TODAY + 1, s: 0, g: 1, s0: 0, b: [0, 0, 0, 0, 0] }]);
  const edges = [[1, 0], [29, 0], [30, 1], [59, 1], [60, 2], [119, 2], [120, 3], [299, 3], [300, 4], [86400, 4]];
  const edge = [];
  let prev = (await (await get(TODAY + 1)).json()).b;
  for (const [t, i] of edges) {
    const j = await (await post({ n: TODAY + 1, r: "s", t, h: 0 })).json();
    const at = j.b.findIndex((x, q) => x !== prev[q]);
    if (at !== i) edge.push([t, at, i]);
    prev = j.b;
  }
  check("時間の帯の境目（29 秒は 1 つ目・30 秒は 2 つ目 … 300 秒は 5 つ目）", edge, []);
  check("別の日の行は動いていない", (await (await get(TODAY)).json()).s, 140);

  await runXfer();
  await runBody();
  await runHeaders();
  runIndex();
}

// ── どの返事にも X-Content-Type-Options: nosniff（D0.45）──
async function runHeaders() {
  const H = (x = {}) => ({ Origin: ORIGIN, "Content-Type": "text/plain", "CF-Connecting-IP": ip(), ...x });
  const one = { "CF-Connecting-IP": "203.0.113.99" };
  for (let i = 0; i < 10; i++) await xtake("ABCDEF", one);                    // 11 回目を 429 にする
  const kinds = [
    ["GET /r 200", () => get(TODAY), 200],
    ["POST /r 200", () => post({ n: TODAY + 1, r: "g", h: 0 }), 200],
    ["POST /r 400", () => post("x"), 400],
    ["Origin 違い 403", () => get(TODAY, { Origin: "https://example.com" }), 403],
    ["パス違い 404", () => fetch(BASE + "/nope", { headers: H() }), 404],
    ["PUT 405", () => fetch(BASE + "/r", { method: "PUT", headers: H(), body: "{}" }), 405],
    ["OPTIONS 204", () => fetch(BASE + "/r", { method: "OPTIONS", headers: H() }), 204],
    ["POST /x 200", () => xput({ days: {} }), 200],
    ["POST /x/take 404", () => xtake("ABCDEF"), 404],
    ["POST /x/take 429", () => xtake("ABCDEF", one), 429],
  ];
  const got = [];
  for (const [name, f, st] of kinds) {
    const r = await f();
    await r.arrayBuffer();
    got.push([name, r.status === st, r.headers.get("x-content-type-options")]);
  }
  check("どの返事にも X-Content-Type-Options: nosniff（200・400・403・404・405・204・429）", got,
    kinds.map(([name]) => [name, true, "nosniff"]));
}

// ── 期限を過ぎた行を消す文が、索引を使うこと（D0.44）──
function runIndex() {
  const q = spawnSync(node, [WRANGLER, "d1", "execute", "make10-daily", "--local", "--persist-to", dir, "--json",
    "--command", "EXPLAIN QUERY PLAN DELETE FROM xfer WHERE x<=1"], { cwd: HERE, encoding: "utf8", env });
  let plan = null;
  try { plan = JSON.parse(q.stdout)[0].results.map((r) => r.detail).join(" / "); } catch (e) { plan = q.stdout + q.stderr; }
  check("期限を過ぎた行を消す文（DELETE FROM xfer WHERE x<=?）は、索引 xfer_x を使う（表を全部読まない）",
    /USING (COVERING )?INDEX xfer_x/.test(plan) ? "索引を使う" : plan, "索引を使う");
}

// ── 中身の上限（D0.43）──
// 手元の wrangler dev は、要求の中身を全部受け取ってから Worker に渡す（すぐ返す Worker でも、送り終えるまで返事が来ない）。
// そこで「全部を読まないこと」は、Worker の fetch を Node から直に呼んで見る。中身は、上限を超えても終わらない流れにして、
// 返事が来ること（3 秒以内）と、Worker が引き出したバイト数が上限 ＋ 1 かたまり（4,096）までであることを確かめる。
// Origin と回数の制限より先には進まない要求なので、D1 は要らない（env に DB を渡さない）
const workerMod = await import(pathToFileURL(main ? resolve(HERE, main) : join(HERE, "src", "index.js")).href);
const CHUNK = 4096;
async function direct(path, { len = null, endless = true, bytes = 0 } = {}) {
  let pulled = 0;
  const body = new ReadableStream({
    pull(c) {
      if (!endless && pulled >= bytes) { c.close(); return; }
      if (endless && pulled > 1e7) return new Promise(() => {});      // 1000 万バイトから先は、来ないまま待たせる
      pulled += CHUNK; c.enqueue(new Uint8Array(CHUNK).fill(97));
    } }, { highWaterMark: 0 });                                         // 先読みさせない（引き出された分だけを数える）
  const headers = { Origin: ORIGIN, "Content-Type": "text/plain" };
  if (len !== null) headers["Content-Length"] = String(len);
  const req = new Request("https://api.make10.app" + path, { method: "POST", headers, body, duplex: "half" });
  const env = { ALLOW_ORIGIN: ORIGIN, DAILY_START: start };
  const r = await Promise.race([workerMod.default.fetch(req, env).then(async (x) => [x.status, await x.text()]),
    new Promise((ok) => setTimeout(() => ok(["3 秒待っても返事が来ない"]), 3000))]);
  return [r, pulled];
}

// wrangler dev を通して、分けて送る（Content-Length なし）中身を送り終える。first … 中身
function raw(path, first) {
  return new Promise((done) => {
    const rq = httpRequest(BASE + path, { method: "POST",
      headers: { Origin: ORIGIN, "Content-Type": "text/plain", "CF-Connecting-IP": ip(), "Transfer-Encoding": "chunked" } });
    rq.on("response", (res) => { let b = ""; res.on("data", (d) => { b += d; }); res.on("end", () => done([res.statusCode, b])); });
    rq.on("error", (e) => done(["error " + e.message]));
    rq.end(first);
  });
}

async function runBody() {
  const busy = [400, JSON.stringify({ e: "body" })];
  for (const [path, max] of [["/r", 200], ["/x", 262144], ["/x/take", 262144]]) {
    let [r, pulled] = await direct(path, { len: 10000000 });
    check(`${path}: Content-Length が 1000 万（上限 ${max}）なら、中身を読まずに 400 {"e":"body"}`, [r, pulled], [busy, 0]);
    [r, pulled] = await direct(path);
    check(`${path}: Content-Length なしで終わらない中身は、上限を超えた所で打ち切って 400（引き出したのは上限 ＋ 4,096 バイトまで）`,
      [r, pulled <= max + CHUNK], [busy, true]);
    [r, pulled] = await direct(path, { len: 10 });
    check(`${path}: Content-Length を小さく偽っても、読みながら上限を超えた所で打ち切って 400`, [r, pulled <= max + CHUNK], [busy, true]);
  }
  const ok = await raw("/r", JSON.stringify({ n: TODAY + 1, r: "g", h: 0 }));
  check("/r: Content-Length なしでも、上限までの中身は受け付ける", [ok[0], JSON.parse(ok[1] || "{}").n], [200, TODAY + 1]);
  const ox = await raw("/x", JSON.stringify({ days: {} }));
  check("/x: Content-Length なしでも、上限までの中身は預かる", [ox[0], CODE.test(JSON.parse(ox[1] || "{}").c)], [200, true]);
  const wide = JSON.stringify({ n: TODAY + 1, r: "g", h: 0, x: "あ".repeat(58) });          // 87 文字・203 バイト
  check("/r: 上限は UTF-8 のバイト数（87 文字でも 203 バイトなら 400 {\"e\":\"body\"}）",
    [wide.length, await body(await post(wide))], [87, [400, { e: "body" }]]);
}

// ── 別の端末へ移す（10-1）──
// 回数の制限（1 つの IP から 1 分に 10 回）は、CF-Connecting-IP ごとに数える。確かめの組ごとに別の IP を名乗り、
// 制限そのものを見る組だけが、同じ IP から続けて送る
let ipNo = 0;
const ip = () => `198.51.100.${++ipNo}`;
const xput = (body, headers) => fetch(BASE + "/x", {
  method: "POST", headers: { "Content-Type": "text/plain", Origin: ORIGIN, "CF-Connecting-IP": ip(), ...headers },
  body: typeof body === "string" ? body : JSON.stringify(body) });
const xtake = (c, headers) => fetch(BASE + "/x/take", {
  method: "POST", headers: { "Content-Type": "text/plain", Origin: ORIGIN, "CF-Connecting-IP": ip(), ...headers },
  body: typeof c === "string" ? JSON.stringify({ c }) : JSON.stringify(c) });
const CODE = /^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{6}$/;

async function runXfer() {
  const data = { v: 1, days: { "3": { r: "s", t: 42, h: 1, sh: 1, e: "1 + 2 + 3 + 4" }, "4": { r: "g", t: null, h: 2, sh: 2 } },
    set: { easy: 1, tap: 0, dark: 1, lang: "en" } };
  let [st, j] = await body(await xput(data));
  check("預ける: 200 で、6 文字のコードと有効な秒数", [st, CODE.test(j.c), j.s], [200, true, XFER_TTL_SEC]);
  const r1 = await xtake(j.c);
  check("受け取る: 預けた中身がそのまま返る（Access-Control-Allow-Origin と no-store）",
    [r1.status, await r1.json(), r1.headers.get("access-control-allow-origin"), r1.headers.get("cache-control")],
    [200, { d: data }, ORIGIN, "no-store"]);
  check("同じコードで 2 回目は受け取れない（受け取ったら消す）", await body(await xtake(j.c)), [404, { e: "code" }]);
  check("預けていないコードは受け取れない", await body(await xtake("ABCDEF")), [404, { e: "code" }]);

  // 期限: 縮めた時間を過ぎたら受け取れない
  [st, j] = await body(await xput(data));
  await new Promise((r) => setTimeout(r, XFER_TTL_SEC * 1000 + 600));
  check(`期限（試しでは ${XFER_TTL_SEC} 秒）を過ぎたら受け取れない`, await body(await xtake(j.c)), [404, { e: "code" }]);

  // 同時に受け取っても、中身を返すのは 1 回だけ
  [st, j] = await body(await xput(data));
  const many = await Promise.all(Array.from({ length: 8 }, () => xtake(j.c).then((r) => r.status)));
  check("同じコードを 8 つ同時に受け取る: 200 は 1 つだけで、残りは 404",
    [many.filter((x) => x === 200).length, many.filter((x) => x === 404).length], [1, 7]);

  // コードは毎回ちがう
  const codes = [];
  for (let i = 0; i < 20; i++) codes.push((await (await xput(data)).json()).c);
  check("20 回預けて、コードは 20 通り（どれも決めた 31 字の 6 文字）",
    [new Set(codes).size, codes.every((c) => CODE.test(c))], [20, true]);

  // 断る値
  const bad = [
    ["預ける: Origin が無い", () => xput(data, { Origin: "" }), 403, "origin"],
    ["預ける: Origin が違う", () => xput(data, { Origin: "https://example.com" }), 403, "origin"],
    ["受け取る: Origin が違う", () => xtake(codes[0], { Origin: "https://example.com" }), 403, "origin"],
    ["預ける: JSON でない", () => xput("hello"), 400, "body"],
    ["預ける: 配列", () => xput("[1]"), 400, "body"],
    ["預ける: 記録の入れ物が無い", () => xput({ set: {} }), 400, "body"],
    ["預ける: 記録の入れ物が配列", () => xput({ days: [] }), 400, "body"],
    ["預ける: 長すぎる（262,144 文字より長い）", () => xput({ days: {}, pad: "a".repeat(262144) }), 400, "body"],
    ["受け取る: コードが 5 文字", () => xtake("ABCDE"), 400, "body"],
    ["受け取る: コードに使わない字（O）", () => xtake("ABCDEO"), 400, "body"],
    ["受け取る: コードが小文字", () => xtake("abcdef"), 400, "body"],
    ["受け取る: コードが無い", () => xtake({}), 400, "body"],
    ["GET /x", () => fetch(BASE + "/x", { headers: { Origin: ORIGIN, "CF-Connecting-IP": ip() } }), 405, "method"],
  ];
  const got = [];
  for (const [name, f, status, e] of bad) {
    const r = await f();
    const k = await r.json().catch(() => null);
    if (r.status !== status || !k || k.e !== e) got.push([name, r.status, k]);
  }
  check(`移す受け口: 断るはずの ${bad.length} 通りを、決めた返事で断る`, got, []);
  check("断った後も、預けたコードは受け取れる（断った要求は行を消さない）", (await xtake(codes[0])).status, 200);
  check("中身の長さの上限（262,144 文字ちょうど）は預かる",
    (await xput(JSON.stringify({ days: {}, pad: "a".repeat(262144 - 20) }))).status, 200);

  // 回数の制限: 同じ IP から 1 分に 10 回まで。11 回目からは 429
  const one = { "CF-Connecting-IP": "203.0.113.7" };
  const seq = [];
  for (let i = 0; i < 12; i++) seq.push((await xtake("ABCDEF", one)).status);
  check("同じ IP から 12 回続けて受け取ろうとする: 10 回目までは 404、11 回目からは 429（{\"e\":\"busy\"}）",
    [seq.slice(0, 10).every((x) => x === 404), seq.slice(10).every((x) => x === 429)], [true, true]);
  check("制限されても、別の IP からは受け取れる", (await xtake(codes[1])).status, 200);
  check("回数の制限は、集計の受け口（/r）には掛けない",
    (await fetch(`${BASE}/r?n=${TODAY}`, { headers: { Origin: ORIGIN, ...one } })).status, 200);
}

// ── 立ち上げて、試して、片付ける ──
const node = process.execPath;
const env = { ...process.env, WRANGLER_SEND_METRICS: "false", CI: "1" };      // 利用状況の送信と、対話の問いかけを切る
// MAKE10_WORKER_SCHEMA に別のファイルを入れると、そちらで表を作る（わざと壊して赤くなることの確かめ用。D0.44）
const schema = process.env.MAKE10_WORKER_SCHEMA || "schema.sql";
// 表は、本番と同じ入口（schema_each.mjs。文を 1 つずつ --command で流す）で作る
const sch = spawnSync(node, [join(HERE, "schema_each.mjs"), "--local", "--persist-to", dir, "--schema", schema],
  { cwd: HERE, encoding: "utf8", env });
if (sch.status !== 0) { console.error(sch.stdout, sch.stderr); rmSync(dir, { recursive: true, force: true }); process.exit(1); }
const args = [WRANGLER, "dev", ...(main ? [main] : []), "--config", join(HERE, "wrangler.toml"), "--local", "--port", String(PORT), "--persist-to", dir,
  "--var", `DAILY_START:${start}`, "--var", `XFER_TTL_MS:${XFER_TTL_SEC * 1000}`, "--show-interactive-dev-session=false"];
const child = spawn(node, args, { cwd: HERE, stdio: ["ignore", "pipe", "pipe"], env });
let log = "";
child.stdout.on("data", (d) => { log += d; });
child.stderr.on("data", (d) => { log += d; });
let code = 1;
try {
  let up = false;
  for (let i = 0; i < 120 && !up; i++) {
    await new Promise((r) => setTimeout(r, 500));
    try { up = (await fetch(BASE + "/nope")).status === 404; } catch (e) { /* まだ */ }
  }
  if (!up) throw new Error("wrangler dev が立ち上がらない\n" + log);
  console.log(`Make10 デイリーの集計: 手元の試し（起点日 ${start}・今日は #${TODAY}・${main || "src/index.js"}）`);
  await run();
  console.log(`\n合計 ${ok} / ${ok + ng} 項目` + (ng ? "  落ちた項目あり" : "  すべて通った"));
  code = ng ? 1 : 0;
} catch (e) {
  console.error("試しが最後まで走らない:", e && e.stack || e);
} finally {
  stop(child);
  await new Promise((r) => setTimeout(r, 800));
  try { rmSync(dir, { recursive: true, force: true }); } catch (e) { /* 掴まれていても、一時フォルダなので放っておく */ }
}
process.exit(code);
