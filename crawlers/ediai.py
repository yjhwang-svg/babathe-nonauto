"""
에디AI 크롤러
- URL: https://advertiser.aedi.ai/advertisements/agency/report
- 날짜: 어제
- 광고주: 바바더닷컴(바바더닷컴)
- 트렌드박스: 노출/클릭/비용/전환(구매수, 매출)
- AI상품매칭: 노출/클릭/비용/전환(구매수, 매출)
- 반환: {"trendbox": {...}, "ai_matching": {...}}
"""

import logging
import os
import re
import time

from utils.dates import get_target_date

logger = logging.getLogger(__name__)

LOGIN_URL  = "https://advertiser.aedi.ai/login"
REPORT_URL = "https://advertiser.aedi.ai/advertisements/agency/report"

ADVERTISER_NAME = "바바더닷컴"

# 조회할 광고 유형
AD_TYPES = {
    "trendbox":    "트렌드박스",
    "ai_matching": "AI상품매칭",
}


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
    return webdriver.Chrome(options=options)


def login(driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    logger.info("[EdiAI] 로그인 시작")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)
    time.sleep(2)

    try:
        driver.save_screenshot("/tmp/ediai_before_login.png")
    except Exception:
        pass

    # ID 입력 — 여러 셀렉터 순서대로 시도
    id_selectors = [
        'input[name="id"]', 'input[name="username"]', 'input[name="email"]',
        'input[type="text"]', 'input[type="email"]',
    ]
    id_input = None
    for sel in id_selectors:
        try:
            id_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, sel)))
            logger.info(f"[EdiAI] ID 필드 찾음: {sel}")
            break
        except Exception:
            continue

    if id_input is None:
        raise RuntimeError("[EdiAI] ID 입력 필드를 찾지 못했습니다.")

    ActionChains(driver).move_to_element(id_input).click().send_keys(_require_env("EDIAI_ID")).perform()
    time.sleep(0.5)

    # PW 입력
    pw_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    ActionChains(driver).move_to_element(pw_input).click().send_keys(_require_env("EDIAI_PW")).perform()
    time.sleep(0.5)

    # 로그인 버튼
    try:
        submit = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], input[type="submit"]')
        submit.click()
    except Exception:
        pw_input.submit()

    time.sleep(4)
    try:
        driver.save_screenshot("/tmp/ediai_login.png")
    except Exception:
        pass

    logger.info(f"[EdiAI] 로그인 후 URL: {driver.current_url}")

    if "login" in driver.current_url.lower():
        raise RuntimeError("[EdiAI] 로그인 실패 — 자격증명 확인 필요")

    logger.info("[EdiAI] 로그인 성공")


def _select_yesterday(driver):
    """날짜를 '어제'로 설정."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, 15)
    time.sleep(2)

    # '어제' 버튼 또는 날짜 preset 클릭 시도
    try:
        yesterday_btn = driver.find_element(
            By.XPATH,
            "//*[text()='어제' or @data-value='yesterday' or contains(@class,'yesterday')]"
        )
        yesterday_btn.click()
        logger.info("[EdiAI] '어제' 버튼 클릭 성공")
        time.sleep(1)
        return
    except Exception:
        pass

    # 날짜 picker에서 직접 입력
    target_date = get_target_date()
    date_inputs = driver.find_elements(
        By.CSS_SELECTOR,
        'input[type="date"], input[placeholder*="날짜"], input[class*="date"]'
    )
    for inp in date_inputs[:2]:
        driver.execute_script("arguments[0].value = arguments[1]", inp, target_date)
    logger.info(f"[EdiAI] 날짜 직접 입력: {target_date}")


def _select_advertiser(driver):
    """광고주 '바바더닷컴' 선택."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support.ui import Select

    wait = WebDriverWait(driver, 15)
    time.sleep(2)

    # select 태그 시도
    try:
        select_el = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'select[name*="advertiser"], select[id*="advertiser"], select')
            )
        )
        select = Select(select_el)
        # 옵션 중 바바더닷컴 찾기
        for option in select.options:
            if ADVERTISER_NAME in option.text:
                select.select_by_visible_text(option.text)
                logger.info(f"[EdiAI] 광고주 선택: {option.text}")
                time.sleep(1)
                return
    except Exception:
        pass

    # 드롭다운이 커스텀 UI인 경우
    try:
        # 광고주 드롭다운 열기
        dropdown_trigger = driver.find_element(
            By.XPATH,
            "//*[contains(@class,'advertiser') or contains(@placeholder,'광고주') or contains(text(),'광고주')]"
        )
        dropdown_trigger.click()
        time.sleep(1)

        # 목록에서 바바더닷컴 찾기
        options = driver.find_elements(
            By.XPATH,
            f"//*[contains(text(),'{ADVERTISER_NAME}')]"
        )
        if options:
            options[0].click()
            logger.info(f"[EdiAI] 광고주 '{ADVERTISER_NAME}' 선택 완료")
        else:
            logger.warning(f"[EdiAI] 광고주 '{ADVERTISER_NAME}' 목록에서 찾지 못함")
    except Exception as e:
        logger.warning(f"[EdiAI] 광고주 선택 실패: {e}")


def _click_search(driver):
    """조회 버튼 클릭."""
    from selenium.webdriver.common.by import By

    try:
        btn = driver.find_element(
            By.CSS_SELECTOR,
            'button[type="submit"], .btn_search, .search_btn, button.btn-primary'
        )
        btn.click()
        logger.info("[EdiAI] 조회 버튼 클릭")
    except Exception as e:
        logger.warning(f"[EdiAI] 조회 버튼 없음: {e}")
    time.sleep(4)


def _find_col_idx(headers: list[str], keywords: list[str]) -> int | None:
    for i, h in enumerate(headers):
        h_norm = h.replace(" ", "").lower()
        for kw in keywords:
            if kw.lower().replace(" ", "") in h_norm:
                return i
    return None


def _extract_table_data(driver, tab_label: str) -> dict | None:
    """현재 화면 테이블에서 노출/클릭/비용/구매/매출 추출."""
    from selenium.webdriver.common.by import By

    try:
        driver.save_screenshot(f"/tmp/ediai_{tab_label}.png")
    except Exception:
        pass

    header_cells = driver.find_elements(By.CSS_SELECTOR, "table thead th, table thead td")
    if not header_cells:
        header_cells = driver.find_elements(By.CSS_SELECTOR, "table tr:first-child th, table tr:first-child td")

    headers = [c.text.strip() for c in header_cells]
    logger.info(f"[EdiAI/{tab_label}] 헤더: {headers}")

    imps_idx     = _find_col_idx(headers, ["노출수", "노출", "impression"])
    click_idx    = _find_col_idx(headers, ["클릭수", "클릭", "click"])
    cost_idx     = _find_col_idx(headers, ["비용", "광고비", "cost", "spend"])
    purchase_idx = _find_col_idx(headers, ["구매수", "구매", "전환수", "전환", "conversion"])
    revenue_idx  = _find_col_idx(headers, ["매출", "전환매출", "revenue"])

    logger.info(
        f"[EdiAI/{tab_label}] 컬럼 — 노출:{imps_idx}, 클릭:{click_idx}, "
        f"비용:{cost_idx}, 구매:{purchase_idx}, 매출:{revenue_idx}"
    )

    # 합계 행 탐색 (tfoot 또는 tbody 마지막 행)
    body_rows = driver.find_elements(By.CSS_SELECTOR, "table tfoot tr, table tbody tr")

    target_row = None
    for row in reversed(body_rows):
        cells = row.find_elements(By.CSS_SELECTOR, "td, th")
        row_text = " ".join(c.text for c in cells)
        if "합계" in row_text or "total" in row_text.lower():
            target_row = cells
            break

    if target_row is None and body_rows:
        # 합계 행이 없으면 단일 행만 있는 경우 그 행 사용
        all_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        if len(all_rows) == 1:
            target_row = all_rows[0].find_elements(By.CSS_SELECTOR, "td")
        else:
            # 전체 합산
            total = {"imps": 0, "clicks": 0, "cost": 0, "purchase": 0, "revenue": 0}
            for row in all_rows:
                cells = row.find_elements(By.CSS_SELECTOR, "td")
                if imps_idx     is not None and imps_idx     < len(cells): total["imps"]     += _clean_number(cells[imps_idx].text)
                if click_idx    is not None and click_idx    < len(cells): total["clicks"]   += _clean_number(cells[click_idx].text)
                if cost_idx     is not None and cost_idx     < len(cells): total["cost"]     += _clean_number(cells[cost_idx].text)
                if purchase_idx is not None and purchase_idx < len(cells): total["purchase"] += _clean_number(cells[purchase_idx].text)
                if revenue_idx  is not None and revenue_idx  < len(cells): total["revenue"]  += _clean_number(cells[revenue_idx].text)
            logger.info(f"[EdiAI/{tab_label}] 전체 합산: {total}")
            return total

    if target_row is None:
        logger.error(f"[EdiAI/{tab_label}] 데이터 행 없음")
        return None

    def _get(idx):
        if idx is not None and idx < len(target_row):
            return _clean_number(target_row[idx].text)
        return 0

    result = {
        "imps":     _get(imps_idx),
        "clicks":   _get(click_idx),
        "cost":     _get(cost_idx),
        "purchase": _get(purchase_idx),
        "revenue":  _get(revenue_idx),
    }
    logger.info(f"[EdiAI/{tab_label}] 결과: {result}")
    return result


def _switch_tab(driver, tab_name: str) -> bool:
    """광고 유형 탭(트렌드박스 / AI상품매칭) 클릭."""
    from selenium.webdriver.common.by import By

    try:
        tab = driver.find_element(
            By.XPATH,
            f"//*[contains(text(),'{tab_name}') and ("
            f"self::a or self::button or self::li or self::span)]"
        )
        tab.click()
        logger.info(f"[EdiAI] 탭 전환: {tab_name}")
        time.sleep(3)
        return True
    except Exception as e:
        logger.warning(f"[EdiAI] 탭 '{tab_name}' 클릭 실패: {e}")
        return False


def scrape(target_date: str | None = None) -> dict:
    """
    에디AI 대행사 리포트에서 트렌드박스 + AI상품매칭 데이터 수집.
    반환:
    {
      "trendbox":    {"imps": N, "clicks": N, "cost": N, "purchase": N, "revenue": N},
      "ai_matching": {"imps": N, "clicks": N, "cost": N, "purchase": N, "revenue": N},
    }
    """
    target_date = target_date or get_target_date()
    driver = build_driver()

    try:
        login(driver)

        logger.info(f"[EdiAI] 리포트 페이지 이동: {REPORT_URL}")
        driver.get(REPORT_URL)
        time.sleep(3)

        # 날짜 설정 + 광고주 선택 + 조회
        _select_yesterday(driver)
        _select_advertiser(driver)
        _click_search(driver)

        results = {}

        for key, tab_name in AD_TYPES.items():
            logger.info(f"[EdiAI] '{tab_name}' 탭 데이터 수집 시작")
            switched = _switch_tab(driver, tab_name)
            if not switched:
                logger.warning(f"[EdiAI] '{tab_name}' 탭 전환 실패 — None 처리")
                results[key] = None
                continue
            data = _extract_table_data(driver, key)
            results[key] = data

        return results
    finally:
        driver.quit()
