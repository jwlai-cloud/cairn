/**
 * Capture the three TOGAF slides for Act 4.
 *
 * Slide B reveals one link per narration clause, so its steps are driven here rather
 * than by a CSS animation. The clause offsets below come from the Act 4 narration in
 * captures/narration.md and must move with it.
 *
 *   node captures/capture-slides.mjs            # PNGs for review
 *   node captures/capture-slides.mjs --video    # webm for the cut
 */
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const OUT = new URL('.', import.meta.url).pathname;
const PAGE = `file://${new URL('../docs/design/slides.html', import.meta.url).pathname}`;
const VIDEO = process.argv.includes('--video');
const VIEWPORT = { width: 1280, height: 800 };

// Act 4 holds, read from the cue sheet rather than written here, so a re-timed sheet
// cannot silently desync the slide section from the narration.
const SHEET = new URL('./narration.md', import.meta.url).pathname;
const slideHolds = readFileSync(SHEET, 'utf8')
  .split('\n')
  .map((l) => l.match(/^\|\s*(\d+):(\d\d)\s*\|\s*(\d+)s\s*\|\s*slide\s*\|/))
  .filter(Boolean)
  .map((m) => Number(m[3]));
if (slideHolds.length !== 6) {
  throw new Error(`expected 6 slide cues in the sheet, found ${slideHolds.length}`);
}
// arch has three states, then the three method frames.
const [A1, A2, A3, HA, HB, HC] = slideHolds;
const B_STEPS = [0, 5, 10, 15, 20];

const browser = await chromium.launch({ args: ['--hide-scrollbars'] });
const context = await browser.newContext({
  viewport: VIEWPORT,
  ...(VIDEO ? { recordVideo: { dir: OUT, size: VIEWPORT } } : {}),
});
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));

// The architecture frame is one slide stepped three times, so it is filmed as one clip.
await page.goto(`${PAGE}#arch`, { waitUntil: 'load' });
await page.evaluate(() => { document.body.dataset.slide = 'arch'; });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(400);
for (const [i, hold] of [A1, A2, A3].entries()) {
  await page.evaluate((n) => window.archStep(n), i + 1);
  if (VIDEO) await page.waitForTimeout(hold * 1000);
  else {
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}../docs/design/arch-${i + 1}.png` });
  }
}

for (const slide of ['a', 'b', 'c']) {
  await page.goto(`${PAGE}#${slide}`, { waitUntil: 'load' });
  // Set it directly too: a hash-only navigation does not re-run the page script, so
  // relying on goto alone captured the first slide three times.
  await page.evaluate((s) => { document.body.dataset.slide = s; }, slide);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);

  if (slide === 'b') {
    if (VIDEO) {
      let last = 0;
      for (const [i, at] of B_STEPS.entries()) {
        await page.waitForTimeout((at - last) * 1000);
        last = at;
        await page.evaluate((n) => window.revealStep(n), i + 1);
      }
      await page.waitForTimeout((HB - last) * 1000);
    } else {
      await page.evaluate(() => window.revealAll());
      await page.waitForTimeout(700);
    }
  } else if (slide === 'c') {
    // Split beat: table alone, then the correction. Six seconds, per the review.
    if (VIDEO) {
      await page.waitForTimeout(6000);
      await page.evaluate(() => window.revealFix());
      await page.waitForTimeout((HC - 6) * 1000);
    } else {
      await page.evaluate(() => window.revealFix());
      await page.waitForTimeout(700);
    }
  } else if (VIDEO) {
    await page.waitForTimeout(({ a: HA, b: HB, c: HC })[slide] * 1000);
  }

  if (!VIDEO) await page.screenshot({ path: `${OUT}../docs/design/togaf-${slide}.png` });
}

await context.close();
await browser.close();
console.log(VIDEO
  ? `recorded ${slideHolds.reduce((a, b) => a + b, 0)}s of slides`
  : 'wrote docs/design/togaf-{a,b,c}.png');
console.log(`pageerrors: ${JSON.stringify(errors.slice(0, 3))}`);
