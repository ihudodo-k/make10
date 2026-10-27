// Make10 promo の定期実行の起こし役（Cloudflare Workers の Cron Triggers）。仕組みは promo/README.md の「定期実行の起こし役」。
// 中身は src/dispatch.js。ここには入口だけを置く（名前付きの export を置かない。Workers が入口として読んで起動に失敗する）
import { dispatch } from "./dispatch.js";

export default {
  async scheduled(controller, env, ctx) {
    await dispatch(controller.cron, env);
  },
  async fetch() {
    return new Response("Not Found", { status: 404 });
  },
};
