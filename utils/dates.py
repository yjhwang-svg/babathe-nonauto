"""
날짜 유틸리티 - KST 기준 전일자 반환
환경변수 TARGET_DATE(YYYY-MM-DD)로 덮어쓰기 가능
"""

import os
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def get_target_date() -> str:
    """KST 기준 전일자를 YYYY-MM-DD 형식으로 반환. TARGET_DATE 환경변수로 덮어쓰기 가능."""
    override = os.environ.get("TARGET_DATE", "").strip()
    if override:
        return override
    yesterday = datetime.now(KST) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")
