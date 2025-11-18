# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Tuple, Callable
import re, os, textwrap, hashlib, inspect 
from .tavily_client import search_tavily, extract_url, extract_text

PROFILE_DOMAINS = [
    "wikipedia.org", "en.wikipedia.org", "ko.wikipedia.org",
    "finance.google.com", "google.com/finance",
    "invest.deepsearch.com", "m.invest.zum.com",
    "companiesmarketcap.com", "marketscreener.com",
    "alphasquare.co.kr",
]

def looks_like_ticker(q: str) -> bool:
    return bool(re.search(r"\b([A-Z]{1,5}(?:\.[A-Z]{2,4})?|\d{6}(?:\.[A-Z]{2,4})?)\b", q))

def search_company_profile(query: str, api_key: str, topk: int = 6, timeout: int = 20) -> List[Dict[str, Any]]:
    q = f"{query} company profile overview 기업 개요 회사 소개 무엇을 하는 회사"
    # ⬇ 원문 발췌를 렌더에서 쓰고 싶다면 include_raw_content=True를 켜도 좋음
    results = search_tavily(q, api_key, top_k=topk, timeout=timeout, include_raw_content=True)
    def score(r: Dict[str, Any]) -> Tuple[int, float]:
        dom = (r.get("source") or r.get("url") or "").lower()
        prio = 0
        for i, d in enumerate(PROFILE_DOMAINS):
            if d in dom:
                prio = 100 - i
                break
        return (-prio, -float(r.get("score", 0.0)))
    return sorted(results, key=score)

def extract_and_summarize_profile(
    urls: List[str],
    api_key: str,
    summarizer: Callable[[str], str],
    max_chars: int = 6000,
) -> str:
    def _safe(s: str | None) -> str:
        return (s or "").strip()

    def _rule_based_summary(corpus: str) -> str:
        ui_ban = re.compile(
            r"(갤럭시 캠퍼스|장바구니|검색버튼|쿠폰|멤버십|이벤트|기획전|추천 제품|슬라이드|"
            r"뒤로가기|홈으로|검색 결과|카테고리|삼성스토어|사업자몰|구독클럽|주문/배송조회|나의 제품)",
            re.I
        )
        sents = re.split(r'(?<=[\.!?])\s+|(?<=다)\.\s+|(?<=요)\.\s+|(?<=니다)\.\s+', corpus)
        sents = [re.sub(r"\s+", " ", s).strip() for s in sents if s and len(s.strip()) >= 8]
        sents = [s for s in sents if not ui_ban.search(s)]

        pos = re.compile(r"(회사|기업|사업|제품|서비스|시장|고객|반도체|메모리|파운드리|디스플레이|모바일|브랜드|경쟁력|글로벌|생태계|R&D|지속가능|ESG)")
        neg = re.compile(r"(연혁|출시|공개|선정|수상|양산|투자|발표|나노|신규)")

        scored = []
        for s in sents:
            sc = 0
            if pos.search(s): sc += 2
            if neg.search(s): sc -= 1
            if len(s) > 120: sc -= 1
            if len(s) < 10: sc -= 2
            scored.append((sc, s))
        scored.sort(reverse=True, key=lambda x: x[0])

        picked = [s for _, s in scored[:7]] or sents[:5]
        text = " ".join(picked)
        text = textwrap.shorten(text, width=700, placeholder="…")
        return "기업 개요: " + text

    # -------- 본문 수집 --------
    take = urls[:5] if urls else []
    texts: List[str] = []

    print(f"[DEBUG] try URLs: {take}")
    for u in take:
        clean = u  # 필요시 extract_url(u) 쓰면 그대로 유지
        try:
            t = _safe(extract_text(clean, api_key))[:max_chars]
        except Exception as e:
            print(f"[DEBUG] extract_text exception on {clean}: {e}")
            t = ""
        print(f"[DEBUG] fetched len={len(t)} | {clean}")
        if len(t) >= 180:
            texts.append(f"[{clean}]\n{t}")
        elif t:
            texts.append(f"[{clean}]\n{t}")

    if not texts:
        bullets = "\n".join(f"- {u}" for u in take[:3])
        return (
            "기업 개요(폴백): 소비자 전자·반도체 등 핵심 사업 중심의 글로벌 기업. "
            "세부 사항은 아래 출처 참조.\n" + bullets
        )

    joined = "\n\n---\n\n".join(texts)
    prompt = (
        "다음 자료를 근거로 '기업 개요'를 한국어 5~7문장으로 요약하세요.\n"
        "- 핵심 사업/제품, 수익원, 주요 시장/고객, 차별점, 최근 이슈(있으면)\n"
        "- 과도한 재무 디테일은 피하고, 문장당 20~30자 이내로 간결하게.\n\n"
        f"{joined[:6000]}\n"
    )

    # -------- 요약 호출 --------
    summary = ""
    try:
        if callable(summarizer):
            summary = _safe(summarizer(prompt))
    except Exception as e:
        print(f"[DEBUG] summarizer exception: {e}")
        summary = ""

    # -------- 품질 체크 → 규칙기반 폴백 --------
    def _looks_bad(s: str) -> bool:
        if len(s) < 50:
            return True
        # 같은 단어 반복(‘제품 제품 제품’ 등)
        if re.search(r'(\b\w{2,}\b)(?:\s*\1){2,}', s):
            return True
        # UI/쇼핑몰 단어가 잔존하면 나쁨
        ui_ban = re.compile(r"(캠퍼스|장바구니|검색버튼|쿠폰|멤버십|이벤트|기획전|추천 제품|슬라이드)", re.I)
        if ui_ban.search(s): 
            return True
        return False

    if not summary or _looks_bad(summary):
        print("[DEBUG] empty/low-quality summary -> rule-based fallback")
        summary = _rule_based_summary(joined)

    return summary[:800]
