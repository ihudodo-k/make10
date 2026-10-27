// Make10 promo の定期実行の起こし役: GitHub の API で promo.yml を起こす中身（src/index.js から使う。試しもこれを読む）。
// index.js に名前付きの export を置くと、Workers はそれを入口として読んで起動に失敗するので、ここに分けてある。
//
// 仕組みは promo/README.md の「定期実行の起こし役」。
//
// GitHub の schedule が数時間遅れて走るので（2026-10-26・27 に約 6 時間）、決まった時刻に Cloudflare から
// GitHub の API で promo.yml を起こす（workflow_dispatch）。promo.yml の schedule は予備として残してあり、
// 両方が走っても、post はその日の行が posts.csv にあれば送らず、collect は同じ日を上書きする。
//
// - 鍵は Worker の secret GH_TOKEN（Fine-grained token。このリポジトリだけ・Actions の Read and write だけ）。ここにも wrangler.toml にも書かない
// - HTTP の入口は何もしない（404）。外から叩いて投稿させられないようにするため

export const REPO = "ihudodo-k/make10";
export const WORKFLOW = "promo.yml";
export const REF = "main";

// Cron の式 → promo.yml に渡す入力。式は wrangler.toml の [triggers] と同じ文字列にする。
// 値は文字列で送る（GitHub の API は入力を文字列で受け取り、promo.yml の型（boolean）に直して inputs に入れる）
export const JOBS = {
  "0 8 * * *": { task: "collect", dry_run: "false" },
  "30 8 * * *": { task: "post", dry_run: "false" },
};

export async function dispatch(cron, env, fetchImpl = fetch) {
  const inputs = JOBS[cron];
  if (!inputs) {
    console.log(`知らない Cron の式なので何もしない: ${cron}`);
    return { ok: false, status: 0 };
  }
  if (!env.GH_TOKEN) {
    console.log("GH_TOKEN が無い（npx.cmd wrangler secret put GH_TOKEN で入れる）。起こさない");
    throw new Error("GH_TOKEN が無い");
  }
  const url = `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const res = await fetchImpl(url, {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "Authorization": `Bearer ${env.GH_TOKEN}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": "make10-promo-cron",           // GitHub の API は User-Agent の無い要求を断る
    },
    body: JSON.stringify({ ref: REF, inputs }),
  });
  if (res.status === 204) {
    console.log(`起こした: ${inputs.task}（${cron}）`);
    return { ok: true, status: 204 };
  }
  const text = (await res.text().catch(() => "")).slice(0, 300);
  console.log(`GitHub が 204 以外を返した: ${res.status} ${inputs.task}（${cron}） ${text}`);
  // 2xx 以外は失敗にする（Cloudflare のダッシュボードの Cron の記録に失敗として残る）
  if (res.status < 200 || res.status >= 300) throw new Error(`GitHub ${res.status}`);
  return { ok: true, status: res.status };
}
