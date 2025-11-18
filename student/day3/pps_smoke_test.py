# -*- coding: utf-8 -*-
"""
PPS(OpenAPI) 스모크 테스트
- .env 로드 -> 서비스키/날짜 파라미터 점검
- pps_api 호출(함수명 차이를 자동 흡수)
- 표준 스키마 변환 후 미리보기 + 저장(writer.save_markdown)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# -------------------- 공통 유틸 --------------------
ROOT_SENTINELS = ("uv.lock", "pyproject.toml", "apps", "student", ".git")

def _guess_root(start: Optional[Path] = None) -> Path:
    start = (start or Path.cwd()).resolve()
    for p in [start, *start.parents]:
        try:
            if any((p / m).exists() for m in ROOT_SENTINELS):
                return p
        except Exception:
            pass
    return Path.cwd().resolve()

def _ensure_sys_path(root: Path) -> None:
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)

def _load_env(root: Path) -> None:
    env = root / ".env"
    if env.exists():
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv(str(env), override=False)
        except Exception:
            # 매우 단순 파서
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    print(f"[INFO] ROOT={root}")
    print(f"[INFO] .env={env} | PPS_SERVICE_KEY: {bool(os.getenv('PPS_SERVICE_KEY'))}")

def _env_snapshot() -> None:
    keys = [
        "PPS_SERVICE_KEY", "PPS_DATE_FROM", "PPS_DATE_TO",
        "PPS_ROWS", "PPS_PAGE_MAX",
    ]
    print("[INFO] 환경 변수:")
    for k in keys:
        v = os.getenv(k)
        if not v:
            print(f"  - {k}=(미설정)")
        elif k == "PPS_SERVICE_KEY":
            print(f"  - {k}={v[:4]}...{v[-4:]}")
        else:
            print(f"  - {k}={v}")

def _as_list(x: Any) -> List[Dict[str, Any]]:
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        if isinstance(x.get("items"), list):
            return x["items"]
        for v in x.values():
            if isinstance(v, list):
                return v
    if isinstance(x, tuple) and x and isinstance(x[0], list):
        return x[0]
    return []

def _preview(items: List[Dict[str, Any]], k: int = 5) -> None:
    print(f"[OK] 표준 스키마 {len(items)}건")
    for i, it in enumerate(items[:k], 1):
        print(f"  [{i}] {it.get('title','-')} | {it.get('agency','-')}"
              f" | 공고일={it.get('announce_date','-')} | 마감={it.get('close_date','-')}"
              f" | 예산={it.get('budget','-')}")
        if it.get("url"):
            print(f"      URL: {it['url']}")

# -------------------- 메인 --------------------
def main() -> int:
    root = _guess_root()
    _ensure_sys_path(root)
    _load_env(root)
    _env_snapshot()

    # pps_api import & 함수명 호환
    try:
        from student.day3.impl.pps_api import to_common_schema  # type: ignore
        try:
            from student.day3.impl.pps_api import pps_fetch_bids as _fetch  # type: ignore
        except Exception:
            from student.day3.impl.pps_api import fetch_pps_notices as _fetch  # type: ignore
    except Exception as e:
        print(f"[FAIL] pps_api import 실패: {e}")
        return 1

    # 질의
    query = "헬스케어" if len(sys.argv) < 2 else " ".join(sys.argv[1:])
    print(f"[STEP] 질의='{query}' → PPS 호출")

    try:
        raw_items = _fetch(keyword=query, page_max=int(os.getenv("PPS_PAGE_MAX", "3") or "3"))
    except TypeError:
        # 시그니처 차이에 대비
        raw_items = _fetch(query)

    # 표준 스키마로 정규화
    try:
        items_std = to_common_schema(raw_items)
    except Exception as e:
        print(f"[FAIL] to_common_schema 실패: {e}")
        return 2

    items_std = _as_list(items_std)
    if not items_std:
        print("[WARN] 결과 0건입니다. 날짜(.env: PPS_DATE_FROM/TO) 또는 키워드를 조정하세요.")
        return 3

    _preview(items_std, 5)

    # 저장 테스트
    try:
        from student.common.writer import save_markdown  # type: ignore
        payload = {"items": items_std}
        saved = save_markdown(kind="pps", query=query, payload=payload, fname_prefix="pps_smoke")
        print(f"[OK] 저장 완료: {saved}")
    except Exception as e:
        print(f"[WARN] 저장 실패(이어도 테스트는 통과): {e}")

    print("[OK] PPS 스모크 테스트 통과 ✅")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
