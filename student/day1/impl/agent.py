# -*- coding: utf-8 -*-
"""
Day1 본체
- 역할: 웹 검색 / 주가 / 기업개요(추출+요약)를 병렬로 수행하고 결과를 정규 스키마로 병합
"""

from __future__ import annotations
from dataclasses import asdict
from typing import Optional, Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from google.adk.models.lite_llm import LiteLlm
from student.common.schemas import Day1Plan
from student.day1.impl.merge import merge_day1_payload
# 외부 I/O
from student.day1.impl.tavily_client import search_tavily, extract_url
from student.day1.impl.finance_client import get_quotes
from student.day1.impl.web_search import (
    looks_like_ticker,
    search_company_profile,
    extract_and_summarize_profile,
)

DEFAULT_WEB_TOPK = 6
MAX_WORKERS = 4
DEFAULT_TIMEOUT = 20

# ------------------------------------------------------------------------------
# TODO[DAY1-I-01] 요약용 경량 LLM 준비
#  - 목적: 기업 개요 본문을 Extract 후 간결 요약
#  - LiteLlm(model="openai/gpt-4o-mini") 형태로 _SUM에 할당
# ------------------------------------------------------------------------------
_SUM: Optional[LiteLlm] = LiteLlm(model="openai/gpt-4o-mini")


def _summarize(text: str) -> str:
    """
    입력 텍스트를 LLM으로 3~5문장 수준으로 요약합니다.
    실패 시 빈 문자열("")을 반환해 상위 로직이 안전하게 진행되도록 합니다.
    """
    # ----------------------------------------------------------------------------
    # TODO[DAY1-I-02] 구현 지침
    #  - _SUM이 None이면 "" 반환(요약 생략)
    #  - _SUM.invoke({...}) 혹은 단순 텍스트 인자 형태로 호출 가능한 래퍼라면
    #    응답 객체에서 본문 텍스트를 추출하여 반환
    #  - 예외 발생 시 빈 문자열 반환
    # ----------------------------------------------------------------------------
    if not text or not isinstance(text, str):
        return ""
    if _SUM is None:
        return ""
    try:
        prompt = f"다음 내용을 3~5문장으로 간결하게 요약해 주세요:\n\n{text[:6000]}"
        # LiteLlm은 단순 텍스트 입력으로 invoke 가능
        response = _SUM.invoke(prompt)
        # 응답 객체에 .output_text 속성이 있으면 사용
        if isinstance(response, dict):
            return response.get("output_text", "").strip()
        elif hasattr(response, "output_text"):
            return getattr(response, "output_text", "").strip()
        elif isinstance(response, str):
            return response.strip()
        else:
            return str(response).strip()
    except Exception:
        return ""
    
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict

def _safe_len(v):
    try:
        return len(v)
    except Exception:
        return 0

class Day1Agent:
    def __init__(self, tavily_api_key: Optional[str], web_topk: int = DEFAULT_WEB_TOPK, request_timeout: int = DEFAULT_TIMEOUT):
        """
        필드 저장만 담당합니다.
        - tavily_api_key: Tavily API 키(없으면 웹 호출 실패 가능)
        - web_topk: 기본 검색 결과 수
        - request_timeout: 각 HTTP 호출 타임아웃(초)
        """
        # ----------------------------------------------------------------------------
        # TODO[DAY1-I-03] 필드 저장
        #  self.tavily_api_key = tavily_api_key
        #  self.web_topk = web_topk
        #  self.request_timeout = request_timeout
        # ----------------------------------------------------------------------------
        self.tavily_api_key = tavily_api_key
        self.web_topk = web_topk
        self.request_timeout = request_timeout

    def handle(self, query: str, plan: Day1Plan) -> Dict[str, Any]:
        """
        병렬 파이프라인:
          1) results 스켈레톤 만들기
             results = {"type":"web_results","query":query,"analysis":asdict(plan),"items":[],
                        "tickers":[], "errors":[], "company_profile":"", "profile_sources":[]}
          2) ThreadPoolExecutor(max_workers=MAX_WORKERS)에서 작업 제출:
             - plan.do_web: search_tavily(검색어, 키, top_k=self.web_topk, timeout=...)
             - plan.do_stocks: get_quotes(plan.tickers)
             - (기업개요) looks_like_ticker(query) 또는 plan에 tickers가 있을 때:
                 · search_company_profile(query, api_key, topk=2) → URL 상위 1~2개
                 · extract_and_summarize_profile(urls, api_key, summarizer=_summarize)
          3) as_completed로 결과 수집. 실패 시 results["errors"]에 '작업명:에러' 저장.
          4) merge_day1_payload(results) 호출해 최종 표준 스키마 dict 반환.
        """
        # ----------------------------------------------------------------------------
        # TODO[DAY1-I-04] 구현 지침(권장 구조)
        #  - results 초기화 (위 키 포함)
        #  - futures 딕셔너리: future -> "web"/"stock"/"profile" 등 라벨링
        #  - 병렬 제출 조건 체크(plan.do_web, plan.do_stocks, 기업개요 조건)
        #  - 완료 수집:
        #      kind == "web"    → results["items"] = data
        #      kind == "stock"  → results["tickers"] = data
        #      kind == "profile"→ results["company_profile"] = text; results["profile_sources"] = urls(옵션)
        #  - 예외: results["errors"].append(f"{kind}: {type(e).__name__}: {e}")
        #  - return merge_day1_payload(results)
        # ----------------------------------------------------------------------------
        # 1) 결과 스켈레톤
        results: Dict[str, Any] = {
            "type": "web_results",
            "query": query,
            "analysis": asdict(plan),         # Day1Plan은 dataclass 가정
            "items": [],                      # web 검색 결과
            "tickers": [],                    # 주가/티커 결과
            "errors": [],                     # 에러 문자열 모음
            "company_profile": "",            # 최종 요약 텍스트
            "profile_sources": [],            # 요약에 사용된 URL들
        }

        futures = {}

        # 2) 병렬 제출
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            # 2-1) 웹 검색
            if getattr(plan, "do_web", False):
                fut = ex.submit(
                    search_tavily,
                    query,
                    self.tavily_api_key,
                    # 구현부 시그니처는 프로젝트 기준으로 맞추세요
                    top_k=self.web_topk,
                    timeout=self.request_timeout,
                )
                futures[fut] = ("web", None)

            # 2-2) 주가 조회
            if getattr(plan, "do_stocks", False) and _safe_len(getattr(plan, "tickers", [])) > 0:
                fut = ex.submit(
                    get_quotes,
                    getattr(plan, "tickers", []),
                )
                futures[fut] = ("stock", None)

            # 2-3) 기업 개요(프로필) 추출+요약
            need_profile = False
            try:
                need_profile = looks_like_ticker(query) or _safe_len(getattr(plan, "tickers", [])) > 0
            except Exception:
                # looks_like_ticker가 실패해도 plan.tickers만으로 결정
                need_profile = _safe_len(getattr(plan, "tickers", [])) > 0

            if need_profile:
                def _profile_job():
                    # 상위 1~2개 URL 확보
                    urls = search_company_profile(
                        query,
                        self.tavily_api_key,
                        topk=2,
                        timeout=self.request_timeout,
                    ) or []
                    urls = list(urls)[:2]

                    # 본문 추출 & 요약
                    prof = extract_and_summarize_profile(
                        urls,
                        self.tavily_api_key,
                        summarizer=_summarize,           # I-02 미구현이어도 안전(빈 문자열 반환 규약)
                        timeout=self.request_timeout,
                    )

                    # 다양한 구현을 허용: prof가 문자열/딕셔너리/튜플일 수 있음
                    text = ""
                    if isinstance(prof, str):
                        text = prof
                    elif isinstance(prof, dict):
                        # {"text": "...", "summary": "..."} 등 다양한 키를 수용
                        text = prof.get("text") or prof.get("summary") or ""
                    elif isinstance(prof, (tuple, list)) and len(prof) > 0:
                        text = prof[0] or ""

                    return {"text": text or "", "urls": urls}

                fut = ex.submit(_profile_job)
                futures[fut] = ("profile", None)

            # 3) 완료 수집
            for fut in as_completed(futures):
                kind, _ = futures[fut]
                try:
                    data = fut.result()
                    if kind == "web":
                        results["items"] = data or []
                    elif kind == "stock":
                        results["tickers"] = data or []
                    elif kind == "profile":
                        # {"text": str, "urls": list[str]} 형태 수용
                        if isinstance(data, dict):
                            results["company_profile"] = data.get("text", "") or ""
                            results["profile_sources"] = data.get("urls", []) or []
                        else:
                            # 방어적 처리
                            results["company_profile"] = data or ""
                except Exception as e:
                    results["errors"].append(f"{kind}: {type(e).__name__}: {e}")

        # 4) 최종 스키마로 머지하여 반환
        try:
            return merge_day1_payload(results)
        except Exception as e:
            # merge 실패도 에러에 기록하여 원본 results라도 반환
            results["errors"].append(f"merge: {type(e).__name__}: {e}")
            return results