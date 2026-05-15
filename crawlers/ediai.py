"""
에디AI 크롤러 (console.aedi.ai 기반)
- 로그인: https://console.aedi.ai/en/login (국가: Korea)
- 리포트: https://advertiser.aedi.ai/advertisements/agency/report
- 광고주: 바바더닷컴(바바더닷컴), 캠페인 2종 순차 조회
- 반환: {"trendbox": {...}, "ai_matching": {...}}
"""

import logging
import os
import re
import time

from utils.dates import get_target_date

logger = logging.getLogger(__name__)

LOGIN_URL  = "https://console.aedi.ai/en/login"
REPORT_URL = "https://advertiser.aedi.ai/advertisements/agency/report"

ADVERTISER_NAME = "바바더닷컴"

# 캠페인 드롭다운에서 선택할 텍스트
CAMPAIGNS = {
    "ai_matching": "AI상품매칭",
    "trendbox":    "트렌드박스",
}

# 합계 행 셀 구조: [''(빈칸), '합계', 노출수, 클릭수, 클릭률, 전환수, 전환율, 광고비, 전환금액, ROAS, ...]
COL_IMPS     = 2
COL_CLICKS   = 3
COL_PURCHASE = 5
COL_COST     = 7
COL_REVENUE  = 8


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
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    logger.info("[EdiAI] 로그인 시작")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)

    # 1. 국가 드롭다운 → Korea 선택
    nation_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[name="nation"]')))
    nation_input.click()
    time.sleep(1)
    korea_option = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'li.kr')))
    korea_option.click()
    logger.info("[EdiAI] 국가 Korea 선택")
    time.sleep(0.5)

    # 2. Username / Password 입력
    driver.find_element(By.CSS_SELECTOR, 'input[name="username"]').send_keys(_require_env("EDIAI_ID"))
    driver.find_element(By.CSS_SELECTOR, 'input[name="password"]').send_keys(_require_env("EDIAI_PW"))
    time.sleep(0.3)

    # 3. Login 버튼 클릭 (type="button", class="btn_login")
    btn = driver.find_element(By.CSS_SELECTOR, 'button.btn_login')
    driver.execute_script("arguments[0].click();", btn)
    logger.info("[EdiAI] Login 버튼 클릭")
    time.sleep(6)

    try:
        driver.save_screenshot("/tmp/ediai_login.png")
    except Exception:
        pass

    current = driver.current_url
    logger.info(f"[EdiAI] 로그인 후 URL: {current}")
    if "/en/login" in current:
        raise RuntimeError(f"[EdiAI] 로그인 실패 — URL: {current}")

    logger.info("[EdiAI] 로그인 성공")


def _set_yesterday(driver):
    """상단 '어제' 버튼 클릭."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, 10)
    try:
        btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[normalize-space()='어제'] | //*[normalize-space()='어제' and (self::button or self::span or self::a)]")
        ))
        btn.click()
        logger.info("[EdiAI] '어제' 버튼 클릭")
        time.sleep(1)
    except Exception as e:
        logger.warning(f"[EdiAI] '어제' 버튼 클릭 실패: {e}")


def _select_advertiser(driver):
    """광고주 드롭다운에서 바바더닷컴 선택."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, 10)
    time.sleep(1)

    try:
        # 광고주 드롭다운 트리거 클릭 (현재 선택값 표시 영역)
        trigger = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//*[contains(text(),'{ADVERTISER_NAME}') and (self::div or self::span or self::button or self::input)]")
        ))
        trigger.click()
        time.sleep(1)

        # 드롭다운 목록에서 바바더닷컴(바바더닷컴) 선택
        options = driver.find_elements(
            By.XPATH, f"//*[contains(text(),'{ADVERTISER_NAME}') and (self::li or self::div or self::option or self::span)]"
        )
        for opt in options:
            if ADVERTISER_NAME in opt.text and opt.is_displayed():
                opt.click()
                logger.info(f"[EdiAI] 광고주 선택: {opt.text.strip()}")
                time.sleep(1)
                return
    except Exception as e:
        logger.warning(f"[EdiAI] 광고주 선택 실패 (이미 선택됐을 수 있음): {e}")


def _select_campaign(driver, campaign_keyword: str):
    """캠페인 드롭다운에서 keyword 포함하는 캠페인 선택."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, 10)
    time.sleep(1)

    try:
        # 두 번째 드롭다운 열기 (캠페인명 표시 영역 클릭)
        trigger = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//*[contains(text(),'{campaign_keyword}') and (self::div or self::span or self::button or self::input)]")
        ))
        trigger.click()
        time.sleep(1)

        options = driver.find_elements(
            By.XPATH, f"//*[contains(text(),'{campaign_keyword}') and (self::li or self::div or self::option or self::span)]"
        )
        for opt in options:
            if campaign_keyword in opt.text and opt.is_displayed():
                opt.click()
                logger.info(f"[EdiAI] 캠페인 선택: {opt.text.strip()}")
                time.sleep(1)
                return
        logger.warning(f"[EdiAI] 캠페인 '{campaign_keyword}' 선택 실패 — 기본값 유지")
    except Exception as e:
        logger.warning(f"[EdiAI] 캠페인 드롭다운 조작 실패: {e}")


def _click_search(driver):
    """'조회' 버튼 클릭."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, 10)
    try:
        btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[normalize-space()='조회']")
        ))
        btn.click()
        logger.info("[EdiAI] 조회 버튼 클릭")
    except Exception as e:
        logger.warning(f"[EdiAI] 조회 버튼 클릭 실패: {e}")
    time.sleep(5)


def _extract_data(driver, label: str) -> dict | None:
    """
    JS로 '합계' 행을 찾아 컬럼 위치 기준으로 데이터 추출.
    컬럼 순서(0-indexed): 날짜|노출수|클릭수|클릭률|전환수|전환율|광고비|전환금액|ROAS|...
    """
    try:
        driver.save_screenshot(f"/tmp/ediai_{label}.png")
    except Exception:
        pass

    # JS로 '합계' 행 찾아 전체 셀 텍스트 반환 (숫자/기호만)
    cells = driver.execute_script("""
        var all = document.querySelectorAll('*');
        for (var i = 0; i < all.length; i++) {
            var t = (all[i].innerText || '').trim();
            if (t === '합계' && all[i].children.length === 0) {
                var row = all[i].parentElement;
                while (row && row.children.length < 5) {
                    row = row.parentElement;
                }
                if (!row) return null;
                var result = [];
                for (var j = 0; j < row.children.length; j++) {
                    result.push((row.children[j].innerText || '').trim());
                }
                return result;
            }
        }
        return null;
    """)

    if not cells:
        # 합계 행 없으면 날짜 행 직접 탐색
        logger.warning(f"[EdiAI/{label}] 합계 행 없음 — 날짜 행 탐색")
        cells = driver.execute_script("""
            var all = document.querySelectorAll('*');
            for (var i = 0; i < all.length; i++) {
                var t = (all[i].innerText || '').trim();
                if (/^\\d{4}-\\d{2}-\\d{2}$/.test(t) && all[i].children.length === 0) {
                    var row = all[i].parentElement;
                    while (row && row.children.length < 5) {
                        row = row.parentElement;
                    }
                    if (!row) return null;
                    var result = [];
                    for (var j = 0; j < row.children.length; j++) {
                        result.push((row.children[j].innerText || '').trim());
                    }
                    return result;
                }
            }
            return null;
        """)

    if not cells:
        logger.error(f"[EdiAI/{label}] 데이터 행을 찾을 수 없음")
        return None

    logger.info(f"[EdiAI/{label}] 셀 수: {len(cells)}, 내용: {cells}")

    def _get(idx):
        if idx < len(cells):
            return _clean_number(cells[idx])
        return 0

    result = {
        "imps":     _get(COL_IMPS),
        "clicks":   _get(COL_CLICKS),
        "cost":     _get(COL_COST),
        "purchase": _get(COL_PURCHASE),
        "revenue":  _get(COL_REVENUE),
    }
    logger.info(f"[EdiAI/{label}] 결과: {result}")
    return result


def scrape(target_date: str | None = None) -> dict:
    """
    에디AI 대행사 리포트 — AI상품매칭 + 트렌드박스 순차 조회.
    반환: {
      "ai_matching": {"imps": N, "clicks": N, "cost": N, "purchase": N, "revenue": N},
      "trendbox":    {"imps": N, "clicks": N, "cost": N, "purchase": N, "revenue": N},
    }
    """
    target_date = target_date or get_target_date()
    driver = build_driver()

    try:
        login(driver)

        logger.info(f"[EdiAI] 리포트 페이지 이동: {REPORT_URL}")
        driver.get(REPORT_URL)
        time.sleep(4)

        # 날짜 = 어제, 광고주 = 바바더닷컴 (페이지 로드 시 이미 설정돼 있을 수 있음)
        _set_yesterday(driver)
        _select_advertiser(driver)

        results = {}

        for key, campaign_keyword in CAMPAIGNS.items():
            logger.info(f"[EdiAI] '{campaign_keyword}' 캠페인 조회 시작")
            _select_campaign(driver, campaign_keyword)
            _click_search(driver)
            data = _extract_data(driver, key)
            results[key] = data

        return results
    finally:
        driver.quit()
