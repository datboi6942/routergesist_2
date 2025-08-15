async function api(path, opts={}){
  const res = await fetch(path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers||{}) },
    credentials: 'include'
  });
  if(!res.ok){ throw new Error(await res.text()); }
  return res.json();
}

async function ensureAuth(){
  try{ await api('/api/auth/state'); }
  catch{ location.href = '/static/login.html'; }
}

async function loadInterfaces(){
  const data = await api('/api/interfaces/');
  const el = document.getElementById('interfaces');
  el.innerHTML = '';
  const table = document.createElement('table');
  table.className = 'iface-table';
  table.innerHTML = `<thead><tr><th>Name</th><th>Type</th><th>State</th><th>IPv4</th><th>Role</th><th style="width:1%"></th></tr></thead>`;
  const tbody = document.createElement('tbody');
  for(const i of data.interfaces){
    const tr = document.createElement('tr');
    const roleBadge = i.role === 'AP' ? '<span class="badge ap">AP</span>' : i.role === 'WAN' ? '<span class="badge wan">WAN</span>' : '<span class="badge">—</span>';
    tr.innerHTML = `<td>${i.name}</td><td>${i.is_wireless ? 'Wi‑Fi' : 'Ethernet'}</td><td>${i.is_up ? 'up' : 'down'}</td><td>${(i.ipv4_addresses||[]).join(', ')||'—'}</td><td>${roleBadge}</td>`;
    const td = document.createElement('td');
    td.className = 'table-actions';
    const apBtn = document.createElement('button'); apBtn.textContent = 'AP'; apBtn.className='tiny'; apBtn.title='Set AP'; apBtn.onclick = () => assignRole(i.name, 'AP');
    const wanBtn = document.createElement('button'); wanBtn.textContent = 'WAN'; wanBtn.className='tiny'; wanBtn.title='Set WAN'; wanBtn.onclick = () => assignRole(i.name, 'WAN');
    td.append(apBtn, ' ', wanBtn);
    tr.appendChild(td);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  el.appendChild(table);
}

async function assignRole(name, role){
  try{
    await api('/api/interfaces/assign', { method: 'POST', body: JSON.stringify({ interface_name: name, role }) });
    await loadInterfaces();
  }catch(e){ alert('Failed: ' + e.message); }
}

async function loadThreats(){
  const data = await api('/api/threats/');
  const el = document.getElementById('threats');
  el.innerHTML = '';
  if(!data.events.length){ el.innerHTML = '<p class="muted">No events.</p>'; return; }
  const table = document.createElement('table');
  table.innerHTML = `<thead><tr><th>Time</th><th>Severity</th><th>Source</th><th>Message</th><th>IP</th><th>Action</th><th></th></tr></thead>`;
  const tbody = document.createElement('tbody');
  for(const ev of data.events.slice(-50).reverse()){
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${new Date(ev.timestamp).toLocaleString()}</td><td>${ev.severity}</td><td>${ev.source}</td><td title="${ev.explanation||''}">${ev.message}</td><td>${ev.ip||'—'}</td><td>${ev.action||'—'}</td>`;
    const td = document.createElement('td');
    const btn = document.createElement('button'); btn.className='small'; btn.textContent='Why?'; btn.onclick = ()=> showWhy(ev);
    td.appendChild(btn); tr.appendChild(td);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  el.appendChild(table);
}

async function nuke(){
  const confirm = document.getElementById('confirm').value;
  const full = document.getElementById('full_device').checked;
  const el = document.getElementById('nukeMsg');
  try{
    const res = await api('/api/nuke/', { method: 'POST', body: JSON.stringify({ confirmation: confirm, full_device: full }) });
    el.textContent = res.message;
  }catch(e){ el.textContent = 'Failed: ' + e.message; }
}

document.getElementById('nukeBtn').addEventListener('click', nuke);

async function init(){
  await ensureAuth();
  await loadOpenAIState();
  await loadInterfaces();
  await loadThreats();
  await startTrafficChart();
  await loadDomains();
  await loadTopDomains();
  await loadSummary();
  await loadConnections();
  await loadTopDomainsByClient();
  await loadNewDomains();
  await refreshBlocklist();
  setInterval(()=>isTabActive('interfaces')&&loadInterfaces(), 5000);
  setInterval(()=>isTabActive('security')&&loadThreats(), 7000);
  // traffic chart is animated via requestAnimationFrame; no interval needed
  setInterval(()=>isTabActive('analytics')&&loadDomains(), 8000);
  setInterval(()=>isTabActive('analytics')&&loadTopDomains(), 10000);
  setInterval(()=>isTabActive('analytics')&&loadSummary(), 6000);
  setInterval(()=>isTabActive('analytics')&&loadConnections(), 12000);
  setInterval(()=>isTabActive('analytics')&&loadTopDomainsByClient(), 12000);
  setInterval(()=>isTabActive('analytics')&&loadNewDomains(), 30000);
  setInterval(()=>isTabActive('security')&&refreshBlocklist(), 8000);
  setupTabs();
  // Bind buttons to avoid inline handlers (CSP safe)
  const saveKeyBtn = document.getElementById('saveKeyBtn'); if(saveKeyBtn) saveKeyBtn.addEventListener('click', saveOpenAIKey);
  const pwUpdateBtn = document.getElementById('pwUpdateBtn'); if(pwUpdateBtn) pwUpdateBtn.addEventListener('click', changePassword);
  const modalCloseBtn = document.getElementById('modalCloseBtn'); if(modalCloseBtn) modalCloseBtn.addEventListener('click', closeModal);
  const blockBtn = document.getElementById('blockIpBtn'); if(blockBtn) blockBtn.addEventListener('click', blockIpNow);
  const fwdBtn = document.getElementById('fwdAddBtn'); if(fwdBtn) fwdBtn.addEventListener('click', addForward);
  const applyBtn = document.getElementById('applyRouterBtn'); if(applyBtn) applyBtn.addEventListener('click', applyRouter);
  const svcRefresh = document.getElementById('svcRefreshBtn'); if(svcRefresh) svcRefresh.addEventListener('click', loadServices);
  const svcDns = document.getElementById('svcRestartDnsmasq'); if(svcDns) svcDns.addEventListener('click', ()=>ctlSvc('dnsmasq','restart'));
  const svcAp = document.getElementById('svcRestartHostapd'); if(svcAp) svcAp.addEventListener('click', ()=>ctlSvc('hostapd','restart'));
  await loadRouterConfig();
  await loadServices();
}

// Settings: OpenAI key and password change
async function loadOpenAIState(){
  try{
    const s = await api('/api/settings/openai');
    const stateEl = document.getElementById('openaiState');
    if(stateEl) stateEl.textContent = s.configured ? 'Configured' : 'Not configured';
  }catch{}
}

async function loadTopDomains(){
  try{
    const data = await api('/api/stats/top-domains');
    const el = document.getElementById('topDomains'); if(!el) return;
    el.innerHTML = '';
    const table = document.createElement('table');
    table.innerHTML = '<thead><tr><th>Domain</th><th>Queries</th></tr></thead>';
    const tbody = document.createElement('tbody');
    (data.items||[]).forEach(([dom,count])=>{ const tr = document.createElement('tr'); tr.innerHTML = `<td>${dom}</td><td>${count}</td>`; tbody.appendChild(tr); });
    table.appendChild(tbody); el.appendChild(table);
  }catch{}
}

async function loadSummary(){
  try{
    const data = await api('/api/stats/summary');
    const el = document.getElementById('summary'); if(!el) return;
    el.innerHTML='';
    const table = document.createElement('table');
    table.innerHTML = '<thead><tr><th>NIC</th><th>Role</th><th>RX (KB/s)</th><th>TX (KB/s)</th></tr></thead>';
    const tbody = document.createElement('tbody');
    const per = data.pernic||{}; Object.keys(per).forEach(n=>{
      const r = per[n]; const tr = document.createElement('tr');
      const rx = (r.rx_bps/1024).toFixed(1); const tx=(r.tx_bps/1024).toFixed(1);
      tr.innerHTML = `<td>${n}</td><td>${r.role}</td><td>${rx}</td><td>${tx}</td>`; tbody.appendChild(tr);
    });
    table.appendChild(tbody); el.appendChild(table);
  }catch{}
}

async function loadConnections(){
  try{
    const data = await api('/api/stats/connections');
    const el = document.getElementById('connections'); if(!el) return;
    el.innerHTML='';
    const row = document.createElement('div'); row.className='row wrap gap-16';
    const a = document.createElement('div'); a.innerHTML='<h3 class="m-0">Top Clients</h3>'; const at = document.createElement('table'); at.innerHTML='<thead><tr><th>Client</th><th>Conns</th></tr></thead>'; const atb=document.createElement('tbody'); (data.top_clients||[]).forEach(([ip,c])=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${ip}</td><td>${c}</td>`; atb.appendChild(tr); }); at.appendChild(atb); a.appendChild(at);
    const b = document.createElement('div'); b.innerHTML='<h3 class="m-0">Top Dest Ports</h3>'; const bt = document.createElement('table'); bt.innerHTML='<thead><tr><th>Port</th><th>Conns</th></tr></thead>'; const btb=document.createElement('tbody'); (data.top_dest_ports||[]).forEach(([p,c])=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${p}</td><td>${c}</td>`; btb.appendChild(tr); }); bt.appendChild(btb); b.appendChild(bt);
    row.appendChild(a); row.appendChild(b); el.appendChild(row);
  }catch{}
}

async function loadTopDomainsByClient(){
  try{
    const data = await api('/api/stats/top-domains-by-client');
    const el = document.getElementById('topDomainsByClient'); if(!el) return;
    el.innerHTML='';
    const table = document.createElement('table');
    table.innerHTML = '<thead><tr><th>Client</th><th>Top Domains</th></tr></thead>';
    const tbody = document.createElement('tbody');
    const byc = data.by_client||{}; Object.keys(byc).forEach(client=>{
      const items = byc[client].map(([d,c])=>`${d} (${c})`).join(', ');
      const tr=document.createElement('tr'); tr.innerHTML=`<td>${client}</td><td>${items}</td>`; tbody.appendChild(tr);
    });
    table.appendChild(tbody); el.appendChild(table);
  }catch{}
}

async function loadNewDomains(){
  try{
    const data = await api('/api/stats/new-domains');
    const el = document.getElementById('newDomains'); if(!el) return;
    el.innerHTML='';
    const list = document.createElement('ul');
    (data.items||[]).slice(0,50).forEach(([ts,dom])=>{ const li=document.createElement('li'); li.textContent=`${new Date(ts*1000).toLocaleTimeString()} — ${dom}`; list.appendChild(li); });
    el.appendChild(list);
  }catch{}
}

async function saveOpenAIKey(){
  const key = document.getElementById('openaiKey').value;
  const msg = document.getElementById('settingsMsg');
  try{
    const res = await api('/api/settings/openai', { method:'POST', body: JSON.stringify({ api_key: key }) });
    msg.textContent = res.ok ? 'Saved.' : 'Saved';
    document.getElementById('openaiKey').value='';
    await loadOpenAIState();
    const stateEl = document.getElementById('openaiState'); if(stateEl) stateEl.textContent = 'Configured';
    alert('OpenAI API key saved.');
  }catch(e){ msg.textContent = 'Save failed'; }
}

async function changePassword(){
  const cur = document.getElementById('curPass').value;
  const nw = document.getElementById('newPass').value;
  const msg = document.getElementById('pwMsg');
  try{
    const res = await api('/api/auth/change-password', { method:'POST', body: JSON.stringify({ current_password: cur, new_password: nw }) });
    msg.textContent = res.ok ? 'Password changed.' : 'Password changed';
    document.getElementById('curPass').value='';
    document.getElementById('newPass').value='';
  }catch(e){ msg.textContent = 'Change failed'; }
}

window.saveOpenAIKey = saveOpenAIKey;
window.changePassword = changePassword;

init();

// Smooth animated traffic chart (no external deps)
let __traffic = {buffer: [], nic: null, lastFetch: 0};
async function startTrafficChart(){
  const cvs = document.getElementById('trafficChart'); if(!cvs) return;
  const ctx = cvs.getContext('2d');
  async function fetchData(){
    try{
      const data = await api('/api/stats/traffic');
      const pernic = data.pernic || {}; const nics = Object.keys(pernic);
      if(nics.length===0) return;
      if(!__traffic.nic) __traffic.nic = nics[0];
      const points = pernic[__traffic.nic] || [];
      __traffic.buffer = points.slice(-300); // last 5 minutes at 1Hz
      __traffic.lastFetch = performance.now();
    }catch{}
  }
  function draw(){
    const w = cvs.width = cvs.clientWidth; const h = cvs.height = 220;
    ctx.clearRect(0,0,w,h);
    const pts = __traffic.buffer;
    if(pts.length<2){ requestAnimationFrame(draw); return; }
    const now = performance.now();
    const rx = pts.map(p=>p[1]); const tx = pts.map(p=>p[2]);
    const max = Math.max(1, ...rx, ...tx);
    const duration = Math.max(1, pts[pts.length-1][0]-pts[0][0]);
    const xForTs = (ts)=>{
      const t0 = pts[0][0]; const t1 = pts[pts.length-1][0];
      return ((ts - t0) / (t1 - t0)) * w;
    };
    const yForVal = (v)=> h - (v/max)*(h-20) - 10;
    // grid and axes
    ctx.strokeStyle = '#2a2f3a'; ctx.lineWidth = 1; ctx.beginPath();
    for(let i=0;i<5;i++){ const y = (h-20)*i/4 + 10; ctx.moveTo(0,y); ctx.lineTo(w,y); }
    ctx.stroke();
    // y-axis labels (KB/s)
    ctx.fillStyle = '#7a8290'; ctx.font = '12px system-ui';
    for(let i=0;i<=4;i++){ const val = (max*i/4)/1024; const y = (h-20)* (1 - i/4) + 10; ctx.fillText(val.toFixed(0)+' KB/s', 6, Math.max(12, Math.min(h-4, y-2))); }
    // x-axis start/end times
    const t0d = new Date(pts[0][0]*1000).toLocaleTimeString();
    const t1d = new Date(pts[pts.length-1][0]*1000).toLocaleTimeString();
    ctx.fillText(t0d, 6, h-4);
    ctx.fillText(t1d, w-80, h-4);
    // rx line
    ctx.strokeStyle = '#5b9cff'; ctx.lineWidth = 2; ctx.beginPath();
    pts.forEach((p,i)=>{ const x = xForTs(p[0]); const y = yForVal(p[1]); if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); });
    ctx.stroke();
    // tx line
    ctx.strokeStyle = '#9cff9c'; ctx.lineWidth = 2; ctx.beginPath();
    pts.forEach((p,i)=>{ const x = xForTs(p[0]); const y = yForVal(p[2]); if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y); });
    ctx.stroke();
    requestAnimationFrame(draw);
  }
  // fetch every 500ms for smoother updates (backend samples ~2 Hz)
  fetchData();
  setInterval(fetchData, 500);
  requestAnimationFrame(draw);
}

function setupTabs(){
  document.querySelectorAll('.tab').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const name = btn.dataset.tab;
      document.querySelectorAll('.tab-pane').forEach(p=>p.classList.remove('active'));
      const pane = document.getElementById('tab-'+name);
      if(pane) pane.classList.add('active');
    });
  });
}

function isTabActive(name){
  const pane = document.getElementById('tab-'+name);
  return pane && pane.classList.contains('active');
}

async function blockIpNow(){
  const ip = document.getElementById('blockIp').value.trim();
  if(!ip) return;
  try{
    await api('/api/security/block', { method:'POST', body: JSON.stringify({ ip }) });
    await refreshBlocklist();
    document.getElementById('blockIp').value='';
  }catch(e){ alert('Block failed: '+e.message); }
}

async function refreshBlocklist(){
  try{
    const data = await api('/api/security/blocklist');
    const el = document.getElementById('blocklist'); if(!el) return;
    el.innerHTML = '';
    const table = document.createElement('table');
    table.innerHTML = '<thead><tr><th>Blocked IPs</th></tr></thead>';
    const tbody = document.createElement('tbody');
    (data.ips||[]).forEach(ip=>{ const tr = document.createElement('tr'); tr.innerHTML = `<td>${ip}</td>`; tbody.appendChild(tr); });
    table.appendChild(tbody);
    el.appendChild(table);
  }catch{}
}

window.blockIpNow = blockIpNow;

async function loadRouterConfig(){
  try{
    const cfg = await api('/api/router/config');
    const el = document.getElementById('routerCfg'); if(!el) return;
    el.innerHTML = '';
    const pre = document.createElement('pre'); pre.textContent = JSON.stringify(cfg, null, 2); el.appendChild(pre);
    await loadForwards(cfg);
    renderRouterForm(cfg);
  }catch{}
}

async function loadForwards(cfg){
  const list = cfg && cfg.forwards ? cfg.forwards : [];
  const el = document.getElementById('forwards'); if(!el) return;
  el.innerHTML = '';
  const table = document.createElement('table');
  table.innerHTML = '<thead><tr><th>Proto</th><th>In</th><th>Dest IP</th><th>Dest Port</th></tr></thead>';
  const tbody = document.createElement('tbody');
  list.forEach(f=>{ const tr = document.createElement('tr'); tr.innerHTML = `<td>${f.proto}</td><td>${f.in_port}</td><td>${f.dest_ip}</td><td>${f.dest_port}</td>`; tbody.appendChild(tr); });
  table.appendChild(tbody); el.appendChild(table);
}

async function addForward(){
  try{
    const proto = document.getElementById('fwdProto').value;
    const in_port = parseInt(document.getElementById('fwdIn').value, 10);
    const dest_ip = document.getElementById('fwdIp').value.trim();
    const dest_port = parseInt(document.getElementById('fwdDest').value, 10);
    await api('/api/router/forward', { method:'POST', body: JSON.stringify({ proto, in_port, dest_ip, dest_port }) });
    await loadRouterConfig();
  }catch(e){ alert('Failed to add forward: '+e.message); }
}

async function applyRouter(){
  try{
    const res = await api('/api/router/apply', { method:'POST' });
    const outEl = document.getElementById('applyOut'); if(outEl) outEl.textContent = res.output || 'Applied';
  }catch(e){ alert('Apply failed: '+e.message); }
}

async function loadServices(){
  try{
    const data = await api('/api/router/services');
    const el = document.getElementById('services'); if(!el) return;
    el.innerHTML = '';
    const table = document.createElement('table');
    table.innerHTML = '<thead><tr><th>Service</th><th>Status</th></tr></thead>';
    const tbody = document.createElement('tbody');
    const status = data.status || {};
    Object.keys(status).forEach(n=>{ const tr = document.createElement('tr'); tr.innerHTML = `<td>${n}</td><td>${status[n]}</td>`; tbody.appendChild(tr); });
    table.appendChild(tbody); el.appendChild(table);
  }catch{}
}

async function ctlSvc(name, action){
  try{
    await api(`/api/router/services/${name}/${action}`, { method:'POST' });
    await loadServices();
  }catch(e){ alert('Service action failed: '+e.message); }
}

function renderRouterForm(cfg){
  const form = document.getElementById('routerForm'); if(!form) return;
  form.innerHTML = '';
  // LAN
  form.appendChild(sectionTitle('LAN'));
  form.appendChild(field('LAN interface', 'lan.interface', cfg.lan.interface));
  form.appendChild(field('LAN CIDR', 'lan.cidr', cfg.lan.cidr));
  form.appendChild(field('DHCP start', 'lan.dhcp_start', cfg.lan.dhcp_start));
  form.appendChild(field('DHCP end', 'lan.dhcp_end', cfg.lan.dhcp_end));
  // WAN
  form.appendChild(sectionTitle('WAN'));
  form.appendChild(field('WAN interface', 'wan.interface', cfg.wan.interface));
  form.appendChild(selectField('WAN mode', 'wan.mode', ['dhcp','static','pppoe'], cfg.wan.mode));
  form.appendChild(field('Static address', 'wan.static.address', cfg.wan.static.address||''));
  form.appendChild(field('Static gateway', 'wan.static.gateway', cfg.wan.static.gateway||''));
  // Wi‑Fi
  form.appendChild(sectionTitle('Wi‑Fi AP'));
  form.appendChild(field('Wi‑Fi interface', 'wifi.interface', cfg.wifi.interface));
  form.appendChild(field('SSID', 'wifi.ssid', cfg.wifi.ssid));
  form.appendChild(field('PSK', 'wifi.psk', cfg.wifi.psk));
  form.appendChild(field('Country', 'wifi.country', cfg.wifi.country));
  form.appendChild(field('Channel', 'wifi.channel', cfg.wifi.channel));
}

function sectionTitle(text){ const h = document.createElement('h3'); h.textContent = text; h.className='m-0'; return h; }
function field(label, path, value){
  const wrap = document.createElement('div'); wrap.className='field';
  const lab = document.createElement('label'); lab.textContent = label; wrap.appendChild(lab);
  const input = document.createElement('input'); input.value = value??''; input.dataset.path = path; wrap.appendChild(input);
  const btn = document.createElement('button'); btn.textContent='Save'; btn.className='small'; btn.addEventListener('click',()=>saveField(input)); wrap.appendChild(btn);
  return wrap;
}
function selectField(label, path, options, value){
  const wrap = document.createElement('div'); wrap.className='field';
  const lab = document.createElement('label'); lab.textContent = label; wrap.appendChild(lab);
  const sel = document.createElement('select'); options.forEach(o=>{ const op = document.createElement('option'); op.value=o; op.textContent=o; if(o===value) op.selected=true; sel.appendChild(op); }); sel.dataset.path = path; wrap.appendChild(sel);
  const btn = document.createElement('button'); btn.textContent='Save'; btn.className='small'; btn.addEventListener('click',()=>saveField(sel)); wrap.appendChild(btn);
  return wrap;
}
async function saveField(el){
  const path = el.dataset.path.split('.'); const value = el.tagName==='SELECT' ? el.value : el.value;
  await api('/api/router/config', { method:'POST', body: JSON.stringify({ path, value }) });
  await loadRouterConfig();
}

async function loadDomains(){
  try{
    const data = await api('/api/stats/domains?limit=100');
    const list = data.recent || [];
    const el = document.getElementById('domains');
    if(!el) return;
    el.innerHTML = '';
    const table = document.createElement('table');
    table.innerHTML = '<thead><tr><th>Time</th><th>Domain</th></tr></thead>';
    const tbody = document.createElement('tbody');
    list.slice(-100).reverse().forEach(([ts, domain])=>{
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${new Date(ts*1000).toLocaleString()}</td><td>${domain}</td>`;
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    el.appendChild(table);
  }catch{}
}

function showModal(text){
  const m = document.getElementById('modal');
  const body = document.getElementById('modalBody');
  body.textContent = text;
  m.classList.add('open');
}
function closeModal(){ document.getElementById('modal').classList.remove('open'); }
window.closeModal = closeModal;

function showWhy(ev){
  const lines = [];
  lines.push(`Severity: ${ev.severity}`);
  if(ev.ip) lines.push(`IP: ${ev.ip}`);
  if(ev.action) lines.push(`Action: ${ev.action}`);
  if(ev.explanation) lines.push('', 'Explanation:', ev.explanation);
  if(ev.context){
    try{ lines.push('', 'Context:', JSON.stringify(ev.context, null, 2)); }catch{}
  }
  showModal(lines.join('\n'));
}


