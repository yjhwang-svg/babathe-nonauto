"""
아이스크린(ive) 크롤러
- URL: https://adv.i-screen.kr/rpt/rpt_adv_day
- 전일자 클릭수 + 소진금액 수집
- 반환: {"imps": 0, "clicks": N, "cost": N}
"""

import logging
import re
import time

from utils.dates import get_target_date

logger = logging.getLogger(__name__)

LOGIN_URL = "https://adv.i-screen.kr/login"
REPORT_URL = "https://adv.i-screen.kr/rpt/rpt_adv_day"


def _require_env(name: str) -> str:
    import os
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
    return webdriver.Chrome(options=options)


def login(driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    logger.info("[iScreen] 로그인 시작")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)

    # ID 입력 필드
    id_input = wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[type="text"], input[name="id"], input[name="userId"], input[name="username"]')
        )
    )
    id_input.clear()
    id_input.send_keys(_require_env("ISCREEN_ID"))

    # PW 입력 필드
    pw_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    pw_input.clear()
    pw_input.send_keys(_require_env("ISCREEN_PW"))

    # 로그인 버튼
    try:
        submit = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
    except Exception:
        submit = driver.find_element(By.CSS_SELECTOR, 'input[type="submit"], button')
    submit.click()

    time.sleep(3)
    try:
        driver.save_screenshot("/tmp/iscreen_login.png")
    except Exception:
        pass

    logger.info(f"[iScreen] 로그인 후 URL: {driver.current_url}")


def _set_date_filter(driver, target_date: str):
    """날짜 필터를 전일자로 설정."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.keys import Keys

    wait = WebDriverWait(driver, 20)

    # 날짜 포맷 변환 (YYYY-MM-DD → YYYYMMDD 또는 YYYY-MM-DD)
    # 사이트 형식에 따라 조정 필요
    date_str = target_date  # YYYY-MM-DD

    # 시작일, 종료일 input 찾기 (다양한 셀렉터 시도)
    date_inputs = driver.find_elements(
        By.CSS_SELECTOR,
        'input[type="date"], input[name*="date"], input[id*="date"], input[id*="Date"], '
        'input[name*="sdate"], input[name*="edate"], input[id*="sdate"], input[id*="edate"]'
    )
    logger.info(f"[iScreen] 날짜 input 수: {len(date_inputs)}")
    for inp in date_inputs:
        logger.info(f"[iScreen] 날짜 input: name={inp.get_attribute('name')} id={inp.get_attribute('id')} value={inp.get_attribute('value')}")

    # 시작일과 종료일 모두 전일자로 설정
    if len(date_inputs) >= 2:
        for inp in date_inputs[:2]:
            driver.execute_script("arguments[0].value = arguments[1]", inp, date_str)
    elif len(date_inputs) == 1:
        driver.execute_script("arguments[0].value = arguments[1]", date_inputs[0], date_str)

    # 조회 버튼 클릭
    try:
        search_btn = driver.find_element(
            By.CSS_SELECTOR,
            'button[type="submit"], input[type="submit"], button.search, button.btn-search, button.btn-primary'
        )
        search_btn.click()
        logger.info("[iScreen] 조회 버튼 클릭")
    except Exception as e:
        logger.warning(f"[iScreen] 조회 버튼 찾기 실패, JavaScript로 form submit 시도: {e}")
        driver.execute_script("document.forms[0].submit()")

    time.sleep(3)


def _extract_data(driver) -> dict | None:
    """결과 테이블에서 클릭수, 소진금액 추출."""
    from selenium.webdriver.common.by import By

    try:
        driver.save_screenshot("/tmp/iscreen_report.png")
    except Exception:
        pass

    # 테이블 헤더에서 컬럼 위치 파악
    header_row = driver.find_elements(By.CSS_SELECTOR, "table thead tr th, table thead tr td")
    if not header_row:
        # thead 없을 경우 첫 번째 tr을 헤더로 간주
        header_row = driver.find_elements(By.CSS_SELECTOR, "table tr:first-child th, table tr:first-child td")

    headers = [cell.text.strip() for cell in header_row]
    logger.info(f"[iScreen] 헤더: {headers}")

    # 컬럼 인덱스 파악 (한국어 키워드 기반)
    click_idx, cost_idx = None, None
    for i, h in enumerate(headers):
        h_lower = h.lower().replace(" ", "")
        if "클릭" in h or "click" in h_lower:
            click_idx = i
        if "소진" in h or "금액" in h or "비용" in h or "cost" in h_lower or "spend" in h_lower or "budget" in h_lower:
            cost_idx = i

    if click_idx is None or cost_idx is None:
        logger.error(f"[iScreen] 클릭/금액 컬럼을 찾지 못했습니다. 헤더: {headers}")
        return None

    # 데이터 행 수집 (합계 행 우선 탐색)
    all_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    if not all_rows:
        all_rows = driver.find_elements(By.CSS_SELECTOR, "table tr")[1:]  # 헤더 제외

    # 합계 행 찾기 (텍스트에 "합계" or "total" 포함하는 행)
    total_row = None
    for row in all_rows:
        cells = row.find_elements(By.CSS_SELECTOR, "td, th")
        row_text = " ".join(c.text for c in cells).lower()
        if "합계" in row_text or "total" in row_text or "sum" in row_text:
            total_row = cells
            break

    # 합계 행이 없으면 마지막 행 사용 (또는 모든 행 합산)
    if total_row is None:
        # 모든 행의 값을 합산
        logger.info("[iScreen] 합계 행 없음 — 전체 합산")
        total_clicks, total_cost = 0, 0
        for row in all_rows:
            cells = row.find_elements(By.CSS_SELECTOR, "td")
            if click_idx < len(cells) and cost_idx < len(cells):
                total_clicks += _clean_number(cells[click_idx].text)
                total_cost   += _clean_number(cells[cost_idx].text)
        return {"imps": 0, "clicks": total_clicks, "cost": total_cost}
    else:
        clicks = _clean_number(total_row[click_idx].text)
        cost   = _clean_number(total_row[cost_idx].text)
        logger.info(f"[iScreen] 합계 행 → clicks={clicks}, cost={cost}")
        return {"imps": 0, "clicks": clicks, "cost": cost}


def scrape(target_date: str | None = None) -> dict | None:
    """아이스크린에서 전일자 클릭수 + 소진금액 반환."""
    target_date = target_date or get_target_date()
    driver = build_driver()
    try:
        login(driver)

        logger.info(f"[iScreen] 리포트 페이지 이동: {REPORT_URL}")
        driver.get(REPORT_URL)
        time.sleep(2)

        _set_date_filter(driver, target_date)
        data = _extract_data(driver)

        if data:
            logger.info(f"[iScreen] 수집 완료: {data}")
        else:
            logger.warning("[iScreen] 데이터 수집 실패")
        return data
    finally:
        driver.quit()
