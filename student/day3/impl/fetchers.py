# -*- coding: utf-8 -*-
"""
정부/공공 포털 및 일반 웹에서 '사업 공고'를 찾기 위한 검색 래퍼

설계 포인트
- '도메인 제한' + '키워드 보강'을 동시에 사용해 노이즈를 줄입니다.
- Tavily Search API를 통해 결과를 가져오며, 결과 스키마는 Day1 web 결과와 동일한 단순 형태를 사용합니다.
- 여기선 '검색'만 담당합니다. 정규화/랭킹은 normalize.py / rank.py에서 수행합니다.

권장 쿼리 전략
- NIPA(정보통신산업진흥원):  site:nipa.kr  +  ("공고" OR "모집" OR "지원")
- Bizinfo(기업마당):       site:bizinfo.go.kr + 유사 키워드
- 일반 웹(Fallback):       쿼리 + "모집 공고 지원 사업" 같은 보조 키워드로 recall 확보
"""

from typing import List, Dict, Any, Optional
import os

# Day1에서 제작한 Tavily 래퍼를 재사용합니다.
from student.day1.impl.tavily_client import search_tavily

DEFAULT_TOPK = 7
DEFAULT_TIMEOUT = 20

# 기본 TopK(권장): NIPA 3, Bizinfo 2, Web 2
NIPA_TOPK = 3
BIZINFO_TOPK = 2
WEB_TOPK = 2

def fetch_nipa(query: str, topk: int = NIPA_TOPK) -> List[Dict[str, Any]]:
    """
    NIPA 도메인에 한정한 사업 공고 검색
    - include_domains=["nipa.kr"] 힌트를 주고, 검색 쿼리에도 site:nipa.kr을 붙입니다.
    - '공고/모집/지원' 같은 키워드로 사업 공고 문서를 우선 노출시킵니다.
    반환: Day1 web 스키마 리스트 [{title, url, content/snippet, ...}, ...]
    """
    # TODO[DAY3-F-01]:
    # 1) os.getenv("TAVILY_API_KEY","")로 키를 읽습니다.
    # 2) 질의 q를 만들 때: f"{query} 공고 모집 지원 site:nipa.kr"
    # 3) search_tavily(q, key, top_k=topk, timeout=DEFAULT_TIMEOUT, include_domains=["nipa.kr"])
    # 4) 그대로 반환
    key = os.getenv("TAVILY_API_KEY", "")
    q = f"{query} 공고 모집 지원 site:nipa.kr"
    try:
        return search_tavily(
            q,
            key,
            top_k=topk,
            timeout=DEFAULT_TIMEOUT,
            include_domains=["nipa.kr"],
        )
    except Exception:
        # 실패 시, 빈 리스트 반환해 계속 진행하도록 실시
        return []

def fetch_bizinfo(query: str, topk: int = BIZINFO_TOPK) -> List[Dict[str, Any]]:
    """
    Bizinfo(기업마당) 도메인에 한정한 사업 공고 검색
    - include_domains=["bizinfo.go.kr"]
    - '공고/모집/지원' 키워드 보강
    """
    # TODO[DAY3-F-02]:
    # 위 NIPA와 동일한 패턴이며, site:bizinfo.go.kr / include_domains=["bizinfo.go.kr"] 를 사용
    key = os.getenv("TAVILY_API_KEY", "")
    q = f"{query} 공고 모집 지원 site:bizinfo.go.kr"
    try:
        return search_tavily(
            q,
            key,
            top_k=topk,
            timeout=DEFAULT_TIMEOUT,
            include_domains=["bizinfo.go.kr"],
        )
    except Exception:
        return []

def fetch_web(query: str, topk: int = WEB_TOPK) -> List[Dict[str, Any]]:
    """
    일반 웹 Fallback: 사업 공고와 관련된 키워드를 넣어 Recall 확보
    - 도메인 제한 없이 Tavily 기본 검색 사용
    - 가짜/홍보성 페이지 노이즈는 뒤 단계(normalize/rank)에서 걸러냅니다.
    """
    # TODO[DAY3-F-03]:
    # 1) 키 읽기
    # 2) q = f"{query} 모집 공고 지원 사업"
    # 3) search_tavily(q, key, top_k=topk, timeout=DEFAULT_TIMEOUT)
    
    api_key = os.getenv("TAVILY_API_KEY", "")
    q = f"{query} 모집 공고 지원 사업"
    return search_tavily(
            q,
            api_key,
            top_k=topk,
            timeout=DEFAULT_TIMEOUT
            )

    # raise NotImplementedError("TODO[DAY3-F-03]: 일반 웹 검색 호출")

def fetch_all(query: str) -> List[Dict[str, Any]]:
    """
    편의 함수: 현재 설정된 전 소스에서 가져오기
    주의) 실전에서는 소스별 topk를 plan을 통해 주입받아야 합니다.
    """
    # TODO[DAY3-F-04]:
    # - 위 세 함수를 순서대로 호출해 리스트를 이어붙여 반환
    # - 실패 시 빈 리스트라도 반환(try/except로 유연 처리 가능)
    
    items : List[Dict[str, Any]] = []

    try :
        items.extend(fetch_nipa(query, NIPA_TOPK))
    except Exception :
        pass
    try:
        items.extend(fetch_bizinfo(query, BIZINFO_TOPK))
    except Exception:
        pass
    try:
        items.extend(fetch_web(query, WEB_TOPK))
    except Exception:
        pass
    return items

    
    # raise NotImplementedError("TODO[DAY3-F-04]: 전체 소스 수집")
