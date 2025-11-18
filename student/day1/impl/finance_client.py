# -*- coding: utf-8 -*-
"""
yfinance 가격 조회
- 목표: 티커 리스트에 대해 현재가/통화를 가져와 표준 형태로 반환
"""

from typing import List, Dict, Any
import re

# (강의 안내) yfinance는 외부 네트워크 환경에서 동작. 인터넷 불가 환경에선 모킹이 필요할 수 있음.


def _normalize_symbol(s: str) -> str:
    """
    6자리 숫자면 한국거래소(.KS) 보정.
    예:
      '005930' → '005930.KS'
      'AAPL'   → 'AAPL' (그대로)
    """
    if re.fullmatch(r"\d{6}", s):
      return f"{s}.KS"
    else:
      return s
    # ----------------------------------------------------------------------------
    # TODO[DAY1-F-01] 구현 지침
    #  - if re.fullmatch(r"\d{6}", s): return f"{s}.KS"
    #  - else: return s
    # ----------------------------------------------------------------------------
    # raise NotImplementedError("TODO[DAY1-F-01]: 한국 티커 보정")


def get_quotes(symbols: List[str], timeout: int = 20) -> List[Dict[str, Any]]:
    """
    yfinance로 심볼별 시세를 조회해 리스트로 반환합니다.
    반환 예:
      [{"symbol":"AAPL","price":123.45,"currency":"USD"},
       {"symbol":"005930.KS","price":...,"currency":"KRW"}]
    실패시 해당 심볼은 {"symbol":sym, "error":"..."} 형태로 표기.
    """
    from yfinance import Ticker  # 지연 임포트

    out: List[Dict[str, Any]] = []
    if not symbols:
        return out

    for raw in symbols:
        sym = _normalize_symbol(str(raw).strip())
        try:
            t = Ticker(sym)

            price = None
            currency = None

            # 1) fast_info 우선 (객체 속성 → dict 폴백 순서)
            fi = getattr(t, "fast_info", None)
            if fi is not None:
                # 객체 속성 접근
                price = getattr(fi, "last_price", None)
                currency = getattr(fi, "currency", None)

                # dict 형태 대응 (None 체크 기반 폴백: 0.0 같은 값 보존)
                if isinstance(fi, dict):
                    if price is None:
                        val = fi.get("last_price")
                        if val is None:
                            val = fi.get("lastPrice")
                        price = val

                    if currency is None:
                        cur = fi.get("currency")
                        if cur is None:
                            cur = fi.get("Currency")  # 드문 케이스 대비
                        currency = cur

            # 2) info 폴백 (여전히 None이면 시도)
            if price is None or currency is None:
                info = getattr(t, "info", {}) or {}
                if price is None:
                    val = info.get("currentPrice")
                    if val is None:
                        val = info.get("regularMarketPrice")
                    price = val
                if currency is None:
                    cur = info.get("currency")
                    if cur is None:
                        cur = info.get("Currency")  # 방어적 폴백
                    currency = cur

            # 3) 값 검증 및 정규화
            if price is None:
                raise ValueError("가격 정보 없음")

            try:
                price_float = float(price)
            except Exception:
                raise ValueError(f"가격 형식 오류: {price!r}")

            if currency is None or str(currency).strip() == "":
                raise ValueError("통화 정보 없음")

            out.append(
                {
                    "symbol": sym,
                    "price": price_float,
                    "currency": str(currency),
                }
            )
        except Exception as e:
            out.append({"symbol": sym, "error": str(e)})

    return out    
    
    # ----------------------------------------------------------------------------
    # TODO[DAY1-F-02] 구현 지침
    #  1) from yfinance import Ticker 임포트(파일 상단 대신 함수 내부 임포트도 OK)
    #  2) 결과 리스트 out=[]
    #  3) 입력 심볼들을 _normalize_symbol로 보정
    #  4) 각 심볼에 대해:
    #       - t = Ticker(sym)
    #       - 가격: getattr(t.fast_info, "last_price", None) 또는 t.fast_info.get("last_price")
    #       - 통화: getattr(t.fast_info, "currency", None)
    #       - 둘 다 숫자/문자 정상 추출 시 out.append({...})
    #       - 예외/누락 시 out.append({"symbol": sym, "error": "설명"})
    #  5) return out
    # ----------------------------------------------------------------------------
    # raise NotImplementedError("TODO[DAY1-F-02]: 주가 조회 구현")
