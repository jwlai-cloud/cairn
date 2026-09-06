/**
 * 2D isometric fallback.
 *
 * Same read model, same colours, no WebGL. If the demo machine or the venue projector
 * cannot give us a GL context, the decision loop must still be presentable.
 */
export const STATE_COLOR = {
  NORMAL: '#34d399',
  CONSTRAINED: '#fbbf24',
  FAILED: '#f87171',
  SELECTED: '#60a5fa',
};

const ISO_X = 1.0;
const ISO_Y = 0.52;

export class MineScene2D {
  constructor(canvas, { onPick } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.onPick = onPick;
    this.site = null;
    this.opts = {};
    this.t = 0;
    this.truckPhase = new Map();
    this._hovered = null;

    canvas.addEventListener('pointermove', (e) => this._hover(e));
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(canvas.parentElement);
    this._resize();
  }

  _resize() {
    const host = this.canvas.parentElement;
    const dpr = Math.min(devicePixelRatio, 2);
    this.w = host.clientWidth || 800;
    this.h = host.clientHeight || 500;
    this.canvas.width = this.w * dpr;
    this.canvas.height = this.h * dpr;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  project(p) {
    const scale = Math.min(this.w / 150, this.h / 110);
    return {
      x: this.w / 2 + (p.x - p.z) * ISO_X * scale * 0.86,
      y: this.h / 2 + (p.x + p.z) * ISO_Y * scale * 0.58,
    };
  }

  build(site) {
    this.site = site;
    site.assets.filter((a) => a.kind === 'TRUCK').forEach((a, i) => {
      if (!this.truckPhase.has(a.assetId)) this.truckPhase.set(a.assetId, i / 8);
    });
  }

  update(site, opts = {}) { this.site = site; this.opts = opts; }

  _routePoint(route, t) {
    const pts = route.path;
    const seg = Math.min(Math.floor(t * (pts.length - 1)), pts.length - 2);
    const local = t * (pts.length - 1) - seg;
    const a = pts[seg];
    const b = pts[seg + 1];
    return { x: a.x + (b.x - a.x) * local, y: 0, z: a.z + (b.z - a.z) * local };
  }

  _hover(event) {
    if (!this.site) return;
    const rect = this.canvas.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;
    let found = null;
    for (const asset of this.site.assets) {
      if (asset.kind === 'BENCH' || asset.kind === 'WEATHER_ZONE') continue;
      const p = this.project(asset.position);
      if (Math.hypot(p.x - mx, p.y - my) < 14) { found = asset; break; }
    }
    if (found?.assetId !== this._hovered) {
      this._hovered = found?.assetId ?? null;
      this.onPick?.(found ?? null, { x: event.clientX, y: event.clientY });
    }
  }

  start() {
    const tick = () => {
      this._frame = requestAnimationFrame(tick);
      this.t += 1 / 60;
      this.draw();
    };
    tick();
  }

  stop() { cancelAnimationFrame(this._frame); }

  draw() {
    const { ctx } = this;
    ctx.clearRect(0, 0, this.w, this.h);
    if (!this.site) return;

    const selected = new Set(this.opts.selectedAssetIds ?? []);
    const plan = new Set(this.opts.planRouteIds ?? []);
    const closed = new Set(this.opts.closedRouteIds ?? []);
    const pulse = 0.35 + Math.abs(Math.sin(this.t * 2.2)) * 0.5;

    // Pit benches as nested diamonds on the west side.
    [[34, '#2c3d55'], [26, '#33465f'], [18, '#3b5069']].forEach(([r, color]) => {
      ctx.beginPath();
      for (let i = 0; i <= 40; i += 1) {
        const a = (i / 40) * Math.PI * 2;
        const p = this.project({ x: -46 + Math.cos(a) * r, y: 0, z: Math.sin(a) * r });
        i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
      }
      ctx.closePath();
      ctx.fillStyle = color; ctx.fill();
      ctx.strokeStyle = '#1a2536'; ctx.stroke();
    });

    // Weather cell.
    const cell = this.site.assets.find((a) => a.kind === 'WEATHER_ZONE');
    if (cell) {
      const p = this.project(cell.position);
      ctx.beginPath(); ctx.ellipse(p.x, p.y, 68, 36, 0, 0, Math.PI * 2);
      ctx.fillStyle = cell.state === 'NORMAL' ? 'rgba(124,142,168,.12)' : `rgba(251,191,36,${0.1 + pulse * 0.12})`;
      ctx.fill();
      ctx.strokeStyle = 'rgba(251,191,36,.5)'; ctx.setLineDash([4, 4]); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#8ea0b8'; ctx.font = '10px ui-monospace, monospace';
      ctx.fillText('RAIN CELL', p.x - 26, p.y - 42);
    }

    // Routes.
    this.site.routes.forEach((route) => {
      const isClosed = closed.has(route.routeId) || !route.open;
      const isPlan = plan.has(route.routeId) && !isClosed;
      ctx.beginPath();
      route.path.forEach((pt, i) => {
        const p = this.project(pt);
        i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
      });
      ctx.lineWidth = isPlan ? 7 : 5;
      ctx.lineCap = 'round';
      ctx.strokeStyle = isClosed ? '#64748b' : (isPlan ? `rgba(96,165,250,${0.55 + pulse * 0.4})` : '#53708f');
      if (isClosed) ctx.setLineDash([6, 6]);
      ctx.stroke();
      ctx.setLineDash([]);
      if (isClosed) {
        const mid = this.project(route.path[Math.floor(route.path.length / 2)]);
        ctx.fillStyle = '#f87171'; ctx.font = 'bold 9px ui-monospace, monospace';
        ctx.fillText('CLOSED', mid.x - 18, mid.y - 8);
      }
    });

    // Fixed assets then trucks, painted back to front.
    const fixed = this.site.assets.filter((a) => !['TRUCK', 'BENCH', 'WEATHER_ZONE'].includes(a.kind));
    const sorted = [...fixed].sort((a, b) => (a.position.x + a.position.z) - (b.position.x + b.position.z));
    sorted.forEach((asset) => this._drawAsset(asset, selected, pulse));

    this.site.assets.filter((a) => a.kind === 'TRUCK').forEach((truck) => {
      const route = this.site.routes.find((r) => r.routeId === truck.homeRouteId);
      let pos = truck.position;
      if (route && truck.state !== 'FAILED') {
        const phase = (this.truckPhase.get(truck.assetId) ?? 0) + this.t * 0.035;
        pos = this._routePoint(route, phase % 1);
      }
      this._drawAsset({ ...truck, position: pos }, selected, pulse);
    });
  }

  _drawAsset(asset, selected, pulse) {
    const { ctx } = this;
    const p = this.project(asset.position);
    const isSel = selected.has(asset.assetId);
    const color = isSel && asset.state === 'NORMAL' ? STATE_COLOR.SELECTED : (STATE_COLOR[asset.state] ?? STATE_COLOR.NORMAL);
    const size = asset.kind === 'TRUCK' ? 5 : 11;

    if (asset.state !== 'NORMAL' || isSel) {
      ctx.beginPath(); ctx.arc(p.x, p.y, size + 6 + pulse * 7, 0, Math.PI * 2);
      ctx.fillStyle = color + '33'; ctx.fill();
    }
    ctx.beginPath();
    if (asset.kind === 'STOCKPILE') {
      ctx.moveTo(p.x, p.y - size); ctx.lineTo(p.x + size, p.y + size * 0.6); ctx.lineTo(p.x - size, p.y + size * 0.6); ctx.closePath();
    } else if (asset.kind === 'TRUCK') {
      ctx.rect(p.x - size, p.y - size * 0.6, size * 2, size * 1.2);
    } else {
      ctx.rect(p.x - size, p.y - size * 0.72, size * 2, size * 1.44);
    }
    ctx.fillStyle = color; ctx.fill();
    ctx.strokeStyle = '#0b0f14'; ctx.lineWidth = 1.5; ctx.stroke();

    if (asset.kind !== 'TRUCK') {
      ctx.fillStyle = '#c3d0e2'; ctx.font = '10px ui-sans-serif, sans-serif';
      ctx.fillText(asset.name, p.x - ctx.measureText(asset.name).width / 2, p.y + size + 14);
    }
  }
}
