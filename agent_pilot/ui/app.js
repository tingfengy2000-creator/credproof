/* Same-origin presentation only. No candidate execution, verdict generation or local fixtures. */
const API = '/api/agent';
const $ = id => document.getElementById(id);
const state = { bootstrap: null, caseId: '', run: null, view: 'source', busy: false,
  error: '', stale: false, replay: false, epoch: 0, timer: null };
const activeStatuses = new Set(['QUEUED', 'RUNNING']);
const statusNames = { QUEUED: '等待执行', RUNNING: '执行中', COMPLETED: '任务结束',
  STOPPED: '已停止', ERROR: '执行异常' };
const verdictNames = { PASS: '通过', FAIL: '未通过', UNKNOWN: '未知' };
const taskNames = { COMPLETED_REPAIRED: '修复任务完成', COMPLETED_UNCHANGED: '保留原代码完成',
  INCOMPLETE: '任务未完成', UNKNOWN: '任务结果未知', FAILED: '任务失败' };
const confirmationNames = { CONFIRMED_LEAK: '确认存在泄露', NO_LEAK_OBSERVED: '未观察到泄露', UNKNOWN: '未知' };
const checkNames = { security: '安全检查', safety: '安全检查', function: '功能检查',
  functionality: '功能检查', boundary: '边界检查', source: '源代码约束',
  syntax: '语法检查', coverage: '执行覆盖', isolation: '隔离执行',
  credential_leak: '凭据泄露检查', allowed_changes: '允许修改范围' };
const escape = value => String(value ?? '').replace(/[&<>"']/g, char =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const text = value => typeof value === 'string' ? value : value == null ? '' : JSON.stringify(value, null, 2);
const array = value => Array.isArray(value) ? value : [];
const displayTime = value => {
  if (!value) return '未提供时间';
  const parsed = new Date(value);
  return Number.isNaN(parsed.valueOf()) ? text(value) : parsed.toLocaleString('zh-CN', { hour12: false });
};
const count = value => Number.isInteger(value) && value >= 0 ? String(value) : '—';
const tone = verdict => ({ PASS: 'pass', FAIL: 'fail', UNKNOWN: 'unknown' }[verdict] || 'neutral');
const badge = (label, style = 'neutral') => `<span class="badge ${style}">${escape(label)}</span>`;
const selectedCase = () => array(state.bootstrap?.cases).find(item => item.id === state.caseId);
const isRunning = () => !!state.run && activeStatuses.has(state.run.status) && !state.replay;
const runPath = id => `${API}/runs/${encodeURIComponent(id)}`;
const announce = message => { $('announcement').textContent = message; };

async function responseChecked(response) {
  if (response.ok) return response;
  let explanation = '';
  try {
    const payload = await response.json();
    explanation = text(payload.detail?.message ?? payload.detail ?? payload.message ?? payload.error ?? '');
  } catch { /* Keep the HTTP status; never treat a non-JSON error as success. */ }
  throw new Error(`请求失败（HTTP ${response.status}）${explanation ? `：${explanation}` : ''}`);
}

async function request(path, body) {
  const controller = new AbortController();
  // A timeout ends this request only, not the task already accepted by the server.
  const timeout = window.setTimeout(() => controller.abort(), 90000);
  try {
    const response = await responseChecked(await fetch(path, { method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin',
      cache: 'no-store', signal: controller.signal }));
    return await response.json();
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('本次请求超时。服务端任务可能仍在执行，请刷新状态；不要重复发起任务。');
    throw error;
  } finally { window.clearTimeout(timeout); }
}

function validateBootstrap(value) {
  if (!value || !Array.isArray(value.cases) || !value.runtime || typeof value.runtime.ready !== 'boolean'
      || value.cases.some(item => !item || typeof item.id !== 'string' || typeof item.source_code !== 'string')) {
    throw new Error('案例或运行设施响应不符合接口契约，已停止展示新的结果。');
  }
  return value;
}

function validateRun(value) {
  if (!value || typeof value.id !== 'string' || typeof value.case_id !== 'string'
      || !Object.hasOwn(statusNames, value.status) || typeof value.source_code !== 'string'
      || !['LIVE', 'REPLAY'].includes(value.mode)) {
    throw new Error('任务响应不符合接口契约，已停止展示新的结果。');
  }
  if (value.validation && !Object.hasOwn(verdictNames, value.validation.verdict)) {
    throw new Error('验收判决缺失或无法识别，不能显示通过。');
  }
  return value;
}

function failure(error) {
  state.error = error instanceof Error ? error.message : text(error);
  state.stale = Boolean(state.run);
  clearPoll();
  announce('请求失败，保留的记录不能当作最新状态。');
}

function renderConnection() {
  const connected = !!state.bootstrap && !state.error;
  $('connection').className = `connection ${state.error ? 'error' : connected ? 'online' : ''}`;
  $('connection').innerHTML = `<i></i>${escape(state.error ? '连接或请求异常' : connected ? '本机服务已连接' : '正在连接本机服务')}`;
  $('error-banner').hidden = !state.error;
  $('error-banner').textContent = state.error
    ? `${state.error}${state.stale ? ' 下方是上次取得的记录，尚未确认当前状态。' : ''}` : '';
  document.body.classList.toggle('is-busy', state.busy || isRunning());
  document.body.classList.toggle('is-stale', state.stale);
}

function renderScope() {
  const cases = array(state.bootstrap?.cases);
  const options = cases.length ? cases.map(item => `<option value="${escape(item.id)}">${escape(item.title || item.id)}</option>`).join('')
    : `<option value="">${state.bootstrap ? '服务端未提供案例' : '等待连接本机服务'}</option>`;
  $('case-select').innerHTML = options;
  $('case-select').value = state.caseId;
  $('case-select').disabled = !cases.length || state.busy || isRunning();
  const item = selectedCase();
  $('case-description').textContent = item?.description || '只显示服务端允许选择的任务，页面不会生成测试输入或安全判决。';
  const rules = array(item?.rules);
  $('rule-list').innerHTML = rules.length ? rules.map(rule => `<li>${escape(text(rule))}</li>`).join('')
    : '<li class="placeholder-line">服务端尚未提供本任务规则。</li>';
  $('model-label').textContent = state.bootstrap?.runtime.model_label || '尚未取得运行信息';
  const ready = state.bootstrap?.runtime.ready;
  $('runtime-status').textContent = state.error ? '状态未确认' : ready === true ? '设施已就绪' : ready === false ? '尚未就绪' : '待检查';
  $('runtime-status').className = `badge ${!state.error && ready === true ? 'pass' : 'neutral'}`;
  const reasons = array(state.bootstrap?.runtime.reasons);
  $('runtime-reason').textContent = reasons.length ? reasons.map(text).join('；')
    : state.bootstrap?.runtime.ready === true ? '服务端报告运行设施就绪。任务仍须经过实际执行和验收。' : '运行设施尚未就绪，不能发起任务。';
  const histories = array(state.bootstrap?.history);
  const previous = $('history-select').value;
  $('history-select').innerHTML = histories.length
    ? '<option value="">选择一份历史运行…</option>' + histories.map(item => `<option value="${escape(item.id)}">${escape(item.label || `${item.case_id} · ${displayTime(item.created_at)}`)}</option>`).join('')
    : '<option value="">尚无可读取的记录</option>';
  if (histories.some(item => item.id === previous)) $('history-select').value = previous;
  $('history-select').disabled = !histories.length || state.busy || isRunning();
  $('load-history').disabled = !$('history-select').value || state.busy || isRunning();
}

function renderActions() {
  const run = state.run;
  const status = run?.status;
  $('mode-label').textContent = state.replay ? 'REPLAY · 历史回放' : run?.mode === 'LIVE' ? 'LIVE · 本次任务' : '尚未执行';
  $('mode-label').className = `mode-label ${state.replay ? 'replay' : run?.mode === 'LIVE' ? 'live' : ''}`;
  const finishedLabel = !activeStatuses.has(status) && taskNames[run?.task_status]
    ? taskNames[run.task_status] : statusNames[status];
  const caption = !run ? selectedCase() ? '已选择案例，尚未执行' : '等待选择'
    : state.replay ? `回放 · ${finishedLabel}` : finishedLabel;
  $('run-status').className = `badge ${status === 'RUNNING' || status === 'QUEUED' ? 'running' : status === 'ERROR' || status === 'STOPPED' ? 'unknown' : 'neutral'}`;
  $('run-status').textContent = caption;
  $('run-description').textContent = state.busy ? '正在向本机服务发送请求…'
    : run ? text(run.phase || run.stop_reason || '按实际返回的任务状态显示') : '模型先读取受限代码，再提出可检验的假设。';
  $('start').disabled = state.busy || isRunning() || !selectedCase() || state.bootstrap?.runtime.ready !== true || !!state.error || state.replay;
  $('start').querySelector('span').textContent = isRunning() ? '任务执行中' : '开始分析与修复';
  $('refresh').disabled = state.busy;
  const changed = ['CHANGED', 'UNAVAILABLE'].includes(run?.material_binding?.status);
  $('recheck').disabled = state.busy || isRunning() || !run || !run.validation || state.stale || changed;
  $('export').disabled = state.busy || isRunning() || !run || state.stale || changed;
  $('material-warning').hidden = !changed;
  $('material-warning').textContent = changed ? '材料已变化或不可读取：历史结果不适用于当前对象。请返回新任务重新验收；旧包仍对应旧对象。' : '';
  $('leave-replay').disabled = state.busy;
  $('replay-banner').hidden = !state.replay;
  $('replay-description').textContent = run
    ? `${run.id} · 回放记录时间 ${displayTime(run.started_at)}。这是已保存记录，不是本次实时执行。`
    : '这里展示已保存的运行记录，不是本次实时执行。';
}

function renderDecisions() {
  const run = state.run;
  const diagnosis = run?.diagnosis;
  const modelText = diagnosis?.model_suspicion ?? run?.model?.diagnosis;
  const leaking = diagnosis?.initially_leaking ?? run?.model?.initially_leaking;
  $('model-summary').textContent = leaking === true ? '模型提出了初始泄露疑点' : leaking === false
    ? '模型判断未观察到初始泄露' : modelText ? '模型已给出诊断意见' : '尚无模型判断';
  $('diagnosis').textContent = modelText == null || modelText === '' ? '尚未取得模型的最终诊断。'
    : typeof modelText === 'boolean' ? `模型${modelText ? '怀疑存在' : '未提出'}初始泄露；这不是程序判决。` : text(modelText);
  $('model-status').textContent = run?.model?.status || (modelText != null ? '已返回诊断' : '未分析');
  const rawNotes = array(run?.model?.raw_notes), proposals = array(run?.model?.proposals);
  $('model-raw').hidden = !rawNotes.length && !proposals.length;
  const deniedCount = run?.model?.denied_proposal_count;
  $('proposal-count').textContent = Number.isInteger(deniedCount) ? `拒绝 ${deniedCount} 项` : '';
  $('model-raw-content').innerHTML = rawNotes.map(note => `<div class="raw-note"><span class="small-label">原始模型文字 · ${escape(note.source || '已保存响应')}</span><pre>${escape(text(note.text))}${note.display_truncated ? '\n[当前展示已截短，原文保留在本地记录]' : ''}</pre></div>`).join('')
    + proposals.map(proposal => `<div class="raw-note"><span class="small-label">提案理由 · ${escape(proposal.status === 'REJECTED' ? '程序已拒绝' : proposal.status || '未提供提案状态')}</span><pre>${escape(text(proposal.rationale))}</pre>${proposal.reason ? `<p>${escape(text(proposal.reason))}</p>` : ''}</div>`).join('');
  const validation = run?.validation;
  const verdict = validation?.verdict;
  $('verdict').className = `badge ${tone(verdict)}`;
  $('verdict').textContent = verdict ? `${verdictNames[verdict]} · ${verdict}` : '未验收';
  $('program-panel').dataset.verdict = verdict || '';
  $('verdict-description').textContent = ({ PASS: '受限验收通过', FAIL: '受限验收未通过', UNKNOWN: '现有证据不足以判定' }[verdict]) || '等待真实检查结果';
  $('verdict-reasons').textContent = array(validation?.reasons).map(text).join('；')
    || (validation ? '服务端未附加判决原因；查看下方实际检查。' : '缺少证据时，页面不会显示通过。');
  $('checked-at').textContent = validation ? `验收记录时间 · ${displayTime(validation.checked_at ?? validation.checked_at_utc ?? run.updated_at)}` : '尚未取得验收时间';
  const confirmations = [];
  if (diagnosis && Object.hasOwn(diagnosis, 'confirmed')) confirmations.push(['原始风险确认', diagnosis.confirmed]);
  if (diagnosis && Object.hasOwn(diagnosis, 'repair_authorized')) confirmations.push(['修复授权', diagnosis.repair_authorized]);
  $('diagnosis-confirmation').hidden = !confirmations.length;
  $('diagnosis-confirmation').innerHTML = confirmations.map(([label, value]) => `<span>${label}<strong>${escape(value === true ? '是' : value === false ? '否' : value == null ? '未知' : confirmationNames[value] || text(value))}</strong></span>`).join('');
}

function renderCode() {
  const run = state.run;
  let source, placeholder;
  if (state.view === 'source') {
    source = run?.source_code ?? selectedCase()?.source_code;
    placeholder = '等待加载已审查代码';
  } else if (state.view === 'candidate') {
    source = run?.candidate_code;
    placeholder = '尚无候选代码；模型未提交时不生成示例补丁。';
  } else {
    source = run?.diff;
    placeholder = '尚无服务端生成的候选差异。';
  }
  const identities = { source: run?.source_sha256 ?? selectedCase()?.source_sha256,
    candidate: run?.candidate_sha256, diff: run?.candidate_sha256 };
  $('code-identity').textContent = identities[state.view] ? `sha256 ${identities[state.view]}` : 'identity 未提供';
  $('code-identity').title = identities[state.view] || '';
  $('code-kind').textContent = { source: '原始受限文件', candidate: '当前候选副本', diff: '服务端实际差异' }[state.view];
  document.querySelectorAll('[data-code-view]').forEach(button => {
    const selected = button.dataset.codeView === state.view;
    button.setAttribute('aria-selected', String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  $('code-content').setAttribute('aria-labelledby', `tab-${state.view}`);
  if (typeof source !== 'string' || !source) {
    const emptyDiff = state.view === 'diff' && run && source === '';
    $('code-content').innerHTML = `<div class="empty-state"><svg class="icon"><use href="#i-code"/></svg><span>${escape(emptyDiff ? '服务端返回空差异：没有记录到代码变化。' : placeholder)}</span></div>`;
    return;
  }
  $('code-content').innerHTML = '<pre>' + source.split('\n').map((line, index) => {
    const kind = state.view !== 'diff' ? '' : line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++')
      ? 'diff-label' : line.startsWith('+') ? 'addition' : line.startsWith('-') ? 'deletion' : '';
    return `<span class="code-line ${kind}"><span class="line-no" aria-hidden="true">${index + 1}</span><span class="line-code">${escape(line) || ' '}</span></span>`;
  }).join('') + '</pre>';
}

function renderEvidence() {
  const entries = array(state.run?.evidence);
  $('evidence-count').textContent = `${entries.length} 条已取得`;
  // Preserve explicit reader expansion across polling, instead of reopening all entries.
  const expanded = new Set([...document.querySelectorAll('.evidence-item[open]')].map(item => item.dataset.evidenceId));
  $('evidence-list').innerHTML = entries.length ? entries.map((entry, index) => {
    const verdict = entry.verdict ?? entry.observation?.verdict;
    const identifier = typeof entry.id === 'string' ? entry.id : `record-${index + 1}`;
    const hypothesis = entry.hypothesis || '该执行记录未附带模型假设';
    const observation = entry.observation;
    return `<details class="evidence-item" data-evidence-id="${escape(identifier)}" ${expanded.has(identifier) ? 'open' : ''}><summary><div><h3>${escape(identifier)}</h3><small>${escape(entry.tool || '隔离执行观察')}${entry.collected_at ? ` · ${escape(displayTime(entry.collected_at))}` : ''}</small></div>${badge(verdictNames[verdict] ? `${verdictNames[verdict]} · ${verdict}` : '未附判决', tone(verdict))}</summary><div class="evidence-body"><span class="small-label">执行前的假设</span><p>${escape(text(hypothesis))}</p><span class="small-label">程序返回的脱敏观察</span><pre>${escape(observation == null ? '没有取得观察内容' : text(observation))}</pre>${entry.source_sha256 ? `<span class="small-label">关联代码 · <code>${escape(entry.source_sha256)}</code></span>` : ''}</div></details>`;
  }).join('') : '<div class="empty-state compact-empty"><svg class="icon"><use href="#i-clock"/></svg><span>工具执行后，脱敏证据会出现在这里。</span><small>没有执行记录，就没有证据条目。</small></div>';
}

function checksMarkup(checks) {
  const entries = Array.isArray(checks) ? checks : checks && typeof checks === 'object'
    ? Object.entries(checks).map(([id, value]) => ({ id, ...value })) : [];
  if (!entries.length) return '<div class="empty-state compact-empty"><span>尚未取得逐项检查</span><small>不会从整体判决反推每项检查都已执行。</small></div>';
  return entries.map(check => {
    const verdict = check.status ?? check.verdict;
    return `<div class="check-row"><div><strong>${escape(check.label || checkNames[check.id] || check.id || '未命名检查')}</strong><p>${escape(text(check.reason ?? check.reasons ?? '服务端未附加说明'))}</p></div>${badge(verdictNames[verdict] ? `${verdictNames[verdict]} · ${verdict}` : '未提供状态', tone(verdict))}</div>`;
  }).join('');
}

function renderValidation() {
  const run = state.run;
  $('check-list').innerHTML = checksMarkup(run?.validation?.checks);
  const limitations = [...array(run?.limitations), ...array(run?.remaining_uncertainty)].map(text);
  $('validation-scope').textContent = limitations.length ? limitations.join('\n') : '验收与模型文字回答分开；缺失、不完整或执行异常均不能推断为通过。';
  const recheck = run?.recheck;
  $('recheck-result').hidden = !recheck;
  if (recheck) {
    const validation = recheck.validation ?? recheck;
    const prior = recheck.prior_report_applicable === true ? '服务端确认先前报告适用于当前材料'
      : recheck.prior_report_applicable === false ? '先前报告不适用于当前材料' : '先前报告适用性未知';
    $('recheck-result').innerHTML = `<div class="recheck-heading"><div><span class="eyebrow">FRESH RECHECK</span><h3>独立复检记录</h3></div>${badge(verdictNames[validation.verdict] ? `${verdictNames[validation.verdict]} · ${validation.verdict}` : recheck.status || '尚无复检判决', tone(validation.verdict))}</div><p>${escape(displayTime(recheck.checked_at ?? validation.checked_at ?? validation.checked_at_utc))} · 固定程序重新验收，不调用模型。</p><p>${escape(prior)}。适用性不替代新验收判决。</p>${recheck.candidate_sha256 ? `<p class="recheck-identity">candidate sha256 ${escape(recheck.candidate_sha256)}</p>` : ''}<p>${escape(array(validation.reasons).map(text).join('；') || '')}</p><details class="technical-details"><summary>查看逐项复检依据（${array(validation.checks).length} 条记录）</summary><div>${checksMarkup(validation.checks)}</div></details>`;
  }
  if (recheck) {
    const integrity = recheck.historical_evidence_integrity;
    $('recheck-result').innerHTML += `<div class="recheck-integrity"><strong>历史材料完整性：${escape(integrity?.status || 'UNKNOWN')}</strong><br>缺失：${escape(array(integrity?.missing_files).join('、') || '无已报告缺失')}<br>变化：${escape(array(integrity?.changed_files).join('、') || '无已报告变化')}<br>旧报告适用性、历史证据完整性与本次复检判决分别显示。</div>`;
  }
  const modelCalls = run?.model?.calls;
  const toolCalls = run?.tool_calls;
  $('task-state').textContent = run ? text(taskNames[run.task_status] || run.task_status || '任务结果未知') : '未启动';
  $('model-calls').textContent = count(modelCalls);
  $('tool-calls').textContent = count(Array.isArray(toolCalls) ? toolCalls.length : toolCalls);
  $('unknown-count').textContent = count(run?.unknown_count);
  $('task-identity').textContent = run ? `任务 ${run.id}${run.stop_reason ? ` · ${text(run.stop_reason)}` : ''}` : '未创建任务';
  $('updated-at').textContent = run ? `最近取得的状态 · ${displayTime(run.updated_at)}` : '状态按请求刷新，不是实时监控。';
}

function renderStories() {
  const demos = array(state.bootstrap?.demonstrations);
  const lenses = { h01: ['i-code', '结构覆盖 · 跨函数传递'], h03: ['i-shield', '反馈调整 · 两份候选'], h07: ['i-check', '正常验证 · 保持原代码'] };
  $('demo-cards').innerHTML = demos.map((item, i) => {
    const [icon, lens] = lenses[item.case_id] || ['i-code', '实际记录 · 独立证据'];
    return `<button class="demo-card ${state.run?.id === item.run_id ? 'selected' : ''}" data-demo="${escape(item.run_id)}" aria-pressed="${state.run?.id === item.run_id}" ${state.busy || isRunning() ? 'disabled' : ''}><span class="demo-card-head"><span class="demo-symbol"><svg class="icon"><use href="#${icon}"/></svg></span><span class="demo-number">0${i + 1} / ${escape(item.case_id.toUpperCase())} · REPLAY</span></span><span class="demo-lens">${escape(lens)}</span><strong>${escape(item.title)}</strong><span class="demo-subtitle">${escape(item.subtitle)}</span><span class="demo-card-foot"><small>查看真实历史回放</small><svg class="icon"><use href="#i-arrow"/></svg></span></button>`;
  }).join('') || '<div class="gallery-empty">尚未加载精选历史记录。可在服务端启用演示记录，或使用下方工作区选择已审查案例。</div>';
  const story = state.run?.presentation;
  $('story-panel').hidden = !story;
  if (!story) return;
  const stages = array(story.stages);
  $('story-panel').innerHTML = `<div class="story-intro"><div><span class="eyebrow">${escape(story.case_id.toUpperCase())} / RECORDED REPLAY</span><h2>${escape(story.title)}</h2><p>${escape(story.phenomenon)}</p></div><div class="story-conclusion"><span class="small-label">这份实际记录说明什么</span><p>${escape(story.explanation)}</p></div></div><div class="stage-list">${stages.map((stage, index) => {
    const verdict = stage.validation?.verdict;
    const counts = Object.entries(stage.validation?.trial_counts || {}).map(([name, value]) => `${verdictNames[name] || name} ${value}`).join(' · ');
    return `<details class="stage ${tone(verdict)}-stage"><summary><span class="stage-order">0${index + 1}</span><span class="stage-heading"><strong>候选 ${index + 1}</strong><small>${escape(stage.candidate_id)}</small></span>${badge(`${verdictNames[verdict] || '未知'} · ${verdict || 'UNKNOWN'}`, tone(verdict))}<span class="stage-count">${escape(counts)}</span><span class="stage-expand">展开实际补丁差异 ＋</span></summary><p>${escape(array(stage.validation?.reasons).join('；'))} ${escape(array(stage.validation?.leak_channels).join('、'))}</p><pre>${escape(stage.diff)}</pre></details>`;
  }).join('') || '<p class="story-preserved">这份记录未提交补丁，验证后保留原代码。</p>'}</div><div class="story-foot"><span>同批固定流程（A-fixed）：${escape(story.fixed_comparison?.verdict || 'UNKNOWN')} · ${escape(taskNames[story.fixed_comparison?.task_status] || story.fixed_comparison?.task_status || '任务状态未知')}</span><span>历史验证结果，与本次复检分别保留</span></div><details class="story-provenance"><summary>查看历史来源与版本</summary><p>批次 ${escape(story.batch)} · 版本 ${escape(story.source_commit || '未提供')}<br>${escape(story.provenance || '')}</p></details>`;
}

function render() { renderConnection(); renderScope(); renderActions(); renderDecisions(); renderCode(); renderEvidence(); renderValidation(); renderStories(); }
function clearPoll() { if (state.timer) window.clearTimeout(state.timer); state.timer = null; }
function schedulePoll() {
  clearPoll();
  if (!isRunning() || state.error) return;
  const epoch = state.epoch;
  state.timer = window.setTimeout(async () => {
    try {
      const value = validateRun(await request(runPath(state.run.id)));
      if (epoch !== state.epoch) return;
      state.run = value;
      state.replay = value.mode === 'REPLAY';
      state.stale = false;
      render();
      if (!isRunning()) announce(`任务状态：${statusNames[value.status]}。`);
      schedulePoll();
    } catch (error) { if (epoch === state.epoch) { failure(error); render(); } }
  }, 2000);
}

async function loadBootstrap() {
  const data = validateBootstrap(await request(`${API}/bootstrap`));
  state.bootstrap = data;
  if (!data.cases.some(item => item.id === state.caseId)) state.caseId = data.cases[0]?.id || '';
}

async function busyAction(action) {
  if (state.busy) return;
  state.busy = true;
  state.error = '';
  render();
  try { await action(); state.stale = false; }
  catch (error) { failure(error); }
  finally { state.busy = false; render(); schedulePoll(); }
}

function acceptRun(value, replay = false) {
  const run = validateRun(value);
  state.run = run;
  state.caseId = run.case_id;
  state.replay = replay || run.mode === 'REPLAY';
  state.stale = false;
  state.epoch += 1;
}

$('start').addEventListener('click', () => busyAction(async () => {
  clearPoll();
  acceptRun(await request(`${API}/runs`, { case_id: state.caseId }));
  announce('任务已由服务端接收，正在取得真实状态。');
}));
$('refresh').addEventListener('click', () => busyAction(async () => {
  await loadBootstrap();
  if (state.run) acceptRun(await request(runPath(state.run.id)), state.replay);
}));
$('demo-cards').addEventListener('click', event => {
  const button = event.target.closest('[data-demo]');
  if (!button || button.disabled) return;
  busyAction(async () => { clearPoll(); acceptRun(await request(runPath(button.dataset.demo)), true); state.view = 'diff'; announce('精选真实历史回放，不是现场模型推理。'); }).then(() => {
    if (state.run && !state.error) $('workbench').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  });
});
$('case-select').addEventListener('change', event => {
  if (state.busy || isRunning()) return;
  clearPoll(); state.caseId = event.target.value; state.run = null; state.replay = false;
  state.error = ''; state.stale = false; state.view = 'source'; state.epoch += 1; render();
});
$('history-select').addEventListener('change', () => { $('load-history').disabled = !$('history-select').value || state.busy || isRunning(); });
$('load-history').addEventListener('click', () => {
  const id = $('history-select').value;
  if (!id) return;
  busyAction(async () => { clearPoll(); acceptRun(await request(runPath(id)), true); announce('已打开历史回放，并非本次实时执行。'); });
});
$('leave-replay').addEventListener('click', () => {
  clearPoll(); state.run = null; state.replay = false; state.stale = false; state.error = '';
  state.view = 'source'; state.epoch += 1; render();
});
$('recheck').addEventListener('click', () => busyAction(async () => {
  const replay = state.replay;
  const value = await request(`${runPath(state.run.id)}/recheck`, {});
  acceptRun(value, replay);
  announce('服务端已返回独立复检记录；首次验收结果保持独立显示。');
}));
$('export').addEventListener('click', () => busyAction(async () => {
  const response = await responseChecked(await fetch(`${runPath(state.run.id)}/export`, { cache: 'no-store', credentials: 'same-origin' }));
  const blob = await response.blob();
  const contentType = response.headers.get('content-type') || '';
  const disposition = response.headers.get('content-disposition') || '';
  const providedName = disposition.match(/filename="?([a-zA-Z0-9._-]+)"?/i)?.[1];
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = providedName || `credproof-${state.run.id}.${contentType.includes('zip') ? 'zip' : 'json'}`;
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  announce('已下载服务端导出的实际证据包。');
}));
document.querySelectorAll('[data-code-view]').forEach(button => {
  button.addEventListener('click', () => { state.view = button.dataset.codeView; renderCode(); });
  button.addEventListener('keydown', event => {
    const tabs = [...document.querySelectorAll('[data-code-view]')];
    let index = tabs.indexOf(button);
    if (event.key === 'ArrowRight') index = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') index = (index + tabs.length - 1) % tabs.length;
    else if (event.key === 'Home') index = 0;
    else if (event.key === 'End') index = tabs.length - 1;
    else return;
    event.preventDefault(); tabs[index].click(); tabs[index].focus();
  });
});
window.addEventListener('pagehide', clearPoll);
render();
busyAction(loadBootstrap);
