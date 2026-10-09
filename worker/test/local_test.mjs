// Make10 デイリーの集計: 手元の試し（DAILY-SPEC 11 章「サーバーの側」・17-3）。
//
//   npm test            （worker/ の中で。Node が要る）
//
// wrangler を手元で立ち上げ（wrangler dev --local と、手元の D1）、
//   1. 範囲の外の値と、Origin が違う要求を、足さずに断ること
//   2. 100 件を同時に送って、数が合うこと（2 回ぶん＝200 件）
// を確かめる。データは毎回、一時フォルダに作って終わったら消す（本番にも、手元の .wrangler にも残さない）。
// 1 つでも落ちたら終了コード 1。
//
// 起点日は、試しのあいだだけ「今日が #11」になる日に差し替える（wrangler.toml の値は遠い未来なので、
// そのままだと受け付ける問題番号が 1 つも無い）。
// MAKE10_WORKER_MAIN に別のファイルを入れると、そちらを Worker の本体として試す（わざと壊して赤くなることの確かめ用）。
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

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
    ["パスが違う", () => fetch(BASE + "/x", { method: "POST", headers: { Origin: ORIGIN }, body: JSON.stringify(good) }), 404, "path"],
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
}

// ── 立ち上げて、試して、片付ける ──
const node = process.execPath;
const env = { ...process.env, WRANGLER_SEND_METRICS: "false", CI: "1" };      // 利用状況の送信と、対話の問いかけを切る
const sch = spawnSync(node, [WRANGLER, "d1", "execute", "make10-daily", "--local", "--persist-to", dir, "--file", "schema.sql"],
  { cwd: HERE, encoding: "utf8", env });
if (sch.status !== 0) { console.error(sch.stdout, sch.stderr); rmSync(dir, { recursive: true, force: true }); process.exit(1); }
const args = [WRANGLER, "dev", ...(main ? [main] : []), "--config", join(HERE, "wrangler.toml"), "--local", "--port", String(PORT), "--persist-to", dir,
  "--var", `DAILY_START:${start}`, "--show-interactive-dev-session=false"];
const child = spawn(node, args, { cwd: HERE, stdio: ["ignore", "pipe", "pipe"], env });
let log = "";
child.stdout.on("data", (d) => { log += d; });
child.stderr.on("data", (d) => { log += d; });
let code = 1;
try {
  let up = false;
  for (let i = 0; i < 120 && !up; i++) {
    await new Promise((r) => setTimeout(r, 500));
    try { up = (await fetch(BASE + "/x")).status === 404; } catch (e) { /* まだ */ }
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
