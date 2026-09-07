/**
 * Open-pit operational scene.
 *
 * The depth read comes from authored geometry and light, not from post: each bench is a
 * lit top face plus a dark riser wall, and a low raking sun separates them. Post-process
 * only does what a camera does - bloom on things that genuinely emit, then tone mapping.
 *
 * Bloom is selective by layer. The bloom camera renders ONLY the emitter layer, so the
 * pass costs almost nothing and no per-frame material substitution is needed. The
 * trade-off is that glow is not occluded by geometry in front of it; from this camera
 * angle nothing sits in front of a marker, so it never shows.
 *
 * Text sprites carry operational wording. They are unlit, toneMapped=false, and are
 * never added to the bloom layer, so labels stay crisp at low bitrate.
 */
import * as THREE from './vendor/three.module.js';
import { EffectComposer } from './vendor/postprocessing/EffectComposer.js';
import { RenderPass } from './vendor/postprocessing/RenderPass.js';
import { ShaderPass } from './vendor/postprocessing/ShaderPass.js';
import { UnrealBloomPass } from './vendor/postprocessing/UnrealBloomPass.js';
import { OutputPass } from './vendor/postprocessing/OutputPass.js';

export const STATE_COLOR = {
  NORMAL: 0x35c08a,      // oxidised copper
  CONSTRAINED: 0xf5b324, // hi-vis amber
  FAILED: 0xe2542c,      // haematite
  SELECTED: 0x6fa8dc,    // survey mark
};
const ROUTE_OPEN = 0x6b5c46;
const ROUTE_CLOSED = 0x4a515c;
const ROUTE_PLAN = 0x6fa8dc;

const BLOOM_LAYER = 1;
const bloomLayer = new THREE.Layers();
bloomLayer.set(BLOOM_LAYER);

// Emissive multipliers are scene-relative and set the contribution hierarchy:
// failed marker > constrained marker > planned route > rain boundary > lit surface.
const EMISSION = { marker: 1.35, plan: 0.95, weather: 0.7 };

export class MineScene {
  constructor(canvas, { onPick } = {}) {
    this.canvas = canvas;
    this.onPick = onPick;
    this.assets = new Map();
    this.routes = new Map();
    this.trucks = [];
    this.labels = [];
    this.clock = new THREE.Clock();
    this.pickables = [];
    this.selectedAssetIds = new Set();

    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    // Threshold is calibrated in HDR, so tone mapping must come after the composite.
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.25;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x07090c);
    this.scene.fog = new THREE.FogExp2(0x0b0e14, 0.0034);

    // Orthographic, not perspective: a mine plan is drawn orthographically, and it
    // stops the near ground plane from dominating the frame the way a wide lens does.
    this.frustum = 108;
    this.camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -400, 900);
    this.target = new THREE.Vector3(2, -8, -6);
    this.camera.position.set(150, 132, 150);
    this.camera.lookAt(this.target);

    this._lights();
    this._ground();
    this._composers();

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    canvas.addEventListener('pointermove', (e) => this._hover(e));

    this._resize();
    this._ro = new ResizeObserver(() => this._resize());
    this._ro.observe(canvas.parentElement);
  }

  // ------------------------------------------------------------------ lighting

  _lights() {
    // Low raking sun is what makes a terraced pit read as deep: it lights the bench
    // tops and leaves the risers in shadow, so the steps separate without any outline.
    const sun = new THREE.DirectionalLight(0xffd7a4, 3.4);
    sun.position.set(-118, 74, 26);
    sun.target.position.set(-46, -10, 0);
    this.scene.add(sun.target);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.near = 10;
    sun.shadow.camera.far = 420;
    const s = 190;
    Object.assign(sun.shadow.camera, { left: -s, right: s, top: s, bottom: -s });
    sun.shadow.bias = -0.0016;
    sun.shadow.normalBias = 0.6;
    this.scene.add(sun);
    this.sun = sun;

    // Cool sky bounce so shadowed risers stay legible rather than crushing to black.
    this.scene.add(new THREE.HemisphereLight(0x7c96b6, 0x36291c, 1.5));
  }

  // -------------------------------------------------------------------- ground

  _ground() {
    const padShape = new THREE.Shape().absarc(0, 0, 92, 0, Math.PI * 2, false);
    padShape.holes.push(new THREE.Path().absarc(-46, 0, 41, 0, Math.PI * 2, true));
    const pad = new THREE.Mesh(
      new THREE.ShapeGeometry(padShape, 72),
      new THREE.MeshStandardMaterial({ color: 0x121311, roughness: 1, metalness: 0 }),
    );
    pad.rotation.x = -Math.PI / 2;
    pad.position.y = -0.4;
    pad.receiveShadow = true;
    this.scene.add(pad);

    // Survey grid on the pad. Faint, and it reads as a surveyed plan rather than sci-fi.
    const grid = new THREE.GridHelper(184, 46, 0x35404f, 0x1c242e);
    grid.position.y = -0.34;
    grid.material.transparent = true;
    grid.material.opacity = 0.5;
    this.scene.add(grid);

    const pit = new THREE.Group();
    pit.position.set(-46, 0, 0);
    // outer radius, inner radius, top height, riser depth
    const benches = [
      [40.5, 31, -0.6, 4.9, 0x453c30],
      [31, 22, -5.5, 4.9, 0x504637],
      [22, 13, -10.4, 4.6, 0x5b5040],
      [13, 0, -15.0, 0, 0x665949],
    ];
    benches.forEach(([outer, inner, y, riser, color], i) => {
      const top = new THREE.Mesh(
        inner > 0 ? new THREE.RingGeometry(inner, outer, 72) : new THREE.CircleGeometry(outer, 72),
        new THREE.MeshStandardMaterial({ color, roughness: 0.96, metalness: 0.02 }),
      );
      top.rotation.x = -Math.PI / 2;
      top.position.y = y;
      top.receiveShadow = true;
      pit.add(top);
      pit.add(this._outline(top, 0xc7b492, 0.5));

      if (riser > 0) {
        const wall = new THREE.Mesh(
          new THREE.CylinderGeometry(inner, inner, riser, 72, 1, true),
          new THREE.MeshStandardMaterial({
            color: 0x33291d, roughness: 1, metalness: 0, side: THREE.DoubleSide,
          }),
        );
        wall.position.y = y - riser / 2;
        wall.receiveShadow = true;
        wall.castShadow = i === 0;
        pit.add(wall);
      }
    });
    this.scene.add(pit);
    this.pitGroup = pit;
    this._label('NORTH PIT · BENCH 1–4', new THREE.Vector3(-46, 6, 34), 0x9a8a70, 0.78);
  }

  /** Camera-facing text sprite. Unlit, untone-mapped, and never on the bloom layer. */
  _label(text, position, color = 0xc9c3b6, scale = 1) {
    const pad = 12;
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const font = 'bold 34px ui-monospace, Menlo, monospace';
    ctx.font = font;
    canvas.width = Math.ceil(ctx.measureText(text).width) + pad * 2;
    canvas.height = 52;
    const c2 = canvas.getContext('2d');
    c2.font = font;
    c2.fillStyle = 'rgba(7,9,12,0.78)';
    c2.fillRect(0, 0, canvas.width, canvas.height);
    c2.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
    c2.fillText(text, pad, 37);

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: texture, transparent: true, depthTest: false, toneMapped: false,
    }));
    sprite.scale.set((canvas.width / 52) * 7 * scale, 7 * scale, 1);
    sprite.position.copy(position);
    sprite.renderOrder = 10;
    this.scene.add(sprite);
    this.labels.push(sprite);
    return sprite;
  }

  // ------------------------------------------------------------------ composer

  _composers() {
    const size = new THREE.Vector2(1, 1);
    this.bloomComposer = new EffectComposer(this.renderer);
    this.bloomComposer.renderToScreen = false;
    this.bloomComposer.addPass(new RenderPass(this.scene, this.camera));
    this.bloomPass = new UnrealBloomPass(size, 1.1, 0.68, 0.46);
    this.bloomComposer.addPass(this.bloomPass);

    this.finalComposer = new EffectComposer(this.renderer);
    this.finalComposer.addPass(new RenderPass(this.scene, this.camera));
    this.finalComposer.addPass(new ShaderPass(new THREE.ShaderMaterial({
      uniforms: {
        baseTexture: { value: null },
        bloomTexture: { value: this.bloomComposer.renderTarget2.texture },
      },
      vertexShader: `varying vec2 vUv;
        void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }`,
      // Additive composite happens in HDR, before OutputPass tone maps.
      fragmentShader: `uniform sampler2D baseTexture; uniform sampler2D bloomTexture;
        varying vec2 vUv;
        void main(){ gl_FragColor = texture2D(baseTexture, vUv) + texture2D(bloomTexture, vUv); }`,
      defines: {},
    }), 'baseTexture'));
    this.finalComposer.addPass(new OutputPass());
  }

  /**
   * Bright thin outline on a matte body. This is what makes a dark form read as a
   * designed object rather than a muddy shaded blob, and it costs one LineSegments.
   */
  _outline(mesh, colorHex = 0xbfae8c, opacity = 0.55) {
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(mesh.geometry, 28),
      new THREE.LineBasicMaterial({
        color: colorHex, transparent: true, opacity, toneMapped: false, depthWrite: false,
      }),
    );
    edges.position.copy(mesh.position);
    edges.rotation.copy(mesh.rotation);
    edges.renderOrder = 4;
    return edges;
  }

  /** Mark a mesh as an emitter: it renders in the base pass and again for bloom. */
  _emitter(mesh, colorHex, strength) {
    mesh.layers.enable(BLOOM_LAYER);
    if (mesh.material.emissive) {
      mesh.material.emissive = new THREE.Color(colorHex);
      mesh.material.emissiveIntensity = strength;
    }
    return mesh;
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
    const pts = route.path.map((p) => new THREE.Vector3(p.x, 0.7, p.z));
    const curve = new THREE.CatmullRomCurve3(pts);
    const line = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 70, 2.1, 8, false),
      new THREE.MeshStandardMaterial({ color: ROUTE_OPEN, roughness: 0.85, metalness: 0.05 }),
    );
    line.receiveShadow = true;
    const glow = new THREE.Mesh(
      new THREE.TubeGeometry(curve, 70, 1.1, 8, false),
      new THREE.MeshStandardMaterial({
        color: 0x000000, emissive: new THREE.Color(ROUTE_PLAN),
        emissiveIntensity: 0, transparent: true, opacity: 0,
      }),
    );
    glow.position.y = 1.4;
    glow.layers.enable(BLOOM_LAYER);
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
        mesh = new THREE.Mesh(new THREE.CylinderGeometry(5, 7.5, 11, 12),
          new THREE.MeshStandardMaterial({ color, roughness: 0.5, metalness: 0.3 }));
        mesh.position.y = 5.5; break;
      case 'PLANT':
        mesh = new THREE.Mesh(new THREE.BoxGeometry(15, 9, 11),
          new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.2 }));
        mesh.position.y = 4.5; break;
      case 'STOCKPILE':
        mesh = new THREE.Mesh(new THREE.ConeGeometry(9, 8, 28),
          new THREE.MeshStandardMaterial({ color, roughness: 1 }));
        mesh.position.y = 4; break;
      case 'WORKSHOP':
        mesh = new THREE.Mesh(new THREE.BoxGeometry(13, 6, 9),
          new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.2 }));
        mesh.position.y = 3; break;
      case 'TRUCK':
        mesh = new THREE.Mesh(new THREE.BoxGeometry(4.2, 3, 7),
          new THREE.MeshStandardMaterial({ color, roughness: 0.5, metalness: 0.2 }));
        mesh.position.y = 2.2; break;
      case 'WEATHER_ZONE': {
        // Layered discs read as a cell with volume for a fraction of a raymarch's cost.
        const cell = new THREE.Group();
        for (let i = 0; i < 4; i += 1) {
          const disc = new THREE.Mesh(
            new THREE.CircleGeometry(24 - i * 2.4, 40),
            new THREE.MeshBasicMaterial({
              color: 0xb59a6a, transparent: true, opacity: 0.055, side: THREE.DoubleSide,
              depthWrite: false,
            }),
          );
          disc.rotation.x = -Math.PI / 2;
          disc.position.y = 19 + i * 2.2;
          cell.add(disc);
        }
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(23, 23.7, 56),
          new THREE.MeshBasicMaterial({ color: 0xf5b324, transparent: true, opacity: 0.45, side: THREE.DoubleSide }),
        );
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = 19;
        ring.layers.enable(BLOOM_LAYER);
        cell.add(ring);
        cell.position.y = 0;
        group.add(cell);
        this._label('RAIN CELL', new THREE.Vector3(asset.position.x, 34, asset.position.z), 0xf5b324, 0.7);
        this.scene.add(group);
        this.assets.set(asset.assetId, { group, mesh: ring, marker: ring, asset, cell });
        return;
      }
      case 'BENCH':
        return;
      default:
        mesh = new THREE.Mesh(new THREE.BoxGeometry(4, 4, 4), new THREE.MeshStandardMaterial({ color }));
        mesh.position.y = 2;
    }

    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData.assetId = asset.assetId;
    group.add(mesh);
    // Outline takes the asset's status colour, so state reads from the silhouette too.
    const outline = this._outline(mesh, color, asset.kind === 'TRUCK' ? 0.75 : 0.62);
    group.add(outline);
    group.userData.outline = outline;

    // Status marker: an octahedral beacon. This is the only part that emits.
    const marker = new THREE.Mesh(
      new THREE.OctahedronGeometry(1.9, 0),
      new THREE.MeshStandardMaterial({
        color: 0x000000, emissive: new THREE.Color(color), emissiveIntensity: 0,
        transparent: true, opacity: 0, roughness: 0.4, toneMapped: true,
      }),
    );
    marker.position.y = 17;
    marker.layers.enable(BLOOM_LAYER);
    group.add(marker);

    this.scene.add(group);
    if (!['TRUCK'].includes(asset.kind)) {
      this._label(asset.name.toUpperCase(),
        new THREE.Vector3(asset.position.x, 14, asset.position.z + (asset.kind === 'PLANT' ? -13 : 9)),
        0xd8d2c6, 0.72);
    }
    this.assets.set(asset.assetId, { group, mesh, marker, asset });
    this.pickables.push(mesh);
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
      if (entry.group.userData.outline) entry.group.userData.outline.material.color.setHex(color);
      if (entry.marker !== entry.mesh) {
        entry.marker.material.color.setHex(color);
        entry.marker.material.emissive.setHex(color);
      }
      entry.marker.userData.active = asset.state !== 'NORMAL' || selected;
      entry.group.userData.stopped =
        asset.assetId.startsWith('asset_truck') && asset.state === 'FAILED';
    });

    const plan = new Set(planRouteIds);
    const closed = new Set(closedRouteIds);
    this.routes.forEach(({ line, glow }, routeId) => {
      const isClosed = closed.has(routeId);
      line.material.color.setHex(isClosed ? ROUTE_CLOSED : ROUTE_OPEN);
      line.material.opacity = isClosed ? 0.4 : 1;
      line.material.transparent = isClosed;
      glow.userData.active = plan.has(routeId) && !isClosed;
      if (!glow.userData.active) { glow.material.opacity = 0; glow.material.emissiveIntensity = 0; }
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

  // ---------------------------------------------------------------------- loop

  start() {
    const tick = () => {
      this._frame = requestAnimationFrame(tick);
      const t = this.clock.getElapsedTime();
      const dt = this.clock.getDelta();
      const pulse = 0.4 + Math.abs(Math.sin(t * 2.1)) * 0.6;

      this.assets.forEach(({ marker, cell }) => {
        if (cell) { cell.rotation.y = t * 0.05; return; }
        const on = marker.userData.active;
        marker.material.opacity = on ? 1 : 0;
        marker.material.emissiveIntensity = on ? EMISSION.marker * (0.72 + pulse * 0.4) : 0;
        marker.rotation.y = t * 0.9;
        marker.position.y = 17 + Math.sin(t * 1.6) * 0.6;
        marker.scale.setScalar(on ? 1 : 0.001);
      });
      this.routes.forEach(({ glow }) => {
        if (!glow.userData.active) return;
        glow.material.opacity = 0.5 + pulse * 0.3;
        glow.material.emissiveIntensity = EMISSION.plan * (0.7 + pulse * 0.35);
      });

      this.trucks.forEach((truck) => {
        const route = this.routes.get(truck.routeId);
        if (!route || truck.group.userData.stopped) return;
        truck.t = (truck.t + dt * 0.035) % 1;
        const p = route.curve.getPointAt(truck.t);
        const ahead = route.curve.getPointAt(Math.min(truck.t + 0.01, 1));
        truck.group.position.set(p.x, 0, p.z);
        truck.group.lookAt(ahead.x, 0, ahead.z);
      });

      const drift = Math.sin(t * 0.05) * 10;
      this.camera.position.set(150 + drift, 132, 150 - drift);
      this.camera.lookAt(this.target);

      // Selective bloom: render only the emitter layer, then composite in HDR.
      this.camera.layers.set(BLOOM_LAYER);
      this.bloomComposer.render();
      this.camera.layers.set(0);
      this.finalComposer.render();
    };
    tick();
  }

  stop() { cancelAnimationFrame(this._frame); }

  _resize() {
    const host = this.canvas.parentElement;
    const w = host.clientWidth || 800;
    const h = host.clientHeight || 500;
    this.renderer.setSize(w, h, false);
    this.bloomComposer.setSize(w, h);
    this.finalComposer.setSize(w, h);
    const aspect = w / h;
    this.camera.left = (-this.frustum * aspect) / 2;
    this.camera.right = (this.frustum * aspect) / 2;
    this.camera.top = this.frustum / 2;
    this.camera.bottom = -this.frustum / 2;
    this.camera.updateProjectionMatrix();
  }
}

export function supportsWebGL() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')));
  } catch { return false; }
}
