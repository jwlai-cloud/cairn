/**
 * Demo capture for the CAIRN situation room.
 *
 * Records the golden path with the pacing from docs/architecture/08 8.5, so the timing
 * can be judged before any narration is written.
 *
 * Viewport is deliberately narrow. Apparent text size in the finished video is set by
 * how far the viewport is scaled up into the frame, not by capture resolution: a 1280
 * viewport in a 1920 frame magnifies everything 1.5x, a 1920 viewport does not magnify
 * it at all. Export resolution is a separate axis and only buys sharpness.
 *
 *   node captures/capture.mjs [outfile.webm] [--fast]
 */
import { chromium } from 'playwright';

const OUT_DIR = new URL('.', import.meta.url).pathname;
const FAST = process.argv.includes('--fast');
const SCALE = FAST ? 0.18 : 1;          // --fast walks the same beats in ~30s
// Record at native 1920 and zoom the page 1.5x. Playwright's recordVideo.size PADS
// rather than scales, so asking for a bigger canvas than the viewport just letterboxes
// the page into a corner. Zooming instead means the layout computes at an effective
// 1280 CSS width - which is what makes the type large in frame - while painting into
// 1920 real pixels, so it stays sharp.
const ZOOM = 1.5;
const VIEWPORT = { width: 1920, height: 1200 };
const VIDEO = { width: 1920, height: 1200 };

const beats = [];
let t0 = 0;   // wall clock at the first recorded frame; set once the page exists

/**
 * Hold the current frame for `seconds`, recording where the beat lands in the VIDEO.
 *
 * The requested hold is not where the beat ends up. Every click carries Playwright's
 * actionability checks and every evaluate a round trip, and on a page running a 3D
 * scene those cost real recorded time - about twenty-nine seconds across a four minute
 * take, unevenly spread. Summing the requested holds therefore drifts, and a caption
 * cut to that sum lands on the wrong shot: the denial beat missed its own toast by
 * twenty-four seconds that way.
 *
 * So measure instead of assume. Recording begins with the page, so wall clock since
 * then is the video clock, and `captures/beats.json` is the single source of truth for
 * every downstream timing.
 */
async function beat(page, seconds, label) {
  const at = (Date.now() - t0) / 1000;
  await page.waitForTimeout(Math.max(seconds * 1000 * SCALE, 120));
  beats.push({ at, seconds: (Date.now() - t0) / 1000 - at, label });
}

const browser = await chromium.launch({
  args: ['--use-gl=angle', '--enable-unsafe-swiftshader', '--hide-scrollbars'],
});
const context = await browser.newContext({
  viewport: VIEWPORT,
  recordVideo: { dir: OUT_DIR, size: VIDEO },
});
const page = await context.newPage();
t0 = Date.now();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));

await page.addStyleTag; // (no-op guard: style is applied after load below)
await page.goto('http://127.0.0.1:8099/', { waitUntil: 'networkidle' });
await page.evaluate((z) => { document.documentElement.style.zoom = String(z); }, ZOOM);
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(900);
await page.click('#btnReset');
await page.waitForTimeout(600);

// Beats follow docs/architecture/10-demo-video-plan.md. Safety and reliability carry
// the spine: the denial, the approval token and the UNKNOWN/reconcile sequence are the
// three beats that must never be cut.

// 0:00 the problem — the room before anything goes wrong
await beat(page, 26, 'Normal shift: 16 900 t of 28 000 t, eight trucks, no alerts');

// 0:26 correlation
await page.click('#btnInjectAll');
await beat(page, 12, 'Five signals from four systems land on the timeline');
await page.click('#btnAnalyse');
await beat(page, 18, 'Four specialists in parallel; spine fills with measured durations');

// 0:56 evidence, including the bad kind
await page.evaluate(() => document.querySelector('.flag.stale')?.scrollIntoView({ block: 'center' }));
await beat(page, 16, 'STALE telemetry and a 13-minute source CONFLICT, both surfaced');
await page.hover('.agent:nth-child(2)');
await beat(page, 10, 'Agent cards: tool chips, evidence counts, confidence, durations');

// 1:22 three options that actually differ
await page.click('[data-scenario="scn_protect_safety"]');
await beat(page, 9, 'Protect safety: +4 900 t, LOW risk');
await page.click('[data-scenario="scn_preserve_equipment"]');
await beat(page, 8, 'Preserve equipment: +6 100 t, crusher capped');
await page.click('[data-scenario="scn_recover_tonnes"]');
await beat(page, 11, 'Recover tonnes: +7 600 t, recommended, reason shown');

// 1:50 CLAIM 1 - the model cannot authorise anything
await page.click('#btnProhibited');
await beat(page, 26, 'DENIED: rule T4-PROHIBITED-INTERLOCK, tier 4, no model call');

// 2:16 CLAIM 2 - a human has to sign
await page.click('#btnApprove');
await beat(page, 12, 'Policy escalates to a named role');
await page.click('#btnApprove');
await beat(page, 16, 'Scoped approval: token bound to plan version and evidence hash');

// 2:44 CLAIM 3 - fail safe when the world is ambiguous
await page.click('#btnTimeout');
await beat(page, 16, 'Dispatch times out AFTER the call may have applied -> UNKNOWN');
await page.locator('#btnReconcile').click({ button: 'right' });
await beat(page, 14, 'Blind retry REFUSED: RECONCILIATION_REQUIRED');
await page.click('#btnReconcile');
await beat(page, 12, 'Reconciled: UNKNOWN -> RECONCILING -> SUCCEEDED');

// 3:26 simulation-only, then the whole chain
await page.click('#btnApprove');
await beat(page, 10, 'Outcome verified: truck still down, residual risks still open');
await page.click('#btnAudit');
await beat(page, 14, 'Audit: event -> evidence -> findings -> policy -> approval -> action -> outcome');
await page.evaluate(() => {
  const el = document.querySelector('.audit');
  if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
});
await beat(page, 10, 'Scroll the full chain');
await page.click('#btnCloseAudit');

// 4:00 replay
await page.click('#btnReset');
await beat(page, 10, 'Reset: the same fixtures replay to the same decision');

await context.close();
await browser.close();

const fs = await import('node:fs');
const files = fs.readdirSync(OUT_DIR).filter((f) => f.endsWith('.webm'));
fs.writeFileSync(`${OUT_DIR}beats.json`, `${JSON.stringify(beats, null, 2)}\n`);

const runtime = beats.at(-1).at + beats.at(-1).seconds;
console.log(`\nrecorded runtime: ${Math.floor(runtime / 60)}:${String(Math.round(runtime % 60)).padStart(2, '0')}`);
console.log(`video: ${files.join(', ') || 'none written'}`);
console.log(`pageerrors: ${JSON.stringify(errors.slice(0, 3))}`);
console.log('\nbeat sheet (measured against the video clock)');
for (const b of beats) {
  const m = Math.floor(b.at / 60);
  const s = String(Math.round(b.at % 60)).padStart(2, '0');
  console.log(`  ${m}:${s}  ${b.seconds.toFixed(1).padStart(5)}s  ${b.label}`);
}
