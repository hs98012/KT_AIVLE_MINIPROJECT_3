# quick_check_profile.py (프로젝트 루트에서 한번 돌려보기)
from impl.web_search import extract_and_summarize_profile
def echo_summarizer(prompt: str) -> str:
    return prompt[0:]  # 스모크와 유사한 더미

URLS = [
  "https://www.samsung.com/sec/about-us/company-info/",
  "https://comp.fnguide.com/SVO2/ASP/SVD_Corp.asp?pGB=1",
  "https://www.jobplanet.co.kr/companies/30139/landing/%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90",
]
print(extract_and_summarize_profile(URLS, api_key=None, summarizer=echo_summarizer))
