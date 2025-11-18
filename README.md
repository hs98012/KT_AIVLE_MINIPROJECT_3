# KT_AIVLE_MINIPROJECT_3

## 프로젝트 소개
헬스케어·사업공고 분석 사례로 확인하는 **산업 맞춤형 에이전트 시스템 구현**

## 프로젝트 기간
- 2025.11.07 ~ 2025.11.12
  
## 개발 환경
- Python
- OpenAI API
- FAISS
- Tavily Search API
- yfinance
  
## 주요 기능
### Day1 – WebAgent (웹/뉴스/주가/기업 정보)

- Tavily로 헬스케어/기업 관련 웹·뉴스 검색
- yfinance로 티커 기반 실시간 주가·기업 정보 수집
- HTML 본문에서 의미 있는 문단만 필터링하는 전처리 로직 (web_search)
- LiteLLM 기반 LLM 요약으로 뉴스/기업 개요를 3~5문장으로 요약
- 멀티스레딩(ThreadPoolExecutor)을 사용해
  - 웹 검색
  - 주가 조회
  - 기업 개요 요약
- 결과를 Markdown 파일로 저장해 이후 RAG/보고서에 재활용 가능

### Day2 – RagAgent (내부 문서 RAG)

- 내부 문서(PDF, 보고서, 정책 자료 등)를 chunking → 클렌징 → 임베딩 → 인덱싱 파이프라인으로 처리
- OpenAI 임베딩을 사용해 벡터화 후 FAISS 인덱스 구축
- docs.jsonl에 chunk·메타데이터 저장, 인덱스(faiss.index)와 함께 관리
- HyDE 기반 Query 확장 후 FAISS 검색
- 검색 결과에 대해 품질/범위 체크, 스코어 임계값을 두어 “근거가 충분할 때만 요약 제공”하는 보수적 게이팅 전략 적용
- Hallucination를 최소화하는 RAG 파이프라인 구현

### Day3 – GovAgent & PPS Agent (정부 공고/입찰)

- 다양한 포털 + PPS OpenAPI를 통합해 사업·입찰 공고를 한 번에 조회
- 마감일, 키워드 적합도, 출처 신뢰도에 기반해 랭킹을 적용하여 “지금 당장 봐야 할 공고” 우선 정렬

#### GovAgent

- NIPA, Bizinfo, 복지부 등 다양한 포털에서
- 정부 공고 제목·URL·요약 수집
- 수집된 공고는 normalize 단계에서 표준 스키마로 변환
  - 사업명
  - 기관
  - 마감일
  - 예산
  - 링크

#### PPS Agent

- 나라장터 OpenAPI를 통해 입찰 공고를 구조화 수집
- 사업명 / 기관 / 마감일 / 예산 / 입찰 방식 등

### 결과
- 하나의 질문으로 뉴스·주가·정부 공고·입찰 정보·내부 문서를 연결하는 멀티 에이전트 기반 정보검색·요약 시스템 구조 설계 및 구현
- 각 Agent 출력이 Markdown 리포트로 저장되어 RAG / 보고서 / 제안서에 바로 활용 가능한 형태로 정제됨을 확인
