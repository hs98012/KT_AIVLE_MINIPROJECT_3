# -*- coding: utf-8 -*-
import os, requests
from typing import List, Dict, Any, Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

TAVILY_BASE = "https://api.tavily.com"

def _headers(api_key: str) -> dict:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

def search_tavily(
    query: str,
    api_key: Optional[str],
    top_k: int = 6,
    timeout: int = 20,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    search_depth: str = "basic",
    include_answer: bool = False,
    include_images: bool = False,
    include_raw_content: bool = False,
    **kwargs: Any,
) -> List[Dict[str, Any]]:
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY is required for web search")

    payload: Dict[str, Any] = {
        "query": query,
        "search_depth": search_depth,
        "max_results": top_k,
        "top_k": top_k,
        "include_answer": include_answer,
        "include_images": include_images,
        "include_raw_content": include_raw_content,
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains
    payload.update({k: v for k, v in kwargs.items() if v is not None})

    r = requests.post(f"{TAVILY_BASE}/search", headers=_headers(api_key), json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data.get("results", []) or []

def extract_url(url: str) -> str:
    """URL을 정리(normalize)해서 반환 (추적 파라미터/fragment 제거)"""
    if not url:
        return ""
    url = url.strip()
    try:
        parts = urlsplit(url)
        qs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
              if not (k.lower().startswith("utm_") or k.lower() in {"fbclid", "gclid"})]
        cleaned = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(qs), ""))
        return cleaned
    except Exception:
        return url

# 본문 추출 (Tavily Extract API 사용)
# web_search.py (발췌) - extract_text 대체/보강 예시
import re, time, html
import requests
from bs4 import BeautifulSoup

UI_NOISE_WORDS = [
    "장바구니","검색버튼","검색창","전체삭제","뒤로가기","홈으로","쿠폰","멤버십","이벤트","기획전",
    "추천 제품","카테고리","슬라이드","삼성스토어","사업자몰","주문/배송조회","구독클럽","고객지원",
    "나의 제품","회원","로그인","바로가기","더보기"
]
UI_NOISE_RE = re.compile("|".join(map(re.escape, UI_NOISE_WORDS)), re.I)

POS_WORDS = [
    "회사","기업","사업","제품","서비스","브랜드","시장","고객","경쟁력","글로벌","해외","네트워크",
    "반도체","메모리","파운드리","디스플레이","모바일","스마트폰","TV","가전","R&D","연구","개발",
    "생태계","지속가능","ESG","전략","수익","포트폴리오"
]
NEG_WORDS = [
    "연혁","출시","공개","선정","수상","양산","투자","발표","나노","신규","슬라이드","추천 제품",
    "쿠폰","멤버십","장바구니","검색","이벤트","기획전"
]

def _score_block(text: str) -> int:
    # UI 잡텍스트 제거
    t = UI_NOISE_RE.sub(" ", text)
    # 너무 짧은 줄 제거 + 공백 정리
    t = re.sub(r"\s+", " ", t).strip()
    # 스코어링
    score = 0
    for w in POS_WORDS:
        if w in t: score += 2
    for w in NEG_WORDS:
        if w in t: score -= 1
    # 형태 힌트: 문장부호/명사 비율 추정(간단)
    if len(t) > 400: score += 2
    if sum(ch.isdigit() for ch in t) > len(t) * 0.15:  # 숫자 과다(표/가격/코드)
        score -= 1
    return score

def extract_text(url: str, api_key: str | None = None, timeout=10) -> str:
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36")
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return ""

    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = resp.apparent_encoding or "utf-8"
    soup = BeautifulSoup(resp.text or "", "html.parser")

    # 1) 명시적 UI 영역 제거
    for t in soup(["script","style","noscript","template","svg"]): t.extract()
    for sel in [
        "header","footer","nav","aside","form","button","input","select",
        "[role=navigation]","#header","#footer",".header",".footer",".nav",".gnb",
        ".breadcrumb",".global-navigation",".local-navigation",".util",".search",
        ".menu",".submenu",".tab",".quick",".floating",".banner",".slider",".carousel"
    ]:
        for node in soup.select(sel): node.extract()

    # 2) 후보 섹션 추출(main/article/section/div[role=main] 중심)
    candidates = []
    def cleaned_text(node):
        txt = node.get_text(" ", strip=True)
        txt = UI_NOISE_RE.sub(" ", txt)
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt

    for css in ["main","article","section","div[role=main]","div"]:
        for node in soup.select(css):
            txt = cleaned_text(node)
            if len(txt) >= 150:
                candidates.append(( _score_block(txt), len(txt), txt ))

    if not candidates:
        body = cleaned_text(soup)
        return body[:8000]

    # 3) 길이보다는 '점수'가 높은 블록을 우선, 동점이면 더 긴 걸 선택
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best = candidates[0][2]

    # 4) 문장 레벨 UI/쇼핑몰 문장 제거
    sents = re.split(r'(?<=[\.!?])\s+|(?<=다)\.\s+|(?<=요)\.\s+|(?<=니다)\.\s+', best)
    sents = [s.strip() for s in sents if s and len(s.strip()) >= 8]
    sents = [s for s in sents if not UI_NOISE_RE.search(s)]
    # 너무 짧거나 중복 심한 문장 제거
    uniq = []
    seen = set()
    for s in sents:
        key = s[:60]
        if key in seen: continue
        seen.add(key)
        uniq.append(s)
    return " ".join(uniq)[:8000]
