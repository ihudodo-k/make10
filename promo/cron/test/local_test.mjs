// Make10 promo の定期実行の起こし役: 手元の試し（鍵なし。GitHub には送らない）。
//
//   npm.cmd test        （promo/cron/ の中で。Node が要る。6 は npm.cmd ci で入れた wrangler を使う）
//
// 1〜5 は fetch を GitHub の返事のまねに差し替えて、
//   1. Cron の 2 つの式（8:00・8:30）が、送る URL・ref・inputs・ヘッダーになること
//   2. 知らない式・鍵が無いときは送らないこと。204 以外はログに状態と本文の先頭を出し、2xx 以外は失敗にすること
//   3. HTTP の入口は 404 で、どこにも送らないこと
//   4. wrangler.toml の crons・src/index.js の JOBS・promo.yml の schedule が同じ式であること。鍵がファイルに書かれていないこと
//   5. 送る inputs で、promo.yml の TASK・DRY の式が schedule のときと同じ値（本物として動く）になること
//   6. 本物のランタイム（wrangler dev --local --test-scheduled）で立ち上がり、HTTP は 404・Cron の入口が式で振り分けること。
//      鍵を入れずに立ち上げるので、GitHub へは送らない（.dev.vars があれば鍵が入るおそれがあるので、6 は止める）
// を確かめる。1 つでも落ちたら終了コード 1。
import { existsSync, readFileSync } from "node:fs";
import { spawn, spawnSync } from "node:child_process";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import worker from "../src/index.js";
import { dispatch, JOBS, REPO, WORKFLOW } from "../src/dispatch.js";

const HERE = dirname(dirname(fileURLToPath(import.meta.url)));        // promo/cron/
const ROOT = join(HERE, "..", "..");
const TOKEN = "test-token-not-real";

let ok = 0, ng = 0;
function check(name, got, want) {
  const same = JSON.stringify(got) === JSON.stringify(want);
  if (same) ok++; else ng++;
  console.log(`  ${same ? "OK" : "NG"}  ${name}` + (same ? "" : `\n        実測=${JSON.stringify(got)}\n        期待=${JSON.stringify(want)}`));
}

// GitHub の返事のまね。送った要求を覚える
function fakeGitHub(status = 204, body = "") {
  const calls = [];
  const f = async (url, init) => {
    calls.push({ url, method: init.method, headers: init.headers, body: JSON.parse(init.body) });
    return new Response(status === 204 ? null : body, { status });
  };
  f.calls = calls;
  return f;
}

// console.log を拾う
async function logsOf(fn) {
  const orig = console.log, lines = [];
  console.log = (...a) => lines.push(a.join(" "));
  let err = null;
  try { await fn(); } catch (e) { err = e; } finally { console.log = orig; }
  return { lines, err };
}

// ── GitHub Actions の式（${{ … }}）の、promo.yml の TASK・DRY に要る分だけの評価 ──
// 値の真偽: false・0・""・null が偽。== は型が違えば数に直して比べ、文字列は大文字小文字を区別しない。&& と || は値を返す
function evalExpr(src, ctx) {
  const toks = src.match(/'(?:[^']|'')*'|&&|\|\||==|!=|[()!]|[A-Za-z_][\w.\-]*/g);
  let i = 0;
  const peek = () => toks[i], next = () => toks[i++];
  const truthy = (v) => !(v === false || v === 0 || v === "" || v === null || v === undefined || Number.isNaN(v));
  const num = (v) => v === null || v === undefined ? 0 : typeof v === "boolean" ? +v : typeof v === "string" ? (v.trim() === "" ? 0 : Number(v)) : v;
  const eq = (a, b) => {
    if (typeof a === "string" && typeof b === "string") return a.toLowerCase() === b.toLowerCase();
    if (typeof a === typeof b) return a === b;
    return num(a) === num(b);
  };
  function primary() {
    const t = next();
    if (t === "(") { const v = or(); next(); return v; }
    if (t === "!") return !truthy(primary());
    if (t.startsWith("'")) return t.slice(1, -1).replace(/''/g, "'");
    if (t === "true") return true;
    if (t === "false") return false;
    if (t === "null") return null;
    return t.split(".").reduce((o, k) => (o == null ? null : o[k] ?? null), ctx);
  }
  function cmp() {
    let a = primary();
    while (peek() === "==" || peek() === "!=") { const op = next(); const b = primary(); a = op === "==" ? eq(a, b) : !eq(a, b); }
    return a;
  }
  function and() { let a = cmp(); while (peek() === "&&") { next(); const b = cmp(); a = truthy(a) ? b : a; } return a; }
  function or() { let a = and(); while (peek() === "||") { next(); const b = and(); a = truthy(a) ? a : b; } return a; }
  return or();
}

// workflow_dispatch の入力を、promo.yml に書いた型で inputs の文脈に直す（GitHub は boolean の入力を真偽値にする）
function typedInputs(raw, types) {
  const out = {};
  for (const [k, v] of Object.entries(raw)) out[k] = types[k] === "boolean" ? String(v).toLowerCase() === "true" : String(v);
  return out;
}

async function run() {
  // ── 1. 送る中身 ──
  console.log("1. Cron の式から送る中身");
  for (const [cron, task] of [["0 8 * * *", "collect"], ["30 8 * * *", "post"]]) {
    const gh = fakeGitHub(204);
    const { lines, err } = await logsOf(() => dispatch(cron, { GH_TOKEN: TOKEN }, gh));
    const c = gh.calls[0] || {};
    check(`${cron}: 1 回だけ送る・失敗にしない`, [gh.calls.length, err && err.message], [1, null]);
    check(`${cron}: URL と方法`, [c.url, c.method],
      [`https://api.github.com/repos/ihudodo-k/make10/actions/workflows/promo.yml/dispatches`, "POST"]);
    check(`${cron}: ref は main・inputs は ${task} で本物（dry_run は false）`, c.body, { ref: "main", inputs: { task, dry_run: "false" } });
    check(`${cron}: ヘッダー（鍵・Accept・API の版・User-Agent・Content-Type）`, c.headers, {
      "Accept": "application/vnd.github+json", "Authorization": `Bearer ${TOKEN}`, "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json", "User-Agent": "make10-promo-cron" });
    check(`${cron}: 204 なら「204 以外」のログを出さない・鍵をログに出さない`,
      [lines.some((l) => l.includes("204 以外")), lines.some((l) => l.includes(TOKEN))], [false, false]);
  }

  // scheduled の入口（default export）からも同じに送る。fetch は全体のものを差し替える
  {
    const gh = fakeGitHub(204), orig = globalThis.fetch;
    globalThis.fetch = gh;
    try { await logsOf(() => worker.scheduled({ cron: "30 8 * * *", scheduledTime: Date.now() }, { GH_TOKEN: TOKEN }, { waitUntil() {} })); }
    finally { globalThis.fetch = orig; }
    check("scheduled の入口から: post を 1 回送る", [gh.calls.length, gh.calls[0]?.body.inputs.task], [1, "post"]);
  }

  // ── 2. 送らない・失敗の扱い ──
  console.log("2. 送らないとき・204 以外のとき");
  {
    const gh = fakeGitHub(204);
    const { err } = await logsOf(() => dispatch("15 8 * * *", { GH_TOKEN: TOKEN }, gh));
    check("知らない式は送らない（失敗にもしない）", [gh.calls.length, err], [0, null]);
  }
  {
    const gh = fakeGitHub(204);
    const { lines, err } = await logsOf(() => dispatch("0 8 * * *", {}, gh));
    check("鍵 GH_TOKEN が無いと送らず、失敗にして名前をログに出す",
      [gh.calls.length, !!err, lines.some((l) => l.includes("GH_TOKEN"))], [0, true, true]);
  }
  {
    const long = JSON.stringify({ message: "Bad credentials", documentation_url: "https://docs.github.com/rest" }) + "x".repeat(1000);
    const gh = fakeGitHub(401, long);
    const { lines, err } = await logsOf(() => dispatch("30 8 * * *", { GH_TOKEN: TOKEN }, gh));
    const line = lines.find((l) => l.includes("204 以外")) || "";
    check("401（鍵の期限切れなど）: ログに状態と本文の先頭・失敗にする",
      [line.includes("401"), line.includes("Bad credentials"), !!err], [true, true, true]);
    check("401: 本文は先頭の 300 字まで・鍵はログに出さない",
      [line.includes(long.slice(0, 301)), line.includes(long.slice(0, 300)), lines.some((l) => l.includes(TOKEN))], [false, true, false]);
  }
  {
    const gh = fakeGitHub(422, '{"message":"Unexpected inputs provided: [\\"dry\\"]"}');
    const { lines, err } = await logsOf(() => dispatch("0 8 * * *", { GH_TOKEN: TOKEN }, gh));
    check("422（入力の名前が promo.yml と合わない）: ログに状態と本文・失敗にする",
      [lines.some((l) => l.includes("422") && l.includes("Unexpected inputs")), !!err], [true, true]);
  }
  {
    const gh = fakeGitHub(200, '{"workflow_run_id":1}');
    const { lines, err } = await logsOf(() => dispatch("0 8 * * *", { GH_TOKEN: TOKEN }, gh));
    check("200（2xx だが 204 以外）: ログに出すが、失敗にはしない",
      [lines.some((l) => l.includes("204 以外") && l.includes("200")), err], [true, null]);
  }

  // ── 3. HTTP の入口 ──
  console.log("3. HTTP の入口");
  {
    const gh = fakeGitHub(204), orig = globalThis.fetch;
    globalThis.fetch = gh;
    const got = [];
    try {
      for (const [method, path] of [["GET", "/"], ["POST", "/"], ["GET", "/dispatch?task=post"], ["POST", "/__scheduled?cron=30+8+*+*+*"]]) {
        const r = await worker.fetch(new Request("https://make10-promo-cron.example" + path, { method }), { GH_TOKEN: TOKEN }, {});
        got.push(r.status);
      }
    } finally { globalThis.fetch = orig; }
    check("どの道・方法でも 404 で、GitHub へは 1 回も送らない", [got, gh.calls.length], [[404, 404, 404, 404], 0]);
  }

  // ── 4. 式の一致と、鍵が書かれていないこと ──
  console.log("4. 設定の一致");
  const toml = readFileSync(join(HERE, "wrangler.toml"), "utf8");
  const yml = readFileSync(join(ROOT, ".github", "workflows", "promo.yml"), "utf8");
  const src = readFileSync(join(HERE, "src", "index.js"), "utf8") + readFileSync(join(HERE, "src", "dispatch.js"), "utf8");
  const tomlCrons = JSON.parse((toml.match(/^crons\s*=\s*(\[.*\])/m) || [, "[]"])[1]);
  const ymlCrons = [...yml.matchAll(/^\s*- cron:\s*"([^"]+)"/gm)].map((m) => m[1]);
  check("wrangler.toml の crons と JOBS が同じ式", tomlCrons.slice().sort(), Object.keys(JOBS).sort());
  check("promo.yml の schedule（予備）と同じ式", ymlCrons.slice().sort(), Object.keys(JOBS).sort());
  check("Worker の名前・送り先のリポジトリとワークフロー", [(toml.match(/^name\s*=\s*"([^"]+)"/m) || [])[1], REPO, WORKFLOW],
    ["make10-promo-cron", "ihudodo-k/make10", "promo.yml"]);
  check("src/index.js は既定の export だけ（名前付きの export があると Workers が起動しない）",
    Object.keys(await import("../src/index.js")), ["default"]);
  check("wrangler.toml に HTTP の入口（routes・workers.dev）が無い",
    [/^\s*routes\s*=/m.test(toml), /^workers_dev\s*=\s*false/m.test(toml)], [false, true]);
  const pat = /github_pat_|ghp_|gho_|ghs_|GH_TOKEN\s*=\s*"/;
  check("src/ と wrangler.toml に鍵の値が書かれていない", [pat.test(src), pat.test(toml)], [false, false]);

  // ── 5. promo.yml の式 ──
  console.log("5. promo.yml の TASK・DRY の式");
  const expr = (name) => (yml.match(new RegExp(`^\\s*${name}:\\s*\\$\\{\\{(.*)\\}\\}\\s*$`, "m")) || [])[1];
  const TASK = expr("TASK"), DRY = expr("DRY");
  check("TASK と DRY の式が読める", [!!TASK, !!DRY], [true, true]);
  // workflow_dispatch の入力の名前と型
  const inBlock = (yml.match(/workflow_dispatch:\s*\n\s*inputs:\s*\n([\s\S]*?)\n\S/) || [])[1] || "";
  const types = {};
  for (const m of inBlock.matchAll(/^ {6}(\w+):\s*\n(?:[\s\S]*?)^ {8}type:\s*(\w+)/gm)) types[m[1]] = m[2];
  const opts = (inBlock.match(/options:\s*\[([^\]]*)\]/) || [, ""])[1].split(",").map((s) => s.trim());
  check("promo.yml の入力: task（choice）と dry_run（boolean）だけ・task は post と collect を選べる",
    [types, opts.includes("post") && opts.includes("collect")], [{ task: "choice", dry_run: "boolean" }, true]);
  check("送る inputs の名前が promo.yml の入力と同じ", Object.keys(JOBS["0 8 * * *"]).sort(), Object.keys(types).sort());
  const evalBoth = (ctx) => [evalExpr(TASK, ctx), evalExpr(DRY, ctx)];
  for (const [cron, inputs] of Object.entries(JOBS)) {
    const viaSchedule = evalBoth({ github: { event_name: "schedule", event: { schedule: cron } }, inputs: {} });
    const viaDispatch = evalBoth({ github: { event_name: "workflow_dispatch", event: {} }, inputs: typedInputs(inputs, types) });
    check(`schedule の ${cron}: TASK=${inputs.task}・DRY=false`, viaSchedule, [inputs.task, "false"]);
    check(`この Worker が起こす ${cron}: schedule のときと同じ（本物として動く）`, viaDispatch, viaSchedule);
  }
  check("手で流す既定（dry_run にチェック）は送らずに試す（DRY=true）",
    evalBoth({ github: { event_name: "workflow_dispatch", event: {} }, inputs: typedInputs({ task: "post", dry_run: "true" }, types) }),
    ["post", "true"]);
  // 型に直さない文字列のままなら DRY は true になる（'false' は空でない文字列なので真）。GitHub が boolean に直す前提を記録する
  check("（参考）inputs が文字列 'false' のままなら DRY=true（送らない側に倒れる）",
    evalBoth({ github: { event_name: "workflow_dispatch", event: {} }, inputs: { task: "post", dry_run: "false" } }), ["post", "true"]);

  // ── 6. 本物のランタイム ──
  console.log("6. 本物のランタイム（wrangler dev）");
  await runtime();

  console.log(`\n合計 ${ok + ng} 項目  ${ng ? `${ng} 項目が落ちた` : "すべて通った"}`);
  setTimeout(() => process.exit(ng ? 1 : 0), 300);
}

async function runtime() {
  const WRANGLER = join(HERE, "node_modules", "wrangler", "bin", "wrangler.js");
  if (existsSync(join(HERE, ".dev.vars"))) { check(".dev.vars が無い（鍵が入らないように）", true, false); return; }
  if (!existsSync(WRANGLER)) { check("wrangler が入っている（promo/cron/ で npm.cmd ci）", false, true); return; }
  const PORT = Number(process.env.MAKE10_CRON_PORT || 8798), BASE = `http://127.0.0.1:${PORT}`;
  const env = { ...process.env, GH_TOKEN: "", WRANGLER_SEND_METRICS: "false" };
  const child = spawn(process.execPath, [WRANGLER, "dev", "--local", "--port", String(PORT), "--test-scheduled"],
    { cwd: HERE, stdio: ["ignore", "pipe", "pipe"], env });
  let log = "";
  child.stdout.on("data", (d) => { log += d; });
  child.stderr.on("data", (d) => { log += d; });
  try {
    let up = false;
    for (let i = 0; i < 80 && !up && child.exitCode === null; i++) {
      await new Promise((r) => setTimeout(r, 500));
      try { await fetch(BASE + "/"); up = true; } catch (e) { /* まだ */ }
    }
    check("立ち上がる（名前付きの export などで落ちない）", up, true);
    if (!up) { console.log(log.slice(-2000)); return; }
    const st = [];
    for (const [method, path] of [["GET", "/"], ["POST", "/"], ["GET", "/dispatch?task=post"]])
      st.push((await fetch(BASE + path, { method })).status);
    check("HTTP の入口はどれも 404", st, [404, 404, 404]);
    const known = await fetch(BASE + "/__scheduled?cron=" + encodeURIComponent("30 8 * * *"));
    const unknown = await fetch(BASE + "/__scheduled?cron=" + encodeURIComponent("15 8 * * *"));
    await new Promise((r) => setTimeout(r, 500));
    check("Cron 30 8: 鍵が無いので送らずに失敗にする・知らない式は何もしない",
      [known.status, log.includes("GH_TOKEN が無い"), unknown.status, log.includes("知らない Cron の式なので何もしない: 15 8 * * *")],
      [500, true, 200, true]);
    check("GitHub へは送っていない（204 以外・起こした のログが無い）",
      [log.includes("204 以外"), log.includes("起こした:")], [false, false]);
  } finally {
    if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"]);
    else child.kill("SIGKILL");
  }
}

run().catch((e) => { console.log("試しが途中で落ちた: " + (e && e.stack || e)); process.exit(1); });
