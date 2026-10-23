// schema.sql の文を 1 つずつ `wrangler d1 execute --command` で流す（npm run schema:remote の中身）。
// 本番の D1 では `--file`（Cloudflare の /import）が Authentication error 10000 で落ち、`--command` は通ったため（2026-10-21）。
//   node schema_each.mjs --remote                         本番の D1 に
//   node schema_each.mjs --local --persist-to <dir>       手元の D1 に（npm test が使う）
//   --schema <file> で schema.sql 以外のファイルを流す。ほかの引数はそのまま wrangler に渡す
// どの文も CREATE … IF NOT EXISTS なので、もう一度流してよい。1 つでも落ちたら、そこで止めて終了コード 1
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const WRANGLER = join(HERE, "node_modules", "wrangler", "bin", "wrangler.js");

// 「--」から行末までは注釈。文の中に文字列は無いので、そのまま消してよい。
// 行の区切りは CRLF でもよい（Windows の Git が core.autocrlf で CRLF にして取り出すと、行末の \r が残って注釈が消えず、
// 1 つ目の文が注釈ごと流れて落ちていた。公開前の総点検の H2。2026-10-23）
export function statements(sql) {
  return sql.split(/\r?\n/).map((l) => l.replace(/--.*$/, "")).join("\n")
    .split(";").map((s) => s.replace(/\s+/g, " ").trim()).filter(Boolean);
}

// 直に動かしたときだけ流す（test/local_test.mjs が statements() を読み込むため）
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args = process.argv.slice(2);
  let schema = "schema.sql";
  const i = args.indexOf("--schema");
  if (i >= 0) { schema = args[i + 1]; args.splice(i, 2); }
  if (!args.includes("--remote") && !args.includes("--local")) {
    console.error("--remote か --local を付けてください");
    process.exit(1);
  }
  const list = statements(readFileSync(join(HERE, schema), "utf8"));
  for (const [k, sql] of list.entries()) {
    console.log(`(${k + 1}/${list.length}) ${sql.slice(0, 60)}${sql.length > 60 ? "…" : ""}`);
    const r = spawnSync(process.execPath, [WRANGLER, "d1", "execute", "make10-daily", ...args, "--command", sql],
      { cwd: HERE, stdio: "inherit", env: { ...process.env, CI: process.env.CI || "1" } });
    if (r.status !== 0) {
      console.error(`(${k + 1}/${list.length}) で落ちた。ログインが切れているときは npx wrangler logout → npx wrangler login`);
      process.exit(1);
    }
  }
  console.log(`${list.length} 文を流した`);
}
