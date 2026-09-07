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
#cap-topo{position:fixed;left:50%;top:46%;transform:translate(-50%,-50%) scale(.97);z-index:9100;
  pointer-events:none;opacity:0;transition:opacity .5s ease,transform .5s ease;
  background:var(--plate);border:1px solid var(--rule-hi);padding:26px 30px 22px;
  box-shadow:0 26px 70px rgba(0,0,0,.42);clip-path:var(--chamfer);min-width:660px}
#cap-topo.on{opacity:1;transform:translate(-50%,-50%) scale(1)}
#cap-topo h4{font-family:var(--cond);font-size:11px;letter-spacing:.16em;text-transform:uppercase;
  color:var(--haematite);margin:0 0 16px}
#cap-topo .row{display:grid;grid-template-columns:132px 1fr 168px;align-items:center;
  gap:12px;padding:5px 0}
#cap-topo .n{font-family:var(--cond);font-size:15px;font-weight:700}
#cap-topo .t{font-family:var(--mono);font-size:11.5px;color:var(--survey);text-align:right}
#cap-topo .wire{height:1px;background:var(--rule-hi);position:relative}
#cap-topo .wire::after{content:'';position:absolute;right:-1px;top:-3px;
  border-top:3.5px solid transparent;border-bottom:3.5px solid transparent;
  border-left:5px solid var(--rule-hi)}
#cap-topo .join{border-top:1px dashed var(--rule-hi);margin:12px 0 10px;padding-top:12px;
  display:grid;grid-template-columns:132px 1fr 168px;align-items:center;gap:12px}
#cap-topo .join .n{color:var(--malachite)}
#cap-topo .cap{font-family:var(--mono);font-size:10px;color:var(--ink-faint);
  letter-spacing:.05em;margin-top:14px}
`;

export const TOPOLOGY_JS = (edges) => {
  const el = document.createElement('div');
  el.id = 'cap-topo';
  el.innerHTML = `<h4>Bounded Strands graph &middot; four specialists in parallel</h4>
    ${edges.specialists.map(([n, t]) => `<div class="row">
      <span class="n">${n}</span><span class="wire"></span><span class="t">${t}</span>
    </div>`).join('')}
    <div class="join">
      <span class="n">${edges.planner[0]}</span><span class="wire"></span>
      <span class="t">${edges.planner[1]}</span>
    </div>
    <div class="cap">the planner waits for all four &middot; edges carry typed findings, not execution order</div>`;
  document.body.append(el);
  window.capTopology = (on) => el.classList.toggle('on', on !== false);
};
