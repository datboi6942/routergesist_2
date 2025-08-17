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
  table.innerHTML = `<thead><tr><th>Name</th><th>Type</th><th>State</th><th>IPv4</th><th>Role</th><th class="th-actions"></th></tr></thead>`;
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
  if(typeof startLongTermCharts === 'function'){
    await startLongTermCharts();
  }
  await loadDomains();
  await loadTopDomains();
  await loadSummary();
  await loadConnections();
  await loadTopDomainsByClient();
  await loadClientsByDomain();
  await loadNewDomains();
  await loadActivity();
  await refreshBlocklist();
  setInterval(()=>isTabActive('interfaces')&&loadInterfaces(), 5000);
  setInterval(()=>isTabActive('security')&&loadThreats(), 7000);
  // traffic chart is animated via requestAnimationFrame; no interval needed
  setInterval(()=>isTabActive('analytics')&&loadDomains(), 8000);
  setInterval(()=>isTabActive('analytics')&&loadTopDomains(), 10000);
  setInterval(()=>isTabActive('analytics')&&loadSummary(), 6000);
  setInterval(()=>isTabActive('analytics')&&loadConnections(), 12000);
  setInterval(()=>isTabActive('analytics')&&loadTopDomainsByClient(), 12000);
  setInterval(()=>isTabActive('analytics')&&loadClientsByDomain(), 15000);
  setInterval(()=>isTabActive('analytics')&&loadNewDomains(), 30000);
  setInterval(()=>isTabActive('analytics')&&loadActivity(), 2000);
  // Persist per-minute WAN averages for long-term charts (guarded)
  if(typeof recordLongTermSample === 'function'){
    setInterval(recordLongTermSample, 60000);
  }
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
  const logoutBtn = document.getElementById('logoutBtn'); if(logoutBtn) logoutBtn.addEventListener('click', logoutNow);
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

async function loadActivity(){
  try{
    const data = await api('/api/stats/activity');
    const el = document.getElementById('activity'); if(!el) return;
    el.innerHTML='';
    const table = document.createElement('table');
    table.innerHTML = '<thead><tr><th>Client</th><th>Activity</th><th>Flows</th><th>Signals</th><th>Top Domains</th></tr></thead>';
    const tbody = document.createElement('tbody');
    (data.items||[]).forEach(item=>{
      const tr = document.createElement('tr');
      const sig = `udp443:${item.udp443||0} tcp443:${item.tcp443||0}`;
      const doms = (item.top_domains||[]).join(', ');
      tr.innerHTML = `<td>${item.ip}</td><td>${item.activity}</td><td>${item.flows}</td><td>${sig}</td><td>${doms}</td>`;
      tbody.appendChild(tr);
    });
    table.appendChild(tbody); el.appendChild(table);
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

async function loadClientsByDomain(){
  try{
    const data = await api('/api/stats/clients-by-domain');
    const el = document.getElementById('clientsByDomain'); if(!el) return;
    el.innerHTML='';
    const table = document.createElement('table');
    table.innerHTML = '<thead><tr><th>Domain</th><th>Clients</th></tr></thead>';
    const tbody = document.createElement('tbody');
    const by = data.by_domain || {};
    Object.keys(by).forEach(domain=>{
      const items = by[domain].map(([client,count])=>`${client} (${count})`).join(', ');
      const tr = document.createElement('tr'); tr.innerHTML = `<td>${domain}</td><td>${items}</td>`; tbody.appendChild(tr);
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
let __traffic = {buffer: [], nic: null, lastFetch: 0, ltMaxBytes: 0, ltLastFetch: 0};
// Expose selected NIC so long-term charts can use the same interface for consistent scales
window.__traffic = __traffic;
async function startTrafficChart(){
  const single = document.getElementById('trafficChart');
  const cvsWan = document.getElementById('trafficChartWan');
  const cvsLan = document.getElementById('trafficChartLan');
  const wanNicName = document.getElementById('wanNicName');
  const lanNicName = document.getElementById('lanNicName');
  const isDual = !!(cvsWan && cvsLan);
  if(!single && !isDual) return;
  const ctxSingle = single ? single.getContext('2d') : null;
  const ctxWan = cvsWan ? cvsWan.getContext('2d') : null;
  const ctxLan = cvsLan ? cvsLan.getContext('2d') : null;
  // ensure device pixel ratio scaling for crisp lines
  function scaleCanvas(cvs, ctx){
    if(!cvs || !ctx) return;
    const dpr = Math.max(1, Math.min(2, (window.devicePixelRatio || 1)));
    // Use bounding box to be more reliable on mobile when canvas has no explicit width/height attributes
    const rect = cvs.getBoundingClientRect();
    const cssW = Math.max(320, Math.floor(rect.width));
    const cssH = Math.max(180, Math.floor(rect.height || 220));
    const targetW = Math.floor(cssW * dpr);
    const targetH = Math.floor(cssH * dpr);
    if(cvs.width !== targetW || cvs.height !== targetH){
      cvs.width = targetW;
      cvs.height = targetH;
      ctx.setTransform(dpr,0,0,dpr,0,0);
    }
  }
  // optional NIC selector (legacy single-chart UI)
  const nicSel = document.getElementById('trafficNic');
  async function fetchData(){
    try{
      const [tData, sData] = await Promise.all([
        api('/api/stats/traffic'),
        api('/api/stats/summary')
      ]);
      const pernic = tData.pernic || {}; const nics = Object.keys(pernic);
      if(nics.length===0) return;
      // Prefer roles from summary when available
      const perSummary = (sData && sData.pernic) ? sData.pernic : {};
      let roleWan = null, roleLan = null;
      Object.keys(perSummary).forEach(n=>{
        const r = perSummary[n] && perSummary[n].role; if(r==='WAN') roleWan = n; if(r==='LAN') roleLan = n;
      });
      // Build candidate NICs (exclude loopback, docker, veth, bridges, tunnels)
      const isExcluded = (name)=> /^(lo|docker\d*|br-|veth|virbr|tun|tap|wg)/.test(name);
      const candidates = nics.filter(n=>!isExcluded(n));
      // If dual charts, pick WAN/LAN by roles first, then heuristics; avoid selecting the same NIC twice
      if(isDual){
        let bestWan=roleWan && candidates.includes(roleWan) ? roleWan : null;
        let bestLan=roleLan && candidates.includes(roleLan) ? roleLan : null;
        let bestWanVal=-1, bestLanVal=-1;
        const endTs = Date.now()/1000; const startTs = endTs - 120;
        const nicList = candidates.length ? candidates : nics;
        for(const nic of nicList){
          const pts = pernic[nic] || [];
          const recent = pts.filter(p=>p[0] >= startTs);
          if(recent.length){
            const avgRx = recent.reduce((a,b)=>a+b[1],0)/recent.length;
            const avgTx = recent.reduce((a,b)=>a+b[2],0)/recent.length;
            if(!bestWan && avgRx > bestWanVal){ bestWanVal = avgRx; bestWan = nic; }
            // Prefer AP-like names for LAN/AP if possible
            const preferAp = /^wl|^uap0/.test(nic) ? 1 : 0;
            const score = avgTx + preferAp * avgTx; // bias wireless
            if((!bestLan && (nic !== bestWan)) || (nic !== bestWan && score > bestLanVal)){
              bestLanVal = score; bestLan = nic;
            }
          }
        }
        __traffic.nic = bestWan || (candidates[0] || nics[0]);
        const lanPick = bestLan && bestLan !== __traffic.nic ? bestLan : ((candidates.find(n=>n!==__traffic.nic)) || __traffic.nic);
        __traffic.buffer = (pernic[__traffic.nic] || []).slice(-7200);
        __traffic.bufferLan = (pernic[lanPick] || []).slice(-7200);
        if(wanNicName) wanNicName.textContent = __traffic.nic;
        if(lanNicName) lanNicName.textContent = lanPick;
        __traffic.lanNic = lanPick;
        __traffic.lastFetch = performance.now();
        // Refresh long-term 1h max occasionally for consistent scale with bottom charts
        if(!__traffic.ltLastFetch || (performance.now() - __traffic.ltLastFetch) > 30000){
          try{
            const lt1h = await api(`/api/stats/longterm?window_seconds=${3600}&nic=${encodeURIComponent(__traffic.nic)}`);
            const arr = (lt1h.pernic && lt1h.pernic[__traffic.nic]) ? lt1h.pernic[__traffic.nic] : [];
            let maxB = 0; arr.forEach(p=>{ if(p[1]>maxB) maxB=p[1]; if(p[2]>maxB) maxB=p[2]; });
            __traffic.ltMaxBytes = maxB;
            __traffic.ltLastFetch = performance.now();
          }catch{}
        }
        return;
      }
      // Single chart path: populate selector on first load
      if(nicSel && !nicSel.dataset.filled){
        nicSel.innerHTML = '';
        nics.forEach(n=>{ const op=document.createElement('option'); op.value=n; op.textContent=n; nicSel.appendChild(op); });
        nicSel.dataset.filled = '1';
        nicSel.addEventListener('change', ()=>{ __traffic.nic = nicSel.value; });
      }
      if(!__traffic.nic){ __traffic.nic = nicSel && nicSel.value ? nicSel.value : nics[0]; if(nicSel && !nicSel.value) nicSel.value = __traffic.nic; }
      const points = pernic[__traffic.nic] || [];
      // Backend now keeps 1 hour at ~2 Hz. We keep the whole hour (7200 points max)
      __traffic.buffer = points.slice(-7200);
      __traffic.lastFetch = performance.now();
      if(!__traffic.ltLastFetch || (performance.now() - __traffic.ltLastFetch) > 30000){
        try{
          const lt1h = await api(`/api/stats/longterm?window_seconds=${3600}&nic=${encodeURIComponent(__traffic.nic)}`);
          const arr = (lt1h.pernic && lt1h.pernic[__traffic.nic]) ? lt1h.pernic[__traffic.nic] : [];
          let maxB = 0; arr.forEach(p=>{ if(p[1]>maxB) maxB=p[1]; if(p[2]>maxB) maxB=p[2]; });
          __traffic.ltMaxBytes = maxB;
          __traffic.ltLastFetch = performance.now();
        }catch{}
      }
    }catch{}
  }
  function draw(){
    if(isDual){
      if(ctxWan){ scaleCanvas(cvsWan, ctxWan); drawOne(cvsWan, ctxWan, __traffic.buffer || []); }
      if(ctxLan){ scaleCanvas(cvsLan, ctxLan); drawOne(cvsLan, ctxLan, __traffic.bufferLan || []); }
      requestAnimationFrame(draw); return;
    }
    if(!ctxSingle || !single){ requestAnimationFrame(draw); return; }
    scaleCanvas(single, ctxSingle);
    drawOne(single, ctxSingle, __traffic.buffer || []);
    requestAnimationFrame(draw);
  }
  // fetch every 500ms for smoother updates (backend samples ~2 Hz)
  fetchData();
  setInterval(fetchData, 500);
  requestAnimationFrame(draw);
}

// Compute dynamic Y-axis params with nice steps and adaptive units (bps/kbps/Mbps/Gbps)
function computeYAxisParams(maxBytesPerSec){
  const maxBps = Math.max(1, maxBytesPerSec * 8);
  const niceStep = (raw)=>{
    const pow10 = Math.pow(10, Math.floor(Math.log10(raw)));
    const base = raw / pow10;
    let factor = 1;
    if(base <= 1) factor = 1; else if(base <= 2) factor = 2; else if(base <= 5) factor = 5; else factor = 10;
    return factor * pow10;
  };
  let stepBps = niceStep(maxBps / 4);
  let yMaxBps = stepBps * 4;
  if(maxBps > yMaxBps * 0.98){ yMaxBps += stepBps; }
  let unit = 'bps'; let unitDiv = 1;
  if(yMaxBps >= 1_000_000_000){ unit='Gbps'; unitDiv=1_000_000_000; }
  else if(yMaxBps >= 1_000_000){ unit='Mbps'; unitDiv=1_000_000; }
  else if(yMaxBps >= 1_000){ unit='kbps'; unitDiv=1_000; }
  const ticksBps = [];
  for(let i=0;i<=4;i++){ ticksBps.push((yMaxBps * i) / 4); }
  return { yMaxBps, unit, unitDiv, ticksBps };
}

function formatTick(bps, unit, unitDiv){
  const val = bps / unitDiv;
  const decimals = val < 10 ? 1 : 0;
  return val.toFixed(decimals) + ' ' + unit;
}

function drawOne(cvs, ctx, pts){
  const w = cvs.width = cvs.clientWidth; const h = cvs.height = 220;
  ctx.clearRect(0,0,w,h);
  if(pts.length<2) return;
  const windowSec = 60*60; const tEnd = pts[pts.length-1][0]; const tStart = tEnd - windowSec;
  const xForTs = (ts)=> ((ts - tStart) / windowSec) * w;
  const rx = pts.map(p=>p[1]); const tx = pts.map(p=>p[2]); const max = Math.max(1, ...rx, ...tx);
  // paddings to ensure labels and legend are not obscured by the graph
  const topPad = 28; const bottomPad = 44;
  const chartHeight = h - topPad - bottomPad;
  ctx.strokeStyle = '#2a2f3a'; ctx.lineWidth = 1; ctx.beginPath();
  for(let i=0;i<5;i++){ const y = topPad + chartHeight * (i/4); ctx.moveTo(0,y); ctx.lineTo(w,y); } ctx.stroke();
  // Dynamic Y-axis in bps with adaptive units; include 1h long-term peak for consistency
  const maxForScale = Math.max(max, __traffic.ltMaxBytes || 0);
  const yAxis = computeYAxisParams(maxForScale);
  ctx.fillStyle = '#7a8290'; ctx.font = '12px system-ui';
  for(let i=0;i<=4;i++){
    const y = topPad + chartHeight * (1 - i/4);
    ctx.fillText(formatTick(yAxis.ticksBps[i], yAxis.unit, yAxis.unitDiv), 6, Math.max(12, Math.min(h-4, y-2)));
  }
  // minute ticks: dense markers every 1 min, labels every 5 min; include "Now" label at right
  const minute = 60; ctx.fillStyle = '#7a8290';
  const tickY0 = h - bottomPad + 6; const tickY1 = tickY0 + 4; const labelY = h - 6;
  ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
  for(let m=0; m<=60; m+=1){
    const ts = tStart + m*minute; const x = xForTs(ts);
    ctx.beginPath(); ctx.moveTo(x, tickY0); ctx.lineTo(x, tickY1); ctx.strokeStyle = '#2a2f3a'; ctx.stroke();
    // Label only every 10 minutes to prevent clutter; skip the final label near "Now"
    if(m%10===0){
      if(x > w - 48) continue; // avoid collision with "Now"
      const lab = new Date(ts*1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
      ctx.fillText(lab, Math.max(20, Math.min(w-20, x)), labelY);
    }
  }
  // "Now" label at right edge
  ctx.textAlign = 'right'; ctx.fillText('Now', w-8, labelY);
  ctx.strokeStyle = '#5b9cff'; ctx.lineWidth = 2; ctx.beginPath();
  let started = false;
  pts.forEach((p)=>{ if(p[0] < tStart) return; const x=xForTs(p[0]); const y= topPad + chartHeight - ((p[1]*8)/yAxis.yMaxBps)*chartHeight; if(x<=0||x>=w) return; if(!started){ ctx.moveTo(x,y); started=true; } else { ctx.lineTo(x,y); } }); if(started) ctx.stroke();
  ctx.strokeStyle = '#9cff9c'; ctx.lineWidth = 2; ctx.beginPath(); started=false;
  pts.forEach((p)=>{ if(p[0] < tStart) return; const x=xForTs(p[0]); const y= topPad + chartHeight - ((p[2]*8)/yAxis.yMaxBps)*chartHeight; if(x<=0||x>=w) return; if(!started){ ctx.moveTo(x,y); started=true; } else { ctx.lineTo(x,y); } }); if(started) ctx.stroke();
  // Legend (top-right, above chart area)
  const legendX = Math.max(8, w - 170); const legendY = 8;
  ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#5b9cff'; ctx.fillRect(legendX, legendY, 12, 4);
  ctx.fillStyle = '#7a8290'; ctx.fillText('RX (download)', legendX+18, legendY+6);
  ctx.fillStyle = '#9cff9c'; ctx.fillRect(legendX, legendY+14, 12, 4);
  ctx.fillStyle = '#7a8290'; ctx.fillText('TX (upload)', legendX+18, legendY+20);
}

// Long-term charts (24h and 7d)
async function startLongTermCharts(){
  const c24 = document.getElementById('lt24');
  const c7 = document.getElementById('lt7d');
  if(!c24 && !c7) return;
  const ctx24 = c24 ? c24.getContext('2d') : null;
  const ctx7 = c7 ? c7.getContext('2d') : null;

  function scaleCanvasLT(cvs, ctx){
    if(!cvs || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const cssW = cvs.clientWidth || 600;
    const cssH = cvs.clientHeight || 220;
    if(cvs.width !== Math.floor(cssW*dpr)){
      cvs.width = Math.floor(cssW*dpr);
      cvs.height = Math.floor(cssH*dpr);
      ctx.setTransform(dpr,0,0,dpr,0,0);
    }
  }

  async function pickWanNic(){
    // 0) Use the same NIC as the live WAN chart if available
    try{
      if(window.__traffic && window.__traffic.nic){ return window.__traffic.nic; }
    }catch{}
    // 1) Prefer configured WAN from router config
    try{
      const cfg = await api('/api/router/config');
      const nic = cfg && cfg.wan && cfg.wan.interface;
      if(nic) return nic;
    }catch{}
    // 2) Try summary roles
    try{
      const s = await api('/api/stats/summary');
      const per = s.pernic || {};
      let wan = Object.keys(per).find(n=> per[n] && per[n].role === 'WAN');
      if(wan) return wan;
      // fallback to NIC with highest rx
      let best = null; let bestVal = -1;
      Object.keys(per).forEach(n=>{ const v = per[n].rx_bps||0; if(v>bestVal){best=n; bestVal=v;} });
      if(best) return best;
    }catch{}
    // 3) Fallback to long-term keys (most samples)
    try{
      const lt = await api(`/api/stats/longterm?window_seconds=${24*3600}`);
      const pernic = lt.pernic || {};
      let candidate = null; let maxLen = -1;
      Object.keys(pernic).forEach(n=>{ const l = (pernic[n]||[]).length; if(l>maxLen){ maxLen=l; candidate=n; } });
      return candidate;
    }catch{ return null; }
  }

  function drawLongTerm(cvs, ctx, pts, windowSeconds){
    if(!cvs || !ctx) return;
    scaleCanvasLT(cvs, ctx);
    const w = cvs.width; const h = cvs.height;
    ctx.clearRect(0,0,w,h);
    if(!pts || pts.length < 2){
      // Show placeholder message so users know to wait for samples
      ctx.fillStyle = '#7a8290';
      ctx.font = '12px system-ui';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('Collecting data… (first point appears in ~1 min)', w/2, h/2);
      return;
    }
    const tEnd = pts[pts.length-1][0];
    const tStart = tEnd - windowSeconds;
    const xForTs = (ts)=> ((ts - tStart) / windowSeconds) * w;
    const rx = pts.map(p=>p[1]); const tx = pts.map(p=>p[2]);
    const max = Math.max(1, ...rx, ...tx);
    // Ensure long-term y-axis matches current live chart scale when available
    let yAxis = computeYAxisParams(max);
    try{
      if(window.__traffic && Array.isArray(window.__traffic.buffer) && window.__traffic.buffer.length){
        const liveRx = window.__traffic.buffer.map(p=>p[1]);
        const liveTx = window.__traffic.buffer.map(p=>p[2]);
        const liveMax = Math.max(1, ...liveRx, ...liveTx);
        // Use the larger of the two to keep scales consistent
        const targetMax = Math.max(max, liveMax);
        yAxis = computeYAxisParams(targetMax);
      }
    }catch{}
    const topPad = 28; const bottomPad = 44;
    const chartHeight = h - topPad - bottomPad;
    // grid
    ctx.strokeStyle = '#2a2f3a'; ctx.lineWidth = 1; ctx.beginPath();
    for(let i=0;i<5;i++){ const y = topPad + chartHeight * (i/4); ctx.moveTo(0,y); ctx.lineTo(w,y); } ctx.stroke();
    // dynamic y-axis (reusing computed yAxis above)
    ctx.fillStyle = '#7a8290'; ctx.font = '12px system-ui';
    for(let i=0;i<=4;i++){
      const y = topPad + chartHeight * (1 - i/4);
      ctx.fillText(formatTick(yAxis.ticksBps[i], yAxis.unit, yAxis.unitDiv), 6, Math.max(12, Math.min(h-4, y-2)));
    }
    // x ticks: 1h ticks for 24h, 12h ticks for 7d; sparse labels to avoid overlap
    const labelEvery = windowSeconds <= 24*3600 ? 4*3600 : 24*3600;
    const tickEvery = windowSeconds <= 24*3600 ? 3600 : 12*3600;
    const tickY0 = h - bottomPad + 6; const tickY1 = tickY0 + 4; const labelY = h - 6;
    ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
    for(let ts = Math.ceil(tStart/tickEvery)*tickEvery; ts<=tEnd; ts+=tickEvery){
      const x = xForTs(ts); ctx.beginPath(); ctx.moveTo(x, tickY0); ctx.lineTo(x, tickY1); ctx.strokeStyle = '#2a2f3a'; ctx.stroke();
    }
    const minSpacing = 64; let lastLabelX = -1e9;
    for(let ts = Math.ceil(tStart/labelEvery)*labelEvery; ts<=tEnd; ts+=labelEvery){
      const x = xForTs(ts);
      if(x - lastLabelX < minSpacing) continue;
      const opt = windowSeconds <= 24*3600 ? {hour:'2-digit'} : {month:'2-digit', day:'2-digit'};
      const lab = new Date(ts*1000).toLocaleString([], opt);
      ctx.fillStyle = '#7a8290'; ctx.fillText(lab, Math.max(20, Math.min(w-28, x)), labelY);
      lastLabelX = x;
    }
    // Right-edge "Now" label
    ctx.textAlign = 'right'; ctx.fillText('Now', w-8, labelY);
    // lines
    ctx.strokeStyle = '#5b9cff'; ctx.lineWidth = 2; ctx.beginPath(); let started=false;
    pts.forEach((p)=>{ if(p[0] < tStart) return; const x=xForTs(p[0]); const y= topPad + chartHeight - ((p[1]*8)/yAxis.yMaxBps)*chartHeight; if(x<=0||x>=w) return; if(!started){ ctx.moveTo(x,y); started=true; } else { ctx.lineTo(x,y); } }); if(started) ctx.stroke();
    ctx.strokeStyle = '#9cff9c'; ctx.lineWidth = 2; ctx.beginPath(); started=false;
    pts.forEach((p)=>{ if(p[0] < tStart) return; const x=xForTs(p[0]); const y= topPad + chartHeight - ((p[2]*8)/yAxis.yMaxBps)*chartHeight; if(x<=0||x>=w) return; if(!started){ ctx.moveTo(x,y); started=true; } else { ctx.lineTo(x,y); } }); if(started) ctx.stroke();
    // legend
    const legendX = Math.max(8, w - 170); const legendY = 8;
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = '#5b9cff'; ctx.fillRect(legendX, legendY, 12, 4);
    ctx.fillStyle = '#7a8290'; ctx.fillText('RX (download)', legendX+18, legendY+6);
    ctx.fillStyle = '#9cff9c'; ctx.fillRect(legendX, legendY+14, 12, 4);
    ctx.fillStyle = '#7a8290'; ctx.fillText('TX (upload)', legendX+18, legendY+20);
  }

  async function refresh(){
    const wan = await pickWanNic();
    if(!wan) return;
    try{
      if(ctx24){
        const d24 = await api(`/api/stats/longterm?window_seconds=${24*3600}&nic=${encodeURIComponent(wan)}`);
        let pts24 = (d24.pernic && d24.pernic[wan]) ? d24.pernic[wan] : [];
        if((!pts24 || pts24.length < 2)){
          // Fallback: aggregate all NICs so user still sees activity
          const all24 = await api(`/api/stats/longterm?window_seconds=${24*3600}`);
          const per = all24.pernic || {};
          pts24 = mergeAllNics(per);
        }
        drawLongTerm(c24, ctx24, pts24, 24*3600);
      }
      if(ctx7){
        const d7 = await api(`/api/stats/longterm?window_seconds=${7*24*3600}&nic=${encodeURIComponent(wan)}`);
        let pts7 = (d7.pernic && d7.pernic[wan]) ? d7.pernic[wan] : [];
        if((!pts7 || pts7.length < 2)){
          const all7 = await api(`/api/stats/longterm?window_seconds=${7*24*3600}`);
          const per7 = all7.pernic || {};
          pts7 = mergeAllNics(per7);
        }
        drawLongTerm(c7, ctx7, pts7, 7*24*3600);
      }
    }catch{}
  }

  function mergeAllNics(pernic){
    // Merge by minute bucket to handle slightly different sample times
    const bucket = new Map();
    Object.values(pernic).forEach(arr=>{
      (arr||[]).forEach(([ts,rx,tx])=>{
        const key = Math.round(ts/60)*60;
        const prev = bucket.get(key) || [key,0,0];
        prev[1]+=rx; prev[2]+=tx; bucket.set(key, prev);
      });
    });
    return Array.from(bucket.values()).sort((a,b)=>a[0]-b[0]);
  }

  await refresh();
  setInterval(refresh, 30000);
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

async function logoutNow(){
  try{
    await api('/api/auth/logout', { method:'POST' });
  }catch{}
  // Always redirect to login to clear any local state
  location.href = '/static/login.html';
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


