/**
 * Stylised open-pit scene.
 *
 * Deliberately not photorealistic: the scene is the spatial interface for the decision
 * loop, so it has to be readable in about two seconds. Geometry is primitives, state is
 * colour, and every value comes from the server read model.
 */
import * as THREE from './vendor/three.module.js';

export const STATE_COLOR = {
  NORMAL: 0x34d399,
  CONSTRAINED: 0xfbbf24,
  FAILED: 0xf87171,
  SELECTED: 0x60a5fa,
};
const ROUTE_OPEN = 0x6d8bab;
const ROUTE_CLOSED = 0x64748b;
const ROUTE_PLAN = 0x60a5fa;

export class MineScene {
  constructor(canvas, { onPick } = {}) {
    this.canvas = canvas;
    this.onPick = onPick;
    this.assets = new Map();   // assetId -> { mesh, marker }
    this.routes = new Map();   // routeId -> { line, glow }
    this.trucks = [];
    this.clock = new THREE.Clock();
    this.pickables = [];
    this.selectedAssetIds = new Set();

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(0x0b0f14, 150, 340);

    // Framed on the content bounding box (pit at x=-46 through plant at x=+52) so the
    // whole operation is in frame at load. The scene must read in about two seconds.
    this.target = new THREE.Vector3(-4, -2, -2);
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.5, 900);
    this.camera.position.set(4, 104, 126);
    this.camera.lookAt(this.target);

    this.scene.add(new THREE.HemisphereLight(0x9fc4ff, 0x1a2433, 1.5));
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(60, 110, 50);
    this.scene.add(key);

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    canvas.addEventListener('pointermove', (e) => this._hover(e));

    this._ground();
    this._resize();
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(canvas.parentElement);
  }

  _ground() {
    // The pad needs a hole punched where the pit is, otherwise it occludes every bench
    // below it and the pit reads as flat ground.
    const padShape = new THREE.Shape().absarc(0, 0, 135, 0, Math.PI * 2, false);
    const pitHole = new THREE.Path().absarc(-46, 0, 41, 0, Math.PI * 2, true);
    padShape.holes.push(pitHole);
    const pad = new THREE.Mesh(
      new THREE.ShapeGeometry(padShape, 64),
      new THREE.MeshStandardMaterial({ color: 0x1a2536, roughness: 1, side: THREE.DoubleSide }),
    );
    pad.rotation.x = -Math.PI / 2;
    pad.position.y = -0.4;
    this.scene.add(pad);

    // Open pit: stepped bench tops with visible risers between them. Flat annuli read
    // as terraces from an oblique camera; open cylinder walls alone do not.
    const pit = new THREE.Group();
    pit.position.set(-46, 0, 0);
    const benches = [
      { outer: 40.5, inner: 31, y: -0.6, top: 0x35485f, wall: 0x263548 },
      { outer: 31, inner: 22, y: -5.5, top: 0x3d5269, wall: 0x2c3d52 },
      { outer: 22, inner: 13, y: -10.4, top: 0x475d75, wall: 0x33465c },
    ];
    benches.forEach(({ outer, inner, y, top, wall }) => {
      const bench = new THREE.Mesh(
        new THREE.RingGeometry(inner, outer, 56),
        new THREE.MeshStandardMaterial({ color: top, roughness: 1, side: THREE.DoubleSide }),
      );
      bench.rotation.x = -Math.PI / 2;
      bench.position.y = y;
      pit.add(bench);

      const riser = new THREE.Mesh(
        new THREE.CylinderGeometry(inner, inner, 4.5, 56, 1, true),
        new THREE.MeshStandardMaterial({ color: wall, roughness: 1, side: THREE.DoubleSide }),
      );
      riser.position.y = y - 2.25;
      pit.add(riser);
    });
    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(13, 48),
      new THREE.MeshStandardMaterial({ color: 0x50697f, roughness: 1 }),
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -15;
    pit.add(floor);
    this.scene.add(pit);
    this.pitGroup = pit;
    this._label('NORTH PIT · BENCHES 1-3', new THREE.Vector3(-46, 6, 34), 0x8ea0b8, 0.78);
  }

  /** Camera-facing text sprite. Labels are the cheapest way to make a stylised scene legible. */
  _label(text, position, color = 0xc3d0e2, scale = 1) {
    const pad = 12;
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.font = 'bold 34px ui-monospace, Menlo, monospace';
    canvas.width = Math.ceil(ctx.measureText(text).width) + pad * 2;
    canvas.height = 52;
    const c2 = canvas.getContext('2d');
    c2.font = 'bold 34px ui-monospace, Menlo, monospace';
    c2.fillStyle = 'rgba(11,15,20,0.72)';
    c2.fillRect(0, 0, canvas.width, canvas.height);
    c2.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
    c2.fillText(text, pad, 37);

    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(canvas), transparent: true, depthTest: false,
    }));
    sprite.scale.set((canvas.width / 52) * 7 * scale, 7 * scale, 1);
    sprite.position.copy(position);
    sprite.renderOrder = 10;
    this.scene.add(sprite);
    return sprite;
  }

  // ------------------------------------------------------------------- build

  build(site) {
    this.routes.forEach(({ line, glow }) => { this.scene.remove(line); this.scene.remove(glow); });
    this.assets.forEach(({ group }) => this.scene.remove(group));
    this.routes.clear(); this.assets.clear(); this.trucks = []; this.pickables = [];

    site.routes.forEach((r) => this._route(r));
    site.assets.forEach((a) => this._asset(a));
  }

  _route(route) {
    const pts = route.path.map((p) => new THREE.Vector3(p.x, 0.6, p.z));
    const curve = new THREE.CatmullRomCurve3(pts);
    const line = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 70, 2.1, 8, false),
      new THREE.MeshStandardMaterial({ color: ROUTE_OPEN, roughness: 0.85 }),
    );
    const glow = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 70, 3.4, 8, false),
      new THREE.MeshBasicMaterial({ color: ROUTE_PLAN, transparent: true, opacity: 0 }),
    );
    this.scene.add(line); this.scene.add(glow);
    this.routes.set(route.routeId, { line, glow, curve, route });
  }

  _asset(asset) {
    const group = new THREE.Group();
    group.position.set(asset.position.x, 0, asset.position.z);
    const color = STATE_COLOR[asset.state] ?? STATE_COLOR.NORMAL;
    let mesh;

    switch (asset.kind) {
      case 'CRUSHER':
        mesh = new THREE.Mesh(new THREE.CylinderGeometry(5, 7.5, 11, 8),
          new THREE.MeshStandardMaterial({ color, roughness: 0.5, metalness: 0.25 }));
        mesh.position.y = 5.5; break;
      case 'PLANT':
        mesh = new THREE.Mesh(new THREE.BoxGeometry(15, 9, 11),
          new THREE.MeshStandardMaterial({ color, roughness: 0.6 }));
        mesh.position.y = 4.5; break;
      case 'STOCKPILE':
        mesh = new THREE.Mesh(new THREE.ConeGeometry(9, 8, 24),
          new THREE.MeshStandardMaterial({ color, roughness: 1 }));
        mesh.position.y = 4; break;
      case 'WORKSHOP':
        mesh = new THREE.Mesh(new THREE.BoxGeometry(13, 6, 9),
          new THREE.MeshStandardMaterial({ color, roughness: 0.8 }));
        mesh.position.y = 3; break;
      case 'TRUCK':
        mesh = new THREE.Mesh(new THREE.BoxGeometry(4.2, 3, 7),
          new THREE.MeshStandardMaterial({ color, roughness: 0.4, emissive: color, emissiveIntensity: 0.35 }));
        mesh.position.y = 2.2; break;
      case 'WEATHER_ZONE': {
        mesh = new THREE.Mesh(new THREE.CylinderGeometry(26, 26, 1.2, 40),
          new THREE.MeshBasicMaterial({ color: 0x7c8ea8, transparent: true, opacity: 0.2 }));
        mesh.position.y = 26;
        this._label('RAIN CELL', new THREE.Vector3(asset.position.x, 34, asset.position.z), 0xfbbf24, 0.7);
        break;
      }
      case 'BENCH':
        return; // benches are drawn as pit geometry
      default:
        mesh = new THREE.Mesh(new THREE.BoxGeometry(4, 4, 4),
          new THREE.MeshStandardMaterial({ color }));
        mesh.position.y = 2;
    }

    mesh.userData.assetId = asset.assetId;
    group.add(mesh);

    // Pulsing marker sits above anything that is not normal.
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(1.5, 12, 10),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0 }),
    );
    marker.position.y = (asset.kind === 'WEATHER_ZONE' ? 34 : 19);
    group.add(marker);

    this.scene.add(group);
    if (!['TRUCK', 'WEATHER_ZONE'].includes(asset.kind)) {
      const labelZ = asset.kind === 'PLANT' ? asset.position.z - 13 : asset.position.z + 9;
      this._label(asset.name.toUpperCase(), new THREE.Vector3(asset.position.x, 15, labelZ), 0xc3d0e2, 0.72);
    }
    this.assets.set(asset.assetId, { group, mesh, marker, asset });
    if (asset.kind !== 'WEATHER_ZONE') this.pickables.push(mesh);
    if (asset.kind === 'TRUCK') {
      this.trucks.push({ assetId: asset.assetId, group, routeId: asset.homeRouteId, t: Math.random() });
    }
  }

  // ------------------------------------------------------------------ update

  update(site, { selectedAssetIds = [], planRouteIds = [], closedRouteIds = [] } = {}) {
    this.selectedAssetIds = new Set(selectedAssetIds);
    site.assets.forEach((asset) => {
      const entry = this.assets.get(asset.assetId);
      if (!entry) return;
      entry.asset = asset;
      const selected = this.selectedAssetIds.has(asset.assetId);
      const color = selected && asset.state === 'NORMAL'
        ? STATE_COLOR.SELECTED
        : (STATE_COLOR[asset.state] ?? STATE_COLOR.NORMAL);
      if (entry.mesh.material.color) entry.mesh.material.color.setHex(color);
      entry.marker.material.color.setHex(color);
      entry.marker.userData.active = asset.state !== 'NORMAL' || selected;
      if (asset.assetId.startsWith('asset_truck') && asset.state === 'FAILED') {
        entry.group.userData.stopped = true;
      } else {
        entry.group.userData.stopped = false;
      }
    });

    const plan = new Set(planRouteIds);
    const closed = new Set(closedRouteIds);
    this.routes.forEach(({ line, glow }, routeId) => {
      const isClosed = closed.has(routeId);
      line.material.color.setHex(isClosed ? ROUTE_CLOSED : ROUTE_OPEN);
      line.material.opacity = isClosed ? 0.35 : 1;
      line.material.transparent = isClosed;
      glow.userData.active = plan.has(routeId) && !isClosed;
      if (!glow.userData.active) glow.material.opacity = 0;
    });
  }

  // -------------------------------------------------------------- interaction

  _hover(event) {
    const rect = this.canvas.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hit = this.raycaster.intersectObjects(this.pickables, false)[0];
    const assetId = hit?.object?.userData?.assetId ?? null;
    if (assetId !== this._hovered) {
      this._hovered = assetId;
      const entry = assetId ? this.assets.get(assetId) : null;
      this.onPick?.(entry?.asset ?? null, { x: event.clientX, y: event.clientY });
    }
  }

  // -------------------------------------------------------------------- loop

  start() {
    const tick = () => {
      this._frame = requestAnimationFrame(tick);
      const t = this.clock.getElapsedTime();
      const pulse = 0.35 + Math.abs(Math.sin(t * 2.2)) * 0.5;

      this.assets.forEach(({ marker }) => {
        marker.material.opacity = marker.userData.active ? pulse : 0;
        marker.scale.setScalar(marker.userData.active ? 0.8 + pulse * 0.5 : 0.001);
      });
      this.routes.forEach(({ glow }) => {
        if (glow.userData.active) glow.material.opacity = 0.1 + pulse * 0.22;
      });

      // Trucks crawl their route. Movement is decorative; state is authoritative.
      const dt = this.clock.getDelta();
      this.trucks.forEach((truck) => {
        const route = this.routes.get(truck.routeId);
        if (!route || truck.group.userData.stopped) return;
        truck.t = (truck.t + dt * 0.035) % 1;
        const p = route.curve.getPointAt(truck.t);
        const ahead = route.curve.getPointAt(Math.min(truck.t + 0.01, 1));
        truck.group.position.set(p.x, 0, p.z);
        truck.group.lookAt(ahead.x, 0, ahead.z);
      });

      this.camera.position.x = Math.sin(t * 0.045) * 8 + 4;
      this.camera.lookAt(this.target);
      this.renderer.render(this.scene, this.camera);
    };
    tick();
  }

  stop() { cancelAnimationFrame(this._frame); }

  _resize() {
    const host = this.canvas.parentElement;
    const w = host.clientWidth || 800;
    const h = host.clientHeight || 500;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }
}

export function supportsWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')));
  } catch { return false; }
}
