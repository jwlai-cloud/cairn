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
import { chromium } from 'playwright';

const OUT = new URL('.', import.meta.url).pathname;
const PAGE = `file://${new URL('../docs/design/togaf-slides.html', import.meta.url).pathname}`;
const VIDEO = process.argv.includes('--video');
const VIEWPORT = { width: 1280, height: 800 };

// Act 4 holds, from the cue sheet. Slide B's steps land on its clause boundaries.
const HOLD = { a: 24, b: 25, c: 14 };
const B_STEPS = [0, 5, 10, 15, 20];

const browser = await chromium.launch({ args: ['--hide-scrollbars'] });
const context = await browser.newContext({
  viewport: VIEWPORT,
  ...(VIDEO ? { recordVideo: { dir: OUT, size: VIEWPORT } } : {}),
});
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));

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
      await page.waitForTimeout((HOLD.b - last) * 1000);
    } else {
      await page.evaluate(() => window.revealAll());
      await page.waitForTimeout(700);
    }
  } else if (VIDEO) {
    await page.waitForTimeout(HOLD[slide] * 1000);
  }

  if (!VIDEO) await page.screenshot({ path: `${OUT}../docs/design/togaf-${slide}.png` });
}

await context.close();
await browser.close();
console.log(VIDEO
  ? `recorded ${HOLD.a + HOLD.b + HOLD.c}s of slides`
  : 'wrote docs/design/togaf-{a,b,c}.png');
console.log(`pageerrors: ${JSON.stringify(errors.slice(0, 3))}`);
