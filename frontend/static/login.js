async function api(path, opts={}){
  const res = await fetch(path, { ...opts, credentials: 'include', headers: { 'Content-Type': 'application/json', ...(opts.headers||{}) } });
  if(!res.ok) throw new Error(await res.text());
  return res.json();
}

async function login(){
  const username = document.getElementById('user').value.trim();
  const password = document.getElementById('pass').value;
  const el = document.getElementById('msg');
  try{
    await api('/api/auth/login', { method:'POST', body: JSON.stringify({ username, password }) });
    location.href = '/';
  }catch(e){ el.textContent = 'Login failed'; }
}

document.getElementById('loginBtn').addEventListener('click', login);
const bBtn = document.getElementById('bootstrapBtn');
async function initBootstrap(){
  try{
    const s = await api('/api/auth/bootstrap-allowed');
    const details = document.querySelector('details');
    if(!s.allowed && details){ details.remove(); }
  }catch{}
  if(bBtn){
    bBtn.addEventListener('click', async ()=>{
      const u = document.getElementById('buser').value.trim();
      const p = document.getElementById('bpass').value;
      const el = document.getElementById('bmsg');
      try{
        if(p.length < 10){ el.textContent = 'Password must be at least 10 characters.'; return; }
        await api('/api/auth/bootstrap', { method:'POST', body: JSON.stringify({ username: u, password: p }) });
        el.textContent = 'Admin created. You can now log in.';
      }catch(e){
        try{ const j = JSON.parse(e.message); el.textContent = j.detail || 'Bootstrap failed'; }
        catch{ el.textContent = 'Bootstrap failed'; }
      }
    });
  }
}
initBootstrap();


