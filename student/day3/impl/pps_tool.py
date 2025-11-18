# -*- coding: utf-8 -*-
"""
PPS(나라장터) 검색 + 렌더 + 저장 유틸
- 의존: student.day3.impl.pps_api (pps_fetch_bids, to_common_schema)
- 정렬: 공고일(announce_date) 기준 최신순(DESC) 필수 적용
- 표: 기본(공고일 → 마감일), 확장표 옵션 지원
"""

from __future__ import annotations
import os, re
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# ---- pps_api 함수 가져오기 ----
from student.day3.impl.pps_api import (
    pps_fetch_bids as _FETCH,
    to_common_schema as _TO_COMMON,
)

KST = timezone(timedelta(hours=9))

# ---------- 경로/저장 ----------
def _slugify(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^0-9A-Za-z가-힣\-_\.]+", "", text)
    return text[:120] or "output"

def _find_project_root() -> Path:
    start = Path(__file__).resolve()
    markers = ("uv.lock", "pyproject.toml", "apps", "student", ".git")
    for p in [start, *start.parents]:
        try:
            if any((p / m).exists() for m in markers):
                return p
        except Exception:
            pass
    return Path.cwd().resolve()

def _default_output_dir() -> Path:
    env_dir = os.getenv("OUTPUT_DIR", "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return (_find_project_root() / "data" / "processed").resolve()

def _save_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding, newline="\n") as f:
        f.write(text)

# ---------- 날짜 유틸 ----------
def _parse_dt_kst(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y%m%d%H%M", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=KST)
        except Exception:
            continue
    return None

def _pretty_date(s: str) -> str:
    dt = _parse_dt_kst(s)
    return dt.strftime("%Y-%m-%d %H:%M") if dt else (s or "")

# ---------- 파라미터 ----------
@dataclass
class PpsParams:
    keyword: str
    rows: int
    page_max: int
    only_open: bool
    table_limit: int
    extended: bool

def _resolve_params(user_query: str) -> PpsParams:
    keyword = (user_query or os.getenv("PPS_DEFAULT_QUERY", "")).strip()
    rows = int(os.getenv("PPS_ROWS", "100") or "100")
    page_max = int(os.getenv("PPS_PAGE_MAX", "2") or "2")
    only_open = (os.getenv("PPS_FILTER_ONLY_OPEN", "0").strip() == "1")

    # 최소 10개는 보여주도록 보장
    env_limit = int(os.getenv("PPS_TABLE_LIMIT", "30") or "30")
    table_limit = max(env_limit, 10)

    extended = (os.getenv("PPS_TABLE_EXTENDED", "0").strip() == "1")
    return PpsParams(keyword, rows, page_max, only_open, table_limit, extended)

# ---------- 후처리(정렬/필터) ----------
def _sort_by_announce_desc(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # 공고일(announce_date) 최신순
    def key(it):
        dt = _parse_dt_kst(str(it.get("announce_date") or ""))
        # 공고일이 없으면 아주 오래된 날짜로 취급
        return dt or datetime(1970, 1, 1, tzinfo=KST)
    return sorted(items, key=key, reverse=True)

def _filter_only_open(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # 마감일이 오늘(KST) 이후인 것만
    now = datetime.now(KST)
    out: List[Dict[str, Any]] = []
    for it in items:
        close = _parse_dt_kst(str(it.get("close_date") or ""))
        if (close is None) or (close >= now):
            out.append(it)
    return out

# ---------- 렌더링 ----------
def _render_table(items: List[Dict[str, Any]], limit: int, extended: bool) -> str:
    if not items:
        return "관련 공고를 찾지 못했습니다."

    def link(u: str) -> str:
        return f"[바로가기]({u})" if u else "-"

    # 기본 표(요청: 공고일 → 마감일)
    if not extended:
        lines = [
            "| 공고일 | 마감일 | 공고명 | 주관기관 | 예산 | 링크 |",
            "|---|---|---|---|---:|---|",
        ]
        for it in items[:limit]:
            lines.append(
                "| {ann} | **{close}** | {title} | {agency} | {budget} | {url} |".format(
                    ann=_pretty_date(it.get("announce_date", "")),
                    close=_pretty_date(it.get("close_date", "")),
                    title=it.get("title", "-"),
                    agency=it.get("agency", "-"),
                    budget=it.get("budget", "-"),
                    url=link(it.get("url", "")),
                )
            )
        return "\n".join(lines)

    # 확장 표(공고일 → 마감일)
    lines = [
        "| 공고일 | 마감일 | 공고명 | 주관기관 | 예산 | 공고번호 | 공고유형 | 계약방법 | 낙찰방법 | 링크 |",
        "|---|---|---|---|---:|---|---|---|---|---|",
    ]
    for it in items[:limit]:
        lines.append(
            "| {ann} | **{close}** | {title} | {agency} | {budget} | {bidno} | {kind} | {contract} | {award} | {url} |".format(
                ann=_pretty_date(it.get("announce_date", "")),
                close=_pretty_date(it.get("close_date", "")),
                title=it.get("title", "-"),
                agency=it.get("agency", "-"),
                budget=it.get("budget", "-"),
                bidno=it.get("bid_no", ""),
                kind=it.get("notice_kind", ""),
                contract=it.get("contract_method", ""),
                award=it.get("award_method", ""),
                url=link(it.get("url", "")),
            )
        )
    return "\n".join(lines)

def _render_markdown(query: str, items: List[Dict[str, Any]], saved_path: str, extended: bool, limit: int) -> str:
    header = (
        f"---\noutput_schema: v1\ntype: markdown\nroute: pps\n"
        f"saved: {saved_path}\nquery: \"{query.replace('\"','\\\"')}\"\n---\n\n"
    )
    body = [
        "# 나라장터 용역 공고(최근)",
        "",
        f"- 질의: {query}",
        "",
        _render_table(items, limit=limit, extended=extended),
    ]
    footer = f"\n\n---\n> 저장 위치: `{saved_path}`\n"
    return header + "\n".join(body) + footer

def _save_md(query: str, items: List[Dict[str, Any]], route: str, extended: bool, limit: int) -> str:
    outdir = _default_output_dir()
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    fname = f"{ts}__{route}__{_slugify(query)}.md"
    abspath = (outdir / fname).resolve()
    md = _render_markdown(query, items, saved_path=str(abspath), extended=extended, limit=limit)
    _save_text(abspath, md)
    return str(abspath)

# ---------- 외부 노출 엔트리 ----------
def pps_search(query: str) -> str:
    """
    1) pps_api에서 용역 공고 수집 (검색형 우선)
    2) 공통 스키마 정규화
    3) (옵션) 마감 지난 공고 제거
    4) 공고일 최신순 정렬
    5) 마크다운 저장 + 본문 반환
    """
    # 파라미터
    p = _resolve_params(query)

    # 수집
    raw_items = _FETCH(keyword=p.keyword, page_max=p.page_max, rows=p.rows, timeout=20, debug=False)

    # 정규화
    items = _TO_COMMON(raw_items)

    # (옵션) 마감 지난 공고 제외
    if p.only_open:
        items = _filter_only_open(items)

    # 공고일 최신순 정렬
    items = _sort_by_announce_desc(items)

    # 저장 + 본문 반환
    _ = _save_md(p.keyword or query, items, route="pps", extended=p.extended, limit=p.table_limit)
    return _render_markdown(p.keyword or query, items, saved_path="(see header)", extended=p.extended, limit=p.table_limit)
