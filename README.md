<h1 id="news-gap-scanner">News Gap Scanner — 괴리값 측정</h1>

<br>
<p align="center">
  <img src="https://github.com/user-attachments/assets/b42a8e94-6eef-4810-a4fe-ca47a22ff4ba" alt="괴리값이미지" width="900">
</p>
유튜브 링크: https://youtu.be/WBpkY4pBq30
<h2>1) 개요</h2>

<p>
  <strong>괴리값</strong>은 “특정 뉴스 이벤트가 발생한 직후의 <em>실제 수익률</em>(예: 1거래일 수익률)”이
  “동일·유사 이벤트의 <em>과거 통계</em>로부터 기대되는 수익률”과 얼마나 벗어났는지(Z-score) 정량화한 값입니다.
</p>
<ul>
  <li><strong>지표</strong>: Z-score 기반. 방향(<code>OVER</code>/<code>UNDER</code>)과 강도(<code>EXTREME</code>/<code>HIGH</code>/<code>MODERATE</code> …)를 함께 산출.</li>
  <li><strong>방향</strong>: 기대치 대비 크게 높으면 <code>OVER</code>, 낮으면 <code>UNDER</code>.</li>
  <li><strong>저장</strong>: 히스토리 기반을 두고 계산 결과를 지속 저장합니다.</li>
</ul>


<br>

<h2>2) 시스템 아키텍처 (데이터 흐름)</h2>

<pre><code>[뉴스 원문/타이틀]
      │
      ▼
(회사 추출) CompanyExtractor  ───▶  회사 상세(코드 포함)
      │                                      ▲
      ▼                                      │
(이벤트 분류) EventClassifier  ───▶  이벤트 코드(최대 2개)
      │
      ▼
[comprehensive_analyzed_news]   (회사/이벤트/날짜 정제 후 DB 적재)
      │
      ├─ (오프라인) NewsGapScanner.build_history  →  news_returns   (과거 수익률 히스토리 구축)
      │
      └─ (일일 배치) DailyScanner.scan             →  news_gaps      (괴리 신호 산출/저장)
</code></pre>

<ul>
  <li><code>comprehensive_analyzed_news</code>: 정제된 뉴스(회사·이벤트·일자) 저장 테이블.</li>
  <li><code>news_returns</code>: 이벤트별 과거 1D 로그수익률 히스토리(μ, σ 산출 근거).</li>
  <li><code>news_gaps</code>: 일일 스캔 결과(실제수익률, 기대치, 표준편차, z-score, 방향/강도) 저장.</li>
</ul>

<br>

<h2>3) 주요 컴포넌트</h2>

<h3>회사 추출기 (CompanyExtractor)</h3>
<ul>
  <li><strong>접근</strong>: 규칙 + LLM 조합으로 회사명을 추출하고 DB/사전에서 <code>stock_code</code> 등을 보강.</li>
  <li><strong>FinalCompanyExtractor, models</strong>: 정규식 패턴과 HCX 추출을 앙상블(가중치·투표)로 통합하고, 검증/정제 단계를 거쳐 최종 후보 반환. <em>애널리스트 리포트는 필터링</em>.</li>
  <li><strong>Data</strong>: 상장/비상장 마스터 구성.</li>
  <li><strong>Aliases</strong>: 별칭 사전 구축/병합(예: “현대차” → “현대자동차”), 유사도 기반 보정·학습.</li>
  <li><strong>Filters</strong>: 그룹명 단독 + 조사 패턴 제외(예: “삼성에는”…).</li>
  <li><strong>learning_aliases</strong>: HyperCLOVA 호출·재시도·파싱 로직 포함.</li>
  <li><strong>파이프라인</strong>:
    <ul>
      <li><em>patterns</em>: 마스터/별칭에서 가중치 패턴 동적 생성, 충돌 해소.</li>
      <li><em>Ensemble</em>: 메서드별 투표·신뢰도 집계 → 관련성 점수로 우선 정렬.</li>
      <li><em>검증/복구</em>: 마스터/컨텍스트/패턴 검증 + false negative 후보 복구.</li>
    </ul>
  </li>
</ul>

<h3>이벤트 분류기 (EventClassifier)</h3>
<ul>
  <li>제목을 <code>company.earnings_result</code>, <code>company.mna_deal</code> 등 정의된 라벨로 정규화. 라벨 후보는 약칭/토큰까지 지원.</li>
  <li><strong>StockEventLabelClassifier</strong>: HCX-007에 3줄 출력(라벨/정확도/근거)을 강제하고, 결과를 <em>화이트리스트 라벨</em>로 정규화.</li>
  <li>신뢰도 저하 또는 <code>other</code>일 경우 룰 백스톱으로 교정.</li>
  <li>라벨/트리거/우선순위는 <code>labels_config</code>로 관리하며, 상황별 프로파일로 우선순위를 오버라이드 가능.</li>
</ul>

<h3>NewsGapScanner (history)</h3>
<ul>
  <li>과거 구간을 훑어 <code>news_returns</code> 테이블 구축(이벤트 라벨 단위 1D 로그수익률의 μ, σ 집계).</li>
  <li>최근 N시간 뉴스에 대해 괴리 스캔을 수행하고 결과를 <code>news_gaps</code>에 저장.</li>
</ul>

<h3>DailyScanner (일일 스캐너)</h3>
<ul>
  <li>전일 뉴스에 대해 히스토리 방식으로 괴리 계산, 저장 및 요약 로그 출력.</li>
  
</ul>

<br>

<h2>4) 괴리값 계산 로직</h2>

<h3>4.1 히스토리 기반</h3>

<h4>목적</h4>
<p>
  동일 유형의 이벤트가 과거에 보였던 <strong>1거래일 로그수익률 분포</strong>로부터
  기대치(평균)와 불확실성(표준편차)을 학습해 두고, 새 뉴스에 대해
  <em>앵커–다음 거래일</em> 구간의 실제 반응을 표준화(Z-score)합니다.
</p>

<h4>핵심 개념</h4>
<ul>
  <li><strong>앵커가격(Anchor)</strong>: 뉴스일자 이상 첫 거래일의 종가. 거래소 휴일·정지 시 다음 가능한 거래일 사용.</li>
  <li><strong>실제수익률(1D)</strong>: 앵커 다음 거래일 종가 <code>C<sub>t+1</sub></code> 대비 로그수익률</li>
</ul>

<pre><code>r_actual = ln( C_{t+1} / C_{t} )
</code></pre>

<ul>
  <li><strong>기대치 / 표준편차</strong>: 내부 <code>event_returns_history</code>에서 이벤트 라벨 단위로 집계된 과거 1D 로그수익률의 μ, σ.</li>
  <li><strong>Z-score</strong>:</li>
</ul>

<pre><code>z = ( r_actual - μ_expected ) / σ_expected
</code></pre>

<ul>
  <li><strong>방향</strong>: <code>z &gt; 0 → OVER</code>, <code>z &lt; 0 → UNDER</code></li>
</ul>

<div style="border:1px solid #e5e7eb;padding:12px;border-radius:8px;background:#fafafa;">
  <strong>강도 분류 (히스토리 기반 기본)</strong>
  <table style="width:100%;border-collapse:collapse;margin-top:8px;">
    <thead>
      <tr>
        <th style="text-align:left;border-bottom:1px solid #ddd;padding:6px;">|z|</th>
        <th style="text-align:left;border-bottom:1px solid #ddd;padding:6px;">강도</th>
      </tr>
    </thead>
    <tbody>
      <tr><td style="padding:6px;border-bottom:1px solid #eee;">≥ 3</td><td style="padding:6px;border-bottom:1px solid #eee;"><strong>EXTREME</strong></td></tr>
      <tr><td style="padding:6px;border-bottom:1px solid #eee;">≥ 2</td><td style="padding:6px;border-bottom:1px solid #eee;"><strong>HIGH</strong></td></tr>
      <tr><td style="padding:6px;">그 외</td><td style="padding:6px;"><strong>MODERATE</strong></td></tr>
    </tbody>
  </table>

</div>

<h4>파이프라인</h4>
<ul>
  <li>실행 시 스캐너 도메인 객체가 과거 통계를 로드/집계(μ, σ)합니다.</li>
  <li>성공 시 각 뉴스에 대해 <code>actual_return</code> / <code>expected_return</code> / <code>expected_std</code> / <code>z_score</code>를 세팅하고, 방향/강도까지 산출하여 일괄 저장합니다.</li>
  <li>엔드포인트에서 스캐너 주입·초기화는 <strong>FastAPI lifespan</strong> 구간에서 수행됩니다.</li>
</ul>
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>데이터 흐름 상세도 · 괴리 판단 기준 · 테이블 관계도</title>
<meta name="color-scheme" content="light dark" />
<style>
  :root{
    --bg: #ffffff;
    --fg: #0f172a;
    --muted: #64748b;
    --card: #f8fafc;
    --border: #e5e7eb;
    --accent: #2563eb;
    --good: #059669;
    --warn: #d97706;
    --bad: #dc2626;
    --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    --round: 12px;
    --shadow: 0 1px 3px rgba(0,0,0,.05), 0 10px 15px -10px rgba(0,0,0,.1);
  }
  @media (prefers-color-scheme: dark){
    :root{
      --bg: #0b1220;
      --fg: #e5e7eb;
      --muted: #94a3b8;
      --card: #0f172a;
      --border: #1f2a44;
      --shadow: 0 1px 3px rgba(0,0,0,.4), 0 10px 15px -10px rgba(0,0,0,.6);
    }
  }
  *{box-sizing:border-box}
  body{
    margin:0; background:var(--bg); color:var(--fg);
    font: 15px/1.65 system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", Arial, sans-serif;
    text-rendering: optimizeLegibility;
  }
  .container{max-width:1100px; margin:0 auto; padding:28px 16px 64px}
  header{margin-bottom:20px}
  h1{font-size:clamp(22px,3.2vw,32px); margin:0 0 6px}
  h2{font-size:clamp(18px,2.2vw,24px); margin:36px 0 12px}
  h3{font-size:clamp(16px,2vw,20px); margin:20px 0 12px}
  p.lead{color:var(--muted); margin:0 0 12px}
  .toc{
    display:flex; flex-wrap:wrap; gap:8px; margin:12px 0 28px
  }
  .toc a{
    text-decoration:none; color:var(--fg); border:1px solid var(--border);
    padding:8px 12px; border-radius:999px; background:var(--card)
  }

  /* Cards & layout */
  .section{margin-top:18px}
  .card{
    background:var(--card); border:1px solid var(--border); border-radius:var(--round);
    box-shadow:var(--shadow); padding:16px
  }
  .grid{
    display:grid; gap:16px
  }
  .grid.cols-2{grid-template-columns:1fr}
  @media (min-width:900px){ .grid.cols-2{grid-template-columns:1fr 1fr} }

  /* Code + inline */
  code, kbd, samp{font-family:var(--mono); font-size:.96em}
  .mono{font-family:var(--mono)}
  .pill{
    display:inline-flex; align-items:center; gap:6px;
    padding:2px 8px; border-radius:999px; border:1px solid var(--border);
    background:rgba(0,0,0,.03)
  }
  @media (prefers-color-scheme: dark){
    .pill{background:rgba(255,255,255,.04)}
  }
  .note{color:var(--muted); font-size:.92em}
  .kbd{padding:.1em .35em; border:1px solid var(--border); border-bottom-width:2px; border-radius:6px; background:rgba(0,0,0,.03)}
  @media (prefers-color-scheme: dark){ .kbd{background:rgba(255,255,255,.04)} }

  /* Tables */
  table{width:100%; border-collapse:collapse; overflow:hidden; border-radius:10px}
  thead th{
    text-align:left; font-weight:700; background:linear-gradient(180deg, rgba(0,0,0,.04), transparent);
    border-bottom:1px solid var(--border)
  }
  th, td{padding:10px 12px; vertical-align:top}
  tbody tr{border-bottom:1px solid var(--border)}
  .zebra tbody tr:nth-child(odd){
    background:rgba(0,0,0,.02)
  }
  @media (prefers-color-scheme: dark){
    .zebra tbody tr:nth-child(odd){
      background:rgba(255,255,255,.03)
    }
  }
  caption{caption-side:top; text-align:left; color:var(--muted); padding:8px 0}

  /* KPI grid */
  .kpis{display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:8px}
  .kpi{padding:12px; border:1px dashed var(--border); border-radius:10px; background:rgba(0,0,0,.02)}
  @media (prefers-color-scheme: dark){ .kpi{background:rgba(255,255,255,.03)} }
  .kpi .label{color:var(--muted); font-size:.9em}
  .kpi .value{font:600 18px/1.2 var(--mono); margin-top:4px}

  /* Z-scale */
  .zscale{position:relative; height:22px; border-radius:999px; border:1px solid var(--border); background:
    linear-gradient(90deg, #0ea5e9, #22c55e 25%, #a3a3a3 50%, #f59e0b 75%, #ef4444);}
  .ticks{position:relative; height:0; }
  .tick{
    position:absolute; top:-6px; width:1px; height:34px; background:var(--border)
  }
  .tick label{
    position:absolute; top:36px; transform:translateX(-50%); font-size:.85em; color:var(--muted)
  }
  .legend{display:flex; justify-content:space-between; margin-top:8px; font-size:.9em; color:var(--muted)}
  .badge{display:inline-block; padding:.25em .6em; border-radius:8px; font:600 .86em/1 var(--mono); border:1px solid var(--border)}
  .badge.over{background:rgba(239,68,68,.08); color:#ef4444}
  .badge.under{background:rgba(14,165,233,.08); color:#0ea5e9}
  .badge.ok{background:rgba(34,197,94,.08); color:#10b981}

  /* SVG ERD wrapper */
  figure{margin:0}
  figcaption{color:var(--muted); font-size:.92em; margin:8px 0 0}

  /* Details */
  details{border:1px solid var(--border); border-radius:10px; padding:12px; background:var(--card)}
  details summary{cursor:pointer; font-weight:600}
</style>
</head>
<body>
  <div class="container">
    <header>
      <h1>🔄 데이터 흐름 상세도</h1>
      <p class="lead">뉴스-이벤트 매핑 → 수익률 계산 → 괴리(Z-score) 탐지 → <code>news_gaps</code> 적재까지의 전 과정을 정리했습니다.</p>
      <nav class="toc" aria-label="내비게이션">
        <a href="#step1">[1단계] 원본 데이터 수집</a>
        <a href="#step2">[2단계] 주가 조회·수익률</a>
        <a href="#step3">[3단계] 수익률 이력</a>
        <a href="#step4">[4단계] 괴리 탐지</a>
        <a href="#step5">[5단계] news_gaps 저장</a>
        <a href="#zrule">📈 괴리 판단 기준</a>
        <a href="#erd">🗄️ 테이블 관계도</a>
      </nav>
    </header>

    <!-- [1단계] -->
    <section id="step1" class="section">
      <h2>[1단계] 원본 데이터 수집</h2>
      <div class="grid cols-2">
        <div class="card">
          <h3 class="mono">rumors_opendart</h3>
          <ol>
            <li><span class="pill"><span>①</span> AI 분류</span> — <code>StockEventLabelClassifier</code></li>
          </ol>
          <div style="margin-top:10px">
            <div class="note">예시 출력</div>
            <ul>
              <li><code>corp_code</code>: <code>"00126380"</code></li>
              <li><code>summary</code>: <code>"반도체 투자 발표"</code></li>
            </ul>
          </div>
          <ol start="3">
            <li><span class="pill"><span>③</span> 종목코드 변환</span> — <code>stock_list</code> 테이블</li>
          </ol>
          <ul>
            <li><code>stock_code</code>: <code>"005930"</code></li>
          </ul>
        </div>

        <div class="card">
          <h3 class="mono">comprehensive_analyzed_news</h3>
          <ol>
            <li><span class="pill"><span>②</span> 종목코드 매핑</span> — <code>normalized_aliases.json</code></li>
          </ol>
          <ul>
            <li><code>stock_name</code>: <code>"삼성전자"</code></li>
            <li><code>event_code</code>: <code>"투자.설비투자"</code></li>
          </ul>
          <ol start="4">
            <li><span class="pill"><span>④</span> 종목코드 확정</span></li>
          </ol>
          <ul>
            <li><code>stock_code</code>: <code>"005930"</code></li>
          </ul>
        </div>
      </div>
    </section>

    <!-- [2단계] -->
    <section id="step2" class="section">
      <h2>[2단계] 주가 데이터 조회 및 수익률 계산</h2>
      <div class="card">
        <h3 class="mono">stock_daily_prices 테이블 조회</h3>
        <table class="zebra" aria-label="일자별 종가 테이블">
          <thead>
            <tr><th scope="col">날짜</th><th scope="col">종가</th><th scope="col">설명</th></tr>
          </thead>
          <tbody>
            <tr><td><code>20241010</code></td><td>65,000</td><td>← 뉴스 발생일</td></tr>
            <tr><td><code>20241011</code></td><td>66,000</td><td>← 앵커 가격 (이후 첫 거래일)</td></tr>
            <tr><td><code>20241014</code></td><td>67,000</td><td>← +1일 (다음 거래일)</td></tr>
            <tr><td><code>20241015</code></td><td>68,000</td><td></td></tr>
            <tr><td><code>20241016</code></td><td>69,000</td><td></td></tr>
            <tr><td><code>20241017</code></td><td>70,000</td><td>← +3일 (3거래일 후)</td></tr>
            <tr><td><code>20241018</code></td><td>71,000</td><td></td></tr>
            <tr><td><code>20241021</code></td><td>72,000</td><td>← +5일 (5거래일 후)</td></tr>
          </tbody>
        </table>

        <h3>계산 결과</h3>
        <div class="kpis">
          <div class="kpi"><div class="label">anchor_price</div><div class="value">66,000</div></div>
          <div class="kpi"><div class="label">return_1d</div><div class="value">ln(67,000 / 66,000) = 0.0150 (1.5%)</div></div>
          <div class="kpi"><div class="label">return_3d</div><div class="value">ln(70,000 / 66,000) = 0.0588 (5.9%)</div></div>
          <div class="kpi"><div class="label">return_5d</div><div class="value">ln(72,000 / 66,000) = 0.0870 (8.7%)</div></div>
        </div>
      </div>
    </section>

    <!-- [3단계] -->
    <section id="step3" class="section">
      <h2>[3단계] 수익률 이력 저장</h2>
      <div class="card">
        <h3 class="mono">event_returns_history 테이블</h3>
        <table class="zebra">
          <thead>
            <tr>
              <th scope="col">stock_code</th>
              <th scope="col">event_date</th>
              <th scope="col">event_cd</th>
              <th scope="col">anchor_pr</th>
              <th scope="col">return1d</th>
              <th scope="col">return3d</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>005930</td><td>20241010</td><td>투자.설비투자</td><td>66,000</td><td>0.0150</td><td>0.0588</td></tr>
            <tr><td>005930</td><td>20240905</td><td>투자.설비투자</td><td>64,500</td><td>0.0120</td><td>0.0450</td></tr>
            <tr><td>005930</td><td>20240801</td><td>투자.설비투자</td><td>63,000</td><td>-0.0050</td><td>0.0200</td></tr>
            <tr><td>…</td><td>…</td><td>…</td><td>…</td><td>…</td><td>…</td></tr>
          </tbody>
        </table>

        <details open style="margin-top:10px">
          <summary><strong>"투자.설비투자" 이벤트 통계</strong></summary>
          <ul style="margin:8px 0 0 18px">
            <li>평균 <code>return_1d</code> = <strong>0.0073</strong> (0.73%)</li>
            <li>표준편차 = <strong>0.0250</strong></li>
          </ul>
        </details>
      </div>
    </section>

    <!-- [4단계] -->
    <section id="step4" class="section">
      <h2>[4단계] 괴리 탐지 (Z-score 계산)</h2>
      <div class="grid cols-2">
        <div class="card">
          <h3>케이스 1 · 정상 범위</h3>
          <ul>
            <li>새로운 뉴스: <em>"삼성전자, 100조 투자 발표"</em></li>
            <li><code>event_code</code>: <code>투자.설비투자</code></li>
          </ul>
          <h4>실제 수익률</h4>
          <p><code>actual_return = 0.0150</code> (1.5%)</p>
          <h4>과거 통계</h4>
          <p><code>expected_return = 0.0073</code> (0.73%)<br/>
             <code>expected_std = 0.0250</code></p>
          <h4>Z-score</h4>
          <p class="mono">z = (0.0150 - 0.0073) / 0.0250 = 0.308</p>
          <p><span class="badge ok">|z| = 0.308 &lt; 2.0 → 괴리 아님</span></p>
        </div>

        <div class="card">
          <h3>케이스 2 · 과대반응</h3>
          <p><code>actual_return = 0.0600</code> (6.0%)<br/>
             <code>expected_return = 0.0073</code> (0.73%) · <code>expected_std = 0.0250</code></p>
          <p class="mono">z = (0.0600 - 0.0073) / 0.0250 = <strong>2.108</strong></p>
          <p>
            <span class="badge over">|z| = 2.108 ≥ 2.0 → 괴리 신호</span>
            <span class="pill">direction: <strong>OVER</strong></span>
            <span class="pill">magnitude: <strong>HIGH</strong></span>
          </p>
        </div>
      </div>
    </section>

    <!-- [5단계] -->
    <section id="step5" class="section">
      <h2>[5단계] <code>news_gaps</code> 테이블 저장</h2>
      <div class="card">
        <table class="zebra">
          <thead>
            <tr>
              <th scope="col">news</th>
              <th scope="col">stock_code</th>
              <th scope="col">stock_name</th>
              <th scope="col">event_code</th>
              <th scope="col">z_score</th>
              <th scope="col">direction</th>
              <th scope="col">magnitude</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>url1</td><td>005930</td><td>삼성전자</td><td>투자.설비투자</td><td>+2.108</td><td><span class="badge over">OVER</span></td><td>HIGH</td></tr>
            <tr><td>url2</td><td>000660</td><td>SK하이닉스</td><td>투자.설비투자</td><td>-2.550</td><td><span class="badge under">UNDER</span></td><td>EXTREME</td></tr>
            <tr><td>url3</td><td>005930</td><td>삼성전자</td><td>인수합병</td><td>+3.200</td><td><span class="badge over">OVER</span></td><td>EXTREME</td></tr>
          </tbody>
        </table>
        <ul style="margin:10px 0 0 18px">
          <li><span class="mono">actual_return</span>: 0.0600 (6.0%)</li>
          <li><span class="mono">expected_return</span>: 0.0073 (0.73%)</li>
          <li><span class="mono">expected_std</span>: 0.0250</li>
          <li><span class="mono">sample_count</span>: 150</li>
          <li><span class="mono">calc_mode</span>: HISTORY</li>
        </ul>
        <p class="note" style="margin-top:6px">※ 위 내용은 [API 응답]에 포함되어 전달됩니다.</p>
      </div>
    </section>

    <!-- 📈 괴리 판단 기준 -->
    <section id="zrule" class="section">
      <h2>📈 괴리 판단 기준</h2>

      <div class="card">
        <h3>Z-score 의미</h3>
        <div class="zscale" title="Z-score scale" aria-hidden="true"></div>
        <div class="ticks" aria-hidden="true">
          <div class="tick" style="left:0%"><label>-3.0</label></div>
          <div class="tick" style="left:16.66%"><label>-2.0</label></div>
          <div class="tick" style="left:33.33%"><label>-1.0</label></div>
          <div class="tick" style="left:50%"><label>0.0</label></div>
          <div class="tick" style="left:66.66%"><label>+1.0</label></div>
          <div class="tick" style="left:83.33%"><label>+2.0</label></div>
          <div class="tick" style="left:100%"><label>+3.0</label></div>
        </div>
        <div class="legend">
          <span>과소반응 (<span class="badge under">UNDER</span>)</span>
          <span>정상</span>
          <span>과대반응 (<span class="badge over">OVER</span>)</span>
        </div>

        <ul style="margin-top:10px">
          <li><code>|Z| &lt; 2.0</code>: 정상 범위 <span class="note">— 저장하지 않음</span></li>
          <li><code>|Z| ≥ 2.0</code>: 괴리 신호 → <code>news_gaps</code> 저장</li>
          <li><code>|Z| ≥ 3.0</code>: 극단적 괴리 (<strong>EXTREME</strong>)</li>
        </ul>

        <h3 style="margin-top:16px">예시: <code>"계약"</code> 이벤트의 역사적 분포</h3>
        <p class="note">과거 150건 기준 — 평균 수익률 <strong>+0.8%</strong>, 표준편차 <strong>2.5%</strong></p>
        <div class="kpis" style="grid-template-columns:repeat(4,1fr)">
          <div class="kpi"><div class="label">-1σ</div><div class="value">-1.7%</div></div>
          <div class="kpi"><div class="label">평균</div><div class="value">+0.8%</div></div>
          <div class="kpi"><div class="label">+1σ</div><div class="value">+3.3%</div></div>
          <div class="kpi"><div class="label">신규 뉴스</div><div class="value">+6.3%</div></div>
        </div>
        <p class="mono" style="margin-top:6px">z = (6.3 − 0.8) / 2.5 = <strong>2.2</strong> → <span class="badge over">HIGH 과대반응</span></p>
      </div>
    </section>

    <!-- 🗄️ 테이블 관계도 -->
    <section id="erd" class="section">
      <h2>🗄️ 테이블 관계도</h2>
      <div class="card">
        <figure aria-label="ERD">
          <!-- 단순 SVG ERD -->
          <svg viewBox="0 0 1100 680" role="img" aria-labelledby="erd-title erd-desc" style="width:100%; height:auto">
            <title id="erd-title">테이블 관계도</title>
            <desc id="erd-desc">stock_list 기준 테이블에서 가격/원천 데이터를 거쳐 event_returns_history와 news_returns, 최종 news_gaps로 흐르는 관계</desc>
            <defs>
              <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="currentColor"></path>
              </marker>
              <style>
                .box{fill: none; stroke: var(--border); stroke-width:1.2}
                .title{font: 700 12px system-ui}
                .cols{font: 11px system-ui; fill: var(--muted)}
                .label{font: 12px system-ui; fill: var(--muted)}
                .link{stroke: currentColor; stroke-width:1.4; marker-end:url(#arrow)}
              </style>
            </defs>

            <!-- stock_list -->
            <rect x="430" y="20" width="240" height="86" rx="12" class="box"/>
            <text x="550" y="45" text-anchor="middle" class="title">stock_list (기준)</text>
            <text x="450" y="68" class="cols">• stock_code <tspan font-weight="700">PK</tspan></text>
            <text x="450" y="84" class="cols">• corp_code · corp_name</text>

            <!-- stock_daily_prices -->
            <rect x="120" y="170" width="280" height="86" rx="12" class="box"/>
            <text x="260" y="195" text-anchor="middle" class="title">stock_daily_prices</text>
            <text x="140" y="218" class="cols">• stock_code <tspan font-weight="700">FK</tspan> · trade_date · close_price</text>

            <!-- rumors_opendart -->
            <rect x="700" y="170" width="280" height="86" rx="12" class="box"/>
            <text x="840" y="195" text-anchor="middle" class="title">rumors_opendart</text>
            <text x="720" y="218" class="cols">• corp_code <tspan font-weight="700">FK</tspan> · rcept_dt · report_nm</text>

            <!-- event_returns_history -->
            <rect x="140" y="360" width="320" height="96" rx="12" class="box"/>
            <text x="300" y="386" text-anchor="middle" class="title">event_returns_history</text>
            <text x="160" y="410" class="cols">• stock_code <tspan font-weight="700">FK</tspan> · event_code</text>
            <text x="160" y="426" class="cols">• return_1d · return_3d · return_5d</text>

            <!-- news_returns -->
            <rect x="660" y="360" width="320" height="96" rx="12" class="box"/>
            <text x="820" y="386" text-anchor="middle" class="title">news_returns</text>
            <text x="680" y="410" class="cols">• stock_code <tspan font-weight="700">FK</tspan> · event_code</text>
            <text x="680" y="426" class="cols">• return_1d · return_3d · return_5d</text>

            <!-- news_gaps -->
            <rect x="430" y="550" width="240" height="96" rx="12" class="box"/>
            <text x="550" y="576" text-anchor="middle" class="title">news_gaps (최종)</text>
            <text x="450" y="600" class="cols">• stock_code <tspan font-weight="700">FK</tspan> · z_score</text>
            <text x="450" y="616" class="cols">• direction · magnitude</text>

            <!-- Links -->
            <path d="M550,106 L300,170" class="link"/>
            <path d="M550,106 L840,170" class="link"/>

            <path d="M260,256 L300,360" class="link"/>
            <path d="M260,256 L820,360" class="link"/>
            <path d="M840,256 L300,360" class="link"/>
            <path d="M840,256 L820,360" class="link"/>

            <path d="M460,456 L550,550" class="link"/>
            <path d="M820,456 L670,550" class="link"/>

            <text x="560" y="320" class="label">수익률 계산</text>
            <text x="550" y="640" class="label" text-anchor="middle">통계 기반 괴리 탐지 → news_gaps</text>
          </svg>
          <figcaption>기준 테이블(<code>stock_list</code>)을 중심으로 가격/공시·뉴스 원천을 결합하여 수익률 이력 및 <code>news_gaps</code>로 적재.</figcaption>
        </figure>
      </div>
    </section>

    <footer style="margin-top:36px; color:var(--muted); font-size:.9em">
      문서 버전: <code>v1.0</code> · 예시는 설명을 위한 샘플 데이터입니다.
    </footer>
  </div>
</body>
</html>

<br>

<hr>
