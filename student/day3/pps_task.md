# PPS 공고 검색 파이프라인

**목표:** 키워드로 나라장터(OpenAPI) **용역(Servc)** 입찰공고를 조회하고, **최신순 표** 형태로 마크다운 리포트를 **저장, 표시**

## 구성요소
- `student/day3/pps_agent.py`
  - ADK Agent(`day3_pps_agent`) + `FunctionTool(func=pps_search)`  
  - ADK 일부 버전은 `FunctionTool(name=..., description=...)` 인자를 지원하지 않으므로 **func만 전달**
- `student/day3/impl/pps_tool.py`
  - `pps_search(query: str) -> str`  
  - 파라미터 해석(.env) → `pps_api.pps_fetch_bids(keyword=...)` 호출(검색형 우선) → `to_common_schema` → (옵션) 마감 제외 → **공고일 최신순 정렬** → 표 렌더 + 저장
- `student/day3/impl/pps_api.py`
  - `pps_fetch_bids(keyword, page_max, rows, ...)` : **getBidPblancListInfoServcPPSSrch**(검색형) 우선 호출, 없으면 **getBidPblancListInfoServc**(일반형) 폴백
  - `to_common_schema(items)` : `{title, agency, announce_date, close_date, budget, url}` 로 정규화

## .env 키 (주요)
- 인증
  - `PPS_SERVICE_KEY` : 공공데이터포털 인증키(필수, 대문자 **ServiceKey** 파라미터 사용: .env.example 확인!)
- 기간
  - `PPS_DATE_FROM`, `PPS_DATE_TO` (YYYYMMDDHHMM)  
  - 미설정 시 `PPS_LOOKBACK_DAYS` (기본 30일)
- 페이지/검색
  - `PPS_ROWS` (기본 100), `PPS_PAGE_MAX` (기본 2), `PPS_INQRY_DIV` (기본 1=공고일자)
  - **서버사이드 키워드 검색**: `pps_fetch_bids(keyword="인공지능", ...)` → 내부에서 `bidNtceNm`로 전달
- 출력/표시
  - `OUTPUT_DIR` (없으면 `data/processed/`)
  - `PPS_FILTER_ONLY_OPEN` = `1` 이면 **마감 지난 공고 제외**
  - `PPS_TABLE_LIMIT` : 표에 표시할 최대 행 수(기본 30)

## 터미널 빠른 테스트
```bash
# 최소 설정(세션 한시적)
export PPS_ROWS=50
export PPS_PAGE_MAX=1
export PPS_INQRY_DIV=1
export PPS_FILTER_ONLY_OPEN=0
export PPS_TABLE_LIMIT=50

# 1) API 단위 테스트
uv run python - <<'PY'
from student.day3.impl.pps_api import pps_fetch_bids, to_common_schema
rows = pps_fetch_bids(keyword="인공지능", page_max=1, rows=20, debug=True)
print("got:", len(rows))
for it in to_common_schema(rows)[:5]:
    print(it["announce_date"], "|", it["title"])
PY

# 2) Tool 단위 테스트(정렬/저장/표 제한 확인)
uv run python - <<'PY'
from student.day3.impl.pps_tool import pps_search
print(pps_search("인공지능")[:800])
PY
