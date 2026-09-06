/**
 * Situation room controller.
 *
 * Renders the server read model. Contains no policy logic: a denial shown here is a
 * denial the server made, and the client cannot talk itself past one.
 */
import { MineScene, supportsWebGL } from './scene3d.js';
import { MineScene2D } from './scene2d.js';

const $ = (id) => document.getElementById(id);
let view = null;
let scene = null;
let using3D = false;

const SEV_CLASS = { LOW: 'ok', MEDIUM: 'warn', HIGH: 'hot', CRITICAL: 'hot' };

// ------------------------------------------------------------------- transport

async function call(path, options = {}) {
  const res = await fetch(path, {
    method: options.method ?? 'GET',
    headers: options.body ? { 'content-type': 'application/json' } : undefined,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = data.error ?? { code: `HTTP_${res.status}`, message: res.statusText };
    throw Object.assign(new Error(err.message), { code: err.code, details: err.details });
  }
  return data;
}

async function refresh(promise) {
  try {
    view = await promise;
    render();
    return view;
  } catch (err) {
    toast(err.code ?? 'ERROR', err.message, err.details, 'deny');
    view = await call('/v1/runs/current');
    render();
    return null;
  }
}

// ------------------------------------------------------------------------ scene

function bootScene() {
  const wants3D = supportsWebGL();
  try {
    if (!wants3D) throw new Error('no webgl');
    scene = new MineScene($('scene3d'), { onPick: showAssetPop });
    using3D = true;
    $('scene3d').hidden = false;
    $('scene2d').hidden = true;
  } catch {
    scene = new MineScene2D($('scene2d'), { onPick: showAssetPop });
    using3D = false;
    $('scene3d').hidden = true;
    $('scene2d').hidden = false;
  }
  $('renderBadge').textContent = using3D ? 'render 3D' : 'render 2D fallback';
  $('toggleRender').textContent = using3D ? 'use 2D fallback' : 'use 3D scene';
  scene.start();
}

function switchRenderer() {
  scene.stop();
  const target3D = !using3D;
  if (target3D && !supportsWebGL()) { toast('NO_WEBGL', 'This browser cannot provide a WebGL context.', null, 'deny'); return; }
  scene = target3D
    ? new MineScene($('scene3d'), { onPick: showAssetPop })
    : new MineScene2D($('scene2d'), { onPick: showAssetPop });
  using3D = target3D;
  $('scene3d').hidden = !target3D;
  $('scene2d').hidden = target3D;
  $('renderBadge').textContent = using3D ? 'render 3D' : 'render 2D fallback';
  $('toggleRender').textContent = using3D ? 'use 2D fallback' : 'use 3D scene';
  scene.build(view.site);
  scene.update(view.site, sceneOptions());
  scene.start();
}

function sceneOptions() {
  const selected = view.scenarios.find((s) => s.scenarioId === view.selectedScenarioId);
  const affected = view.incident?.affectedAssetIds ?? [];
  return {
    selectedAssetIds: selected ? selected.impacts.affectedAssets : affected,
    planRouteIds: selected ? selected.routeOverlay : (view.incident?.affectedRouteIds ?? []),
    closedRouteIds: selected ? selected.closedRouteIds : [],
  };
}

function showAssetPop(asset, at) {
  const pop = $('assetPop');
  if (!asset) { pop.hidden = true; return; }
  const events = (view?.events ?? []).filter((e) => e.assetId === asset.assetId);
  pop.innerHTML = `
    <h4>${asset.name}</h4>
    <p>${asset.detail}</p>
    <p><b>${asset.state}</b> · capacity ${asset.capacityPercent}%</p>
    ${events.map((e) => `<p>· ${e.title}</p>`).join('')}`;
  pop.hidden = false;
  const host = $('sceneHost').getBoundingClientRect();
  pop.style.left = `${Math.min(at.x - host.left + 14, host.width - 300)}px`;
  pop.style.top = `${Math.max(at.y - host.top - 10, 8)}px`;
}

// ------------------------------------------------------------------- rendering

function render() {
  if (!view) return;
  $('shift').textContent = view.site.shiftLabel;
  $('site').textContent = `SITE: ${view.site.name}`;
  $('modeBadge').textContent = `mode ${view.mode} · ${view.modelId}`;
  $('policyBadge').textContent = view.policyVersion;

  const chip = $('incidentStatus');
  if (view.outcome) { chip.textContent = 'PLAN EXECUTED (SIMULATED)'; chip.className = 'status-chip done'; }
  else if (view.incident) { chip.textContent = `INCIDENT: ${view.incident.status}`; chip.className = 'status-chip alert'; }
  else if (view.events.length) { chip.textContent = 'SIGNALS ARRIVING'; chip.className = 'status-chip recovering'; }
  else { chip.textContent = 'NORMAL SHIFT'; chip.className = 'status-chip'; }

  renderKpis();
  renderIncident();
  renderAgents();
  renderEvidence();
  renderScenarios();
  renderTimeline();
  renderButtons();

  scene.build(view.site);
  scene.update(view.site, sceneOptions());
}

function renderKpis() {
  const k = view.kpi;
  const pct = Math.round((k.tonnesMoved / k.tonnesTarget) * 100);
  const cells = [
    ['Tonnes moved', k.tonnesMoved.toLocaleString(), `${pct}% of ${k.tonnesTarget.toLocaleString()} t target`, pct >= 95 ? 'good' : pct >= 85 ? 'warn' : 'bad'],
    ['Crusher availability', `${k.crusherAvailabilityPercent}%`, 'Primary Crusher 01', k.crusherAvailabilityPercent >= 95 ? 'good' : k.crusherAvailabilityPercent >= 80 ? 'warn' : 'bad'],
    ['Active trucks', `${k.activeTrucks}`, `of ${view.baselineKpi.activeTrucks} on shift`, k.activeTrucks >= view.baselineKpi.activeTrucks ? 'good' : 'warn'],
    ['Weather window', k.weatherWindowMinutes == null ? '—' : `${k.weatherWindowMinutes} min`, k.weatherWindowMinutes == null ? 'no active alert' : 'to East Ramp closure', k.weatherWindowMinutes == null ? '' : 'bad'],
    ['Unresolved risks', `${k.unresolvedRisks}`, 'open risk findings', k.unresolvedRisks === 0 ? 'good' : 'warn'],
  ];
  $('kpiStrip').innerHTML = cells.map(([label, value, sub, cls]) => `
    <div class="kpi">
      <div class="kpi-label">${label}</div>
      <div class="kpi-value ${cls}">${value}</div>
      <div class="kpi-sub">${sub}</div>
    </div>`).join('');
}

function renderIncident() {
  const body = $('incidentBody');
  if (!view.incident) {
    body.className = 'muted';
    body.textContent = view.events.length
      ? `${view.events.length} signal(s) received. Run the analysis to correlate them.`
      : 'No incident. Inject events to begin.';
    return;
  }
  const inc = view.incident;
  body.className = '';
  const notices = [...view.notices, ...view.conflictNotes];
  body.innerHTML = `
    <div class="incident-title">${inc.title}</div>
    <div class="incident-narr">${inc.narrative}</div>
    <div class="meta-row">
      <span class="tag hot">${inc.severity}</span>
      <span class="tag info">${inc.eventIds.length} events → 1 incident</span>
      ${inc.weatherWindowMinutes != null ? `<span class="tag warn">${inc.weatherWindowMinutes} min window</span>` : ''}
      <span class="tag ok">confidence ${inc.confidence}</span>
      <span class="tag">${inc.correlationId}</span>
    </div>
    ${notices.length ? `<div class="meta-row" style="flex-direction:column;gap:4px">
      ${notices.map((n) => `<span class="tag ${n.startsWith('STALE') ? 'hot' : 'warn'}" style="white-space:normal;text-align:left">${n}</span>`).join('')}
    </div>` : ''}`;
}

function renderAgents() {
  $('agentList').innerHTML = view.nodes.map((n) => {
    const extras = [
      n.assumptions.length ? `<li><b>Assumptions:</b> ${n.assumptions.join('; ')}</li>` : '',
      n.unknowns.length ? `<li><b>Unknowns:</b> ${n.unknowns.join('; ')}</li>` : '',
      n.findings.length ? `<li><b>Findings:</b><ul>${n.findings.map((f) => `<li>${f}</li>`).join('')}</ul></li>` : '',
    ].filter(Boolean).join('');
    return `
    <div class="agent ${n.status.toLowerCase()}">
      <div class="agent-head">
        <span class="agent-state"></span>
        <span class="agent-name">${n.label}</span>
        <span class="agent-kind">${n.kind}</span>
      </div>
      ${n.headline ? `<div class="agent-headline">${n.headline}</div>` : `<div class="agent-headline muted">${n.role}</div>`}
      ${n.status === 'COMPLETED' ? `<div class="agent-sub">
        ${n.confidence != null ? `confidence ${n.confidence} · ` : ''}${n.evidenceIds.length} evidence${n.durationMs ? ` · ${n.durationMs}ms` : ''}
      </div>` : ''}
      ${extras ? `<details><summary>evidence, assumptions, uncertainty</summary><ul>
        ${n.evidenceIds.length ? `<li><b>Evidence:</b> ${n.evidenceIds.join(', ')}</li>` : ''}${extras}
      </ul></details>` : ''}
    </div>`;
  }).join('');
}

function renderEvidence() {
  $('evidenceCount').textContent = view.evidence.length;
  $('evidenceList').innerHTML = view.evidence.map((e) => {
    const cls = e.stale ? 'stale' : (e.conflictsWith.length ? 'conflict' : 'fresh');
    const flag = e.stale ? '<span class="ev-flag stale">STALE</span>'
      : (e.conflictsWith.length ? '<span class="ev-flag conflict">CONFLICT</span>' : '');
    return `<div class="ev ${cls}">
      <div><span class="ev-id">${e.evidenceId}</span>${flag}</div>
      <div>${e.summary}</div>
      <div class="ev-meta">${e.sourceSystem} · freshness ${e.freshnessSeconds}s · reliability ${e.reliability} · ${e.dataClassification}</div>
    </div>`;
  }).join('') || '<div class="muted">No evidence yet.</div>';
}

function renderScenarios() {
  const host = $('scenarioCards');
  if (!view.scenarios.length) {
    host.innerHTML = '<div class="empty">Run the analysis to generate recovery options.</div>';
    $('recommendNote').textContent = '';
    return;
  }
  $('recommendNote').textContent = view.recommendationReason;
  host.innerHTML = view.scenarios.map((s) => {
    const sel = s.scenarioId === view.selectedScenarioId;
    const rec = s.scenarioId === view.recommendedScenarioId;
    const pct = Math.round(s.impacts.estimatedThroughputDelta * 100);
    return `
    <div class="card ${sel ? 'selected' : ''}" data-scenario="${s.scenarioId}">
      <div class="card-head">
        <span class="card-title">${s.title}</span>
        ${rec ? '<span class="rec-flag">RECOMMENDED</span>' : ''}
      </div>
      <div class="card-sum">${s.summary}</div>
      <div class="card-metrics">
        <div class="metric"><div class="metric-l">tonnes</div><div class="metric-v">+${s.impacts.estimatedTonnesDelta.toLocaleString()}</div></div>
        <div class="metric"><div class="metric-l">recovery</div><div class="metric-v">${s.impacts.estimatedRecoveryMinutes}m</div></div>
        <div class="metric"><div class="metric-l">throughput</div><div class="metric-v">${pct}%</div></div>
      </div>
      <div class="card-foot">
        <span class="tag ${SEV_CLASS[s.safetyRiskLevel]}">safety ${s.safetyRiskLevel}</span>
        <span class="tag info">confidence ${s.confidence}</span>
        <span class="tag">approval: ${s.requiredApprovals.join(' + ')}</span>
      </div>
      <details>
        <summary>assumptions, constraints, evidence</summary>
        <ul>
          <li><b>Assumptions:</b> ${s.assumptions.join('; ')}</li>
          <li><b>Unknowns:</b> ${s.unknowns.join('; ')}</li>
          <li><b>Constraints:</b> ${s.constraints.join(', ')}</li>
          <li><b>Evidence:</b> ${s.evidenceIds.join(', ')}</li>
          <li><b>Actions requested:</b> ${s.requestedActionTypes.join(', ')}</li>
        </ul>
      </details>
    </div>`;
  }).join('');

  host.querySelectorAll('.card').forEach((el) => {
    el.addEventListener('click', (e) => {
      if (e.target.closest('details')) return;
      selectScenario(el.dataset.scenario);
    });
  });
}

function renderTimeline() {
  const items = view.events.map((e, i) => {
    const at = new Date(e.source.receivedAt).toISOString().slice(11, 16);
    return `<div class="tl-item">
      ${i ? '<span class="tl-line"></span>' : ''}
      <span class="tl-dot ${e.severity}" title="${e.title}"></span>
      <span class="tl-label">${at} ${e.title}</span>
    </div>`;
  });
  $('timeline').innerHTML = items.join('') || '<span class="muted" style="font-size:11px">No events injected. Shift running normally.</span>';
}

function renderButtons() {
  const hasEvents = view.events.length > 0;
  const analysed = view.scenarios.length > 0;
  const approval = view.approval;
  $('btnInject').disabled = view.events.length >= 5;
  $('btnInjectAll').disabled = view.events.length >= 5;
  $('btnAnalyse').disabled = !hasEvents || analysed;
  $('btnProhibited').disabled = !hasEvents;

  const btn = $('btnApprove');
  btn.disabled = !view.selectedScenarioId;
  if (view.outcome) { btn.textContent = 'Outcome verified'; btn.disabled = true; }
  else if (approval?.status === 'CONSUMED') { btn.textContent = 'Verify outcome'; btn.disabled = false; }
  else if (approval?.status === 'APPROVED') { btn.textContent = 'Execute simulated action'; btn.disabled = false; }
  else if (approval?.status === 'PENDING') { btn.textContent = `Approve as ${approval.requiredRoles[0]}`; btn.disabled = false; }
  else if (view.selectedScenarioId) { btn.textContent = 'Request approval'; }
  else { btn.textContent = 'Select a plan first'; }
}

// -------------------------------------------------------------------- actions

async function selectScenario(scenarioId) {
  await refresh(call(`/v1/scenarios/${scenarioId}/select`, { method: 'POST' }));
}

async function approveStep() {
  const a = view.approval;
  if (view.outcome) return;
  if (!a || a.status === 'SUPERSEDED' || a.status === 'REJECTED' || a.status === 'EXPIRED') {
    const ok = await refresh(call('/v1/approvals', { method: 'POST', body: { scenarioId: view.selectedScenarioId } }));
    if (ok) toast('APPROVAL REQUIRED', `Policy escalated this plan. ${ok.approval.requiredRoles.join(' + ')} must approve before any state change.`,
      { approvalId: ok.approval.approvalId, expiresAt: ok.approval.expiresAt, policyVersion: ok.policyVersion }, 'ok');
    return;
  }
  if (a.status === 'PENDING') {
    const ok = await refresh(call('/v1/approvals/decision', { method: 'POST', body: { approve: true, approverRole: a.requiredRoles[0] } }));
    if (ok) toast('APPROVED', `Scoped approval issued to ${ok.approval.approverRole}. Token bound to plan version ${ok.approval.scenarioVersion}.`,
      { approvalToken: `${ok.approval.approvalToken.slice(0, 18)}…`, evidenceHash: ok.approval.evidenceHash }, 'ok');
    return;
  }
  if (a.status === 'APPROVED') {
    const ok = await refresh(call('/v1/actions', { method: 'POST' }));
    if (ok) toast('SIMULATED ACTION', ok.actions.map((r) => `${r.actionType} → ${r.artefactRef}`).join(' · '),
      { idempotencyKeys: ok.actions.map((r) => r.idempotencyKey).join(', '), simulated: true }, 'ok');
    return;
  }
  if (a.status === 'CONSUMED') {
    const ok = await refresh(call('/v1/outcome/verify', { method: 'POST' }));
    if (ok) toast('OUTCOME VERIFIED', ok.outcome.headline, { unresolved: ok.outcome.unresolvedItems.join(' | ') }, 'ok');
  }
}

async function attemptProhibited() {
  try {
    await call('/v1/actions/prohibited', { method: 'POST', body: { actionType: 'OVERRIDE_SAFETY_INTERLOCK' } });
    toast('UNEXPECTED', 'A prohibited action was not denied. This is a defect.', null, 'deny');
  } catch (err) {
    toast('POLICY DENIED', err.message, { ...err.details, decidedBy: 'deterministic policy service (no model call)' }, 'deny');
  }
  view = await call('/v1/runs/current');
  render();
}

async function openAudit() {
  const audit = await call(`/v1/audit/${view.correlationId}`);
  $('auditMeta').textContent = `${audit.correlationId} · ${audit.policyVersion} · ${audit.promptVersion} · ${audit.modelId}`;
  $('auditBody').innerHTML = audit.entries.map((e) => `
    <div class="audit-row">
      <div class="audit-seq">${String(e.seq).padStart(2, '0')}</div>
      <div>
        <div class="audit-stage">${e.stage}</div>
        <div class="audit-summary">${e.summary}</div>
        <div class="audit-actor">actor: ${e.actor} · ${new Date(e.at).toISOString().slice(11, 19)}Z</div>
        ${Object.keys(e.refs).length ? `<div class="audit-refs">${Object.entries(e.refs).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(' · ')}</div>` : ''}
      </div>
    </div>`).join('');
  $('auditDrawer').hidden = false;
}

function toast(title, message, detail, kind) {
  const el = $('toast');
  el.className = `toast ${kind ?? ''}`;
  el.innerHTML = `<div class="toast-title">${title}</div><div>${message}</div>
    ${detail ? `<div class="toast-detail">${Object.entries(detail).map(([k, v]) => `${k}: ${v}`).join(' · ')}</div>` : ''}`;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 9000);
}

// ----------------------------------------------------------------------- wiring

$('btnInject').onclick = () => refresh(call('/v1/events/next', { method: 'POST' }));
$('btnInjectAll').onclick = () => refresh(call('/v1/events', { method: 'POST' }));
$('btnAnalyse').onclick = () => refresh(call('/v1/runs/current/analyse', { method: 'POST' }));
$('btnApprove').onclick = approveStep;
$('btnProhibited').onclick = attemptProhibited;
$('btnAudit').onclick = openAudit;
$('btnCloseAudit').onclick = () => { $('auditDrawer').hidden = true; };
$('btnReset').onclick = async () => {
  $('auditDrawer').hidden = true;
  $('toast').hidden = true;
  await refresh(call('/v1/runs/current/reset', { method: 'POST' }));
};
$('toggleRender').onclick = switchRenderer;

bootScene();
view = await call('/v1/runs/current');
render();
