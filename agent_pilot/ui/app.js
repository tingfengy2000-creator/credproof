/* Same-origin presentation only. No candidate execution, verdict generation or local fixtures.
   Every verdict shown here comes from the local service; missing data is shown as missing. */
const API = '/api/agent';
const $ = id => document.getElementById(id);
const state = { bootstrap: null, projectModes: null, caseId: '', run: null, view: 'source', busy: false,
  error: '', stale: false, replay: false, epoch: 0, timer: null, demoRuns: {}, project: null, review: null,
  bench: null, benchError: '', patchCache: {}, route: { name: 'overview', arg: '', query: new URLSearchParams() },
  reviewTab: 'diff', reviewAutoLoaded: false };
const activeStatuses = new Set(['QUEUED', 'RUNNING']);
const statusNames = { QUEUED: '等待执行', RUNNING: '执行中', COMPLETED: '任务结束',
  STOPPED: '已停止', ERROR: '执行异常' };
const verdictNames = { PASS: '通过', FAIL: '未通过', UNKNOWN: '未知' };
const sealNames = { PASS: '通过', FAIL: '不通过', UNKNOWN: '证据不足' };
const taskNames = { COMPLETED_REPAIRED: '修复任务完成', COMPLETED_UNCHANGED: '保留原代码完成',
  INCOMPLETE: '任务未完成', UNKNOWN: '任务结果未知', FAILED: '任务失败' };
const confirmationNames = { CONFIRMED_LEAK: '确认存在凭据泄露', CONFIRMED_VIOLATION: '确认存在边界违规', NO_LEAK_OBSERVED: '未观察到凭据泄露', UNKNOWN: '未知' };
const checkNames = { security: '安全检查', safety: '安全检查', function: '功能检查',
  functionality: '功能检查', boundary: '边界检查', source: '源代码约束',
  syntax: '语法检查', coverage: '执行覆盖', isolation: '隔离执行',
  credential_leak: '凭据泄露检查', allowed_changes: '允许修改范围' };
const conditionGroups = [
  ['业务保持', [['pytest', '业务测试进程正常结束'], ['required_pytest_tests', '必要业务测试全部执行并通过'],
    ['entry_completed', '入口正常完成'], ['required_entry_scenarios', '每个声明的场景得到预期结果']]],
  ['不泄密', [['no_credential_output', '返回值、输出、日志和异常中没有凭据']]],
  ['不乱读', [['required_allowed_file_read', '实际读取了允许的资料文件', true], ['no_forbidden_file_read', '没有读取禁止目录'],
    ['no_out_of_scope_file_read', '没有读取范围外的文件']]],
  ['不乱连', [['allowed_service_receipt', '允许的服务收到了请求', true], ['required_service_credential', '带凭据完成了认证', true],
    ['allowed_service_path', '访问路径在允许前缀内'], ['no_forbidden_service_receipt', '禁止的服务没有收到请求'],
    ['no_unauthorized_connection', '没有未授权的连接']]],
  ['隔离', [['isolation_receipt', '业务测试在隔离环境中执行']]],
];
const channelNames = { stdout: '标准输出', stderr: '错误输出', logs: '日志', return: '返回值', exception: '异常信息' };
const projectNames = { material_assistant: '资料助手', 'python-dotenv': 'python-dotenv' };
const unknownReasons = { required_tests_not_executed: '必要的业务测试没有全部执行', required_tests_all_skipped: '必要的业务测试全部被跳过',
  sandbox_execution_incomplete: '隔离环境没有完成执行', pytest_observation_incomplete: '业务测试的观测不完整' };
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
const seal = (verdict, size = '') => `<span class="seal ${size} is-${tone(verdict) === 'neutral' ? 'neutral' : tone(verdict)}">${escape(sealNames[verdict] || '未验收')}</span>`;
const selectedCase = () => array(state.bootstrap?.cases).find(item => item.id === state.caseId);
const isRunning = () => !!state.run && activeStatuses.has(state.run.status) && !state.replay;
const runPath = id => `${API}/runs/${encodeURIComponent(id)}`;
const announce = message => { $('announcement').textContent = message; };
const readOnly = () => state.bootstrap?.frontend_handoff?.read_only === true;
const noExecution = () => readOnly() || state.bootstrap?.access_mode === 'view';
const short = value => typeof value === 'string' ? value.slice(0, 12) : '—';
const modelName = name => {
  const value = String(name || '');
  const match = value.match(/^(qwen[\d.]*)-coder:(\d+)b/i);
  return match ? `${match[1].replace(/^qwen/i, 'Qwen')}-Coder ${match[2]}B` : value || '未知模型';
};

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
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json', ...(path.startsWith('/api/review/') ? { 'X-CredProof-Review-Session': state.bootstrap.review_session } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin',
      cache: 'no-store', signal: controller.signal }));
    return await response.json();
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('本次请求超时。服务端任务可能仍在执行，请刷新状态，不要重复发起任务。');
    throw error;
  } finally { window.clearTimeout(timeout); }
}

function validateBootstrap(value) {
  if (!value || !Array.isArray(value.cases) || !value.runtime || typeof value.runtime.ready !== 'boolean'
      || value.cases.some(item => !item || typeof item.id !== 'string' || typeof item.source_code !== 'string')) {
    throw new Error('案例或运行设施响应不符合接口约定，已停止展示新的结果。');
  }
  return value;
}

function validateRun(value) {
  if (!value || typeof value.id !== 'string' || typeof value.case_id !== 'string'
      || !Object.hasOwn(statusNames, value.status) || typeof value.source_code !== 'string'
      || !['LIVE', 'REPLAY'].includes(value.mode)) {
    throw new Error('任务响应不符合接口约定，已停止展示新的结果。');
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

/* ---------- Routing ---------- */
const routes = { overview: '验收概览', patches: '补丁记录', patch: '补丁详情', report: '验收报告', pipeline: '流水线闸门',
  'human-review': '人工审阅', workbench: '案例回放', 'project-entry': '接入项目', method: '工作原理' };
const aliases = { cases: 'workbench', projects: 'project-entry', top: 'overview', mechanism: 'method', ci: 'pipeline', main: null };
const navOf = { patch: 'patches', report: 'patches' };

function parseRoute() {
  let raw = location.hash.slice(1);
  try { raw = decodeURIComponent(raw); } catch { /* keep raw */ }
  const [path, query] = raw.split('?');
  const [first, ...rest] = path.split('/');
  let name = Object.hasOwn(aliases, first) ? aliases[first] : first;
  if (!name || !routes[name]) name = 'overview';
  return { name, arg: rest.join('/'), query: new URLSearchParams(query || '') };
}

function applyRoute() {
  if (location.hash === '#main') return;
  state.route = parseRoute();
  const name = state.route.name;
  document.querySelectorAll('.view').forEach(view => { view.hidden = view.dataset.view !== name; });
  document.querySelectorAll('[data-nav]').forEach(link => {
    if (link.dataset.nav === (navOf[name] || name)) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  });
  $('page-title').textContent = routes[name];
  document.title = `${routes[name]} · 密证 CredProof`;
  if (name === 'patches') {
    const origin = state.route.query.get('origin');
    if (origin && [...$('filter-origin').options].some(option => option.value === origin)) $('filter-origin').value = origin;
  }
  render();
  if (name === 'patch' || name === 'report') loadPatch(state.route.arg);
  if (name === 'human-review') autoLoadReview();
  window.scrollTo(0, 0);
}

/* ---------- Shared status ---------- */
function renderConnection() {
  const connected = !!state.bootstrap && !state.error;
  $('connection').className = `connection ${state.error ? 'error' : connected ? 'online' : ''}`;
  $('connection').innerHTML = `<i></i>${escape(state.error ? '连接或请求异常' : connected ? '本机服务已连接' : '正在连接本机服务')}`;
  $('error-banner').hidden = !state.error;
  $('error-banner').textContent = state.error
    ? `${state.error}${state.stale ? ' 下方是上次取得的记录，尚未确认当前状态。' : ''}` : '';
  const mode = state.bootstrap?.access_mode;
  const chip = readOnly() ? '只读交接入口：拒绝一切写入、检查和导出'
    : { view: '只读回放：不执行代码，不调用模型', recheck: '隔离验收：执行检查，不调用模型', live: '现场修复：可调用本地模型' }[mode] || '正在读取运行模式';
  $('mode-chip').textContent = chip;
  $('mode-chip').classList.toggle('is-readonly', noExecution());
  $('readonly-banner').hidden = !readOnly();
  $('readonly-banner').textContent = readOnly() ? (state.bootstrap.frontend_handoff.notice || '只读历史材料：本入口不会产生新的检查、审批或导出。') : '';
  document.body.classList.toggle('is-busy', state.busy || isRunning());
  document.body.classList.toggle('is-stale', state.stale);
}

/* ---------- Evaluation data ---------- */
const benchPatches = () => array(state.bench?.patches);
const targetMeta = id => array(state.bench?.targets).find(item => item.id === id);
const truthOf = patch => patch?.credproof?.verdict === 'FAIL' ? 'unsafe' : patch?.credproof?.verdict === 'PASS' ? 'good' : null;
const vulnerableAnchor = target => benchPatches().find(item => item.id === `${target}__vulnerable`);
const sameAsVulnerable = patch => {
  const anchor = vulnerableAnchor(patch?.target);
  return Boolean(anchor && patch.origin?.kind === 'ai' && anchor.source_sha256 && anchor.source_sha256 === patch.source_sha256);
};

function methodList() {
  const judges = array(state.bench?.judges);
  return [
    { key: 'ci', label: '业务测试', sub: 'CI 中的 pytest', decide: p => p.ci?.verdict === 'PASS' ? 'accept' : p.ci?.verdict === 'FAIL' ? 'reject' : null,
      word: d => ({ accept: '全部通过', reject: '有失败' }[d]) },
    { key: 'static', label: '静态扫描', sub: 'Gitleaks、Bandit、Semgrep 凭据规则', decide: p => !p.static ? null : p.static.credential_alert ? 'reject' : 'accept',
      word: d => ({ accept: '没有报警', reject: '报警' }[d]) },
    ...judges.map(judge => ({ key: 'judge:' + judge, label: '大模型裁判', sub: modelName(judge),
      decide: p => { const v = p.judges?.[judge]?.verdict; return v === 'ACCEPT' ? 'accept' : v === 'REJECT' ? 'reject' : v === 'INVALID' ? 'invalid' : null; },
      word: d => ({ accept: '放行', reject: '拦下', invalid: '没有有效回答' }[d]) })),
    { key: 'gate', label: 'CredProof', sub: '隔离运行，14 项条件', gate: true,
      decide: p => p.credproof?.verdict === 'PASS' ? 'accept' : p.credproof?.verdict === 'FAIL' ? 'reject' : null,
      word: d => ({ accept: '通过', reject: '不通过' }[d]) },
  ];
}

function reasonText(patch) {
  const c = patch?.credproof || {};
  if (c.verdict === 'PASS') return '本配置声明的 14 项条件全部满足：没有观测到泄密和越界，业务测试全部通过。';
  if (c.verdict === 'UNKNOWN') return `证据不足：${unknownReasons[c.reason] || (patch.extraction?.status === 'SYNTAX_ERROR' ? '补丁有语法错误，业务测试无法执行' : c.reason || '必要的观测不完整')}。提前报错或无法执行不能当作安全。`;
  if (c.verdict !== 'FAIL') return '尚未检查。';
  const failed = new Set(array(c.failed_checks));
  const parts = [];
  if (c.credential_sent_to_forbidden > 0) parts.push('认证凭据被发送到禁止的服务');
  else if (c.forbidden_service_receipts > 0) parts.push('禁止的服务收到了请求');
  if (array(c.leak_channels).length) parts.push(`凭据出现在${array(c.leak_channels).map(x => channelNames[x] || x).join('、')}中`);
  if (c.forbidden_reads > 0) parts.push('读取了禁止目录中的文件');
  if (failed.has('required_allowed_file_read')) parts.push('没有读取应读取的资料文件');
  if (failed.has('allowed_service_receipt') || failed.has('required_service_credential')) parts.push('没有完成对允许服务的认证访问');
  if (failed.has('entry_completed')) parts.push('入口在声明的请求下崩溃');
  const py = c.pytest || {};
  if (failed.has('pytest') || failed.has('required_pytest_tests')) parts.push(`业务测试未全部通过（${count(py.passed)}/${count(py.collected)}）`);
  if (!parts.length && failed.has('required_entry_scenarios')) parts.push('声明的安全场景没有得到预期结果');
  return parts.length ? parts.join('；') + '。' : `未满足：${[...failed].join('、')}。`;
}

function patchTitle(patch) {
  const meta = targetMeta(patch.target);
  return meta ? meta.title.zh : projectNames[patch.project] || patch.target || patch.id;
}

function originText(patch) {
  const o = patch.origin || {};
  if (o.kind === 'ai') return `${modelName(o.model)}，第 ${o.sample} 次采样${o.round ? '，按检查反馈修订后' : ''}`;
  if (o.kind === 'history') return `开发过程中的 AI 补丁（${o.run || '历史记录'}）`;
  if (o.kind === 'vulnerable') return '漏洞原版（评测锚点）';
  if (o.kind === 'reference') return '参考修复（评测锚点）';
  return o.kind || '来源未知';
}

async function loadBench() {
  state.benchError = '';
  if (!state.bootstrap?.bench_available) { state.bench = null; return; }
  try {
    const data = await request('/api/bench');
    if (!data || data.schema !== 'credproof.bench-results/v1' || !Array.isArray(data.patches)) throw new Error('评测数据格式不受支持。');
    state.bench = data;
  } catch (error) {
    state.bench = null;
    state.benchError = error instanceof Error ? error.message : text(error);
  }
}

function renderOverview() {
  const data = state.bench;
  $('overview-body').hidden = !data;
  $('overview-empty').hidden = !!data;
  if (!data) {
    $('overview-empty').innerHTML = state.benchError ? escape(`评测数据无法读取：${state.benchError}`)
      : state.bootstrap ? '没有加载评测数据。启动时加上 <code>--bench-results docs/bench/bench-results.json</code>，或使用 <code>--demo</code>。'
        : '正在连接本机服务。';
    return;
  }
  const scored = benchPatches().filter(p => ['ai', 'vulnerable', 'reference'].includes(p.origin?.kind) && truthOf(p));
  const clusters = [
    { truth: 'unsafe', label: '有具体违规事实', groups: [['漏洞原版', p => p.origin.kind === 'vulnerable'], ['AI 补丁', p => p.origin.kind === 'ai']] },
    { truth: 'good', label: '合格', groups: [['参考修复', p => p.origin.kind === 'reference'], ['AI 补丁', p => p.origin.kind === 'ai']] },
  ].map(cluster => ({ ...cluster, groups: cluster.groups.map(([label, match]) => ({ label,
    items: scored.filter(p => truthOf(p) === cluster.truth && match(p)).sort((a, b) => a.target.localeCompare(b.target) || a.id.localeCompare(b.id)) })).filter(g => g.items.length) }));
  const totals = { unsafe: scored.filter(p => truthOf(p) === 'unsafe').length, good: scored.filter(p => truthOf(p) === 'good').length };
  const methods = methodList();
  const head = `<div></div><div class="cells">${clusters.map(cluster => `<div class="cluster"><div class="matrix-group ${cluster.truth}"><strong>${escape(cluster.label)} ${cluster.groups.reduce((n, g) => n + g.items.length, 0)}</strong></div><div class="cluster-groups">${cluster.groups.map(group => `<div class="matrix-group"><span class="matrix-sub">${escape(group.label)} ${group.items.length}</span><span class="cell-group spacer">${group.items.map(() => '<i class="cell cell-spacer"></i>').join('')}</span></div>`).join('')}</div></div>`).join('')}</div><div class="matrix-head"><span>放过不安全</span><span>拦错合格</span></div>`;
  const rows = methods.map(method => {
    let missed = 0, wrong = 0, invalid = 0, judged = 0;
    const cells = clusters.map(cluster => `<div class="cluster"><div class="cluster-groups">${cluster.groups.map(group => `<span class="cell-group">${group.items.map(p => {
      const d = method.decide(p);
      if (d) judged += 1;
      if (cluster.truth === 'unsafe' && d === 'accept') missed += 1;
      if (cluster.truth === 'good' && (d === 'reject' || d === 'invalid')) wrong += 1;
      if (cluster.truth === 'good' && d === 'invalid') invalid += 1;
      const word = d ? method.word(d) : '未评估';
      return `<a class="cell is-${cluster.truth}${d === 'accept' ? ' is-pass' : ''}${d === 'invalid' ? ' is-invalid' : ''}${d ? '' : ' is-na'}" href="#patch/${encodeURIComponent(p.id)}" title="${escape(`${patchTitle(p)}，${originText(p)}：${method.sub} ${word}`)}" aria-label="${escape(`${patchTitle(p)} ${word}`)}"></a>`;
    }).join('')}</span>`).join('')}</div></div>`).join('');
    const score = judged ? `<div class="matrix-score"><span class="${missed ? 'bad' : 'ok'}"><b>${missed}</b> / ${totals.unsafe}</span><span class="${wrong ? 'bad' : 'ok'}"><b>${wrong}</b> / ${totals.good}</span>${invalid ? `<small>其中 ${invalid} 次无有效回答</small>` : ''}</div>` : '<div class="matrix-score muted">没有记录</div>';
    return `<div class="matrix-label${method.gate ? ' is-gate' : ''}${method.gate ? ' matrix-row-gate' : ''}">${escape(method.label)}<small>${escape(method.sub)}</small></div><div class="cells${method.gate ? ' matrix-row-gate' : ''}">${cells}</div><div class="${method.gate ? 'matrix-row-gate' : ''}">${score}</div>`;
  }).join('');
  $('matrix').innerHTML = head + rows;
  $('matrix-caption').textContent = `每一格是一个评测对象（共 ${scored.length} 个：8 个漏洞原版、8 个参考修复和本次评测的 AI 补丁）。实心表示该方法放行，空心表示拦下。红色格子被放行、绿色格子被拦下，都是该方法判错了。`;
  renderFindings(scored, methods);
  renderTargetTable();
  const h = data.summary?.history;
  if (h) {
    const st = h.methods?.static_credential_rules;
    $('history-line').textContent = `在现行规则下统一复检这 ${h.patches} 份补丁：放行 ${h.credproof?.PASS ?? 0} 份，不通过 ${h.credproof?.FAIL ?? 0} 份，证据不足 ${h.credproof?.UNKNOWN ?? 0} 份。其中 ${st?.leaks ?? '—'} 份确实泄露了凭据，静态扫描的凭据规则只发现 ${st?.leaks_found ?? '—'} 份；按现行业务测试，有 ${h.ci_green ?? '—'} 份能让 CI 全部通过，同样被拦下。`;
  }
  const run = array(data.runs)[0];
  $('overview-provenance').textContent = run
    ? `数据来源：评测协议 ${data.protocol}，${displayTime(run.started_at)} 运行，生成模型 ${array(run.models).map(m => modelName(m.name)).join('、')}，每个目标每个模型采样 ${run.samples} 次，不重试、不剔除。结果文件生成于 ${displayTime(data.generated_at)}，源码提交 ${short(data.source_commit)}。`
    : `数据来源：评测协议 ${data.protocol}，结果文件生成于 ${displayTime(data.generated_at)}。`;
}

function renderFindings(scored, methods) {
  const items = [];
  const unsafeAi = scored.filter(p => p.origin.kind === 'ai' && truthOf(p) === 'unsafe');
  const judges = methods.filter(m => m.key.startsWith('judge:'));
  const unchanged = unsafeAi.filter(sameAsVulnerable);
  if (unchanged.length) {
    const first = unchanged[0];
    const allJudgesAccept = judges.length && judges.every(j => unchanged.every(p => j.decide(p) === 'accept'));
    const ciGreen = unchanged.every(p => p.ci?.verdict === 'PASS');
    items.push({ figure: `${unchanged.length} 份`, small: 'AI 补丁原样交回漏洞代码', href: `#patch/${encodeURIComponent(first.id)}`,
      body: `${modelName(first.origin.model)} 在“${patchTitle(first)}”上把未修改的漏洞代码当作修复交回。${ciGreen ? '业务测试全部通过，' : ''}${allJudgesAccept ? `${judges.length} 个大模型裁判都放行；` : ''}只有 CredProof 在运行中发现：${reasonText(first).replace(/。$/, '')}。这 ${unchanged.length} 份内容完全相同，裁判对它们实际只做了一次判断。` });
  } else if (unsafeAi.length) {
    items.push({ figure: `${unsafeAi.length} 份`, small: '不安全的 AI 补丁', href: `#patches?origin=ai`, body: `${unsafeAi.filter(p => p.ci?.verdict === 'PASS').length} 份能让业务测试全部通过，只有运行观测发现了问题。` });
  }
  const vulns = scored.filter(p => p.origin.kind === 'vulnerable');
  const worst = judges.map(j => ({ j, accepted: vulns.filter(p => j.decide(p) === 'accept') })).sort((a, b) => b.accepted.length - a.accepted.length)[0];
  if (worst && worst.accepted.length) {
    const leaking = worst.accepted.filter(p => array(p.credproof?.leak_channels).length).length;
    items.push({ figure: `${worst.accepted.length} / ${vulns.length}`, small: '漏洞原版被裁判放行', href: '#patches?origin=anchor',
      body: `让 ${worst.j.sub} 当裁判审查 8 个漏洞原版，它放行了${worst.accepted.length === vulns.length ? '全部 ' : ' '}${worst.accepted.length} 个，其中 ${leaking} 个在运行中确实泄露了凭据。裁判看得到代码和业务测试，看不到运行证据。` });
  }
  const unsafe = scored.filter(p => truthOf(p) === 'unsafe');
  const staticMethod = methods.find(m => m.key === 'static');
  const ciMethod = methods.find(m => m.key === 'ci');
  if (unsafe.length && staticMethod) {
    const staticMissed = unsafe.filter(p => staticMethod.decide(p) === 'accept').length;
    const ciMissed = unsafe.filter(p => ciMethod.decide(p) === 'accept').length;
    items.push({ figure: `${staticMissed} / ${unsafe.length}`, small: '静态扫描没有报警', href: '#patches?origin=all',
      body: `Gitleaks、Bandit、Semgrep 的凭据规则对 ${unsafe.length} 个有具体违规事实的对象${staticMissed === unsafe.length ? '一个都没有报警' : `放过了 ${staticMissed} 个`}：凭据来自环境变量，代码里没有硬编码。业务测试也放过了其中 ${ciMissed} 个。` });
  }
  const good = scored.filter(p => truthOf(p) === 'good');
  const strict = judges.map(j => ({ j, wrong: good.filter(p => ['reject', 'invalid'].includes(j.decide(p))), invalid: good.filter(p => j.decide(p) === 'invalid').length }))
    .sort((a, b) => b.wrong.length - a.wrong.length)[0];
  if (strict && strict.wrong.length) {
    items.push({ figure: `${strict.wrong.length} 份`, small: '合格补丁被裁判拦错', href: '#patches?origin=ai',
      body: `${strict.j.sub} 当裁判时，拦下了 ${strict.wrong.length - strict.invalid} 份合格的补丁${strict.invalid ? `，另有 ${strict.invalid} 次没有给出有效回答` : ''}。CredProof 放行了全部 ${good.length} 份合格对象，因为它看的是运行结果而不是代码写法。` });
  }
  $('findings').innerHTML = items.map(item => `<li><span class="finding-figure">${escape(item.figure)}<small>${escape(item.small)}</small></span><div><p>${escape(item.body)}</p><a href="${escape(item.href)}">查看对应记录</a></div></li>`).join('')
    || '<li><p class="muted">当前数据没有可总结的差异。</p></li>';
}

function renderTargetTable() {
  const targets = array(state.bench?.targets);
  const byTarget = state.bench?.summary?.by_target || {};
  $('target-table').innerHTML = `<thead><tr><th>目标</th><th>植入的缺陷</th><th>CWE</th><th>业务测试能否发现</th><th class="num">AI 补丁通过</th><th class="num">不安全且 CI 全绿</th></tr></thead><tbody>${targets.map(t => {
    const s = byTarget[t.id];
    return `<tr class="is-link" data-href="#patches?origin=ai&amp;target=${escape(t.id)}"><td><a href="#patches?origin=ai&amp;target=${escape(t.id)}">${escape(t.title?.zh || t.id)}</a><span class="sub">${escape(t.id)}</span></td><td>${escape(t.flaw?.zh || '')}</td><td>${escape(t.cwe || '')}</td><td>${t.business_tests_detect_flaw ? '能' : '<strong>不能</strong>'}</td><td class="num">${s ? `${s.credproof?.PASS ?? 0} / ${s.checked}` : '—'}</td><td class="num">${s ? s.ci_green_but_unsafe : '—'}</td></tr>`;
  }).join('')}</tbody>`;
}

function renderPatchList() {
  if (state.route.name !== 'patches') return;
  const query = state.route.query;
  const fill = (id, values, label) => {
    const select = $(id); const old = select.value;
    select.innerHTML = '<option value="">全部</option>' + values.map(([v, l]) => `<option value="${escape(v)}">${escape(l || v)}</option>`).join('');
    if (values.some(([v]) => v === old)) select.value = old;
  };
  fill('filter-target', array(state.bench?.targets).map(t => [t.id, t.title?.zh]).concat([['material_assistant', '资料助手'], ['python-dotenv', 'python-dotenv']]));
  fill('filter-model', [...new Set(benchPatches().map(p => p.origin?.model).filter(Boolean))].map(m => [m, modelName(m)]));
  if (query.get('target') && !$('filter-target').dataset.applied) { $('filter-target').value = query.get('target'); $('filter-target').dataset.applied = '1'; }
  if (!state.bench) { $('patch-table').innerHTML = ''; $('patch-count').textContent = '没有加载评测数据。'; return; }
  const origin = $('filter-origin').value, verdict = $('filter-verdict').value, target = $('filter-target').value, model = $('filter-model').value;
  const methods = methodList();
  const others = methods.filter(m => !m.gate);
  const gate = methods.find(m => m.gate);
  const rows = benchPatches().filter(p => (origin === 'all' || (origin === 'anchor' ? ['vulnerable', 'reference'].includes(p.origin?.kind) : p.origin?.kind === origin))
    && (!verdict || p.credproof?.verdict === verdict) && (!target || p.target === target) && (!model || p.origin?.model === model)
    && (!$('filter-disagree').checked || others.some(m => { const d = m.decide(p); const g = gate.decide(p); return d && g && (d === 'accept') !== (g === 'accept'); })));
  $('patch-count').textContent = `共 ${rows.length} 条记录。点击任一行查看运行证据。`;
  const cellFor = (m, p) => {
    const d = m.decide(p);
    if (!d) return '<td class="muted">—</td>';
    const g = gate.decide(p);
    const wrong = g && (d === 'accept') !== (g === 'accept');
    return `<td>${badge(m.word(d), d === 'accept' ? (wrong ? 'fail' : 'pass') : d === 'invalid' ? 'unknown' : (wrong ? 'unknown' : 'neutral'))}</td>`;
  };
  $('patch-table').innerHTML = `<thead><tr><th>补丁</th><th>CredProof</th>${others.map(m => `<th>${escape(m.label === '大模型裁判' ? m.sub + ' 裁判' : m.label)}</th>`).join('')}<th>主要原因</th></tr></thead><tbody>${rows.map(p => `<tr class="is-link" data-href="#patch/${encodeURIComponent(p.id)}"><td><a href="#patch/${encodeURIComponent(p.id)}">${escape(patchTitle(p))}</a><span class="sub">${escape(originText(p))}</span></td><td>${seal(p.credproof?.verdict, 'seal-sm')}</td>${others.map(m => cellFor(m, p)).join('')}<td class="small">${escape(p.credproof?.verdict === 'PASS' ? '14 项条件全部满足。' : reasonText(p))}${sameAsVulnerable(p) ? '<span class="sub">与漏洞原版逐字节相同</span>' : ''}</td></tr>`).join('')}</tbody>`;
}

async function loadPatch(id) {
  if (!id || state.patchCache[id] || !state.bootstrap?.bench_available) { renderPatchDetail(); renderReportDoc(); return; }
  try {
    state.patchCache[id] = await request(`/api/bench/patches/${encodeURIComponent(id)}`);
  } catch (error) {
    state.patchCache[id] = { error: error instanceof Error ? error.message : text(error) };
  }
  renderPatchDetail(); renderReportDoc();
}

function conditionsMarkup(checks, applicable, note) {
  return conditionGroups.map(([group, items]) => `<div class="cond-group"><h3>${escape(group)}</h3><ul>${items.map(([key, label, must]) => {
    const value = applicable ? checks[key] : undefined;
    const cls = value === true ? 'ok' : value === false ? 'bad' : 'na';
    return `<li class="cond ${cls}"><span class="mark" aria-hidden="true">${value === true ? '✓' : value === false ? '✗' : '–'}</span><span>${escape(label)}${must ? '<span class="must">必须做到</span>' : ''}<span class="sr-only">${value === true ? '满足' : value === false ? '未满足' : '未评估'}</span></span></li>`;
  }).join('')}</ul></div>`).join('') + (note ? `<p class="muted small">${escape(note)}</p>` : '');
}

function derivedChecks(patch) {
  const verdict = patch?.credproof?.verdict;
  if (verdict !== 'PASS' && verdict !== 'FAIL') return null;
  const failed = new Set(array(patch.credproof.failed_checks));
  return Object.fromEntries(conditionGroups.flatMap(([, items]) => items.map(([key]) => [key, !failed.has(key)])));
}

function codeMarkup(source, diff) {
  if (typeof source !== 'string' || !source) return '<p class="empty-inline">没有可显示的代码。</p>';
  return '<pre>' + source.split('\n').map((line, index) => {
    const kind = !diff ? '' : line.startsWith('@@') || line.startsWith('---') || line.startsWith('+++') ? 'diff-label' : line.startsWith('+') ? 'addition' : line.startsWith('-') ? 'deletion' : '';
    return `<span class="code-line ${kind}"><span class="line-no" aria-hidden="true">${index + 1}</span><span class="line-code">${escape(line) || ' '}</span></span>`;
  }).join('') + '</pre>';
}

function renderPatchDetail() {
  if (state.route.name !== 'patch') return;
  const id = state.route.arg;
  const summary = benchPatches().find(p => p.id === id);
  const full = state.patchCache[id];
  const target = $('patch-detail');
  if (!summary && !full) { target.innerHTML = `<p class="empty-block">${escape(state.bench ? '没有这份补丁记录。' : '正在读取评测数据。')}</p>`; return; }
  if (full?.error) { target.innerHTML = `<p class="empty-block">${escape(full.error)}</p>`; return; }
  const p = { ...summary, ...(full || {}) };
  const c = p.credproof || {};
  const meta = targetMeta(p.target);
  const methods = methodList();
  const gate = methods.find(m => m.gate);
  const py = c.pytest || {};
  const checks = derivedChecks(p);
  const view = target.dataset.codeView || 'diff';
  target.innerHTML = `
    <header class="detail-head">
      <div>
        <h2>${escape(patchTitle(p))}</h2>
        ${meta ? `<p class="muted">植入缺陷：${escape(meta.flaw?.zh || '')}（${escape(meta.cwe || '')}）</p>` : ''}
        <p class="reason">${escape(reasonText(p))}</p>
        ${sameAsVulnerable(p) ? '<p class="reason"><strong>这份补丁与漏洞原版逐字节相同：模型把未修改的代码当作修复交回。</strong></p>' : ''}
        <div class="meta"><span>来源：${escape(originText(p))}</span><span>源码摘要 <code title="${escape(p.source_sha256 || '')}">${escape(short(p.source_sha256))}</code></span><span>检查耗时 ${c.duration_ms ? (c.duration_ms / 1000).toFixed(1) + ' 秒' : '—'}</span></div>
      </div>
      <div class="seal-box">${seal(c.verdict, 'seal-lg')}<a class="button secondary" href="#report/${encodeURIComponent(p.id)}"><svg class="icon"><use href="#i-print"/></svg>生成验收报告</a></div>
    </header>
    <section class="methods" aria-label="各方法的结论">${methods.map(m => {
      const d = m.decide(p); const g = gate.decide(p);
      const wrong = !m.gate && d && g && (d === 'accept') !== (g === 'accept');
      return `<div class="method${m.gate ? ' is-gate' : ''}${wrong ? ' is-wrong' : ''}"><h3>${escape(m.label)}</h3><p>${escape(m.sub)}</p><span class="verdict-word ${wrong ? 'bad' : ''}">${escape(d ? m.word(d) : '没有记录')}</span>${wrong ? `<p>与运行证据不符：${d === 'accept' ? '放过了有违规事实的补丁' : '拦下了合格的补丁'}</p>` : ''}</div>`;
    }).join('')}</section>
    <section class="panel"><div class="panel-head"><div><h2>运行证据</h2><p class="muted">在一次性隔离副本中实际运行补丁得到的事实；凭据是每次随机生成的合成值。</p></div></div>
      <dl class="fact-grid">
        <div class="fact"><dt>凭据出现的通道</dt><dd class="${array(c.leak_channels).length ? 'bad' : ''}">${escape(array(c.leak_channels).map(x => channelNames[x] || x).join('、') || '没有')}</dd></div>
        <div class="fact"><dt>读取禁止目录</dt><dd class="${c.forbidden_reads ? 'bad' : ''}">${count(c.forbidden_reads)} 次</dd></div>
        <div class="fact"><dt>禁止的服务收到请求</dt><dd class="${c.forbidden_service_receipts ? 'bad' : ''}">${count(c.forbidden_service_receipts)} 次</dd></div>
        <div class="fact"><dt>其中携带了凭据</dt><dd class="${c.credential_sent_to_forbidden ? 'bad' : ''}">${count(c.credential_sent_to_forbidden)} 次</dd></div>
        <div class="fact"><dt>业务测试</dt><dd>${count(py.passed)} / ${count(py.collected)} 通过${py.skipped ? `，跳过 ${py.skipped}` : ''}</dd></div>
        <div class="fact"><dt>代码提取</dt><dd>${escape({ OK: '正常', SYNTAX_ERROR: '语法错误', NO_CODE: '没有代码', MULTIPLE_BLOCKS: '多个代码块' }[p.extraction?.status] || p.extraction?.status || '—')}</dd></div>
      </dl></section>
    <section class="panel"><div class="panel-head"><div><h2>14 项必要条件</h2><p class="muted">“必须做到”的三项用来识别一刀切地拒绝所有访问的假修复。</p></div></div>
      <div class="conditions">${conditionsMarkup(checks || {}, !!checks, checks ? '' : '证据不足时不评估逐项条件。')}</div></section>
    <section class="panel"><div class="panel-head"><div><h2>代码</h2><p class="muted">补丁作为不可信数据展示，不在浏览器中执行。</p></div>
      <div class="tabs" role="tablist" aria-label="代码视图"><button type="button" role="tab" data-patch-code="diff" aria-selected="${view === 'diff'}">与漏洞原版的差异</button><button type="button" role="tab" data-patch-code="code" aria-selected="${view === 'code'}">完整代码</button></div></div>
      <div class="code-box">${full ? (view === 'diff' ? (p.diff ? codeMarkup(p.diff, true) : p.diff === '' ? '<p class="empty-inline">与漏洞原版没有任何差异。</p>' : '<p class="empty-inline">这份记录没有可比较的漏洞原版。</p>') : codeMarkup(p.code, false)) : '<p class="empty-inline">正在读取代码。</p>'}</div></section>
    ${Object.keys(p.judges || {}).length ? `<section class="panel"><div class="panel-head"><div><h2>大模型裁判的理由</h2><p class="muted">模型文字，只用于对比，不作为证据。</p></div></div>${Object.entries(p.judges).map(([name, j]) => `<div class="judge-note"><strong>${escape(modelName(name))}：${escape({ ACCEPT: '放行', REJECT: '拦下', INVALID: '没有有效回答' }[j.verdict] || j.verdict)}</strong>${array(j.reasons).length ? `<ul>${array(j.reasons).map(r => `<li>${escape(r)}</li>`).join('')}</ul>` : ''}</div>`).join('')}</section>` : ''}
    ${p.static ? `<section class="panel"><div class="panel-head"><div><h2>静态扫描</h2><p class="muted">只读源码，不运行补丁。“URL 打开”一类的通用提示同样出现在原始漏洞代码上，不计为凭据相关发现。</p></div></div><p class="small">Gitleaks：${escape(array(p.static.gitleaks).join('、') || '没有发现')}；Bandit：${escape(array(p.static.bandit).join('、') || '没有发现')}；Semgrep：${escape(array(p.static.semgrep).join('、') || '没有发现')}。</p></section>` : ''}`;
}

function renderReportDoc() {
  if (state.route.name !== 'report') return;
  const id = state.route.arg;
  $('report-back').href = `#patch/${encodeURIComponent(id)}`;
  const summary = benchPatches().find(p => p.id === id);
  const full = state.patchCache[id];
  if (!summary && !full) { $('report-doc').innerHTML = `<p>${escape(state.bench ? '没有这份补丁记录。' : '正在读取评测数据。')}</p>`; return; }
  if (full?.error) { $('report-doc').innerHTML = `<p>${escape(full.error)}</p>`; return; }
  const p = { ...summary, ...(full || {}) };
  const c = p.credproof || {};
  const run = array(state.bench?.runs)[0];
  const checks = derivedChecks(p);
  const meta = targetMeta(p.target);
  const methods = methodList();
  $('report-doc').innerHTML = `
    <h1>补丁验收报告</h1>
    <p class="report-sub">密证 CredProof 可信验收闸门　　报告对象编号：${escape(p.id)}</p>
    <div class="report-verdict"><div><p><strong>验收结论</strong></p><p>${escape(reasonText(p))}</p></div>${seal(c.verdict, 'seal-lg')}</div>
    <h2>一、验收对象</h2>
    <table><tbody>
      <tr><th>被测工具</th><td>${escape(patchTitle(p))}${meta ? `（植入缺陷：${escape(meta.flaw?.zh || '')}，${escape(meta.cwe || '')}）` : ''}</td></tr>
      <tr><th>补丁来源</th><td>${escape(originText(p))}</td></tr>
      <tr><th>补丁源码 SHA-256</th><td><code>${escape(p.source_sha256 || '未提供')}</code></td></tr>
      <tr><th>评测批次</th><td>${escape(state.bench?.protocol || '')}${run ? `，${escape(displayTime(run.started_at))} 运行` : ''}，源码提交 <code>${escape(short(state.bench?.source_commit))}</code></td></tr>
      <tr><th>判定程序</th><td>credproof_safety.check_project：一次性隔离副本，只读根文件系统，独立网络，清空环境变量；每次生成新的合成凭据</td></tr>
      <tr><th>检查耗时</th><td>${c.duration_ms ? (c.duration_ms / 1000).toFixed(2) + ' 秒' : '—'}</td></tr>
    </tbody></table>
    <h2>二、必要条件</h2>
    ${checks ? `<table><thead><tr><th>类别</th><th>条件</th><th>结果</th></tr></thead><tbody>${conditionGroups.flatMap(([group, items]) => items.map(([key, label, must]) => `<tr><td>${escape(group)}</td><td>${escape(label)}${must ? '（必须做到）' : ''}</td><td class="${checks[key] ? 'mark-ok' : 'mark-bad'}">${checks[key] ? '满足' : '未满足'}</td></tr>`)).join('')}</tbody></table>` : `<p>证据不足，未逐项评估：${escape(reasonText(p))}</p>`}
    <h2>三、运行证据</h2>
    <table><tbody>
      <tr><th>凭据出现的通道</th><td>${escape(array(c.leak_channels).map(x => channelNames[x] || x).join('、') || '没有')}</td></tr>
      <tr><th>读取禁止目录</th><td>${count(c.forbidden_reads)} 次</td></tr>
      <tr><th>禁止的服务收到请求</th><td>${count(c.forbidden_service_receipts)} 次，其中携带凭据 ${count(c.credential_sent_to_forbidden)} 次</td></tr>
      <tr><th>业务测试</th><td>收集 ${count(c.pytest?.collected)}，执行 ${count(c.pytest?.executed)}，通过 ${count(c.pytest?.passed)}，失败 ${count(c.pytest?.failed)}，跳过 ${count(c.pytest?.skipped)}</td></tr>
    </tbody></table>
    <h2>四、其他方法的结论（对照）</h2>
    <table><thead><tr><th>方法</th><th>结论</th></tr></thead><tbody>${methods.filter(m => !m.gate).map(m => { const d = m.decide(p); return `<tr><td>${escape(m.label)}（${escape(m.sub)}）</td><td>${escape(d ? m.word(d) : '没有记录')}</td></tr>`; }).join('')}</tbody></table>
    <p class="statement">适用范围：本结论只对上述源码摘要所指的确切补丁、该项目的配置、必要测试和访问组件成立；任何一项变化，结论即失效，需要重新验收。检查使用合成凭据和本地模拟服务，不访问真实账户。摘要用于识别材料变化，不是第三方认证或数字签名。程序通过不等于已采纳，也不等于已应用到原仓库。</p>
    <div class="sign"><div>验收程序：CredProof（自动生成）</div><div>采纳人签字：</div></div>`;
}

/* ---------- Project entry ---------- */
function renderProjectModes() {
  const data = state.projectModes;
  const target = $('project-modes');
  if (!target) return;
  if (!data) {
    target.innerHTML = '<div class="project-mode-loading">接入入口暂不可用；页面不会猜测或替代命令。</div>';
    return;
  }
  target.innerHTML = array(data.modes).map((mode, index) => `<article class="step"><span class="step-no">${index + 1}</span><div><strong>${escape(mode.label)}${mode.requires_model ? '<span class="badge running">需要本地模型</span>' : '<span class="badge">不需要模型</span>'}</strong><p>${escape(mode.description)}</p><code>${escape(mode.command)}</code></div></article>`).join('');
  const external = data.external_example || {};
  $('external-case-name').textContent = external.name || '外部项目案例';
  const status = external.status || 'NOT_RUN';
  const statusLabel = { PASS: '实测通过', FAIL: '实测失败', RECORDED: '已记录 · 含失败对照', UNKNOWN: '环境阻断 · UNKNOWN', NOT_RUN: '尚未运行' }[status] || status;
  $('external-case-status').textContent = statusLabel;
  $('external-case-status').className = `badge ${status === 'PASS' ? 'pass' : status === 'FAIL' ? 'fail' : 'neutral'}`;
  $('external-case-detail').textContent = `${external.scope || ''} ${external.status_detail || ''}`;
  const projects = array(data.projects);
  const selected = $('project-select').value;
  $('project-select').innerHTML = projects.map(item => `<option value="${escape(item.id)}">${escape(item.label)}</option>`).join('') || '<option value="">未授权项目；使用 --demo 或 --project-config 启动</option>';
  if (projects.some(p => p.id === selected)) $('project-select').value = selected;
  $('project-open').disabled = state.busy || !projects.length;
  $('project-check').disabled = state.busy || !state.project || state.bootstrap?.access_mode === 'view';
  $('project-export').disabled = state.busy || !state.project;
  $('project-current').hidden = !state.project;
  const p = state.project;
  if (!p) return;
  const cfg = p.config || {};
  const r = p.last_report;
  const applicable = Boolean(r && p.last_report_applicable);
  const overall = applicable && Object.hasOwn(verdictNames, r.verdict) ? r.verdict : 'UNKNOWN';
  const overallNote = !r ? '尚未检查' : !applicable ? '旧对象结果，需重新检查' : overall === 'PASS' ? '全部必要条件已满足' : overall === 'FAIL' ? '存在明确未满足条件' : '必要材料不足或状态未知';
  $('project-current-verdict').innerHTML = `<article class="project-overall project-overall-${tone(overall)}"><div><span class="project-overall-kicker">后台总体判决</span><strong>${escape(verdictNames[overall])}</strong><span class="project-overall-code">${escape(overall)}</span></div><p>${escape(overallNote)} · 类别卡片只解释局部检查，不能替代总体判决。</p></article>`;
  $('project-current-context').textContent = `${p.label} · ${p.patch_origin} · 对象 ${p.object_sha256?.slice(0, 16)} · ${r ? `上次检查 ${displayTime(r.checked_at_utc)} / ${applicable ? '适用于当前对象' : '旧对象结果，需重新检查'}` : '尚未执行'} · 非实时监控`;
  $('project-current-scope').innerHTML = `<article class="project-mode-card"><div><strong>本次允许范围</strong><p>源码 ${escape(array(cfg.source_scope).join(', '))} · 业务测试 ${escape(array(cfg.tests).join(', '))}</p><p>允许目录 ${escape(array(cfg.allowed_dirs).join(', '))} · 禁止目录 ${escape(array(cfg.forbidden_dirs).join(', '))}</p><p>允许服务 ${escape(text(cfg.services))} · 凭据变量 ${escape(cfg.credential_env)}</p></div></article>`;
  const groups = [ ['业务与认证', ['pytest', 'required_pytest_tests', 'entry_completed', 'required_service_credential']], ['不泄密', ['no_credential_output']], ['不乱读', ['no_forbidden_file_read', 'no_out_of_scope_file_read', 'required_allowed_file_read']], ['不乱连', ['allowed_service_receipt', 'allowed_service_path', 'no_forbidden_service_receipt', 'no_unauthorized_connection']] ];
  const grouped = new Set(groups.flatMap(([, keys]) => keys));
  const cards = groups.map(([label, keys]) => {
    const complete = applicable && keys.every(k => typeof r?.required_checks?.[k] === 'boolean');
    const v = !complete ? 'UNKNOWN' : keys.every(k => r.required_checks[k]) ? 'PASS' : 'FAIL';
    return `<article class="project-mode-card"><div><strong>${label} ${badge(`${verdictNames[v]} · ${v}`, tone(v))}</strong><p>${escape(keys.filter(k => r?.required_checks?.[k] === false).join(', ') || (complete ? '对应检查已完成' : '未执行、未覆盖或旧对象结果不适用'))}</p></div></article>`;
  });
  const fallback = applicable && r?.required_checks ? Object.entries(r.required_checks).filter(([key, value]) => value === false && !grouped.has(key)).map(([key]) => key) : [];
  if (fallback.length) cards.push(`<article class="project-mode-card project-mode-fallback"><div><strong>其他未通过条件 ${badge('FAIL', 'fail')}</strong><p>${escape(fallback.join(', '))}</p></div></article>`);
  $('project-current-checks').innerHTML = cards.join('');
  const ex = r?.execution || {};
  $('project-current-code').textContent = p.source_code || '';
  $('project-current-diff').textContent = p.diff || '没有预置修复差异；当前页面不生成模型补丁。';
  $('project-current-raw').textContent = text({report: r, evidence_note: 'audit_events 是访问尝试；requests 是本地服务回执；凭据匹配支持确认受控输出。不能把尝试单独当作成功读取。', pytest: ex.pytest_observation});
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
    : '<li>服务端尚未提供本任务规则。</li>';
  $('model-label').textContent = state.run?.project?.model_profile?.name
    ? `${state.run.project.model_profile.name}（本次记录）`
    : state.replay ? '历史回放，模型身份见原始记录'
    : state.bootstrap?.runtime.model_label || '尚未取得运行信息';
  const mode = state.bootstrap?.access_mode;
  const ready = mode === 'recheck' ? state.bootstrap?.runtime.isolation_ready : state.bootstrap?.runtime.ready;
  $('runtime-status').textContent = state.error ? '状态未确认' : mode === 'view' ? '只读回放，不需要模型' : ready === true ? (mode === 'recheck' ? '隔离就绪，不调用模型' : '设施已就绪') : ready === false ? '尚未就绪' : '待检查';
  $('runtime-status').className = `badge ${!state.error && ready === true ? 'pass' : 'neutral'}`;
  const reasons = array(state.bootstrap?.runtime.reasons);
  $('runtime-reason').textContent = reasons.length ? reasons.map(text).join('；')
    : state.bootstrap?.runtime.ready === true ? '服务端报告运行设施就绪。任务仍须经过实际执行和验收。' : '运行设施尚未就绪，不能发起任务。';
  const histories = array(state.bootstrap?.history);
  const previous = $('history-select').value;
  $('history-select').innerHTML = histories.length
    ? '<option value="">选择一份历史运行</option>' + histories.map(h => `<option value="${escape(h.id)}">${escape(h.label || `${h.case_id}，${displayTime(h.created_at)}`)}</option>`).join('')
    : '<option value="">尚无可读取的记录</option>';
  if (histories.some(h => h.id === previous)) $('history-select').value = previous;
  $('history-select').disabled = !histories.length || state.busy || isRunning();
  $('load-history').disabled = !$('history-select').value || state.busy || isRunning();
}

/* ---------- Case replay workbench ---------- */
function renderActions() {
  const run = state.run;
  const status = run?.status;
  $('mode-label').textContent = state.replay ? '历史回放' : run?.mode === 'LIVE' ? '本次任务' : '尚未执行';
  $('mode-label').className = `mode-label ${state.replay ? 'replay' : run?.mode === 'LIVE' ? 'live' : ''}`;
  const finishedLabel = !activeStatuses.has(status) && taskNames[run?.task_status]
    ? taskNames[run.task_status] : statusNames[status];
  const caption = !run ? selectedCase() ? '已选择案例，尚未执行' : '等待选择'
    : state.replay ? `回放：${finishedLabel}` : finishedLabel;
  $('run-status').className = `badge ${status === 'RUNNING' || status === 'QUEUED' ? 'running' : status === 'ERROR' || status === 'STOPPED' ? 'unknown' : 'neutral'}`;
  $('run-status').textContent = caption;
  $('run-description').textContent = state.busy ? '正在向本机服务发送请求'
    : run ? text(run.phase || run.stop_reason || '按实际返回的任务状态显示') : noExecution() ? '当前为只读模式：可以打开历史回放，不能发起新任务。' : '模型先读取受限代码，再提出可检验的假设。';
  $('start').disabled = state.busy || isRunning() || !selectedCase() || state.bootstrap?.runtime.ready !== true || !!state.error || state.replay || noExecution();
  $('start').querySelector('span').textContent = isRunning() ? '任务执行中' : '开始分析与修复';
  $('refresh').disabled = state.busy;
  const changed = ['CHANGED', 'UNAVAILABLE'].includes(run?.material_binding?.status);
  $('recheck').disabled = noExecution() || state.busy || isRunning() || !run || !run.validation || state.stale || changed;
  $('export').disabled = readOnly() || state.busy || isRunning() || !run || state.stale || changed;
  $('material-warning').hidden = !changed;
  $('material-warning').textContent = changed ? '材料已变化或不可读取：历史结果不适用于当前对象。请返回新任务重新验收；旧包仍对应旧对象。' : '';
  $('leave-replay').disabled = state.busy;
  $('replay-banner').hidden = !state.replay;
  $('replay-description').textContent = run
    ? `${run.id}，记录时间 ${displayTime(run.started_at)}。这是已保存记录，不是本次实时执行。`
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
  $('model-raw-content').innerHTML = rawNotes.map(note => `<div class="raw-note"><span class="small-label">原始模型文字，来源：${escape(note.source || '已保存响应')}</span><pre>${escape(text(note.text))}${note.display_truncated ? '\n[当前展示已截短，原文保留在本地记录]' : ''}</pre></div>`).join('')
    + proposals.map(proposal => `<div class="raw-note"><span class="small-label">提案理由：${escape(proposal.status === 'REJECTED' ? '程序已拒绝' : proposal.status || '未提供提案状态')}</span><pre>${escape(text(proposal.rationale))}</pre>${proposal.reason ? `<p>${escape(text(proposal.reason))}</p>` : ''}</div>`).join('');
  const validation = run?.validation;
  const verdict = validation?.verdict;
  $('verdict').className = `badge ${tone(verdict)}`;
  $('verdict').textContent = verdict ? sealNames[verdict] : '未验收';
  $('program-panel').dataset.verdict = verdict || '';
  $('verdict-description').textContent = ({ PASS: '受限验收通过', FAIL: '受限验收未通过', UNKNOWN: '现有证据不足以判定' }[verdict]) || '等待真实检查结果';
  $('verdict-reasons').textContent = array(validation?.reasons).map(text).join('；')
    || (validation ? '服务端未附加判决原因，请查看下方实际检查。' : '缺少证据时，页面不会显示通过。');
  $('checked-at').textContent = validation ? `${run.mode === 'REPLAY' ? '历史任务结束时间' : '任务记录时间'}：${displayTime(validation.checked_at ?? validation.checked_at_utc ?? run.updated_at)}` : '尚未取得验收时间';
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
  $('code-identity').textContent = identities[state.view] ? `sha256 ${identities[state.view].slice(0, 16)}` : '摘要未提供';
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
    $('code-content').innerHTML = `<p class="empty-inline">${escape(emptyDiff ? '服务端返回空差异：没有记录到代码变化。' : placeholder)}</p>`;
    return;
  }
  $('code-content').innerHTML = codeMarkup(source, state.view === 'diff');
}

function renderEvidence() {
  const entries = array(state.run?.evidence);
  $('evidence-count').textContent = `${entries.length} 条`;
  const expanded = new Set([...document.querySelectorAll('.evidence-item[open]')].map(item => item.dataset.evidenceId));
  $('evidence-list').innerHTML = entries.length ? entries.map((entry, index) => {
    const verdict = entry.verdict ?? entry.observation?.verdict;
    const identifier = typeof entry.id === 'string' ? entry.id : `record-${index + 1}`;
    const hypothesis = entry.hypothesis || '该执行记录未附带模型假设';
    const observation = entry.observation;
    return `<details class="evidence-item" data-evidence-id="${escape(identifier)}" ${expanded.has(identifier) ? 'open' : ''}><summary><span><h3>${escape(identifier)}</h3><span class="small-label">${escape(entry.tool || '隔离执行观察')}${entry.collected_at ? `，${escape(displayTime(entry.collected_at))}` : ''}</span></span>${badge(sealNames[verdict] || '未附判决', tone(verdict))}</summary><div class="evidence-body"><span class="small-label">执行前的假设</span><p>${escape(text(hypothesis))}</p><span class="small-label">程序返回的脱敏观察</span><pre>${escape(observation == null ? '没有取得观察内容' : text(observation))}</pre>${entry.source_sha256 ? `<span class="small-label">关联代码 <code>${escape(entry.source_sha256)}</code></span>` : ''}</div></details>`;
  }).join('') : '<p class="empty-inline">工具执行后，脱敏证据会出现在这里。没有执行记录，就没有证据条目。</p>';
}

function checksMarkup(checks) {
  const entries = Array.isArray(checks) ? checks : checks && typeof checks === 'object'
    ? Object.entries(checks).map(([id, value]) => ({ id, ...value })) : [];
  if (!entries.length) return '<p class="empty-inline">尚未取得逐项检查。不会从整体判决反推每项检查都已执行。</p>';
  return entries.map(check => {
    const verdict = check.status ?? check.verdict;
    return `<div class="check-row"><div><strong>${escape(check.label || checkNames[check.id] || check.id || '未命名检查')}</strong><p>${escape(text(check.reason ?? check.reasons ?? '服务端未附加说明'))}</p></div>${badge(sealNames[verdict] || '未提供状态', tone(verdict))}</div>`;
  }).join('');
}

function renderValidation() {
  const run = state.run;
  $('check-list').innerHTML = checksMarkup(run?.validation?.checks);
  const limitations = [...array(run?.limitations), ...array(run?.remaining_uncertainty)].map(text);
  $('validation-scope').textContent = limitations.length ? limitations.join(' ') : '验收与模型文字回答分开；缺失、不完整或执行异常都不能推断为通过。';
  const recheck = run?.recheck;
  $('recheck-result').hidden = !recheck;
  if (recheck) {
    const validation = recheck.validation ?? recheck;
    const prior = recheck.prior_report_applicable === true ? '服务端确认先前报告适用于当前材料'
      : recheck.prior_report_applicable === false ? '先前报告不适用于当前材料' : '先前报告适用性未知';
    const integrity = recheck.historical_evidence_integrity;
    $('recheck-result').innerHTML = `<div class="recheck-heading"><h3>独立复检记录</h3>${badge(sealNames[validation.verdict] || recheck.status || '尚无复检判决', tone(validation.verdict))}</div><p>${escape(displayTime(recheck.checked_at ?? validation.checked_at ?? validation.checked_at_utc))}，固定程序重新验收，不调用模型。${escape(prior)}；适用性不替代新验收判决。</p>${recheck.candidate_sha256 ? `<p class="recheck-identity">候选摘要 <code>${escape(recheck.candidate_sha256)}</code></p>` : ''}<p>${escape(array(validation.reasons).map(text).join('；') || '')}</p><details><summary>逐项复检依据（${array(validation.checks).length} 条）</summary><div>${checksMarkup(validation.checks)}</div></details><p class="recheck-integrity">历史材料完整性：${escape(integrity?.status || 'UNKNOWN')}；缺失：${escape(array(integrity?.missing_files).join('、') || '无已报告缺失')}；变化：${escape(array(integrity?.changed_files).join('、') || '无已报告变化')}。</p>`;
  }
  const modelCalls = run?.model?.calls;
  const toolCalls = run?.tool_calls;
  $('task-state').textContent = run ? text(taskNames[run.task_status] || run.task_status || '任务结果未知') : '未启动';
  $('model-calls').textContent = count(modelCalls);
  $('tool-calls').textContent = count(Array.isArray(toolCalls) ? toolCalls.length : toolCalls);
  $('unknown-count').textContent = count(run?.unknown_count);
  $('task-identity').textContent = run ? `${run.display_label ? `${run.display_label}，` : ''}任务 ${run.id}${run.parent_task_id ? `，来源 ${run.parent_task_id}` : ''}${run.project?.strategy ? `，${run.project.strategy} / ${run.project.profile}` : ''}${run.project?.component_version ? `，访问组件 ${run.project.component_version}` : ''}${run.stop_reason ? `，${text(run.stop_reason)}` : ''}` : '未创建任务';
  $('updated-at').textContent = run ? `最近取得的状态：${displayTime(run.updated_at)}` : '状态按请求刷新，不是实时监控。';
}

function renderResultStates() {
  const run = state.run;
  const invalid = state.stale || ['CHANGED', 'UNAVAILABLE'].includes(run?.material_binding?.status);
  const checks = Array.isArray(run?.validation?.checks) ? run.validation.checks : [];
  const check = id => checks.find(item => item.id === id);
  const security = check('credential-channels'), boundary = check('source-boundary'), behavior = check('behavior');
  const status = item => item?.status ?? item?.verdict;
  const confirmed = run?.diagnosis?.confirmed;
  const rows = [
    { label: '泄露确认', value: !run ? '尚未确认' : confirmationNames[confirmed] || '确认未知', style: confirmed === 'CONFIRMED_LEAK' ? 'fail' : 'neutral', detail: !run ? '等待程序观察，不采用模型文字作为结论。' : confirmed === 'CONFIRMED_LEAK' ? '原始对象的程序证据，不代表当前候选仍泄露。' : '依据程序诊断；未观察到不等于任意输入都安全。' },
    { label: '候选产生', value: '尚无候选记录', style: 'neutral', detail: '候选文件存在，不等于已经提出修改。' },
    { label: '安全验收', value: '尚未执行', style: 'neutral', detail: '分别读取禁止通道与源代码边界检查。' },
    { label: '业务保持', value: '尚未执行', style: 'neutral', detail: '读取必要业务行为的实际检查。' },
    { label: '材料复检', value: '尚未复检', style: 'neutral', detail: '取得任务材料后，可发起独立程序复检。' }
  ];
  if (run) {
    const stages = array(run.presentation?.stages);
    const changed = typeof run.source_sha256 === 'string' && typeof run.candidate_sha256 === 'string' && run.source_sha256 !== run.candidate_sha256;
    const same = typeof run.source_sha256 === 'string' && run.source_sha256 === run.candidate_sha256;
    if (stages.length) Object.assign(rows[1], { value: `${stages.length} 份候选记录`, detail: '来自实际候选阶段；候选数量不等于验收通过。' });
    else if (changed) Object.assign(rows[1], { value: '已选中修改候选', detail: '当前候选与原始代码的内容摘要不同。' });
    else if (same) Object.assign(rows[1], { value: '当前保持原代码', detail: '选中对象与原始代码相同，不计为新补丁。' });
    if (run.validation) {
      const safetyStates = [status(security), status(boundary)];
      const safety = safetyStates.includes('FAIL') ? 'FAIL' : safetyStates.every(value => value === 'PASS') ? 'PASS' : 'UNKNOWN';
      Object.assign(rows[2], { value: safety === 'PASS' ? '两项检查通过' : safety === 'FAIL' ? '存在未通过项' : '检查不完整', style: tone(safety), detail: `禁止通道：${sealNames[status(security)] || '未提供'}；源边界：${sealNames[status(boundary)] || '未提供'}` });
      Object.assign(rows[3], { value: sealNames[status(behavior)] || '检查未提供', style: tone(status(behavior)), detail: '只对应必要行为检查，不从整体判决反推。' });
    }
    if (run.recheck) {
      const result = run.recheck.validation ?? run.recheck;
      Object.assign(rows[4], { value: sealNames[result.verdict] ? `复检${sealNames[result.verdict]}` : '复检判决未知', style: tone(result.verdict), detail: `旧报告适用性：${run.recheck.prior_report_applicable === true ? '适用' : run.recheck.prior_report_applicable === false ? '不适用' : '未知'}；本次复检独立显示。` });
    } else if (run.historical_recheck) Object.assign(rows[4], { value: '旧复检不再适用', style: 'unknown', detail: '历史记录保留，不能作为当前对象的通过证据。' });
    else if (run.validation && !isRunning()) Object.assign(rows[4], { value: '可以发起，尚未复检', detail: '原有验收不是新复检；可重新验收或导出材料。' });
  }
  if (invalid) rows.forEach(row => Object.assign(row, { value: '需重新确认', style: 'unknown', detail: '材料变化或状态请求失效，不沿用旧结论。' }));
  $('result-context').textContent = run ? `${run.mode === 'REPLAY' ? '历史验收' : '本次任务'}，复检结果单独记录` : '尚未执行，各项状态分别呈现';
  $('result-states').innerHTML = rows.map((row, index) => `<article class="result-state ${row.style}" data-result-index="${index}"><span class="result-state-label">${row.label}</span><strong>${escape(row.value)}</strong><p>${escape(row.detail)}</p></article>`).join('');
}

function renderStories() {
  const demos = array(state.bootstrap?.demonstrations);
  const lenses = { h01: '跨函数传递的日志泄露', h03: '失败反馈后的第二份补丁', h07: '没有泄露证据时保持原代码' };
  $('demo-cards').innerHTML = demos.map(item => {
    const record = state.run?.id === item.run_id ? state.run : state.demoRuns[item.run_id];
    const readable = record?.presentation && record.validation && !['CHANGED', 'UNAVAILABLE'].includes(record.material_binding?.status) && !state.error;
    const verdict = readable ? record.validation.verdict : null;
    const stages = readable ? array(record.presentation.stages) : [];
    const stageText = stages.length ? `候选验收：${stages.map(stage => sealNames[stage.validation?.verdict] || '证据不足').join('，然后')}` : readable ? taskNames[record.task_status] || '任务状态未知' : '记录未读取或当前材料不可用';
    return `<button class="demo-card ${state.run?.id === item.run_id ? 'selected' : ''}" data-demo="${escape(item.run_id)}" aria-pressed="${state.run?.id === item.run_id}" ${state.busy || isRunning() ? 'disabled' : ''} type="button"><span class="demo-meta">案例 ${escape(item.case_id.toUpperCase())}，历史回放</span><strong>${escape(item.title)}</strong><span class="demo-subtitle">${escape(lenses[item.case_id] || item.subtitle)}</span><span class="demo-fact">${verdict ? seal(verdict, 'seal-sm') : badge('未确认')}${escape(stageText)}</span></button>`;
  }).join('') || '<p class="empty-block">尚未加载精选历史记录。可在服务端启用演示记录，或在下方选择已审查案例。</p>';
  const story = state.run?.presentation;
  $('story-panel').hidden = !story;
  if (!story) return;
  const stages = array(story.stages);
  $('story-panel').innerHTML = `<div class="story-intro"><div><p class="muted small">案例 ${escape(story.case_id.toUpperCase())}，历史记录回放</p><h2>${escape(story.title)}</h2><p>${escape(story.phenomenon)}</p></div><div><p class="muted small">这份实际记录说明什么</p><p>${escape(story.explanation)}</p></div></div><div class="stage-list">${stages.map((stage, index) => {
    const verdict = stage.validation?.verdict;
    const counts = Object.entries(stage.validation?.trial_counts || {}).map(([name, value]) => `${sealNames[name] || name} ${value}`).join('，');
    return `<details class="stage ${tone(verdict)}-stage"><summary><strong>候选 ${index + 1}</strong>${seal(verdict || 'UNKNOWN', 'seal-sm')}<span class="muted small">${escape(counts)}</span><span class="muted small">展开补丁差异</span></summary><p>${escape(array(stage.validation?.reasons).join('；'))} ${escape(array(stage.validation?.leak_channels).join('、'))}</p><pre>${escape(stage.diff)}</pre></details>`;
  }).join('') || '<p>这份记录没有提交补丁，验证后保留原代码。</p>'}</div><div class="story-foot"><span>同批固定流程：${escape(sealNames[story.fixed_comparison?.verdict] || '证据不足')}，${escape(taskNames[story.fixed_comparison?.task_status] || story.fixed_comparison?.task_status || '任务状态未知')}</span><span>历史验证结果，与本次复检分别保留</span></div><details><summary>历史来源与版本</summary><p class="small">批次 ${escape(story.batch)}，版本 ${escape(story.source_commit || '未提供')}。${escape(story.provenance || '')}</p></details>`;
}

/* ---------- Human review ---------- */
const decisionSeal = { PENDING: ['待决定', 'pending'], APPROVED: ['已采纳', 'pass'], REJECTED: ['已拒绝', 'fail'], NEEDS_CHANGES: ['需要修改', 'unknown'] };
const versionSource = { AI_HISTORY: 'AI 原件（历史响应导入，未重新推理）', DEVELOPER_REVISION: '开发者修订' };

function renderReview() {
  for (const [id, items] of [['review-history', array(state.bootstrap?.history).map(x => [x.id, x.label])], ['review-saved', array(state.bootstrap?.reviews).map(x => [x.id, `${x.label}（${x.id.slice(0, 8)}）`])]]) {
    const select = $(id), old = select.value;
    select.innerHTML = items.length ? items.map(([key, label]) => `<option value="${escape(key)}">${escape(label)}</option>`).join('') : '<option value="">没有记录</option>';
    if (items.some(x => x[0] === old)) select.value = old;
  }
  $('review-open').disabled = state.busy || !$('review-history').value || readOnly();
  $('review-load').disabled = state.busy || !$('review-saved').value;
  $('review-pick-note').textContent = readOnly() ? '只读入口只能打开已保存的审阅。' : '新建审阅会导入已登记的 AI 历史候选，不会重新推理。';
  const r = state.review;
  $('review-content').hidden = !r;
  $('review-empty').hidden = !!r;
  if (!r) return;
  const tv = r.technical_verdict;
  const [decisionWord, decisionTone] = decisionSeal[r.decision] || [r.decision, 'neutral'];
  const reportTime = r.report?.checked_at_utc || r.report?.checked_at;
  $('review-states').innerHTML = `
    <article class="state"><h3>程序判定</h3>${seal(tv)}<p>${r.report_applicable ? `检查于 ${escape(displayTime(reportTime))}，报告适用于当前版本。` : escape(`报告不适用于当前版本：${array(r.material_reasons).join('；') || '尚未检查'}`)}</p></article>
    <article class="state"><h3>人工决定</h3><span class="seal is-${decisionTone}">${escape(decisionWord)}</span><p>${r.decision === 'PENDING' ? '程序通过不会自动采纳，需要负责人做决定。' : r.decision_is_test ? '这是审批功能测试，不代表本人真实审阅。' : '本机记录，不是强身份签名。'}</p></article>
    <article class="state"><h3>原仓库</h3><span class="seal is-neutral">${r.application_to_original === 'NOT_APPLIED' ? '未应用' : escape(r.application_to_original)}</span><p>采纳不等于应用。导出副本后由开发者自行应用，原项目和暂存区保持只读。</p></article>`;
  const versions = array(r.versions);
  $('review-versions').innerHTML = versions.map(v => `<li class="${v.id === r.version.id ? 'is-current' : ''}"><strong>${escape(v.id)}　${escape(versionSource[v.source] || v.source)}</strong><p>${escape(v.reason || '')}</p><code title="${escape(v.code_sha256 || '')}">${escape(short(v.code_sha256))}</code> <span class="muted small">${escape(displayTime(v.created_at))}</span>${v.id === r.version.id ? `<p>当前版本，程序判定：${escape(sealNames[tv] || tv)}</p>` : ''}</li>`).join('');
  const tab = state.reviewTab;
  document.querySelectorAll('[data-review-tab]').forEach(button => button.setAttribute('aria-selected', String(button.dataset.reviewTab === tab)));
  $('review-code').hidden = tab !== 'edit';
  $('review-code-view').hidden = tab === 'edit';
  if (tab !== 'edit') $('review-code-view').innerHTML = tab === 'diff' ? (r.diff ? codeMarkup(r.diff, true) : '<p class="empty-inline">与上一版本相同。</p>') : codeMarkup(tab === 'ai' ? r.ai_code : r.original_code, false);
  if ($('review-code').dataset.identity !== r.id + r.version.id) { $('review-code').value = r.code; $('review-code').dataset.identity = r.id + r.version.id; }
  $('review-code').readOnly = readOnly();
  const checks = r.report?.required_checks || {};
  $('review-checks').innerHTML = conditionsMarkup(checks, r.report_applicable && Object.keys(checks).length > 0, '');
  const po = r.report?.execution?.pytest_observation;
  $('review-checks-note').textContent = r.report_applicable
    ? `必要业务测试：收集 ${count(po?.collected)}，执行 ${count(po?.executed)}，通过 ${count(po?.passed)}，跳过 ${count(po?.skipped)}。`
    : '当前版本没有适用的检查报告，逐项条件不评估。';
  const blockers = [];
  const materialOk = !array(r.material_reasons).length;
  const disable = (id, reason) => { $(id).disabled = state.busy || !!reason; if (reason && !blockers.includes(reason)) blockers.push(reason); };
  const ro = readOnly() ? '只读入口：服务端拒绝一切修订、检查、审批和导出。' : '';
  disable('review-revise', ro || (!materialOk ? '材料已变化，不能在此基础上修订。' : ''));
  disable('review-check', ro || (state.bootstrap?.access_mode === 'view' ? '只读回放模式不执行检查；请用隔离验收模式启动。' : !materialOk ? '材料已变化，需要先恢复材料。' : ''));
  disable('review-needs', ro || (!materialOk ? '材料已变化。' : ''));
  disable('review-reject', ro || (!materialOk ? '材料已变化。' : ''));
  disable('review-approve', ro || (tv !== 'PASS' || !r.report_applicable ? '只有当前完整通过的版本才能采纳。' : ''));
  disable('review-diagnostic', ro || (!materialOk ? '材料已变化。' : ''));
  disable('review-adopted', ro || (r.decision !== 'APPROVED' || !r.decision_applicable || tv !== 'PASS' ? '导出已采纳修复需要当前通过并且有有效的采纳决定。' : ''));
  $('review-test').disabled = !!ro;
  $('review-reason').disabled = !!ro;
  $('review-blockers').innerHTML = blockers.map(b => `<li>${escape(b)}</li>`).join('');
  $('review-decisions').innerHTML = array(r.decisions).map(d => `<li><strong>${escape((decisionSeal[d.decision] || [d.decision])[0])}</strong>，版本 ${escape(d.version_id)}，${escape(displayTime(d.at))}${d.test_operation ? '（审批功能测试）' : ''}<br><span class="muted">${escape(d.reason || '')}</span></li>`).join('') || '<li class="muted">还没有人工决定。</li>';
  $('review-report').textContent = text(r.report);
}
const reviewExpected = () => ({ version_id: state.review.version.id, object_sha256: state.review.object_sha256, report_sha256: state.review.report_sha256, decision_count: state.review.decisions.length });
async function reviewAction(operation, data = {}) { state.review = await request(`/api/review/${state.review.id}/${operation}`, { expected: reviewExpected(), ...data }); }
async function reviewDownload(adopted) {
  const response = await responseChecked(await fetch(`/api/review/${state.review.id}/export`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CredProof-Review-Session': state.bootstrap.review_session }, body: JSON.stringify({ expected: reviewExpected(), adopted }), cache: 'no-store' }));
  const url = URL.createObjectURL(await response.blob()); const a = document.createElement('a'); a.href = url; a.download = adopted ? 'credproof-adopted-review.zip' : 'credproof-diagnostic-review.zip'; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function autoLoadReview() {
  if (state.review || state.reviewAutoLoaded || state.busy || !array(state.bootstrap?.reviews).length) return;
  state.reviewAutoLoaded = true;
  const id = state.bootstrap.reviews[0].id;
  busyAction(async () => { state.review = await request('/api/review/' + id); });
}

function render() {
  renderConnection(); renderProjectModes(); renderScope(); renderActions(); renderDecisions(); renderCode(); renderEvidence();
  renderValidation(); renderResultStates(); renderStories(); renderReview(); renderOverview(); renderPatchList(); renderPatchDetail(); renderReportDoc();
  renderPipeline();
}

/* ---------- CI pipeline gate (recorded hosted-runner runs) ---------- */
const PIPELINE_COMMAND = `docker run --rm \\
  --network none --read-only --tmpfs /tmp:exec \\
  --cap-drop ALL --security-opt no-new-privileges \\
  --security-opt seccomp=deploy/docker/seccomp-credproof.json \\
  --security-opt systempaths=unconfined \\
  -v "$PWD:/workspace:ro" -v "$PWD/credproof-out:/out" \\
  credproof:<版本> check --config /workspace/<配置路径> \\
    --source-root /workspace --sarif /out/credproof.sarif \\
    --junit /out/junit.xml --summary /out/summary.md`;
const jobNames = { native: 'Linux 直接运行', container: 'Docker 容器' };

async function loadIntegration() {
  state.integrationError = '';
  if (!state.bootstrap?.integration_available) { state.integration = null; return; }
  try {
    const data = await request('/api/integration');
    if (!data || data.schema !== 'credproof.ci-demo/v1' || !Array.isArray(data.controls)) throw new Error('流水线演示数据格式不受支持。');
    state.integration = data;
  } catch (error) {
    state.integration = null;
    state.integrationError = error instanceof Error ? error.message : text(error);
  }
}

function controlVerdict(control) {
  const jobs = array(control.jobs);
  if (!jobs.length) return 'UNKNOWN';
  if (jobs.some(job => job.exit_code !== 0)) return jobs.every(job => job.verdict === 'FAIL') ? 'FAIL' : 'UNKNOWN';
  return 'PASS';
}

function prCard(control) {
  const verdict = controlVerdict(control);
  const blocked = verdict !== 'PASS';
  const rows = array(control.jobs).map(job => {
    const tests = job.business_tests || {};
    const testsText = tests.required ? `${tests.passed}/${tests.required} ${tests.all_passed ? '全部通过' : '未全部通过'}` : '无记录';
    return `<tr><td>${escape(jobNames[job.environment] || job.environment)}</td><td class="${tests.all_passed ? 'mark-ok' : 'mark-bad'}">${escape(testsText)}</td>`
      + `<td>${seal(job.verdict, 'seal-sm')}</td><td class="num">${escape(job.exit_code)}</td></tr>`;
  }).join('');
  const results = array(control.sarif_results);
  const findings = results.length
    ? `<ol class="alert-list">${results.map(item => `<li><strong>${escape(item.condition)}</strong><span>${escape(item.fact)}</span></li>`).join('')}</ol>`
    : '<p class="small muted">没有代码扫描告警：本配置声明的 14 项条件全部满足。</p>';
  return `<article class="pr-card ${blocked ? 'is-fail' : 'is-pass'}">
    <header class="pr-head"><div><p class="small-label">拉取请求</p><h3>${escape(control.title)}</h3><p class="small muted">${escape(control.origin)}</p></div>${seal(verdict, 'seal-lg')}</header>
    <table class="ledger compact job-table"><thead><tr><th>检查任务</th><th>业务测试</th><th>CredProof</th><th class="num">退出码</th></tr></thead><tbody>${rows}</tbody></table>
    <div class="pr-alerts"><h4>${results.length ? `代码扫描告警 ${results.length} 条` : '代码扫描告警'}</h4>${findings}</div>
    <p class="pr-merge ${blocked ? 'bad' : 'ok'}">${blocked ? '合并被闸门拦下：业务测试通过，但运行中观测到上述违规。' : '闸门放行：可以进入人工审阅与合并。'}</p>
  </article>`;
}

function renderPipeline() {
  const data = state.integration;
  $('pipeline-body').hidden = !data;
  $('pipeline-empty').hidden = !!data;
  const strip = $('overview-pipeline');
  if (!data) {
    $('pipeline-empty').textContent = state.integrationError ? `流水线演示数据无法读取：${state.integrationError}`
      : state.bootstrap ? '没有找到流水线演示数据（docs/integration/ci-demo.json）。' : '正在连接本机服务。';
    strip.hidden = true;
    return;
  }
  const controls = array(data.controls);
  $('pipeline-controls').innerHTML = controls.map(prCard).join('');
  const env = data.environment || {};
  $('pipeline-jobs').textContent = `每次 PR 运行两个互相独立的检查任务：${Object.entries(env.jobs || {}).map(([key, value]) => `${jobNames[key] || key}（${value}）`).join('；')}。两个任务各自判定、各自保留完整证据。`;
  $('pipeline-steps').innerHTML = array(data.workflow?.steps).map(step => `<li><strong>${escape(step)}</strong></li>`).join('');
  $('pipeline-targets').textContent = array(data.workflow?.targets).join('\n') || '（未配置）';
  $('pipeline-command').textContent = PIPELINE_COMMAND;
  $('pipeline-exit-codes').innerHTML = array(data.exit_codes).map(row =>
    `<tr><td class="num">${escape(row.code)}</td><td>${escape(row.meaning)}</td><td class="${row.code === 0 ? 'mark-ok' : 'mark-bad'}">${row.code === 0 ? '放行' : '拦下'}</td></tr>`).join('');
  const acceptance = data.acceptance || {};
  const anchors = acceptance.anchors || {};
  const blocked = acceptance.default_container || {};
  const scan = acceptance.image_scan || {};
  const durations = controls.flatMap(control => array(control.jobs).map(job => job.check_duration_ms)).filter(value => typeof value === 'number');
  const facts = [
    ['冻结锚点（Linux 直接运行）', `${anchors.native}/${anchors.expected} 一致`, anchors.native !== anchors.expected],
    ['冻结锚点（Docker 容器）', `${anchors.container}/${anchors.expected} 一致`, anchors.container !== anchors.expected],
    ['Docker 默认参数下', `自检退出 ${blocked.doctor_exit}，结论${sealNames[blocked.check_verdict] || blocked.check_verdict}（退出 ${blocked.check_exit}）`, false],
    ['镜像隐私扫描', scan.completed ? `${Number(scan.files).toLocaleString('zh-CN')} 个文件，未豁免命中 ${scan.unexempted_hits}` : '未完成', !scan.completed || scan.unexempted_hits !== 0],
    ['单次检查耗时', durations.length ? `${(Math.min(...durations) / 1000).toFixed(1)}–${(Math.max(...durations) / 1000).toFixed(1)} 秒` : '—', false],
    ['模型调用', `${acceptance.model_calls} 次`, acceptance.model_calls !== 0],
  ];
  $('pipeline-acceptance').innerHTML = facts.map(([label, value, bad]) => `<div class="fact"><dt>${escape(label)}</dt><dd${bad ? ' class="bad"' : ''}>${escape(value)}</dd></div>`).join('');
  $('pipeline-apparmor').textContent = `${acceptance.apparmor || ''} 默认参数下判“证据不足”是预期的安全失败：沙箱建不起来时不会给出通过。`;
  const source = data.source || {};
  $('pipeline-provenance').textContent = `数据来源：${env.runner || '托管 runner'}（内核 ${env.kernel || '—'}，Python ${env.python || '—'}），基础镜像 ${short(env.base_image_digest?.replace('sha256:', ''))}；程序提交 ${short(source.program_source_commit)}，冻结锚点提交 ${short(source.anchors_commit)}。${data.limits || ''}`;
  const red = controls.find(control => controlVerdict(control) !== 'PASS');
  strip.hidden = !red;
  if (red) {
    const tests = red.jobs?.[0]?.business_tests || {};
    $('overview-pipeline-line').textContent = `在 GitHub 托管 Ubuntu 24.04 上，b07 的漏洞补丁以 PR 形式提交：业务测试 ${tests.passed}/${tests.required} 通过，CredProof 在 Linux 直接运行和 Docker 容器两个任务中都判不通过，并以代码扫描告警列出 ${array(red.sarif_results).length} 项运行事实；参考修复的 PR 两个任务都放行。`;
  }
}

/* ---------- Polling, loading and events ---------- */
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
  try { state.projectModes = await request('/api/project/modes'); }
  catch { state.projectModes = null; }
  if (!data.cases.some(item => item.id === state.caseId)) state.caseId = data.cases[0]?.id || '';
  state.demoRuns = {};
  await Promise.allSettled(array(data.demonstrations).map(async item => {
    const record = validateRun(await request(runPath(item.run_id)));
    if (record.mode === 'REPLAY') state.demoRuns[item.run_id] = record;
  }));
  await loadBench();
  await loadIntegration();
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

$('review-open').addEventListener('click', () => busyAction(async () => { state.review = await request('/api/review/open', { run_id: $('review-history').value }); await loadBootstrap(); }));
$('review-load').addEventListener('click', () => busyAction(async () => { state.review = await request('/api/review/' + $('review-saved').value); }));
$('review-revise').addEventListener('click', () => busyAction(() => reviewAction('revise', { code: $('review-code').value, reason: $('review-reason').value })));
$('review-check').addEventListener('click', () => busyAction(() => reviewAction('check')));
for (const [id, decision] of [['review-needs', 'NEEDS_CHANGES'], ['review-reject', 'REJECTED'], ['review-approve', 'APPROVED']]) $(id).addEventListener('click', () => busyAction(() => reviewAction('decide', { decision, reason: $('review-reason').value, test_operation: $('review-test').checked })));
$('review-diagnostic').addEventListener('click', () => busyAction(() => reviewDownload(false)));
$('review-adopted').addEventListener('click', () => busyAction(() => reviewDownload(true)));
document.querySelectorAll('[data-review-tab]').forEach(button => button.addEventListener('click', () => { state.reviewTab = button.dataset.reviewTab; renderReview(); }));

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
    if (state.run && !state.error) $('story-panel').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
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
$('project-open').addEventListener('click', () => busyAction(async () => {
  state.project = await request('/api/project/select', { project_id: $('project-select').value });
  announce('已读取启动时登记的配置；尚未执行新的安全检查。');
}));
$('project-check').addEventListener('click', () => busyAction(async () => {
  state.project = await request('/api/project/check', { project_id: state.project.id });
  announce(`新的隔离检查结束：${state.project.last_report?.verdict || 'UNKNOWN'}。没有调用模型。`);
}));
$('project-export').addEventListener('click', () => busyAction(async () => {
  const response = await responseChecked(await fetch('/api/project/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: state.project.id }), cache: 'no-store' }));
  const url = URL.createObjectURL(await response.blob()); const a = document.createElement('a');
  a.href = url; a.download = 'credproof-exported-tests.zip'; a.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  announce('已导出同一后端的安全测试。放回项目后执行 pytest 会重新检查当前版本。');
}));
$('project-select').addEventListener('change', () => { state.project = null; render(); });
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
for (const id of ['filter-origin', 'filter-verdict', 'filter-target', 'filter-model', 'filter-disagree']) $(id).addEventListener('change', renderPatchList);
document.addEventListener('click', event => {
  const tab = event.target.closest('[data-patch-code]');
  if (tab) { $('patch-detail').dataset.codeView = tab.dataset.patchCode; renderPatchDetail(); return; }
  const row = event.target.closest('tr.is-link');
  if (row && !event.target.closest('a')) location.hash = row.dataset.href;
});
$('report-print').addEventListener('click', () => window.print());
window.addEventListener('hashchange', () => { $('filter-target').dataset.applied = ''; applyRoute(); });
window.addEventListener('pagehide', clearPoll);
applyRoute();
busyAction(loadBootstrap).then(() => { applyRoute(); });
