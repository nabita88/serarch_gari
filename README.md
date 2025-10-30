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

<br>

<hr>
