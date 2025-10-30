# -*- coding: utf-8 -*-


from copy import deepcopy


LABEL_REGISTRY_BASE = {
    # ---------- Flow ----------
    "flow.trading_resumption": {"fine": True,  "priority": 160, "triggers": [r"(거래|매매)\s*(재개|재개\s*공시)"]},
    "flow.trading_halt_cb":    {"fine": False, "priority": 300, "triggers": [r"(매매|거래)\s*정지", r"\bVI\b", r"(서킷|써킷)\s*브레이커"]},
    "flow.index_inout":        {"fine": False, "priority": 217, "triggers": [r"(편입|편출).*(코스피200|코스닥150|KOSPI|MSCI|FTSE|정기\s*변경|리밸런싱)"]},
    "flow.options_expiry":     {"fine": False, "priority": 320, "triggers": [r"(옵션|선물옵션).{0,8}(만기|만기일|만기\s*도래)", r"(동시\s*만기|트리플\s*위칭|quad(ruple)?\s*witching)", r"(옵션|선물).{0,8}(만기월|월물\s*만기)"]},

    # ---------- Company (세분) ----------
    # M&A cycle
    "company.mna_letter_of_intent":     {"fine": True, "priority": 110, "triggers": [r"\bLOI\b", r"\bMOU\b", r"인수\s*의향서", r"양해각서", r"조건부?\s*합의", r"프레임워크\s*협약"]},
    "company.mna_binding_agreement":    {"fine": True, "priority": 111, "triggers": [r"\bSPA\b", r"본\s*계약\s*체결", r"최종\s*계약", r"주식\s*매매\s*계약"]},
    "company.mna_regulatory_clearance": {"fine": True, "priority": 112, "triggers": [r"(공정위|공정거래위원회|FTC|EC|SAMR).*(승인|심사\s*통과|클리어런스)"]},
    "company.mna_termination":          {"fine": True, "priority": 113, "triggers": [r"(딜|거래|합병|인수).*(해지|무산|종료|철회|termination)"]},

    # Equity/Lockup/Stock option
    "company.major_shareholder_change":    {"fine": True, "priority": 124, "triggers": [r"(최대\s*주주|지배\s*주주).*(변경|교체)"]},
    "company.share_pledge_change":         {"fine": True, "priority": 125, "triggers": [r"(질권|담보).*(설정|해지)"]},
    "company.lockup_expiry":               {"fine": True, "priority": 120, "triggers": [r"(보호\s*예수|락업).*(해제|만료)"]},
    "company.stock_option_grant":          {"fine": True, "priority": 122, "triggers": [r"스톡\s*옵션.*(부여|grant)"]},
    "company.stock_option_exercise":       {"fine": True, "priority": 123, "triggers": [r"스톡\s*옵션.*(행사|exercise)"]},
    "company.treasury_share_cancellation": {"fine": True, "priority": 121, "triggers": [r"(자사주|자기주식).*(소각|말소)"]},

    # Finance/Credit
    "company.debt_restructuring":    {"fine": True, "priority": 130, "triggers": [r"(리파이낸싱|재조정|재무\s*구조\s*개선|만기\s*연장)"]},
    "company.covenant_waiver":       {"fine": True, "priority": 131, "triggers": [r"(재무\s*약정|코버넌트).*(면제|유예|waiver)"]},
    "company.rating_watch_outlook":  {"fine": True, "priority": 132, "triggers": [r"(관찰\s*대상|Watch|전망|Outlook).*(상향|하향|부여|변경)"]},
    "company.early_redemption_call": {"fine": True, "priority": 133, "triggers": [r"(조기\s*상환|콜\s*옵션\s*행사|early\s*redemption|call)"]},

    # Operations/Facility/Safety
    "company.capex_expansion":            {"fine": True, "priority": 140, "triggers": [r"(대규모|대형)\s*(설비|공장|fab|라인).*(증설|투자|capex|CAPEX|확대)"]},
    "company.plant_shutdown_maintenance": {"fine": True, "priority": 141, "triggers": [r"(정기\s*보수|셧\s*다운|shutdown|가동\s*중단)"]},
    "company.plant_restart_rampup":      {"fine": True, "priority": 142, "triggers": [r"(재\s*가동|가동\s*재개|램프\s*업|ramp[\s-]*up)"]},
    "company.operational_incident":       {"fine": True, "priority": 143, "triggers": [r"(화재|폭발|누출|정전|침수|사고|사망|부상)"]},
    "company.service_launch_termination": {"fine": True, "priority": 144, "triggers": [r"(서비스|상품|플랫폼).*(출시|론칭|종료|단종|terminate)"]},

    # Legal/Regulatory
    "company.regulatory_sanction_fine":     {"fine": True,  "priority": 150, "triggers": [r"(과징금|행정\s*제재|고발|징계).*(부과|처분|확정)"]},
    "company.litigation_filed":             {"fine": True,  "priority": 151, "triggers": [r"(소송|집단\s*소송|소제기|제소|complaint\s*filed)"]},
    "company.litigation_outcome":           {"fine": True,  "priority": 152, "triggers": [r"(판결|합의|소취하|승소|패소|일부승소|settlement|verdict)"]},
    "company.violation_of_law":             {"fine": False, "priority": 218, "triggers": [r"(구속|압수수색|기소|수사|위법|혐의)"]},
    "company.whistleblowing_investigation": {"fine": False, "priority": 180, "triggers": [r"(내부\s*고발|제보)", r"(내부\s*조사|감사)\s*(개시|착수)"]},
    "company.labor_strike_negotiation":     {"fine": False, "priority": 106, "triggers": [r"(파업|쟁의|단체\s*행동|노조)", r"(교섭|협상|중재)"]},

    # Listing/Trading status
    "company.delisting_watch": {"fine": True, "priority": 161, "triggers": [r"(관리\s*종목|상장\s*폐지|상폐).*(사유|통지|우려|리스크)"]},

    # ---------- Company (포괄) ----------
    "company.mna_deal":            {"fine": False, "priority": 210, "triggers": [r"(인수|합병|M&A|지분\s*인수|경영권\s*인수)"]},
    "company.big_contract_update": {"fine": False, "priority": 211, "triggers": [r"(공급\s*계약|납품\s*계약|장기\s*공급|대규모\s*계약|수주)"]},
    "company.stock_split":         {"fine": False, "priority": 212, "triggers": [r"(액면\s*분할|주식\s*분할|역\s*분할)"]},
    "company.earnings_result":     {"fine": False, "priority": 213, "triggers": [r"(실적|영업익|매출|순이익|흑자|적자|컨센서스)"]},
    "company.guidance_update":     {"fine": False, "priority": 214, "triggers": [r"(가이던스|전망|가이드).*(상향|하향|조정)"]},

    # ---------- Sector ----------
    # Semiconductor
    "sector.semicon_node_transition":   {"fine": False, "priority": 215, "triggers": [r"(HBM|양산|수율|노드|nm|공정)"]},
    "sector.semicon_tapeout":           {"fine": True,  "priority": 180, "triggers": [r"(테이프\s*아웃|tape[-\s]*out)"]},
    "sector.semicon_qualification_pass":{"fine": True,  "priority": 181, "triggers": [r"(퀄|qualification|인증|검증).*(통과|승인)"]},
    "sector.semicon_capacity_commit":   {"fine": True,  "priority": 182, "triggers": [r"(capacity|캐파|CAPA|증설).*(커밋|commit|장기\s*공급)"]},
    "sector.semicon_capex_yield":       {"fine": False, "priority": 366, "triggers": [r"(수율|yield).{0,10}(개선|향상|문제|불량|이슈)", r"(CAPEX|capex|캐펙스|설비\s*투자|증설)\b", r"(EUV|리소그래피|포토).{0,10}(장비|툴).{0,10}(증설|투자|도입)"]},

    # Biotech
    "sector.biotech_clinical_result":        {"fine": False, "priority": 220, "triggers": [r"임상\s*(1|2|3|I|II|III)\s*(상)?\s*(결과|탑라인|top[-\s]*line|데이터|중간\s*분석)", r"(ORR|PFS|OS|DOR|CR|PR|HR)\s*(개선|달성|충족|실패|유의미)", r"(유효성|안전성|내약성).{0,10}(확인|평가|개선|문제)"]},
    "sector.biotech_regulatory":             {"fine": False, "priority": 216, "triggers": [r"(FDA|EMA|허가|승인)"]},
    "sector.biotech_ind_clearance":          {"fine": True,  "priority": 170, "triggers": [r"\bIND\b.*(승인|접수|허가)"]},
    "sector.biotech_nda_bla_filing":         {"fine": True,  "priority": 171, "triggers": [r"\b(NDA|BLA)\b.*(제출|접수|filing)"]},
    "sector.biotech_pdufa_set":              {"fine": True,  "priority": 172, "triggers": [r"\bPDUFA\b.*(일|데드라인|타깃|목표\s*일)"]},
    "sector.biotech_fasttrack_designation":  {"fine": True,  "priority": 173, "triggers": [r"(Fast[-\s]*Track|가속\s*승인|희귀\s*의약품|Orphan)\s*(지정|승인)"]},
    "sector.biotech_trial_enrollment_complete":{"fine": True,"priority": 174, "triggers": [r"(등록|모집).*(완료|마감)"]},
    "sector.biotech_primary_endpoint_result": {"fine": True, "priority": 175, "triggers": [r"(주\s*평가\s*지표|Primary\s*Endpoint).*(달성|충족|실패|미달성)"]},
    "sector.biotech_clinical_hold_lifted":   {"fine": True, "priority": 176, "triggers": [r"(임상).*(중지|보류|Hold).*(해제|Lifted)"]},

    # 기타 섹터
    "sector.retail_sssg_inventory":         {"fine": False, "priority": 360, "triggers": [r"\bSSSG\b", r"same[-\s]*store\s*(sales|growth)", r"(like[-\s]*for[-\s]*like|LFL)\s*(sales|growth)?", r"(동일|기존)\s*점포.*(매출|성장|신장|증가|감소)", r"(리테일|소매|의류|패션|백화점|마트|편의점|매장|점포).{0,12}(재고|인벤토리|재고율|재고\s*일수|DIO|DOH)", r"(재고|인벤토리|재고율|재고\s*일수|DIO|DOH).{0,12}(리테일|소매|의류|패션|백화점|마트|편의점|매장|점포)"]},
    "sector.software_saas_metrics":         {"fine": False, "priority": 361, "triggers": [r"\bARR\b", r"\bMRR\b", r"\bNRR\b", r"(net|dollar[-\s]*based)\s*revenue\s*retention", r"\bDBNRR?\b", r"(RPO|remaining\s*performance\s*obligations)\b", r"\bACV\b|\bTCV\b", r"(CAC|고객\s*획득\s*비용)\b", r"(LTV|고객\s*생애\s*가치)\b", r"(유료\s*좌석|paid\s*seats?)", r"(리텐션|유지\s*율).{0,12}(구독|subscription|SaaS|소프트웨어|클라우드|좌석|seat)", r"(구독|subscription|SaaS|소프트웨어|클라우드).{0,12}이탈\s*율"]},
    "sector.energy_oil_gas":                {"fine": False, "priority": 362, "triggers": [r"\bWTI\b|\bBrent\b", r"(국제\s*유가|유가|원유\s*가격)", r"(정제\s*마진|크랙\s*스프레드|crack\s*spread)", r"\bOPEC\+?\b", r"(EIA|API).{0,12}(원유|휘발유|재고|stock|inventory)", r"(천연\s*가스|LNG|Henry\s*Hub|가스전|셰일|shale)", r"(리그\s*카운트|rig\s*count)", r"(감산|증산).{0,10}(OPEC|사우디|러시아|원유|석유)"]},
    "sector.shipping_freight_index":        {"fine": False, "priority": 363, "triggers": [r"\bBDI\b", r"\bSCFI\b|\bCCFI\b|\bFBX\b", r"\bBDTI\b|\bBCTI\b", r"(Drewry|WCI).*(Index|지수)", r"(컨테이너|해운|선사|항로|항만).{0,12}운임", r"운임.{0,12}(컨테이너|해운|선사|항로|항만)", r"운임\s*지수"]},
    "sector.financial_nim_provision_capital":{"fine": False, "priority": 364, "triggers": [r"\bNIM\b|순\s*이자\s*마진|Net\s*Interest\s*Margin", r"\bNII\b|순\s*이자\s*이익", r"(대손\s*충당금|충당금).*(적립|전입|환입|추가)", r"(신용\s*비용|credit\s*cost)", r"\bNPL\b|부실\s*여신|연체\s*율", r"\bCET1\b|보통주\s*자본\s*비율|Tier\s*1|총\s*자본\s*비율|BIS\s*비율", r"\bRWA\b|위험\s*가중\s*자산", r"(자본\s*적정성|capital\s*adequacy)"]},
    "sector.auto_ev_policy_recall":         {"fine": False, "priority": 365, "triggers": [r"(전기차|EV|하이브리드|PHEV|FCEV|완성차|차량|승용차|SUV|트럭).{0,12}(리콜|결함\s*시정|무상\s*수리)", r"\bNHTSA\b|국토교통부.{0,12}(리콜|결함|조사)|교통안전공단.{0,12}(리콜|결함|조사)", r"(전기차|EV|배터리).{0,12}(보조금|인센티브|세액\s*공제|지원금)", r"(인플레이션\s*감축법|Inflation\s*Reduction\s*Act)", r"\bZEV\b|Zero[-\s]*Emission\s*Vehicle", r"Euro\s*7|유로\s*7|유럽\s*배출\s*규제", r"\bCAFE\b|연비\s*기준|배출\s*규제", r"(충전\s*인프라|충전소\s*의무화|charging\s*infrastructure)"]},

    # ---------- Calendar ----------
    "calendar.earnings_date":             {"fine": False, "priority": 380, "triggers": [r"(실적|earnings).{0,10}(발표|공개|컨퍼런스\s*콜|컨콜)\s*(일|일정|예정|date)", r"(잠정|확정)\s*실적\s*(예정|발표\s*일)"]},
    "calendar.dividend_dates":            {"fine": False, "priority": 381, "triggers": [r"(배당|분기\s*배당|중간\s*배당|연말\s*배당).{0,10}(기준일|지급일|배정일|ex[-\s]*dividend|ex[-\s]*date)"]},
    "calendar.options_expiry_date":       {"fine": False, "priority": 382, "triggers": [r"(옵션|선물옵션).{0,8}(만기일)", r"(동시\s*만기|트리플\s*위칭|quad(ruple)?\s*witching)\s*(일|세션)?"]},
    "calendar.index_rebalance_effective": {"fine": False, "priority": 383, "triggers": [r"(지수|index|KOSPI|KOSDAQ|MSCI|FTSE).{0,12}(리밸런싱|정기\s*변경|정기\s*편출입).{0,8}(시행|효력|발효|적용|effective)"]},
    "calendar.lockup_expiration":         {"fine": False, "priority": 384, "triggers": [r"(락업|보호\s*예수).{0,10}(해제|만료|만기).{0,6}(일|date|예정)"]},
    "calendar.investor_day_ndr":          {"fine": False, "priority": 385, "triggers": [r"(Investor\s*Day|IR\s*Day|Capital\s*Markets\s*Day|투자자\s*설명회)", r"\bNDR\b|non[-\s]*deal\s*roadshow|로드쇼"]},
    "calendar.shareholder_meeting":       {"fine": False, "priority": 386, "triggers": [r"(주주\s*총회|정기\s*주총|임시\s*주총|AGM|EGM)\b"]},

    # ---------- KRX ----------
    "krx.shortselling_ban_toggle": {"fine": False, "priority": 400, "triggers": [r"(공매도).{0,6}(금지|재개|해제|부분\s*해제|연장|금지\s*연장)", r"(금융위|KRX|금융감독원).{0,12}(공매도).{0,8}(조치|발표|공지)"]},
    "krx.short_sale_hot_stock":    {"fine": False, "priority": 401, "triggers": [r"(공매도).{0,6}(과열\s*종목|과열|제한|규제)\b", r"(공매도\s*과열)\s*(지정|해제)"]},
    "krx.single_price_auction":    {"fine": False, "priority": 402, "triggers": [r"(단일\s*가|단일가)\s*(매매|호가|경매|적용)", r"(투자\s*경고|경고).{0,6}(단일\s*가|단일가)"]},
    "krx.watchlist_designation":   {"fine": False, "priority": 403, "triggers": [r"(투자\s*주의|투자\s*경고|매매\s*주의|투자\s*위험)\s*(지정|해제)", r"(관리\s*종목)\s*(지정|해제)"]},
    "krx.query_disclosure":        {"fine": False, "priority": 404, "triggers": [r"(조회\s*공시)\s*(요구|요청|답변|회신)", r"KRX.{0,12}(조회\s*공시)"]},
    "krx.unfaithful_disclosure":   {"fine": False, "priority": 405, "triggers": [r"(불성실\s*공시)\s*(법인|지정|제재|부과)", r"(공시).*(번복|오류|정정).*(제재|과징금|경고)"]},
    "krx.delisting_notice":        {"fine": False, "priority": 406, "triggers": [r"(상장\s*폐지|상폐).{0,8}(사유|통지|예고|예정)", r"(상장)\s*(유지|폐지)\s*심의"]},
    "krx.trading_halt_vi":         {"fine": False, "priority": 407, "triggers": [r"\bVI\b|변동성\s*완화\s*(장치|VI).{0,6}(발동|해제)", r"(매매|거래)\s*정지"]},

    # ---------- Analyst ----------
    "analyst.target_price": {"fine": False, "priority": 450, "triggers": [r"(목표\s*주가|목표가|target\s*price).*(상향|하향|변경|유지)"]},
    "analyst.rating_change": {"fine": False, "priority": 451, "triggers": [r"(투자의견|investment\s*rating).*(상향|하향|변경|유지|개시)", r"\b(매수|비중확대|Outperform|중립|Hold|Underperform|매도)\b"]},
    "analyst.report":        {"fine": False, "priority": 452, "triggers": [r"(리서치|리포트|보고서|note)\s*(발간|발표|출간|게시)", r"(커버리지|coverage)\s*(개시|initiated)"]},
    "analyst.conference":    {"fine": False, "priority": 453, "triggers": [r"(컨퍼런스|conference|세미나|포럼|fireside\s*chat|IR\s*행사|roadshow|NDR|투자자\s*설명회)"]},

    # ---------- Capital/Debt 추가 ----------
    "company.capital_increase_rights":  {"fine": False, "priority": 339, "triggers": [r"유상\s*증자", r"신주\s*발행", r"제3자\s*배정"]},
    "company.bonus_issue":              {"fine": False, "priority": 340, "triggers": [r"무상\s*증자"]},
    "company.capital_reduction":        {"fine": False, "priority": 341, "triggers": [r"(감자|자본\s*감소)\s*(결정|실시|승인)", r"(무상\s*감자|유상\s*감자)"]},
    "company.capital_increase_mixed":   {"fine": False, "priority": 342, "triggers": [r"(유상|무상)\s*증자.*(병행|혼합|동시)", r"(유무상)\s*증자"]},
    "company.at1_issue":                {"fine": False, "priority": 343, "triggers": [r"(신종\s*자본\s*증권|AT1|Additional\s*Tier\s*1|영구채).*(발행|결정|모집)"]},
    "company.convertible_bond_issue":   {"fine": False, "priority": 344, "triggers": [r"(전환\s*사채|CB).*(발행|모집|사모|공모|신규\s*발행)"]},
    "company.bw_issue":                 {"fine": False, "priority": 345, "triggers": [r"(신주\s*인수권부\s*사채|BW).*(발행|모집|사모|공모)"]},
    "company.exchangeable_bond_issue":  {"fine": False, "priority": 346, "triggers": [r"(교환\s*사채|EB).*(발행|모집|사모|공모)"]},

    # ---------- M&A/분할/교환 ----------
    "company.mna_merger":              {"fine": False, "priority": 347, "triggers": [r"(합병|흡수\s*합병|신설\s*합병|merger)"]},
    "company.share_exchange_transfer": {"fine": False, "priority": 348, "triggers": [r"(주식\s*교환|주식\s*이전|share\s*(exchange|transfer))"]},
    "company.split_merger":            {"fine": False, "priority": 349, "triggers": [r"(분할\s*합병|split[-\s]*merger|분할\s*후\s*합병)"]},
    "company.listing_overseas":        {"fine": False, "priority": 350, "triggers": [r"해외\s*(상장|상장\s*추진)", r"(NYSE|NASDAQ|LSE|HKEX).*(상장|listing)"]},

    # ---------- 영업/자산/지분 ----------
    "company.business_acquisition":       {"fine": False, "priority": 351, "triggers": [r"(사업|영업).{0,6}(양수|양수도|인수|취득|포괄양수)"]},
    "company.business_disposal":          {"fine": False, "priority": 352, "triggers": [r"(사업|영업).{0,6}(양도|매각|처분|포괄양도)"]},
    "company.tangible_asset_acquisition": {"fine": False, "priority": 353, "triggers": [r"(유형\s*자산|토지|건물|기계|설비|부동산|공장).{0,10}(취득|매입|양수)", r"(공장|라인|설비).{0,10}(매입|취득|인수)"]},
    "company.tangible_asset_disposal":    {"fine": False, "priority": 354, "triggers": [r"(유형\s*자산|토지|건물|기계|설비|부동산|공장).{0,10}(매각|처분|양도)"]},
    "company.equity_acquisition":         {"fine": False, "priority": 355, "triggers": [r"(지분|주식|shares?).{0,10}(취득|인수|매입|확대)"]},
    "company.equity_disposal":            {"fine": False, "priority": 356, "triggers": [r"(지분|주식).{0,10}(매각|처분|축소|매도|양도)"]},
    "company.security_bond_rights_acq":   {"fine": False, "priority": 357, "triggers": [r"(유가\s*증권|채권|어음|증권|파생|권리).{0,10}(취득|매입)", r"(콜옵션|풋옵션|워런트).{0,10}(취득|매입)"]},
    "company.security_bond_rights_disp":  {"fine": False, "priority": 358, "triggers": [r"(유가\s*증권|채권|어음|증권|파생|권리).{0,10}(처분|매각|양도)", r"(콜옵션|풋옵션|워런트).{0,10}(양도|매각|처분)"]},
    "company.asset_transaction_misc":     {"fine": False, "priority": 359, "triggers": [r"(자산|asset|부동산|토지|건물|설비|지적\s*재산|IP).{0,12}(거래|양수도|매각|취득|처분)"]},
    "company.putback_option":             {"fine": False, "priority": 360, "triggers": [r"(풋백|put[-\s]*back|풋\s*백)\s*(옵션|권리)", r"(Put\s*Option).{0,6}(부여|행사|발생|계약)"]},

    # ---------- Buyback ----------
    "company.buyback_acquire":          {"fine": False, "priority": 361, "triggers": [r"(자사주|자기\s*주식).{0,6}(취득|매입|buy[-\s]*back)", r"(이사회|board).{0,10}(자사주\s*취득)"]},
    "company.buyback_dispose":          {"fine": False, "priority": 362, "triggers": [r"(자사주|자기\s*주식).{0,6}(처분|매각|양도)"]},
    "company.buyback_trust_sign":       {"fine": False, "priority": 363, "triggers": [r"(자사주|자기\s*주식).{0,6}(신탁).{0,6}(계약|체결)"]},
    "company.buyback_trust_terminate":  {"fine": False, "priority": 364, "triggers": [r"(자사주|자기\s*주식).{0,6}(신탁).{0,6}(해지|종료)"]},

    # ---------- Distress ----------
    "company.default_event":        {"fine": False, "priority": 365, "triggers": [r"(기한\s*이익\s*상실|cross\s*default|디폴트|채무\s*불이행|연체|만기\s*도래\s*상환\s*불이행)", r"(원리금|이자).{0,6}(미지급|연체)"]},
    "company.business_suspension":  {"fine": False, "priority": 366, "triggers": [r"(영업|사업).{0,6}(정지|중단|일시\s*중단|suspension)", r"(생산|가동).{0,6}(중단|정지|suspend)"]},
    "company.rehabilitation_apply": {"fine": False, "priority": 367, "triggers": [r"(회생\s*절차|법정\s*관리|법정관리).{0,6}(신청|개시|접수)", r"(회생\s*계획).{0,6}(인가|제출|신청)"]},
    "company.dissolution_cause":    {"fine": False, "priority": 368, "triggers": [r"(해산).{0,6}(사유|결의|결정|발생)", r"(법인\s*해산|회사\s*해산)"]},

    # ---------- 기타 ----------
    "company.preannouncement_warning": {"fine": False, "priority": 305, "triggers": [r"(사전\s*공시|예고\s*공시|향후\s*공시\s*예정|pre[-\s]*announcement)"]},
    "company.dividend_change":        {"fine": False, "priority": 306, "triggers": [r"(배당).{0,6}(증액|감액|변경|특별\s*배당|중간\s*배당)", r"(배당\s*성향|배당금).{0,6}(조정|변경|상향|하향)"]},
    "company.convertible_pref_update":{"fine": False, "priority": 310, "triggers": [r"(전환\s*우선주|상환\s*전환\s*우선주|RCPS|CPS).{0,10}(발행|전환|상환|조건\s*변경|콜|풋)", r"(우선주).{0,10}(전환|상환|조건\s*변경)"]},
    "company.management_change":      {"fine": False, "priority": 312, "triggers": [r"(대표이사|CEO|CFO|사장|부사장|임원|이사|감사).{0,6}(선임|해임|변경|사임|임명)", r"(경영\s*진|경영진).{0,6}(개편|교체|변경)"]},
    "company.insider_transaction":    {"fine": False, "priority": 313, "triggers": [r"(임원|내부자|오너|최대\s*주주).{0,10}(매수|매도|처분|취득|거래)", r"(지분\s*변동)\s*(보고|공시)"]},
    "company.product_pricing_update": {"fine": False, "priority": 314, "triggers": [r"(출고가|판매\s*가격|요금|요율|운임|가격).{0,6}(인상|인하|조정|변경|동결)"]},
    "company.supply_chain_disruption":{"fine": False, "priority": 315, "triggers": [r"(공급\s*망|공급\s*차질|수급\s*불균형|부품\s*부족|납기\s*지연|리드\s*타임).{0,10}(지연|차질|중단|악화)", r"(파업|천재지변|항만|물류).{0,10}(지연|차질|중단)"]},
    "company.accounting_audit_issue": {"fine": False, "priority": 316, "triggers": [r"(감사|회계).{0,10}(의견\s*거절|의견\s*한정|지연|중단|문제|정정)", r"(재무\s*제표|회계\s*처리).{0,10}(오류|정정|착오|수정|재작성)"]},
    "company.litigation_regulatory":  {"fine": False, "priority": 317, "triggers": [r"(소송|가처분|분쟁|소제기|제소|complaint)", r"(당국|규제|검찰|경찰|공정위|금감원|SEC|DOJ).{0,10}(조사|제재|수사|벌금|fine)"]},
    "company.esg_labor_incident":     {"fine": False, "priority": 318, "triggers": [r"(ESG|환경|안전|노동|노무).{0,10}(사고|문제|이슈|위반|사망|부상)", r"(아동\s*노동|인권|성희롱|갑질|차별)"]},
    "company.dart_correction":        {"fine": False, "priority": 319, "triggers": [r"(정정\s*공시|정정\s*신고|추가\s*공시|변경\s*공시)", r"(DART|공시).{0,10}(정정|추가|변경)"]},
    "company.credit_rating_change":   {"fine": False, "priority": 321, "triggers": [r"(신용\s*등급|issuer\s*rating|신용평가).{0,10}(상향|하향|변경|부여)"]},
    "company.product_safety_recall":  {"fine": False, "priority": 322, "triggers": [r"(리콜|안전\s*문제|자발적\s*리콜|강제\s*리콜|수거\s*명령)", r"(결함|안전|화재).{0,10}(우려|문제).{0,10}(리콜|수거|시정)"]},
    "company.data_breach":            {"fine": False, "priority": 323, "triggers": [r"(정보\s*유출|데이터\s*유출|랜섬웨어|해킹|침해|사이버\s*공격)", r"(고객\s*정보|개인\s*정보).{0,10}(노출|유출|침해)"]},

    # Fallback
    "other": {"fine": False, "priority": 10**6, "triggers": []},
}


PRIORITY_PROFILES = {
    "intraday_kr": {
        # 거래/생존
        "flow.trading_resumption": 10,
        "company.operational_incident": 12,
        "company.default_event": 14,
        "company.business_suspension": 16,
        "company.rehabilitation_apply": 18,
        "krx.delisting_notice": 20,
        "company.delisting_watch": 22,
        "krx.watchlist_designation": 24,
        "krx.trading_halt_vi": 26,
        "flow.trading_halt_cb": 27,

        # M&A
        "company.mna_binding_agreement": 30,
        "company.mna_merger": 31,
        "company.mna_termination": 32,
        "company.share_exchange_transfer": 33,
        "company.split_merger": 35,
        "company.mna_regulatory_clearance": 36,
        "company.mna_letter_of_intent": 38,
        "company.mna_deal": 39,

        # 자본/주식 구조
        "company.capital_increase_rights": 50,
        "company.capital_reduction": 52,
        "company.at1_issue": 54,
        "company.convertible_bond_issue": 56,
        "company.exchangeable_bond_issue": 57,
        "company.bw_issue": 58,
        "company.buyback_acquire": 60,
        "company.buyback_trust_sign": 61,
        "company.buyback_dispose": 62,
        "company.buyback_trust_terminate": 63,
        "company.stock_split": 65,
        "company.bonus_issue": 68,

        # 계약/설비/자산
        "company.big_contract_update": 70,
        "company.capex_expansion": 72,
        "sector.semicon_capacity_commit": 73,
        "company.business_acquisition": 74,
        "company.business_disposal": 75,
        "company.tangible_asset_acquisition": 76,
        "company.tangible_asset_disposal": 77,
        "company.listing_overseas": 78,
        "flow.index_inout": 79,

        # 운영(정기)/서비스
        "company.plant_shutdown_maintenance": 95,
        "company.plant_restart_rampup": 96,
        "company.service_launch_termination": 98,
        "company.labor_strike_negotiation": 106,

        # 실적/가이던스/신용
        "company.earnings_result": 100,
        "company.guidance_update": 101,
        "company.credit_rating_change": 104,
        "company.rating_watch_outlook": 105,

        # 바이오
        "sector.biotech_primary_endpoint_result": 110,
        "sector.biotech_regulatory": 112,
        "sector.biotech_clinical_hold_lifted": 114,
        "sector.biotech_nda_bla_filing": 118,
        "sector.biotech_ind_clearance": 119,
        "sector.biotech_pdufa_set": 122,
        "sector.biotech_trial_enrollment_complete": 126,

        # 반도체
        "sector.semicon_node_transition": 130,
        "sector.semicon_tapeout": 131,
        "sector.semicon_qualification_pass": 132,

        # 법무/규제 일반
        "company.violation_of_law": 170,
        "company.regulatory_sanction_fine": 172,
        "company.litigation_outcome": 174,
        "company.litigation_filed": 176,
        "company.data_breach": 178,
        "company.product_safety_recall": 179,
        "company.whistleblowing_investigation": 180,

        # 캘린더/섹터지표
        "flow.options_expiry": 320,
        "calendar.earnings_date": 330,
        "calendar.dividend_dates": 331,
        "calendar.options_expiry_date": 332,
        "calendar.index_rebalance_effective": 333,
        "calendar.lockup_expiration": 334,
        "calendar.investor_day_ndr": 335,
        "calendar.shareholder_meeting": 336,
        "sector.retail_sssg_inventory": 360,
        "sector.software_saas_metrics": 361,
        "sector.energy_oil_gas": 362,
        "sector.shipping_freight_index": 363,
        "sector.financial_nim_provision_capital": 364,
        "sector.auto_ev_policy_recall": 365,
        "sector.semicon_capex_yield": 366,
        "krx.shortselling_ban_toggle": 380,
    },
    # 필요 시 다른 프로파일 추가 가능
}

def get_registry(profile: str | None = None) -> dict:
    """기본 레지스트리에 프로파일 우선순위를 덮어씌운 사본을 반환"""
    reg = deepcopy(LABEL_REGISTRY_BASE)
    if profile:
        patch = PRIORITY_PROFILES.get(profile)
        if patch:
            for k, v in patch.items():
                if k in reg:
                    reg[k]["priority"] = int(v)
    return reg