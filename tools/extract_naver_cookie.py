"""
네이버 쇼핑파트너센터 NAVER_COOKIE 추출 도구

사용법:
  python tools/extract_naver_cookie.py

실행하면 Chrome 브라우저가 열립니다.
네이버에 직접 로그인(SMS 인증 포함)하면 쿠키를 자동으로 추출해줍니다.
출력된 JSON을 GitHub Secrets > NAVER_COOKIE 에 붙여넣으세요.
"""

import json
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


TARGET_URL = "https://center.shopping.naver.com"
NAVER_LOGIN_URL = "https://center.shopping.naver.com/login?target_uri=https%3A%2F%2Fcenter.shopping.naver.com%2Faccount%2Fcharge"

REQUIRED_COOKIES = {"NID_AUT", "NID_SES", "NID_JKL"}


def build_visible_driver():
    options = Options()
    # 창이 보이도록 headless 비활성화
    options.add_argument("--window-size=1200,900")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return webdriver.Chrome(options=options)


def wait_for_login(driver, timeout=300):
    print("\n브라우저가 열렸습니다.")
    print("네이버에 직접 로그인해주세요 (SMS 인증도 완료하세요).")
    print(f"최대 {timeout//60}분 대기합니다...\n")

    deadline = time.time() + timeout
    while time.time() < deadline:
        cookies = {c["name"]: c for c in driver.get_cookies()}
        if "NID_AUT" in cookies and "NID_SES" in cookies:
            print("로그인 감지! 쿠키 추출 중...")
            return cookies
        time.sleep(2)

    raise TimeoutError("로그인 대기 시간 초과")


def extract_cookies():
    driver = build_visible_driver()
    try:
        driver.get(NAVER_LOGIN_URL)

        cookies = wait_for_login(driver)

        # 쇼핑파트너센터 접근 후 추가 쿠키 수집
        driver.get(TARGET_URL)
        time.sleep(3)
        all_cookies = {c["name"]: c for c in driver.get_cookies()}

        # 필요한 쿠키만 추출 (민감하지 않은 필수 쿠키)
        result = []
        for name, cookie in all_cookies.items():
            result.append({
                "name": cookie["name"],
                "value": cookie["value"],
                "domain": cookie.get("domain", ".naver.com"),
                "path": cookie.get("path", "/"),
            })

        print("\n" + "="*60)
        print("✅ 추출 완료! 아래 JSON을 GitHub Secrets > NAVER_COOKIE 에 붙여넣으세요:")
        print("="*60)
        print(json.dumps(result, ensure_ascii=False))
        print("="*60)

        # 파일로도 저장
        output_path = "tools/naver_cookie.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n📄 파일로도 저장됨: {output_path}")
        print("⚠️  이 파일은 민감 정보입니다. Git에 커밋하지 마세요!")

    finally:
        driver.quit()


if __name__ == "__main__":
    extract_cookies()
