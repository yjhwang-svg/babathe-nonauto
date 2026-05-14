"""
네이버 쇼핑파트너센터 크롤러
- PC: https://center.shopping.naver.com/report/order
- MO: https://center.shopping.naver.com/report/mobile/order
- 전일자 조회, 합계 행에서 노출수 / 클릭수 / 적용수수료 추출
- 반환: {"imps": N, "clicks": N, "cost": N}

※ 네이버 로그인은 보안이 강함.
  - user-agent 설정, 쿠키 재사용 등으로 안정성 확보
  - 첫 실행 시 SMS 인증이 요구될 수 있음 → NAVER_COOKIE 환경변수로 세션 쿠키 주입 가능
"""

import json
import logging
import os
import re
import time

from utils.dates import get_target_date

logger = logging.getLogger(__name__)

NAVER_LOGIN_URL = "https://nid.naver.com/nidlogin.login"
PC_REPORT_URL   = "https://center.shopping.naver.com/report/order"
MO_REPORT_URL   = "https://center.shopping.naver.com/report/mobile/order"


def _require_env(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise EnvironmentError(f"환경변수 {name}이 설정되지 않았습니다.")
    return val


def _clean_number(text: str) -> int:
    cleaned = re.sub(r"[^\d]", "", str(text).strip())
    return int(cleaned) if cleaned else 0


def build_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # 네이버 봇 감지 회피용 user-agent
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return webdriver.Chrome(options=options)


def _inject_cookies(driver, cookie_json: str):
    """NAVER_COOKIE 환경변수(JSON 배열)를 드라이버에 주입."""
    try:
        cookies = json.loads(cookie_json)
        driver.get("https://naver.com")
        time.sleep(1)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.debug(f"쿠키 주입 실패: {e}")
        logger.info(f"[NaverShopping] 쿠키 {len(cookies)}개 주입 완료")
    except Exception as e:
        logger.warning(f"[NaverShopping] 쿠키 주입 오류: {e}")


def login(driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    naver_id = _require_env("NAVER_ID")
    naver_pw = _require_env("NAVER_PW")

    logger.info("[NaverShopping] 네이버 로그인 시작")
    driver.get(NAVER_LOGIN_URL)
    time.sleep(2)

    wait = WebDriverWait(driver, 20)

    # JavaScript로 입력 (봇 감지 우회)
    driver.execute_script(
        f"document.querySelector('#id').value = '{naver_id}';"
    )
    driver.execute_script(
        f"document.querySelector('#pw').value = '{naver_pw}';"
    )
    time.sleep(1)

    # 로그인 버튼 클릭
    try:
        login_btn = driver.find_element(By.CSS_SELECTOR, "#log\\.login, .btn_login, button[type='submit']")
        login_btn.click()
    except Exception:
        driver.execute_script("document.querySelector('button[type=submit], #log\\.login').click()")

    time.sleep(4)

    try:
        driver.save_screenshot("/tmp/naver_login.png")
    except Exception:
        pass

    current = driver.current_url
    logger.info(f"[NaverShopping] 로그인 후 URL: {current}")

    # SMS 인증 화면 감지
    if "sms" in current.lower() or "otp" in current.lower() or "auth" in current.lower():
        raise RuntimeError(
            "[NaverShopping] SMS/2단계 인증 화면 감지. "
            "NAVER_COOKIE 환경변수로 세션 쿠키를 주입하거나 "
            "계정의 2단계 인증을 해제해주세요."
        )

    if "nidlogin" in current:
        raise RuntimeError("[NaverShopping] 네이버 로그인 실패 — 아이디/비밀번호 확인 필요")

    logger.info("[NaverShopping] 로그인 성공")


def _set_date_yesterday(driver, target_date: str):
    """날짜 필터를 전일자로 설정 후 조회."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, 20)
    time.sleep(3)

    try:
        driver.save_screenshot("/tmp/naver_before_date.png")
    except Exception:
        pass

    # 날짜 범위 버튼 중 "어제" 버튼 시도
    try:
        yesterday_btn = driver.find_element(
            By.XPATH,
            "//*[contains(text(),'어제') or contains(@data-period,'yesterday') or contains(@class,'yesterday')]"
        )
        yesterday_btn.click()
        logger.info("[NaverShopping] '어제' 버튼 클릭")
        time.sleep(2)
    except Exception:
        # 직접 날짜 input에 입력
        logger.info("[NaverShopping] '어제' 버튼 없음 — 날짜 직접 입력 시도")
        date_inputs = driver.find_elements(
            By.CSS_SELECTOR,
            'input[type="date"], input[type="text"][placeholder*="날짜"], '
            'input[class*="date"], input[id*="date"]'
        )
        if len(date_inputs) >= 2:
            for inp in date_inputs[:2]:
                driver.execute_script("arguments[0].value = arguments[1]", inp, target_date)
        elif date_inputs:
            driver.execute_script("arguments[0].value = arguments[1]", date_inputs[0], target_date)

    # 조회 버튼 클릭
    try:
        search_btn = driver.find_element(
            By.CSS_SELECTOR,
            'button[type="submit"], .btn_search, .search_btn, button.btn-primary'
        )
        search_btn.click()
        logger.info("[NaverShopping] 조회 버튼 클릭")
    except Exception as e:
        logger.warning(f"[NaverShopping] 조회 버튼 클릭 실패: {e}")

    time.sleep(4)


def _find_col_idx(headers: list[str], keywords: list[str]) -> int | None:
    """헤더 목록에서 키워드와 매칭되는 컬럼 인덱스 반환."""
    for i, h in enumerate(headers):
        h_norm = h.replace(" ", "").lower()
        for kw in keywords:
            if kw in h_norm:
                return i
    return None


def _extract_summary(driver, label: str) -> dict | None:
    """결과 테이블의 합계 행에서 노출수/클릭수/적용수수료 추출."""
    from selenium.webdriver.common.by import By

    try:
        driver.save_screenshot(f"/tmp/naver_{label}_report.png")
    except Exception:
        pass

    # 헤더 행 파악
    header_cells = driver.find_elements(By.CSS_SELECTOR, "table thead th, table thead td")
    if not header_cells:
        header_cells = driver.find_elements(By.CSS_SELECTOR, "table tr:first-child th, table tr:first-child td")

    headers = [c.text.strip() for c in header_cells]
    logger.info(f"[NaverShopping/{label}] 헤더: {headers}")

    imps_idx  = _find_col_idx(headers, ["노출수", "노출"])
    click_idx = _find_col_idx(headers, ["클릭수", "클릭"])
    cost_idx  = _find_col_idx(headers, ["적용수수료", "수수료", "비용"])

    logger.info(f"[NaverShopping/{label}] 컬럼 인덱스 — 노출:{imps_idx}, 클릭:{click_idx}, 수수료:{cost_idx}")

    if click_idx is None or cost_idx is None:
        logger.error(f"[NaverShopping/{label}] 필수 컬럼을 찾지 못했습니다.")
        return None

    # 합계 행 탐색
    body_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr, table tfoot tr")
    for row in reversed(body_rows):  # 합계는 보통 하단에 위치
        cells = row.find_elements(By.CSS_SELECTOR, "td, th")
        row_text = " ".join(c.text for c in cells)
        if "합계" in row_text or "total" in row_text.lower() or "sum" in row_text.lower():
            imps   = _clean_number(cells[imps_idx].text)  if imps_idx  is not None and imps_idx  < len(cells) else 0
            clicks = _clean_number(cells[click_idx].text) if click_idx < len(cells) else 0
            cost   = _clean_number(cells[cost_idx].text)  if cost_idx  < len(cells) else 0
            logger.info(f"[NaverShopping/{label}] 합계 → imps={imps}, clicks={clicks}, cost={cost}")
            return {"imps": imps, "clicks": clicks, "cost": cost}

    # 합계 행이 없으면 전체 합산
    logger.info(f"[NaverShopping/{label}] 합계 행 없음 — 전체 합산")
    total_imps, total_clicks, total_cost = 0, 0, 0
    for row in body_rows:
        cells = row.find_elements(By.CSS_SELECTOR, "td")
        if not cells:
            continue
        if imps_idx is not None and imps_idx < len(cells):
            total_imps += _clean_number(cells[imps_idx].text)
        if click_idx < len(cells):
            total_clicks += _clean_number(cells[click_idx].text)
        if cost_idx < len(cells):
            total_cost += _clean_number(cells[cost_idx].text)
    return {"imps": total_imps, "clicks": total_clicks, "cost": total_cost}


def scrape(target_date: str | None = None) -> dict:
    """
    PC, MO 리포트를 각각 조회하여 반환.
    반환: {"pc": {...}, "mo": {...}}
    각 값: {"imps": N, "clicks": N, "cost": N}
    """
    target_date = target_date or get_target_date()

    # NAVER_COOKIE가 있으면 쿠키 방식 우선
    cookie_json = os.environ.get("NAVER_COOKIE", "").strip()

    driver = build_driver()
    try:
        if cookie_json:
            logger.info("[NaverShopping] 쿠키 기반 로그인 시도")
            _inject_cookies(driver, cookie_json)
        else:
            login(driver)

        results = {}

        for label, url in [("PC", PC_REPORT_URL), ("MO", MO_REPORT_URL)]:
            logger.info(f"[NaverShopping/{label}] 리포트 페이지 이동: {url}")
            driver.get(url)
            _set_date_yesterday(driver, target_date)
            data = _extract_summary(driver, label)
            results[label.lower()] = data
            if data:
                logger.info(f"[NaverShopping/{label}] 완료: {data}")
            else:
                logger.warning(f"[NaverShopping/{label}] 수집 실패")

        return results
    finally:
        driver.quit()
