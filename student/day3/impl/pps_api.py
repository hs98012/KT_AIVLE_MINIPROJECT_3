# -*- coding: utf-8 -*-
"""
나라장터 OpenAPI
- 1순위: getBidPblancListInfoServcPPSSrch (검색형, 공고명 부분검색: bidNtceNm)
- 폴백 : getBidPblancListInfoServc (일반형)
- 필수 파라미터: ServiceKey(대문자 S), type=json, inqryDiv, inqryBgnDt, inqryEndDt, pageNo, numOfRows
- 날짜창: .env의 PPS_DATE_FROM / PPS_DATE_TO (YYYYMMDDHHMM) 없으면 PPS_LOOKBACK_DAYS(기본 30일)
- 반환: pps_fetch_bids() -> 원본 items(list[dict])
- 표 변환: to_common_schema() -> title/agency/announce_date/close_date/budget/url/… 확장 필드 포함
"""

from __future__ import annotations
import os, requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone

# -------------------- 기본 설정 --------------------
KST = timezone(timedelta(hours=9))
BASE = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService"

# 용역 전용 엔드포인트
OP_SERVC_SEARCH = "getBidPblancListInfoServcPPSSrch"  # 검색형(공고명 부분검색 bidNtceNm 지원)
OP_SERVC_GENERAL = "getBidPblancListInfoServc"        # 일반형

# -------------------- 날짜/문자 유틸 --------------------
def _coerce_dt(s: str, end: bool) -> str:
    """'YYYYMMDDHHMM' 또는 'YYYYMMDD' → 'YYYYMMDDHHMM'로 보정. 비어있으면 lookback 기준 생성."""
    s = (s or "").strip()
    if len(s) == 12 and s.isdigit():
        return s
    if len(s) == 8 and s.isdigit():
        return s + ("2359" if end else "0000")
    # fallback: 최근 N일
    lookback = int(os.getenv("PPS_LOOKBACK_DAYS", "30") or "30")
    now = datetime.now(KST)
    return (now.strftime("%Y%m%d2359") if end else (now - timedelta(days=lookback)).strftime("%Y%m%d0000"))

def _date_window() -> Tuple[str, str]:
    return _coerce_dt(os.getenv("PPS_DATE_FROM", ""), False), _coerce_dt(os.getenv("PPS_DATE_TO", ""), True)

def _parse_dt_kst(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=KST)
        except Exception:
            pass
    return None

def _pretty_dt(s: str) -> str:
    dt = _parse_dt_kst(s)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else (s or "")

def _money(x: Any) -> str:
    try:
        n = int(float(str(x).replace(",", "").strip()))
        return f"{n:,}원"
    except Exception:
        return str(x or "")

def _detail_link(it: Dict[str, Any]) -> str:
    bidno = str(it.get("bidNtceNo") or it.get("bidno") or "").strip()
    bidseq = str(it.get("bidNtceOrd") or it.get("bidseq") or "0").strip()
    if not bidno:
        return ""
    # 공식 상세 페이지 딥링크(단일공고)
    return f"https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo={bidno}&bidPbancOrd={bidseq}"

# -------------------- 공통 파라미터/호출 --------------------
def _params_base(page: int, rows: int) -> Dict[str, Any]:
    bgn, end = _date_window()
    return {
        "ServiceKey": (os.getenv("PPS_SERVICE_KEY") or os.getenv("PPS_API_KEY") or "").strip(),
        "type": "json",
        "inqryDiv": os.getenv("PPS_INQRY_DIV", "1").strip() or "1",
        "inqryBgnDt": bgn,
        "inqryEndDt": end,
        "pageNo": str(page),
        "numOfRows": str(rows),
    }

def _call(op: str, params: Dict[str, Any], timeout: int = 20, debug: bool = False) -> Dict[str, Any]:
    url = f"{BASE}/{op}"
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if debug:
        header = data.get("response", {}).get("header", {})
        body = data.get("response", {}).get("body", {})
        total = body.get("totalCount")
        items = body.get("items")
        n = (
            len(items) if isinstance(items, list)
            else len(items.get("item")) if isinstance(items, dict) and isinstance(items.get("item"), list)
            else 1 if isinstance(items, dict) else 0
        )
        print(f"[PPS][{op}] page={params.get('pageNo')} total={total} got={n} code={header.get('resultCode')}")
    return data

def _extract(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = payload.get("response", {}).get("body", {})
    items = body.get("items")
    if items is None:
        return []
    if isinstance(items, list):
        return items
    if isinstance(items, dict):
        it = items.get("item")
        if isinstance(it, list):
            return it
        if isinstance(it, dict):
            return [it]
        return [items]
    return []

# -------------------- 메인: 서버사이드 키워드 검색(용역 전용) --------------------
def pps_fetch_bids(
    keyword: Optional[str] = "",
    page_max: int = int(os.getenv("PPS_PAGE_MAX", "2") or "2"),
    rows: int = int(os.getenv("PPS_ROWS", "100") or "100"),
    timeout: int = 20,
    debug: bool = False,
) -> List[Dict[str, Any]]:
    """
    용역 공고만 조회.
    - keyword가 있으면: getBidPblancListInfoServcPPSSrch + bidNtceNm=keyword
      (결과 없을 때만 일반형으로 폴백)
    - keyword가 없으면: 일반형으로 전량 수집
    - 반환: payload body.items (list[dict])
    """
    kw = (keyword or "").strip()
    params0 = _params_base(1, rows)

    def in_window(it: Dict[str, Any]) -> bool:
        bgn, end = params0["inqryBgnDt"], params0["inqryEndDt"]
        bgn_dt, end_dt = _parse_dt_kst(bgn), _parse_dt_kst(end)
        adt = _parse_dt_kst(str(it.get("bidNtceDt") or it.get("ntceDt") or it.get("bidBeginDt") or ""))
        if not (adt and bgn_dt and end_dt):
            return True
        return bgn_dt <= adt <= end_dt

    items: List[Dict[str, Any]] = []

    # 1) 검색형(키워드 있을 때)
    if kw:
        for page in range(1, page_max + 1):
            p = dict(params0, pageNo=str(page))
            p["bidNtceNm"] = kw  # 공고명 부분검색
            data = _call(OP_SERVC_SEARCH, p, timeout=timeout, debug=debug)
            chunk = _extract(data)
            if not chunk:
                break
            items.extend(chunk)

    # 2) 결과 없으면 일반형 폴백(혹은 애초에 키워드 없음)
    if not items:
        for page in range(1, page_max + 1):
            p = dict(params0, pageNo=str(page))
            data = _call(OP_SERVC_GENERAL, p, timeout=timeout, debug=debug)
            chunk = _extract(data)
            if not chunk:
                break
            items.extend(chunk)
        # 일반형으로 가져왔는데 키워드가 있었다면 제목 최소 필터
        if kw:
            k = kw.casefold()
            def title(it):
                return str(it.get("bidNtceNm") or it.get("bidNm") or it.get("ntceNm") or "").casefold()
            items = [it for it in items if k in title(it)]

    # 3) 날짜창 재확인(서버가 느슨할 가능성 대비)
    items = [it for it in items if in_window(it)]

    if debug:
        bgn, end = params0["inqryBgnDt"], params0["inqryEndDt"]
        print(f"[PPS][FINAL] op={'SEARCH' if kw else 'GENERAL'} out={len(items)} window={bgn}~{end} keyword={kw!r}")

    return items

# -------------------- 공통 스키마(표 렌더용) --------------------
def to_common_schema(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    원시 items를 공통 스키마로 정규화.
    기본 필드 + 확장 필드(공고유형/계약방법/낙찰방법/공고번호)를 포함한다.
    반환 키:
      - title, agency, announce_date, close_date, budget, url
      - bid_no, notice_kind, contract_method, award_method
      - raw (원본 dict)
    """
    out: List[Dict[str, Any]] = []
    for it in items or []:
        title = str(it.get("bidNtceNm") or it.get("bidNm") or it.get("ntceNm") or "").strip()
        agency = str(it.get("dminsttNm") or it.get("ntceInsttNm") or it.get("orgNm") or "").strip()

        # 날짜
        announce = str(it.get("bidNtceDt") or it.get("ntceDt") or it.get("bidBeginDt") or "")
        close = str(it.get("bidClseDt") or it.get("opengDt") or it.get("bidEndDt") or "")

        # 예산
        budget = _money(it.get("presmptPrce") or it.get("asignBdgtAmt") or it.get("totPrdprc") or "")

        # 링크/번호
        bidno = str(it.get("bidNtceNo") or it.get("bidno") or "").strip()
        bidseq = str(it.get("bidNtceOrd") or it.get("bidseq") or "0").strip()
        url = str(it.get("bidNtceUrl") or it.get("bidNtceDtlUrl") or _detail_link(it)).strip()

        # 부가정보
        notice_kind = str(it.get("ntceKindNm") or "").strip()                # 등록공고/재공고 등
        contract_method = str(it.get("cntrctCnclsMthdNm") or "").strip()     # 계약방법
        award_method = str(it.get("sucsfbidMthdNm") or "").strip()           # 낙찰방법

        out.append({
            "title": title or "(제목 없음)",
            "agency": agency or "-",
            "announce_date": _pretty_dt(announce) or "-",
            "close_date": _pretty_dt(close) or "-",
            "budget": budget or "-",
            "url": url,
            "bid_no": f"{bidno}-{bidseq}" if bidno else "",
            "notice_kind": notice_kind,
            "contract_method": contract_method,
            "award_method": award_method,
            "raw": it,
        })
    return out
