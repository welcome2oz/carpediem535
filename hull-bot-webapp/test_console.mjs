// hull-bot-console.html 점검: fixtures/(봇 코드가 실제로 쓴 형식의 파일)를 브라우저 내부 저장소에 넣고
// 운영 현황·매매 기록·로그·상태·STOP·설정 검사를 확인. 실행: node test_console.mjs  (playwright 필요)
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFileSync, readdirSync, statSync } from "node:fs";
import assert from "node:assert/strict";

const here = new URL(".", import.meta.url);
const html = readFileSync(new URL("hull-bot-console.html", here));
const files = {};
(function walk(rel) {
  for (const n of readdirSync(new URL("fixtures/" + rel, here))) {
    const p = rel + n;
    if (statSync(new URL("fixtures/" + p, here)).isDirectory()) walk(p + "/"); else files[p] = readFileSync(new URL("fixtures/" + p, here), "utf-8");
  }
})("");
files[".env"] = "BYBIT_API_SECRET=secret";

const server = createServer((_, res) => res.end(html)).listen(0, "127.0.0.1"); // 폴더 API는 localhost에서도 동작
await new Promise(r => server.once("listening", r));
const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const page = await browser.newPage();
const alerts = [];
page.on("dialog", d => { alerts.push(d.message()); d.accept(); });
page.on("pageerror", e => { throw e; });
await page.goto(`http://127.0.0.1:${server.address().port}/`);

// 설명서: 연결 전에는 펼쳐져 있음
assert.ok(await page.isVisible("#guide") && await page.isVisible("text=처음 시작하기"));
if (process.env.SHOTS) for (const [w, n] of [[1280, "desktop"], [390, "mobile"]]) {
  await page.setViewportSize({ width: w, height: 900 }); await page.screenshot({ path: `${process.env.SHOTS}/guide_${n}.png`, fullPage: true });
}
await page.setViewportSize({ width: 1280, height: 900 });

await page.evaluate(async files => {
  const root = await navigator.storage.getDirectory();
  for (const [path, text] of Object.entries(files)) {
    const parts = path.split("/"); let d = root;
    for (const p of parts.slice(0, -1)) d = await d.getDirectoryHandle(p, { create: true });
    const w = await (await d.getFileHandle(parts.at(-1), { create: true })).createWritable(); await w.write(text); await w.close();
  }
  await window.useDir(root);
}, files);
const file = name => page.evaluate(async n => { try { return await (await (await navigator.storage.getDirectory()).getFileHandle(n)).getFile().then(f => f.text()); } catch { return null; } }, name);
const text = sel => page.textContent(sel);

// 운영 현황: 모의(보유 중인 두 다리 포지션) / 테스트넷(손절 2번 → 재진입 제한, 실현손익 합계)
await page.waitForSelector("#bots .bot");
assert.ok(!(await page.isVisible("#guide")));                                 // 연결 후 접힘
await page.click("#guideBtn"); assert.ok(await page.isVisible("#guide"));
await page.click("#guideClose"); assert.ok(!(await page.isVisible("#guide")));
const [paper, , testnet, live] = await page.$$eval("#bots .bot", els => els.map(e => e.textContent.replace(/\s+/g, " ")));
for (const s of ["실행 중", "모의 계좌 USDT", "XUSDT", "상승", "보유", "현물 9.975062 + 선물 9.984", "97.63", "펀딩 -1.00"]) assert.ok(paper.includes(s), `모의 카드에 "${s}" 없음: ${paper}`);
for (const s of ["BTCUSDT", "ETHUSDT", "재진입 제한", "실현손익 -84.82 USDT (2회)", "하락", "마지막 청산"]) assert.ok(testnet.includes(s), `테스트넷 카드에 "${s}" 없음: ${testnet}`);
assert.match(live, /사용 기록 없음/);

// 매매 기록: 테스트넷, 기본 '매매만' = 진입 2 + 청산 1 + 포지션 종료 1 + 진입 안 함(재진입 제한) 1, 한국시각 변환
await page.selectOption("#mode", "testnet"); await page.waitForSelector("#fEv");
assert.equal(await page.$$eval("#view tbody tr", t => t.length), 5);
assert.match(await text("#view"), /5건 · 실현손익 합계 -84\.82 USDT/);
assert.match(await text("#view tbody tr:last-child"), /2026-05-01 09:02/);         // 00:02:05 UTC → 09:02 KST
await page.selectOption("#fEv", "all"); await page.waitForFunction(() => document.querySelectorAll("#view tbody tr").length === 14);
await page.selectOption("#fEv", "stop"); await page.waitForFunction(() => document.querySelectorAll("#view tbody tr").length === 3);
await page.selectOption("#fSym", "ETHUSDT"); await page.selectOption("#fEv", "일일 신호");
await page.waitForFunction(() => document.querySelectorAll("#view tbody tr").length === 3);

// 로그·상태 (.env는 어디에도 보이지 않아야 함)
await page.selectOption("#mode", "paper");
await page.click('[data-tab="log"]'); await page.waitForSelector("#logpre");
assert.match(await text("#logpre"), /손절가 갱신/);
await page.click('[data-tab="state"]'); await page.waitForSelector("#view h2");
assert.match(await text("#view"), /state_paper\.json[\s\S]*paper_account\.json/);
assert.doesNotMatch(await page.content(), /secret/);

// STOP 파일
await page.check("#stopfile"); await page.waitForTimeout(300); assert.equal(await file("STOP"), "");
await page.uncheck("#stopfile"); await page.waitForTimeout(300); assert.equal(await file("STOP"), null);

// 설정: bot.py가 거부할 값은 저장 안 함, 올바르면 저장 + 백업
await page.click('[data-tab="config"]'); await page.waitForSelector("#cfg");
const base = JSON.parse(files["config.json"]);
const bad = [{ leverage: 20 }, { mode: "real" }, { symbols: [] }, { capital_mode: "equity_share" }, { fixed_usdt: { BTCUSDT: 1000 } }, { stop_pct: 5 }, { max_reentry: 1.5 }];
for (const b of bad) { await page.fill("#cfg", JSON.stringify({ ...base, ...b })); await page.click("#saveCfg"); await page.waitForTimeout(80); }
await page.fill("#cfg", "{bad"); await page.click("#saveCfg"); await page.waitForTimeout(80);
assert.equal(alerts.length, bad.length + 1, alerts.join(" | "));
assert.equal(await file("config.json"), files["config.json"]);
await page.fill("#cfg", JSON.stringify({ ...base, max_reentry: null, fixed_usdt: { BTCUSDT: 500, ETHUSDT: 500 } }));
await page.click("#saveCfg"); await page.waitForTimeout(300);
assert.equal(alerts.length, bad.length + 1, alerts.at(-1));
assert.equal(JSON.parse(await file("config.json")).fixed_usdt.BTCUSDT, 500);
assert.equal(await file("config.json.bak"), files["config.json"]);

if (process.env.SHOTS) for (const [w, n] of [[1280, "desktop"], [390, "mobile"]]) {
  await page.click('[data-tab="journal"]'); await page.selectOption("#mode", "testnet"); await page.setViewportSize({ width: w, height: 900 });
  await page.waitForTimeout(400); await page.screenshot({ path: `${process.env.SHOTS}/console_${n}.png`, fullPage: true });
}
await browser.close(); server.close();
console.log("모든 점검 통과");
