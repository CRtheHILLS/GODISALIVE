#!/usr/bin/env python3
"""지식 그래프 지도(map.html) 렌더러 — 단일 파일, 외부 의존성 없음, 시스템 폰트.
캔버스 힘-배치(force layout)를 직접 구현했다 (10년 뒤에도 그대로 열리도록 라이브러리 없이)."""
import json
from pathlib import Path

COLORS = {  # subtype → 색
    "lectures": "#8a2b5a", "readings": "#8a5a2b", "books": "#6d3b12", "people": "#274c66", "places": "#1d7a3f",
    "themes": "#b07d1e", "words": "#5b3f8a", "timeline": "#3b6b8a", "knowledge": "#8a5a2b",
    "archaeology": "#1d7a3f", "history": "#2f6f4f", "manuscripts": "#2a7a7a", "science": "#4f7a2f", "evidence": "#1d7a3f",
    "verse": "#2b6cb0", "tag": "#b8b0a4", "missing": "#c0392b", "speaker": "#c2185b",
}
LABELS = {"lectures": "설교·강의", "readings": "봉독", "books": "성경 권", "people": "인물", "places": "장소", "themes": "주제",
          "words": "원어", "timeline": "연대", "archaeology": "고고학 증거", "history": "문헌 증거", "manuscripts": "사본 증거",
          "science": "과학 증거", "verse": "성경 장", "tag": "태그", "missing": "아직 없는 노트", "speaker": "설교자·강사"}

TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GODISALIVE 지식지도</title>
<style>
:root{--bg:#faf6ee;--card:#fff;--ink:#2b2620;--sub:#6b6156;--accent:#8a5a2b;--line:#e6ddcd}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;background:var(--bg);color:var(--ink);font-family:"Malgun Gothic","맑은 고딕","Noto Sans KR",sans-serif;font-size:15px;overflow:hidden}
#top{position:fixed;left:0;right:0;top:0;height:56px;display:flex;gap:14px;align-items:center;padding:0 16px;background:rgba(250,246,238,.95);border-bottom:2px solid var(--accent);z-index:5;flex-wrap:wrap}
#top h1{font-size:17px;letter-spacing:.15em;color:var(--accent)} #top .n{color:var(--sub);font-size:13px}
#top label{font-size:13px;cursor:pointer;user-select:none} #top input[type=search]{padding:5px 9px;border:1px solid var(--line);border-radius:8px;font-size:14px;width:200px}
#top button{padding:5px 10px;border:1px solid var(--accent);background:#fff;color:var(--accent);border-radius:8px;cursor:pointer;font-size:13px}
canvas{position:fixed;left:0;top:56px;width:100%;height:calc(100% - 56px);cursor:grab}
#side{position:fixed;right:0;top:56px;bottom:0;width:340px;background:var(--card);border-left:1px solid var(--line);padding:18px;overflow:auto;transform:translateX(100%);transition:transform .2s;z-index:4;font-size:14px;line-height:1.6}
#side.on{transform:none} #side h2{font-size:19px;margin:4px 0 8px;line-height:1.35} #side .k{color:var(--sub);font-size:12px;letter-spacing:.1em}
#side .pill{display:inline-block;border-radius:6px;padding:0 8px;color:#fff;font-size:12px;margin-right:6px}
#side ul{margin:4px 0 12px 18px} #side li{cursor:pointer} #side li:hover{color:var(--accent)} #side a{color:#274c66}
#side .x{position:absolute;right:12px;top:10px;border:0;background:none;font-size:20px;cursor:pointer;color:var(--sub)}
#legend{position:fixed;left:14px;bottom:14px;background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:10px;padding:10px 14px;font-size:12.5px;z-index:4;max-width:260px}
#legend span.d{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px;vertical-align:-1px}
#legend .row{display:inline-block;margin:2px 10px 2px 0}
#tip{position:fixed;pointer-events:none;background:#2b2620;color:#fff;padding:4px 9px;border-radius:6px;font-size:13px;display:none;z-index:6;max-width:360px}
</style></head><body>
<div id="top"><h1>GODISALIVE · 지식지도</h1><span class="n" id="counts"></span>
<input type="search" id="q" placeholder="찾기 (제목·id·구절)">
<label><input type="checkbox" data-t="knowledge" checked> 지식 노트</label>
<label><input type="checkbox" data-t="evidence" checked> 증거</label>
<label><input type="checkbox" data-t="verse" checked> 성경 장</label>
<label><input type="checkbox" data-t="speaker" checked> 설교자</label>
<label><input type="checkbox" data-t="tag"> 태그</label>
<label><input type="checkbox" data-t="missing" checked> 끊어진 링크</label>
<button id="relayout">다시 배치</button><span class="n" id="gen"></span></div>
<canvas id="c"></canvas>
<div id="side"><button class="x" id="close">×</button><div id="detail"></div></div>
<div id="legend"></div><div id="tip"></div>
<script>
const G = __DATA__; const COLORS = __COLORS__; const LABELS = __LABELS__;
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let W, H, dpr = window.devicePixelRatio || 1;
function resize(){ W = innerWidth; H = innerHeight - 56; cv.width = W*dpr; cv.height = H*dpr; cv.style.width = W+'px'; cv.style.height = H+'px'; ctx.setTransform(dpr,0,0,dpr,0,0); }
addEventListener('resize', resize); resize();
const byId = {}; G.nodes.forEach(n => { byId[n.id] = n; n.color = COLORS[n.subtype] || COLORS[n.type] || '#888'; n.r = 4 + Math.sqrt(n.degree||0)*2.4; });
G.edges.forEach(e => { e.s = byId[e.source]; e.t = byId[e.target]; });
const nb = {}; G.edges.forEach(e => { (nb[e.source] = nb[e.source]||[]).push(e.t); (nb[e.target] = nb[e.target]||[]).push(e.s); });
let vis = {knowledge:true, evidence:true, verse:true, tag:false, missing:true, speaker:true}, query = '';
function shown(n){ if(!vis[n.type]) return false; if(!query) return true; const q = query.toLowerCase();
  return (n.title||'').toLowerCase().includes(q) || n.id.toLowerCase().includes(q) || (n.verses||[]).join(' ').toLowerCase().includes(q); }
let cam = {x:0, y:0, k:1}, drag = null, hover = null, sel = null, alpha = 1;
function seed(){ G.nodes.forEach((n,i) => { const a = i*2.399963, r = 40*Math.sqrt(i)+20; n.x = Math.cos(a)*r; n.y = Math.sin(a)*r; n.vx = n.vy = 0; }); alpha = 1; }
seed();
function tick(){ // 단순 힘-배치: 밀어내기 + 선 당기기 + 중심 끌림
  const ns = G.nodes.filter(shown); const n = ns.length; if(!n) return;
  const rep = n > 600 ? 900 : 1600;
  for(let i=0;i<n;i++){ const a = ns[i]; for(let j=i+1;j<n;j++){ const b = ns[j]; let dx = a.x-b.x, dy = a.y-b.y; let d2 = dx*dx+dy*dy+0.01; if(d2 > 250000) continue;
      const f = rep/d2; const d = Math.sqrt(d2); dx/=d; dy/=d; a.vx += dx*f; a.vy += dy*f; b.vx -= dx*f; b.vy -= dy*f; } }
  G.edges.forEach(e => { if(!shown(e.s)||!shown(e.t)) return; const dx = e.t.x-e.s.x, dy = e.t.y-e.s.y, d = Math.sqrt(dx*dx+dy*dy)+0.01;
      const L = e.kind==='tag' ? 140 : e.kind==='verse' ? 90 : e.kind==='speaker' ? 80 : 70; const k = (e.kind==='tag'?0.004:0.02)*(d-L)/d; e.s.vx += dx*k; e.s.vy += dy*k; e.t.vx -= dx*k; e.t.vy -= dy*k; });
  ns.forEach(a => { a.vx -= a.x*0.003; a.vy -= a.y*0.003; if(drag && drag.n===a) return; a.x += a.vx*alpha; a.y += a.vy*alpha; a.vx *= 0.6; a.vy *= 0.6; });
  alpha = Math.max(0.02, alpha*0.995);
}
function draw(){ ctx.clearRect(0,0,W,H); ctx.save(); ctx.translate(W/2+cam.x, H/2+cam.y); ctx.scale(cam.k, cam.k);
  const hl = sel || hover; const hlSet = hl ? new Set([hl.id, ...(nb[hl.id]||[]).map(m=>m.id)]) : null;
  G.edges.forEach(e => { if(!shown(e.s)||!shown(e.t)) return; const on = hlSet && (e.s===hl||e.t===hl);
      ctx.beginPath(); ctx.moveTo(e.s.x,e.s.y); ctx.lineTo(e.t.x,e.t.y);
      ctx.setLineDash(e.kind==='verse' ? [3,4] : e.kind==='tag' ? [1,5] : []);
      ctx.strokeStyle = on ? '#c0392b' : e.kind==='evidence' ? 'rgba(29,122,63,.55)' : e.kind==='verse' ? 'rgba(43,108,176,.45)' : e.kind==='tag' ? 'rgba(0,0,0,.08)' : 'rgba(43,38,32,.35)';
      ctx.lineWidth = (on ? 2.2 : e.kind==='evidence' ? 1.6 : 1)/cam.k; ctx.stroke(); });
  ctx.setLineDash([]);
  const many = G.nodes.filter(shown).length > 250;
  G.nodes.forEach(n => { if(!shown(n)) return; const dim = hlSet && !hlSet.has(n.id);
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, 7); ctx.fillStyle = dim ? '#ddd6ca' : n.color; ctx.fill();
      if(n.type==='missing'){ ctx.setLineDash([2,2]); ctx.strokeStyle = '#c0392b'; ctx.lineWidth = 1.5/cam.k; ctx.stroke(); ctx.setLineDash([]); }
      if(n===sel){ ctx.strokeStyle = '#2b2620'; ctx.lineWidth = 2.5/cam.k; ctx.stroke(); }
      if(!dim && (!many || n.degree >= 3 || n===hl) && n.type!=='tag'){ ctx.font = Math.max(11, 13/cam.k) + 'px "Malgun Gothic","맑은 고딕",sans-serif'; ctx.fillStyle = '#2b2620'; ctx.textAlign = 'center';
          ctx.fillText((n.title||n.id).slice(0,28), n.x, n.y + n.r + 13/cam.k); } });
  ctx.restore(); }
function loop(){ tick(); draw(); requestAnimationFrame(loop); } loop();
function pick(mx, my){ const x = (mx - W/2 - cam.x)/cam.k, y = (my - 56 - H/2 - cam.y)/cam.k; let best = null, bd = 1e9;
  G.nodes.forEach(n => { if(!shown(n)) return; const d = Math.hypot(n.x-x, n.y-y); if(d < n.r + 6/cam.k && d < bd){ bd = d; best = n; } }); return best; }
const tip = document.getElementById('tip');
cv.addEventListener('mousemove', ev => { if(drag){ if(drag.n){ drag.n.x = (ev.clientX - W/2 - cam.x)/cam.k; drag.n.y = (ev.clientY - 56 - H/2 - cam.y)/cam.k; alpha = Math.max(alpha, .3); } else { cam.x = drag.cx + ev.clientX - drag.mx; cam.y = drag.cy + ev.clientY - drag.my; } return; }
  hover = pick(ev.clientX, ev.clientY); cv.style.cursor = hover ? 'pointer' : 'grab';
  if(hover){ tip.style.display = 'block'; tip.style.left = (ev.clientX+14)+'px'; tip.style.top = (ev.clientY+10)+'px'; tip.textContent = (hover.title||hover.id) + '  · 연결 ' + (hover.degree||0); } else tip.style.display = 'none'; });
cv.addEventListener('mousedown', ev => { const n = pick(ev.clientX, ev.clientY); drag = n ? {n} : {mx:ev.clientX, my:ev.clientY, cx:cam.x, cy:cam.y}; drag.sx = ev.clientX; drag.sy = ev.clientY; });
addEventListener('mouseup', ev => { if(drag && Math.hypot(ev.clientX-drag.sx, ev.clientY-drag.sy) < 4){ select(pick(ev.clientX, ev.clientY)); } drag = null; });
cv.addEventListener('wheel', ev => { ev.preventDefault(); const f = ev.deltaY < 0 ? 1.12 : 1/1.12; const mx = ev.clientX - W/2, my = ev.clientY - 56 - H/2;
  cam.x = mx - (mx - cam.x)*f; cam.y = my - (my - cam.y)*f; cam.k *= f; }, {passive:false});
const side = document.getElementById('side'), det = document.getElementById('detail');
function esc(s){ return String(s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function row(k, v){ return '<div class="k" style="margin-top:8px">' + k + '</div><div>' + v + '</div>'; }
function select(n){ sel = n; if(!n){ side.classList.remove('on'); return; } side.classList.add('on');
  const kind = LABELS[n.subtype] || LABELS[n.type] || n.type; const nbs = (nb[n.id]||[]).filter(m => m.id !== n.id);
  const groups = {}; nbs.forEach(m => { const k = LABELS[m.subtype]||LABELS[m.type]||m.type; (groups[k] = groups[k]||[]).push(m); });
  let h = '<span class="pill" style="background:' + n.color + '">' + esc(kind) + '</span>' + (n.grade ? '<span class="pill" style="background:#1d7a3f">등급 ' + esc(n.grade) + '</span>' : '') + '<h2>' + esc(n.title||n.id) + '</h2>';
  h += '<div class="k">ID</div><div style="font-size:12.5px;color:#6b6156;word-break:break-all">' + esc(n.id) + '</div>';
  if(n.path) h += row('파일', '<a href="' + esc(n.uri) + '" target="_blank">' + esc(n.path) + '</a>');
  if(n.source) h += row('출처 영상', '<a href="' + esc(n.source) + '" target="_blank">' + esc(n.source) + '</a>');
  if(n.speaker) h += row('화자', esc(n.speaker));
  if(n.date) h += row('날짜', esc(n.date));
  if(n.verses && n.verses.length) h += row('구절', esc(n.verses.join(' · ')));
  if(n.tags && n.tags.length) h += row('태그', esc(n.tags.join(', ')));
  h += '<div class="k" style="margin-top:12px">연결 ' + nbs.length + '</div>';
  Object.keys(groups).sort().forEach(k => { h += '<div style="margin-top:6px;font-weight:bold;font-size:13px">' + esc(k) + ' (' + groups[k].length + ')</div><ul>' + groups[k].map(m => '<li data-id="' + esc(m.id) + '">' + esc(m.title||m.id) + '</li>').join('') + '</ul>'; });
  det.innerHTML = h;
  det.querySelectorAll('li').forEach(li => li.onclick = () => { const m = byId[li.dataset.id]; if(!m) return;
    if(!vis[m.type]){ vis[m.type] = true; document.querySelector('[data-t=' + m.type + ']').checked = true; }
    select(m); cam.x = -m.x*cam.k; cam.y = -m.y*cam.k; }); }
document.getElementById('close').onclick = () => select(null);
document.querySelectorAll('#top input[type=checkbox]').forEach(cb => cb.onchange = () => { vis[cb.dataset.t] = cb.checked; alpha = Math.max(alpha, .5); });
document.getElementById('q').oninput = ev => { query = ev.target.value.trim(); };
document.getElementById('relayout').onclick = () => { seed(); cam = {x:0,y:0,k:1}; };
const s = G.stats; document.getElementById('counts').textContent = '노트 ' + s.notes + ' · 점 ' + s.nodes + ' · 선 ' + s.edges + ' · 덩어리 ' + s.components + (Object.keys(s.dangling).length ? ' · ⚠ 끊어진 링크 ' + Object.keys(s.dangling).length : '');
document.getElementById('gen').textContent = '생성 ' + G.generated_at.replace('T',' ');
const used = new Set(G.nodes.map(n => n.subtype)); let lg = '';
Object.keys(LABELS).forEach(k => { if(used.has(k)) lg += '<span class="row"><span class="d" style="background:' + COLORS[k] + '"></span>' + LABELS[k] + '</span>'; });
lg += '<div style="color:#6b6156;margin-top:6px">실선 링크 · 굵은 초록 증거 · 점선 파랑 같은 성경 장 · 휠 확대 · 끌어서 이동 · 점 클릭 상세</div>';
document.getElementById('legend').innerHTML = lg;
</script></body></html>
"""

def render_html(g: dict, root: Path) -> str:
    data = json.dumps(g, ensure_ascii=False).replace("</", "<\\/")
    return (TEMPLATE.replace("__DATA__", data).replace("__COLORS__", json.dumps(COLORS, ensure_ascii=False))
            .replace("__LABELS__", json.dumps(LABELS, ensure_ascii=False)))
