// Gap Monitor JavaScript
const API_BASE = "";

const ENDPOINTS = {
  stats: (days=100) => `${API_BASE}/api/gaps/stats?days=${days}`,
  gaps:  (days=100) => `${API_BASE}/api/gaps/list?days=${days}&limit=100`,
  stock: (code, days=100) => `${API_BASE}/api/gaps/check/${code}?days=${days}`,
};

const EVENT_LABELS = {
  "company.asset_transaction_misc": "자산 관련 공시/기타",
  "company.capital_increase_mixed": "유상증자(복합)",
  "company.big_contract_update": "대형 계약 업데이트",
  "company.mna_deal": "M&A 거래",
  "company.mna_letter_of_intent": "M&A 의향서(LOI)",
  "company.mna_merger": "M&A 합병",
  "company.business_acquisition": "사업 인수",
  "company.earnings_result": "실적 발표",
  "company.operational_incident": "운영 이슈",
  "company.labor_strike_negotiation": "노사 협상",
  "company.stock_split": "주식 분할",
  "company.convertible_bond_issue": "전환사채 발행",
  "company.litigation_outcome": "소송 결과",
  "company.debt_restructuring": "부채 구조조정",
  "company.funding_round": "자금 조달",
  "company.dividend_announcement": "배당 발표",
  "company.management_change": "경영진 변경",
  "company.regulatory_sanction_fine": "규제 제재/벌금",
  "company.service_launch_termination": "서비스 출시/종료",
  "company.bonus_issue": "무상증자",
  "company.buyback_acquire": "자사주 취득",
  "company.buyback_dispose": "자사주 처분",
  "sector.biotech_regulatory": "바이오 규제",
  "sector.semicon_node_transition": "반도체 노드 전환",
  "market.price_movement": "시장 급등락",
  "flow.trading_resumption": "거래 재개",
};

async function fetchJson(url){
  const res = await fetch(url);
  if(!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function loadStats(){
  return fetchJson(ENDPOINTS.stats(100));
}

async function loadGaps(){
  const result = await fetchJson(ENDPOINTS.gaps(100));
  if(result.gaps) return result.gaps;
  return Array.isArray(result) ? result : [];
}

async function loadStock(code){
  return fetchJson(ENDPOINTS.stock(code, 100));
}

const fmt = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2, minimumFractionDigits: 0 });
const fmt1 = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 1, minimumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const abs = (x) => Math.abs(Number(x) || 0);

function evLabel(code){ return EVENT_LABELS[code] || code || "—" }
function dirIcon(d){ return d === "OVER" ? "▲" : "▼" }
function dirClass(d){ return d === "OVER" ? "over" : "under" }

function isSafeHttpUrl(url){
  try{
    const u = new URL(String(url), location.href);
    return u.protocol === 'http:' || u.protocol === 'https:';
  }catch(e){ return false; }
}

function el(tag, props={}, children=[]){
  const e = document.createElement(tag);
  for(const [k,v] of Object.entries(props || {})){
    if(k === 'dataset' && v && typeof v === 'object'){ 
      for(const [dk,dv] of Object.entries(v)) e.dataset[dk] = dv; 
    }
    else if(k === 'style' && v && typeof v === 'object'){ 
      Object.assign(e.style, v); 
    }
    else if(k === 'href'){ 
      if(isSafeHttpUrl(v)) e.setAttribute('href', v); 
    }
    else e[k] = v;
  }
  children.forEach(c => e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c));
  return e;
}

function magChipEl(m){
  const cls = m === "EXTREME" ? "extreme" : (m === "HIGH" ? "high" : "mod");
  return el('span', { className: `chip ${cls}`, textContent: m });
}

let CHARTS = {};

function renderSummary(stats){
  document.getElementById('kTotal').textContent = fmt.format(stats.total);
  document.getElementById('kOver').textContent  = fmt.format(stats.by_direction?.OVER ?? 0);
  document.getElementById('kUnder').textContent = fmt.format(stats.by_direction?.UNDER ?? 0);
  document.getElementById('kExtreme').textContent = fmt.format(stats.by_magnitude?.EXTREME ?? 0);

  const top = Object.entries(stats.by_event_code || {}).sort((a,b)=>b[1]-a[1])[0];
  document.getElementById('kTopEvent').textContent = top ? evLabel(top[0]) : "-";

  renderCharts(stats);

  const now = new Date();
  document.getElementById('lastUpdated').textContent =
    `마지막 갱신: ${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} `
    + `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
}

function calculateFilteredStats(rows){
  const stats = {
    total: rows.length,
    by_direction: {},
    by_magnitude: {},
    by_event_code: {}
  };

  rows.forEach(r => {
    stats.by_direction[r.direction] = (stats.by_direction[r.direction] || 0) + 1;
    stats.by_magnitude[r.magnitude] = (stats.by_magnitude[r.magnitude] || 0) + 1;
    stats.by_event_code[r.event_code] = (stats.by_event_code[r.event_code] || 0) + 1;
  });

  return stats;
}

function renderCharts(stats){
  const dirData = {
    labels: ["OVER", "UNDER"],
    datasets: [{ data: [stats.by_direction?.OVER ?? 0, stats.by_direction?.UNDER ?? 0] }]
  };
  const magData = {
    labels: ["MODERATE","HIGH","EXTREME"],
    datasets: [{ data: [stats.by_magnitude?.MODERATE ?? 0, stats.by_magnitude?.HIGH ?? 0, stats.by_magnitude?.EXTREME ?? 0] }]
  };
  const evEntries = Object.entries(stats.by_event_code || {}).sort((a,b)=>b[1]-a[1]).slice(0,8);
  const evData = {
    labels: evEntries.map(([k])=> evLabel(k)),
    datasets: [{ data: evEntries.map(([,v])=> v) }]
  };

  const c1 = document.getElementById('chartDirection');
  const c2 = document.getElementById('chartMagnitude');
  const c3 = document.getElementById('chartEvents');

  CHARTS.dir?.destroy(); CHARTS.mag?.destroy(); CHARTS.ev?.destroy();

  if (window.Chart) {
    CHARTS.dir = new Chart(c1, {
      type: "doughnut",
      data: dirData,
      options: {
        plugins: { legend:{ display:true, position:"bottom" } },
        animation: { duration: 400 }
      }
    });
    CHARTS.mag = new Chart(c2, {
      type: "bar",
      data: magData,
      options: {
        plugins:{ legend:{ display:false } },
        scales:{ y:{ beginAtZero:true, ticks:{ precision:0 } } },
        animation:{ duration: 400 }
      }
    });
    CHARTS.ev = new Chart(c3, {
      type: "bar",
      data: evData,
      options: {
        indexAxis: "y",
        plugins:{ legend:{ display:false } },
        scales:{ x:{ beginAtZero:true, ticks:{ precision:0 } } },
        animation:{ duration: 400 }
      }
    });
  } else {
    console.warn("Chart.js not found. Skipping chart render.");
  }
}

let RAW = [];

function applyFilters(rows){
  const q = document.getElementById('q').value.trim().toLowerCase();
  const showOver  = document.getElementById('fOver').checked;
  const showUnder = document.getElementById('fUnder').checked;
  const zMin = parseFloat(document.getElementById('zMin').value || "0");
  const mags = Array.from(document.querySelectorAll('.mag:checked')).map(i=>i.value);

  return rows.filter(r=>{
    const matchesQ = !q || (String(r.stock_name||"").toLowerCase().includes(q)) || (String(r.stock_code||"").includes(q));
    const matchesDir = (r.direction==="OVER" && showOver) || (r.direction==="UNDER" && showUnder);
    const matchesMag = mags.includes(r.magnitude);
    const matchesZ   = Math.abs(r.z_score ?? 0) >= zMin;
    return matchesQ && matchesDir && matchesMag && matchesZ;
  });
}

function renderTable(){
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = "";
  const filtered = applyFilters(RAW);
  const rows = filtered
    .reduce((acc, cur) => {
      const key = [cur.stock_code, cur.event_code, cur.date, cur.direction, cur.magnitude, Math.round((cur.z_score||0)*100)/100].join("|");
      if(!acc._seen.has(key)){ acc._seen.add(key); acc.list.push(cur); }
      return acc;
    }, {_seen:new Set(), list:[]}).list
    .sort((a,b)=> Math.abs(b.z_score) - Math.abs(a.z_score));

  for(const r of rows){
    const tr = document.createElement('tr');

    tr.appendChild(el('td', { textContent: r.date || "—" }));

    const tdStock = document.createElement('td');
    tdStock.append(document.createTextNode(r.stock_name || "—"), " ",
      el('span', { className: 'muted', textContent: `(${r.stock_code || "—"})` }));
    tr.appendChild(tdStock);

    tr.appendChild(el('td', { textContent: evLabel(r.event_code) }));

    const badge = el('span', { className: `badge ${dirClass(r.direction)}`, textContent: `${dirIcon(r.direction)} ${r.direction}` });
    tr.appendChild(el('td', {}, [badge]));

    tr.appendChild(el('td', {}, [magChipEl(r.magnitude)]));

    tr.appendChild(el('td', { style: { fontVariantNumeric: 'tabular-nums' }, textContent: fmt2.format(Number(r.z_score ?? 0)) }));

    const btn = el('button', { className: 'row-btn', textContent: '보기', dataset: { code: String(r.stock_code || '') } });
    tr.appendChild(el('td', {}, [btn]));

    tbody.appendChild(tr);
  }

  const filteredStats = calculateFilteredStats(filtered);
  document.getElementById('kTotal').textContent = fmt.format(filteredStats.total);
  document.getElementById('kOver').textContent  = fmt.format(filteredStats.by_direction?.OVER ?? 0);
  document.getElementById('kUnder').textContent = fmt.format(filteredStats.by_direction?.UNDER ?? 0);
  document.getElementById('kExtreme').textContent = fmt.format(filteredStats.by_magnitude?.EXTREME ?? 0);

  const top = Object.entries(filteredStats.by_event_code || {}).sort((a,b)=>b[1]-a[1])[0];
  document.getElementById('kTopEvent').textContent = top ? evLabel(top[0]) : "-";

  renderCharts(filteredStats);
}

const drawer = document.getElementById('drawer');
document.getElementById('drawerClose').addEventListener('click', ()=> drawer.classList.remove('open'));
drawer.addEventListener('click', (e)=>{ if(e.target===drawer) drawer.classList.remove('open'); });

async function openDetail(code){
  const data = await loadStock(code);

  const name = data?.stock_name || "—";
  const title = `${name} (${code})`;
  document.getElementById('drawerTitle').textContent = title;
  document.getElementById('drawerSub').textContent = `최근 ${data?.days ?? 100}일 · 신호 ${data?.gap_count ?? 0}건`;

  const body = document.getElementById('drawerBody');
  body.innerHTML = "";

  const list = (data?.has_gap && Array.isArray(data?.gap_signals) && data.gap_signals.length)
    ? data.gap_signals.slice().sort((a,b)=> Math.abs(b.z_score)-Math.abs(a.z_score))
    : [];

  if(!list.length){
    body.innerHTML = `<div class="muted">최근 기간 내 괴리 신호가 없습니다.</div>`;
    drawer.classList.add('open');
    return;
  }

  const wrap = el('div', { className: 'news' });

  for(const s of list){
    const ar = Number(s.actual_return ?? NaN);
    const er = Number(s.expected_return ?? NaN);
    const hasReturns = Number.isFinite(ar) && Number.isFinite(er);

    const sum = hasReturns ? (Math.abs(ar) + Math.abs(er) || 1) : 1;
    const widthPct = hasReturns ? Math.min(100, Math.round((Math.abs(ar) / sum) * 100)) : 0;

    const left = el('div', {}, [
      s.news_id && isSafeHttpUrl(s.news_id)
        ? el('a', { href: s.news_id, target: '_blank', rel: 'noopener noreferrer', textContent: s.news_title || '뉴스' })
        : el('strong', { textContent: s.news_title || evLabel(s.event_code) || '뉴스' }),
      el('div', { className: 'muted', style: { marginTop: '2px' }, textContent: `${s.news_date || ''} · ${evLabel(s.event_code)} · H+${s.horizon ?? 1}` })
    ]);

    const right = el('div', { style: { textAlign: 'right' } }, [
      el('div', {}, [ el('span', { className: `badge ${dirClass(s.direction)}`, textContent: `${dirIcon(s.direction)} ${s.direction}` }) ]),
      el('div', { style: { marginTop: '6px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' } }, [
        document.createTextNode('Z = '), el('strong', { textContent: fmt2.format(Number(s.z_score ?? 0)) }), document.createTextNode(' · '), magChipEl(s.magnitude)
      ])
    ]);

    const progressChildren = hasReturns
      ? [
          el('span', { className: 'muted', textContent: '실제 수익률' }),
          el('div', { className: 'bar' }, [
            el('i', { className: ar >= 0 ? 'pos' : 'neg', style: { width: `${widthPct}%` } })
          ]),
          el('span', { textContent: `${fmt1.format(ar)}%` }),
          el('span', { className: 'muted', style: { marginLeft: '8px' }, textContent: 'vs 기대' }),
          el('strong', { textContent: `${fmt1.format(er)}%` })
        ]
      : [ el('span', { className: 'muted', textContent: '수익률 데이터 없음' }) ];

    const progress = el('div', { className: 'progress', style: { gridColumn: '1 / -1' } }, progressChildren);

    const item = el('div', { className: 'news-item' }, [ left, right, progress ]);
    wrap.appendChild(item);
  }

  body.appendChild(wrap);
  drawer.classList.add('open');
}

document.getElementById('tbody').addEventListener('click', (e)=>{
  const btn = e.target.closest('button.row-btn');
  if(btn && btn.dataset.code){ openDetail(btn.dataset.code); }
});

function csvEscape(s){ return `"${String(s ?? "").replace(/"/g,'""')}"` }

function exportCsv(){
  const rows = applyFilters(RAW).sort((a,b)=> Math.abs(b.z_score) - Math.abs(a.z_score));
  const header = ["date","stock_name","stock_code","event","direction","magnitude","z_score"];
  const lines = [header.join(",")];
  for(const r of rows){
    lines.push([
      r.date, r.stock_name||"", r.stock_code||"", evLabel(r.event_code),
      r.direction, r.magnitude, (r.z_score ?? 0)
    ].map(csvEscape).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type:"text/csv;charset=utf-8" });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `gaps_${new Date().toISOString().slice(0,10)}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
}

async function init(){
  const themeToggle = document.getElementById('themeToggle');
  const syncTheme = ()=> document.body.setAttribute('data-theme', themeToggle.checked ? 'dark' : 'light');
  themeToggle.addEventListener('change', syncTheme); syncTheme();

  document.getElementById('q').addEventListener('input', renderTable);
  document.getElementById('fOver').addEventListener('change', renderTable);
  document.getElementById('fUnder').addEventListener('change', renderTable);
  document.querySelectorAll('.mag').forEach(el => el.addEventListener('change', renderTable));
  
  const zMin = document.getElementById('zMin');
  const zMinVal = document.getElementById('zMinVal');
  zMin.addEventListener('input', ()=>{ 
    const val = parseFloat(zMin.value);
    zMinVal.textContent = fmt1.format(val); 
    renderTable(); 
  });
  zMinVal.textContent = fmt1.format(parseFloat(zMin.value));

  document.getElementById('btnCsv').addEventListener('click', exportCsv);

  const [stats, gaps] = await Promise.all([loadStats(), loadGaps()]);
  RAW = gaps;
  renderSummary(stats);
  renderTable();
}

init().catch(err => {
  console.error(err);
  alert("데이터 로딩 중 오류가 발생했습니다.");
});
