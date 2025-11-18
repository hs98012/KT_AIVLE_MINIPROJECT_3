# -*- coding: utf-8 -*-
"""
Day3(정부공고, 용역 전용) 에이전트
- 입력: 키워드(예: "인공지능", "AI 교육")
- 동작: impl/pps_tool.py의 pps_search() FunctionTool 호출
- 출력: 한국어 Markdown (표 포함)
"""

from __future__ import annotations
import os

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.function_tool import FunctionTool

# 도구 함수
from student.day3.impl.pps_tool import pps_search

# 모델 설정 (max_output_tokens 인자 사용 금지: OpenAI 400 에러 방지)
MODEL = LiteLlm(
    model=os.getenv("DAY4_INTENT_MODEL", "openai/gpt-4o-mini"),
    temperature=float(os.getenv("DAY4_TEMPERATURE", "0.2")),
)

# FunctionTool — 필수 인자만!
pps_tool = FunctionTool(func=pps_search)

INSTRUCTION = """\
너는 Day3PpsAgent로서 '나라장터 용역 공고' 질의만 처리한다. 한국어로 답하라.

[입력]
- 사용자 메시지는 키워드(예: "인공지능", "AI 교육") 위주다.

[동작]
1) 반드시 도구(pps_search)를 1회 호출하여 결과를 받는다. (서버사이드 키워드 검색)
2) 도구는 한국어 Markdown을 반환한다. 표에는 마감일/공고명/주관기관/예산/링크가 포함된다.
3) 도구의 마크다운을 그대로 전달하되, 불필요한 문구를 덧붙이지 않는다.

[주의]
- 웹 뉴스/회사 동향 등 다른 범주의 정보는 섞지 않는다.
- 날짜는 KST 기준, 절대 날짜(YYYY-MM-DD)로 표기되는 마크다운을 유지한다.
"""

day3_pps_agent = Agent(
    name="PPSAgent",
    model=MODEL,
    instruction=INSTRUCTION,
    tools=[pps_tool],
)
