/**
 * Capture-only spotlight. Injected into the page by the capture script and never shipped
 * in the app - the product does not need a narrator's pointer, and adding one to app/web
 * would put demo furniture in the product.
 *
 * Dims everything except one element and rings it. The dim is a full-viewport overlay
 * with a hole punched by clip-path rather than four positioned bars, so a rounded or
 * chamfered target stays readable at its own edges.
 */
export const HIGHLIGHT_CSS = `
#cap-dim{position:fixed;inset:0;z-index:9000;pointer-events:none;background:rgba(8,10,14,.72);
  opacity:0;transition:opacity .45s ease}
#cap-dim.on{opacity:1}
#cap-ring{position:fixed;z-index:9001;pointer-events:none;border:2px solid #E2542C;
  box-shadow:0 0 0 1px rgba(226,84,44,.35),0 0 26px rgba(226,84,44,.30);
  opacity:0;transition:opacity .45s ease,left .22s ease,top .22s ease,width .22s ease,height .22s ease}
#cap-ring.on{opacity:1}
#cap-ring::after{content:'';position:absolute;inset:-7px;border:1px solid rgba(226,84,44,.28)}
`;

export const HIGHLIGHT_JS = () => {
  const dim = document.createElement('div');
  dim.id = 'cap-dim';
  const ring = document.createElement('div');
  ring.id = 'cap-ring';
  document.body.append(dim, ring);

  const PAD = 10;

  // The capture zooms the document, and the two coordinate systems do not agree.
  // getBoundingClientRect returns visual pixels, but the overlay lives inside the zoomed
  // root, so the CSS pixels written to its style are multiplied by the zoom again. A
  // measured target at y=1147 put the ring at y=1705. Divide the measurement back.
  const zoom = () => parseFloat(getComputedStyle(document.documentElement).zoom) || 1;

  // The ring follows its target instead of being measured once. A single beat can change
  // the element under it several times - the reliability drill swaps the toast three
  // times, from OUTCOME UNKNOWN to RETRY REFUSED to RECONCILED - and each has different
  // content and so different dimensions. Measured once, the ring ends up sized for the
  // first one and the later text spills out of it.
  let tracking = null;

  const place = (el) => {
    const r = el.getBoundingClientRect();
    const z = zoom();
    const box = {
      x: Math.max(r.left - PAD, 0) / z, y: Math.max(r.top - PAD, 0) / z,
      w: (r.width + PAD * 2) / z, h: (r.height + PAD * 2) / z,
    };
    Object.assign(ring.style, {
      left: `${box.x}px`, top: `${box.y}px`,
      width: `${box.w}px`, height: `${box.h}px`,
    });
    // Punch the target out of the dim so it keeps its own contrast.
    dim.style.clipPath = `polygon(0 0, 100% 0, 100% 100%, 0 100%, 0 0,
      ${box.x}px ${box.y}px,
      ${box.x}px ${box.y + box.h}px,
      ${box.x + box.w}px ${box.y + box.h}px,
      ${box.x + box.w}px ${box.y}px,
      ${box.x}px ${box.y}px)`;
    dim.classList.add('on');
    ring.classList.add('on');
  };

  window.capHighlight = (selector) => {
    const first = document.querySelector(selector);
    if (!first) return false;
    place(first);
    if (tracking) cancelAnimationFrame(tracking);
    const follow = () => {
      const el = document.querySelector(selector);
      if (el) place(el);
      tracking = requestAnimationFrame(follow);
    };
    tracking = requestAnimationFrame(follow);
    return true;
  };

  window.capClear = () => {
    if (tracking) { cancelAnimationFrame(tracking); tracking = null; }
    dim.classList.remove('on');
    ring.classList.remove('on');
  };
};

/**
 * Strands fan-in, shown over the live room rather than as a separate slide.
 *
 * Three claims and nothing else: the four specialists run at once, the planner waits for
 * all four, and the edges carry typed findings rather than execution order. Node budget
 * and timeout are deliberately absent - the live spine already shows measured durations,
 * and the narration already says the work is bounded.
 *
 * The type names are read from app.agents.graph at build time, not written by hand. The
 * review's draft guessed OperationsOptions and RiskFinding; the graph actually returns
 * ConstraintSet and RiskAssessment.
 */
export const TOPOLOGY_CSS = `
#cap-topo{position:fixed;left:50%;top:45%;transform:translate(-50%,-50%) scale(.96);z-index:9100;
  pointer-events:none;opacity:0;transition:opacity .5s ease,transform .5s ease;
  background:var(--plate);border:1px solid var(--rule-hi);padding:20px 24px 16px;
  box-shadow:0 26px 70px rgba(0,0,0,.42);clip-path:var(--chamfer)}
#cap-topo.on{opacity:1;transform:translate(-50%,-50%) scale(1)}
#cap-topo h4{font-family:var(--cond);font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--haematite);margin:0 0 4px}
#cap-topo .cap{font-family:var(--mono);font-size:10px;color:var(--ink-faint);letter-spacing:.05em;
  margin-top:2px;text-align:center}
#cap-topo svg{display:block}
#cap-topo .nl{font-family:var(--cond);font-size:15px;font-weight:700;fill:var(--ink)}
#cap-topo .ns{font-family:var(--mono);font-size:8.5px;fill:var(--ink-faint)}
#cap-topo .el{font-family:var(--mono);font-size:9.5px;fill:var(--survey)}
#cap-topo .card{fill:var(--raise);stroke:var(--rule-hi);stroke-width:1}
#cap-topo .card.join{fill:var(--ok-bg);stroke:var(--ok-line);stroke-width:1.5}
#cap-topo .card.src{fill:var(--plate);stroke:var(--rule)}
#cap-topo .wire{fill:none;stroke:var(--rule-hi);stroke-width:1.4}
#cap-topo .wire.typed{stroke:var(--survey);stroke-width:1.8}
`;

/**
 * The Strands fan-in, drawn as a graph rather than a list.
 *
 * Hand geometry, and deliberately so. archify was tried first and its workflow renderer
 * routes the vertical leg of a cross-lane edge through the source column, so a symmetric
 * four-into-one join always crosses the intervening lanes' nodes - see
 * docs/review/archify-fan-in-note.md. The shape here is fixed, small and known in
 * advance, which is exactly when hand geometry beats a layout engine.
 *
 * Three things have to be obvious: the four run at once, the planner waits for all four,
 * and the edges carry typed findings rather than execution order.
 */
export const TOPOLOGY_JS = (edges) => {
  const W = 700, CARD_W = 168, CARD_H = 46, ROW = 62, TOP = 34;
  const LX = 8, MX = 300, RX = 500;
  const rows = edges.specialists.length;
  const H = TOP + rows * ROW + 10;
  const midY = TOP + (rows * ROW) / 2 - ROW / 2 + CARD_H / 2;

  const card = (x, y, label, sub, cls = '') => `
    <rect class="card ${cls}" x="${x}" y="${y}" width="${CARD_W}" height="${CARD_H}" rx="2"/>
    <text class="nl" x="${x + 12}" y="${y + 20}">${label}</text>
    <text class="ns" x="${x + 12}" y="${y + 34}">${sub}</text>`;

  // Each specialist leaves its right edge, runs to a shared corridor, then curves into
  // the planner's left edge. One corridor, four curves: that is what makes it a join.
  const wire = (y) => {
    const x0 = LX + CARD_W, y0 = y + CARD_H / 2, x1 = RX;
    return `<path class="wire typed" d="M${x0} ${y0} H${MX - 46}
      C${MX} ${y0} ${MX} ${midY} ${MX + 46} ${midY} H${x1}"/>`;
  };

  // The card says what the agent gathered; the edge says what it hands on. Naming the
  // type in both places filled the frame with the same word twice.
  const spec = edges.specialists.map(([name, type, sub], i) => {
    const y = TOP + i * ROW;
    return wire(y) + card(LX, y, name, sub) +
      `<text class="el" x="${MX - 52}" y="${y + CARD_H / 2 - 11}">${type}</text>`;
  }).join('');

  const el = document.createElement('div');
  el.id = 'cap-topo';
  el.innerHTML = `<h4>Bounded Strands graph</h4>
    <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
      ${spec}
      ${card(RX, midY - CARD_H / 2, edges.planner[0], edges.planner[2], 'join')}
      <text class="el" x="${RX + 6}" y="${midY - CARD_H / 2 - 8}">${edges.planner[1]}</text>
    </svg>
    <div class="cap">four specialists at once &middot; the planner waits for all four &middot;
      every edge carries a typed finding</div>`;
  document.body.append(el);
  window.capTopology = (on) => el.classList.toggle('on', on !== false);
};
