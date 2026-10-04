// hull-bot-console.html 점검: 가짜 봇 폴더(브라우저 내부 저장소)로 기록·로그·상태·STOP·설정 저장을 확인.
// 실행: node test_console.mjs  (playwright 필요. 크롬 경로는 CHROME 환경변수로 지정 가능)
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

const html = readFileSync(new URL("./hull-bot-console.html", import.meta.url));
const server = createServer((_, res) => res.end(html)).listen(0, "127.0.0.1"); // 폴더 API는 localhost에서도 동작
await new Promise(r => server.once("listening", r));
const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const page = await browser.newPage();
const alerts = [];
page.on("dialog", d => { alerts.push(d.message()); d.accept(); });
await page.goto(`http://127.0.0.1:${server.address().port}/`);

await page.evaluate(async () => {
  const root = await navigator.storage.getDirectory();
  const put = async (d, name, text) => { const w = await (await d.getFileHandle(name, { create: true })).createWritable(); await w.write(text); await w.close(); };
  await put(root, "bot.py", "");
  await put(root, ".env", "BYBIT_API_SECRET=secret");
  await put(root, "journal_paper.csv", '﻿time,symbol,event,note\n2026-10-01,BTCUSDT,진입,"a, b"\n2026-10-02,BTCUSDT,청산,"say ""hi"""\n');
  await put(root, "config.json", '{"mode":"paper","leverage":2,"stop_pct":0.05}');
  await put(root, "state_BTCUSDT.json", '{"in_position":false}');
  await put(await root.getDirectoryHandle("logs", { create: true }), "bot_paper.log", "줄1\n신호 상승\n");
  await window.useDir(root);
});
const file = name => page.evaluate(async n => { try { return await (await (await navigator.storage.getDirectory()).getFileHandle(n)).getFile().then(f => f.text()); } catch { return null; } }, name);

// 운영 현황·매매 기록 (따옴표·쉼표 포함 CSV, 최신순)
await page.waitForSelector("#bots .bot");
assert.match(await page.textContent("#bots"), /로그 갱신 중/);
assert.deepEqual(await page.$$eval("tbody tr", trs => trs.map(t => t.cells[3].textContent)), ['say "hi"', "a, b"]);
await page.fill("#filter", "진입");
await page.waitForFunction(() => document.querySelectorAll("tbody tr").length === 1);

// 로그·상태 (.env는 보이지 않아야 함)
await page.click('[data-tab="log"]'); await page.waitForSelector("#logpre");
assert.match(await page.textContent("#logpre"), /신호 상승/);
await page.click('[data-tab="state"]'); await page.waitForSelector("#view h2");
const stateText = await page.textContent("#view");
assert.match(stateText, /state_BTCUSDT\.json/); assert.doesNotMatch(stateText, /secret/);

// STOP 파일
await page.check("#stopfile"); await page.waitForTimeout(300);
assert.equal(await file("STOP"), "");
await page.uncheck("#stopfile"); await page.waitForTimeout(300);
assert.equal(await file("STOP"), null);

// 설정 검사·저장·백업
await page.click('[data-tab="config"]'); await page.waitForSelector("#cfg");
for (const bad of ['{"leverage": 20}', '{"mode": "real"}', "{bad"]) {
  await page.fill("#cfg", bad); await page.click("#saveCfg"); await page.waitForTimeout(100);
}
assert.equal(alerts.length, 3, alerts.join(" | "));
assert.equal(JSON.parse(await file("config.json")).mode, "paper");
await page.fill("#cfg", '{"mode":"demo","leverage":2,"stop_pct":0.05}'); await page.click("#saveCfg"); await page.waitForTimeout(300);
assert.equal(JSON.parse(await file("config.json")).mode, "demo");
assert.equal(JSON.parse(await file("config.json.bak")).mode, "paper");

await browser.close(); server.close();
console.log("모든 점검 통과");
