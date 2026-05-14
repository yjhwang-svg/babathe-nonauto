"""
버즈빌UA 크롤러
- 두 개의 adgroup_id(설정 시트에서 읽기)를 각각 조회 후 clicks + budget 합산
- 반환: {"imps": 0, "clicks": N, "cost": N}
"""

import logging
import re
import time
from datetime import datetime

from utils.dates import get_target_date

logger = logging.getLogger(__name__)

LOGIN_URL = "https://dashboard.buzzvil.com/login"
REPORT_URL_TEMPLATE = "https://dashboard.buzzvil.com/campaign/direct_sales/adgroups/{adgroup_id}/report"


def _require_env(name: str) -> str:
    import os
    val = os.environ.get(name, "").strip()
    if not val:
        raise EnvironmentError(f"환경변수 {name}이 설정되지 않았습니다.")
    return val


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

    logger.info("[Buzzvil] 로그인 시작")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 20)

    email_input = wait.until(
        EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'input[type="email"], input[name="email"], input[name="username"]')
        )
    )
    email_input.clear()
    email_input.send_keys(_require_env("BUZZVIL_EMAIL"))

    pw = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    pw.clear()
    pw.send_keys(_require_env("BUZZVIL_PASSWORD"))

    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()

    # 로그인 처리까지 넉넉하게 대기
    time.sleep(6)
    try:
        wait.until(EC.url_changes(LOGIN_URL))
    except Exception:
        pass
    time.sleep(2)

    try:
        driver.save_screenshot("/tmp/buzzvil_login.png")
    except Exception:
        pass

    current_url = driver.current_url
    logger.info(f"[Buzzvil] 로그인 후 URL: {current_url}")

    # 에러 메시지 로그
    if "login" in current_url.lower():
        try:
            err_el = driver.find_element(
                By.CSS_SELECTOR, ".error-message, .alert, [class*='error'], [class*='Error']"
            )
            logger.error(f"[Buzzvil] 페이지 에러 메시지: {err_el.text}")
        except Exception:
            pass
        raise RuntimeError(f"[Buzzvil] 로그인 실패 — URL: {current_url}")

    # 대시보드 요소가 나타날 때까지 추가 대기
    try:
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "nav, .sidebar, [class*='dashboard'], [class*='nav']")
        ))
    except Exception:
        logger.warning("[Buzzvil] 대시보드 요소 미확인 — 계속 진행")

    logger.info("[Buzzvil] 로그인 성공")
    time.sleep(2)


def _clean_number(text: str) -> int:
    cleaned = re.sub(r"[^\d]", "", text.strip())
    return int(cleaned) if cleaned else 0


def _parse_date(text: str) -> str:
    text = text.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
    m = re.match(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    m = re.match(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", text)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return text


def _get_header_indices(header_cells: list) -> dict:
    mapping = {}
    for i, cell in enumerate(header_cells):
        text = cell.text.strip().lower()
        if "date" in text:
            mapping["date"] = i
        elif "impression" in text:
            mapping["imps"] = i
        elif "click" in text:
            mapping["clicks"] = i
        elif "spent" in text or "budget" in text or "spend" in text:
            mapping["cost"] = i
    return mapping


def _fetch_adgroup_data(driver, adgroup_id: str, target_date: str) -> dict | None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.common.exceptions import TimeoutException

    url = REPORT_URL_TEMPLATE.format(adgroup_id=adgroup_id)
    logger.info(f"[Buzzvil] adgroup {adgroup_id} 조회: {url}")
    driver.get(url)

    wait = WebDriverWait(driver, 40)
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
    except TimeoutException:
        logger.warning(f"[Buzzvil] adgroup {adgroup_id} 테이블 로드 타임아웃")
    time.sleep(4)

    try:
        header_cells = driver.find_elements(By.CSS_SELECTOR, "table thead th, table thead td")
        col = _get_header_indices(header_cells)
    except Exception:
        col = {"date": 0, "imps": 1, "clicks": 2, "cost": 3}

    date_idx = col.get("date", 0)
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    logger.info(f"[Buzzvil] adgroup {adgroup_id} 테이블 행 수: {len(rows)}")

    for row in rows:
        cells = row.find_elements(By.CSS_SELECTOR, "td")
        if not cells or date_idx >= len(cells):
            continue
        if target_date not in _parse_date(cells[date_idx].text):
            continue
        try:
            return {
                "imps":   _clean_number(cells[col.get("imps",   1)].text),
                "clicks": _clean_number(cells[col.get("clicks", 2)].text),
                "cost":   _clean_number(cells[col.get("cost",   3)].text),
            }
        except (IndexError, ValueError) as e:
            logger.error(f"[Buzzvil] adgroup {adgroup_id} 셀 파싱 오류: {e}")
            return None

    logger.warning(f"[Buzzvil] adgroup {adgroup_id}: {target_date} 데이터 없음")
    return None


def scrape(adgroup_ids: list[str], target_date: str | None = None) -> dict | None:
    """
    여러 adgroup_id를 조회하여 clicks + cost 합산 반환.
    imps는 0으로 고정 (버즈빌 UA 특성상 노출 미집계).
    """
    target_date = target_date or get_target_date()
    driver = build_driver()
    try:
        login(driver)
        total = {"imps": 0, "clicks": 0, "cost": 0}
        any_success = False
        for adgroup_id in adgroup_ids:
            data = _fetch_adgroup_data(driver, adgroup_id.strip(), target_date)
            if data:
                total["imps"]   += data["imps"]
                total["clicks"] += data["clicks"]
                total["cost"]   += data["cost"]
                any_success = True
            else:
                logger.warning(f"[Buzzvil] adgroup {adgroup_id} 데이터 없음 — 합산에서 제외")
        if not any_success:
            return None
        logger.info(f"[Buzzvil] 합산 결과: {total}")
        return total
    finally:
        driver.quit()
