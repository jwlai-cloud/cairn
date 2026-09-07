/**
 * Demo capture for the CAIRN situation room.
 *
 * Records the live application in the order the cue sheet declares, with the highlight
 * overlay pointing at whatever the narration is discussing. Nothing is mocked for the
 * camera and no frame is a slide pretending to be software - the three TOGAF frames are
 * genuinely slides and are recorded separately by capture-slides.mjs.
 *
 * The cue sheet in captures/narration.md is the plan; this file must hold each beat for
 * the duration declared there. Beats are also measured against the video clock and
 * written to captures/beats.json, because a requested hold and where the beat lands in
 * the recording are not the same number.
 *
 * Beats are tagged pre or post. The slides splice between them, so edit.sh assembles
 * app-pre, slides, app-post.
 *
 *   node captures/capture.mjs [--fast]
 */
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { HIGHLIGHT_CSS, HIGHLIGHT_JS, TOPOLOGY_CSS, TOPOLOGY_JS } from './overlays.mjs';

const OUT_DIR = new URL('.', import.meta.url).pathname;
const FAST = process.argv.includes('--fast');
const SCALE = FAST ? 0.15 : 1;
// Native 1920 with the page zoomed 1.5x. Playwright's recordVideo.size pads rather than
// scales, so a canvas larger than the viewport letterboxes the page into a corner.
// Zooming makes the layout compute at an effective 1280 CSS width, which is what makes
// the type large in frame, while still painting into 1920 real pixels.
const ZOOM = 1.5;
const VIEWPORT = { width: 1920, height: 1200 };
const TOPOLOGY = JSON.parse(readFileSync(new URL('./topology.json', import.meta.url)));

// Holds come from the cue sheet, in app-cue order, so a re-timed sheet cannot leave the
// capture running to the old durations. The sheet's Source column says which cues are
// filmed here and which are slides.
const APP_HOLDS = readFileSync(new URL('./narration.md', import.meta.url), 'utf8')
  .split('\n')
  .map((l) => l.match(/^\|\s*(\d+):(\d\d)\s*\|\s*(\d+)s\s*\|\s*app\s*\|/))
  .filter(Boolean)
  .map((m) => Number(m[3]));
if (APP_HOLDS.length !== 12) {
  throw new Error(`expected 12 app cues in the sheet, found ${APP_HOLDS.length}`);
}
let cueIndex = 0;

const beats = [];
let t0 = 0;

/**
 * Run one cue: stamp its start, do its interactions, then hold until its declared
 * duration has elapsed.
 *
 * The interactions have to be inside the cue, not before it. An earlier version took the
 * clicks and intermediate waits first and only stamped the start of the final hold, which
 * put cue four twenty seconds late in beats.json and left the assembly four seconds short.
 * Measuring from the top also makes each cue last exactly what the sheet declares, so the
 * cue sheet's times are the output times by construction rather than by luck.
 */
async function cue(page, section, label, fn) {
  const seconds = APP_HOLDS[cueIndex++];
  const at = (Date.now() - t0) / 1000;
  if (fn) await fn();
  const spent = (Date.now() - t0) / 1000 - at;
  const left = seconds * SCALE * 1000 - spent * 1000;
  await page.waitForTimeout(Math.max(left, 120));
  beats.push({ at, seconds: (Date.now() - t0) / 1000 - at, section, label });
}

// Wait for the target to be visible first. Several of these follow a click whose fetch
// resolves later, and highlighting a hidden element measures a zero-sized rect: the ring
// lands in the top-left corner and the thing being discussed gets dimmed instead. That
// happened on the denial beat, which is the worst possible place for it.
// Press a control visibly: flash it, let the viewer see it, then click. Without this the
// capture clicks silently and a toast appears at the bottom of the screen with no visible
// cause, which is what made the demo confusing to watch.
const press = async (page, sel) => {
  await page.locator(sel).first().waitFor({ state: 'visible', timeout: 15000 });
  await page.evaluate((x) => window.capPress(x), sel);
  await wait(page, 900);
  await page.click(sel);
};

const hl = async (page, sel) => {
  await page.locator(sel).first().waitFor({ state: 'visible', timeout: 15000 });
  await page.evaluate((s) => window.capHighlight(s), sel);
};
const clear = (page) => page.evaluate(() => window.capClear());
const wait = (page, ms) => page.waitForTimeout(Math.max(ms * SCALE, 60));

const browser = await chromium.launch({
  args: ['--use-gl=angle', '--enable-unsafe-swiftshader', '--hide-scrollbars'],
});
const context = await browser.newContext({
  viewport: VIEWPORT,
  recordVideo: { dir: OUT_DIR, size: VIEWPORT },
});
const page = await context.newPage();
t0 = Date.now();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));

await page.goto('http://127.0.0.1:8099/', { waitUntil: 'networkidle' });
await page.evaluate((z) => { document.documentElement.style.zoom = String(z); }, ZOOM);
await page.addStyleTag({ content: HIGHLIGHT_CSS + TOPOLOGY_CSS });
await page.evaluate(HIGHLIGHT_JS);
await page.evaluate(TOPOLOGY_JS, TOPOLOGY);
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(900);
await page.click('#btnReset');
await page.waitForTimeout(600);

// ---------------------------------------------------------------------------- pre

// 0:00 · a shift, not a dashboard
await cue(page, 'pre', 'Normal shift, trucks running, CAIRN quiet');

// 0:22 · the decision window
await cue(page, 'pre', 'Crusher, truck and weather events land', async () => {
  await press(page, '#btnInjectAll');
  await hl(page, '#timeline');
});
await clear(page);

// 0:43 · the design in one glance
await cue(page, 'pre', 'The decision spine at rest', () => hl(page, '.spine'));

// 1:02 · correlate, and the graph starts
await cue(page, 'pre', 'Strands graph fills, four specialists in parallel',
  () => page.click('#btnAnalyse'));

// 1:22 · why Strands. This is the typed-findings claim, so the fan-in is shown over the
// live room rather than as a separate slide: the spine stays visible around it.
await cue(page, 'pre', 'Typed findings cross the edges: the fan-in, over the live room',
  async () => {
    // Proportions of the beat, not fixed milliseconds. The old 6.5s and 10.5s summed to
    // exactly the hold this cue had at the time, so recalibrating the holds shorter would
    // have pushed the reveal past the end of its own beat.
    const hold = APP_HOLDS[cueIndex - 1] * 1000;
    await hl(page, '.spine');
    await wait(page, hold * 0.28);
    await page.evaluate(() => window.capTopology(true));
    await wait(page, hold * 0.62);
    await page.evaluate(() => window.capTopology(false));
  });
await clear(page);

// 1:42 · honest evidence
await cue(page, 'pre', 'Stale telemetry and a source conflict, both surfaced', async () => {
  await page.evaluate(() => document.querySelector('.flag.stale')?.scrollIntoView({ block: 'center' }));
  await hl(page, '#evidenceList');
});
await clear(page);

// 1:58 · options, not a magic answer
await cue(page, 'pre', 'Three options, then the recommended plan and its route', async () => {
  const opts = APP_HOLDS[cueIndex - 1] * 1000;
  await hl(page, '#scenarioCards');
  await press(page, '[data-scenario="scn_protect_safety"]');
  await wait(page, opts * 0.22);
  await press(page, '[data-scenario="scn_preserve_equipment"]');
  await wait(page, opts * 0.22);
  await press(page, '[data-scenario="scn_recover_tonnes"]');
});
await clear(page);

// 2:17 · where the system draws the line
await cue(page, 'pre', 'DENIED by deterministic policy, no model call', async () => {
  await press(page, '#btnProhibited');
  await hl(page, '#toast');
});
await clear(page);

// 2:41 · a person has to sign
await cue(page, 'pre', 'Scoped approval: named role, plan version, single use', async () => {
  const appr = APP_HOLDS[cueIndex - 1] * 1000;
  await press(page, '#btnApprove');
  await wait(page, appr * 0.32);
  await press(page, '#btnApprove');
  await hl(page, '#toast');
});
await clear(page);

// 3:00 · when the world misbehaves
await cue(page, 'pre', 'Timeout to UNKNOWN, blind retry refused, then reconciled', async () => {
  // Proportions again: three actions at 0.9s of press affordance each, plus two reads,
  // has to fit whatever hold the sheet declares for this beat.
  const drill = APP_HOLDS[cueIndex - 1] * 1000;
  await press(page, '#btnTimeout');
  await hl(page, '#toast');
  await wait(page, drill * 0.40);
  await page.locator('#btnReconcile').click({ button: 'right' });
  await wait(page, drill * 0.32);
  await press(page, '#btnReconcile');
});
await clear(page);

// --------------------------------------------------------------------------- post
// The three TOGAF frames splice in here.

// 4:27 · the audit trail. One of the two moments a viewer should carry away.
await cue(page, 'post', 'The chain: event, evidence, findings, policy, approval, action, outcome',
  async () => {
    await press(page, '#btnAudit');
    await hl(page, '.audit');
    await wait(page, APP_HOLDS[cueIndex - 1] * 1000 * 0.30);
    await page.evaluate(() => {
      const el = document.querySelector('.audit');
      if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    });
  });
await clear(page);

// 4:38 · close
await cue(page, 'post', 'The room, reset and quiet', async () => {
  await page.click('#btnCloseAudit');
  await page.click('#btnReset');
});

await context.close();
await browser.close();

const fs = await import('node:fs');
const files = fs.readdirSync(OUT_DIR).filter((f) => f.endsWith('.webm'));
fs.writeFileSync(`${OUT_DIR}beats.json`, `${JSON.stringify(beats, null, 2)}\n`);

const runtime = beats.at(-1).at + beats.at(-1).seconds;
const pre = beats.filter((b) => b.section === 'pre');
const preEnd = pre.at(-1).at + pre.at(-1).seconds;
console.log(`\napp runtime: ${Math.floor(runtime / 60)}:${String(Math.round(runtime % 60)).padStart(2, '0')}`);
console.log(`pre ends at ${preEnd.toFixed(1)}s, post starts at ${beats.find((b) => b.section === 'post').at.toFixed(1)}s`);
console.log(`video: ${files.join(', ') || 'none written'}`);
console.log(`pageerrors: ${JSON.stringify(errors.slice(0, 3))}`);
console.log('\nbeat sheet (measured against the video clock)');
for (const b of beats) {
  const whole = Math.round(b.at);
  const m = Math.floor(whole / 60);
  const s = String(whole % 60).padStart(2, '0');
  console.log(`  ${b.section === 'post' ? '+' : ' '}${m}:${s}  ${b.seconds.toFixed(1).padStart(5)}s  ${b.label}`);
}
