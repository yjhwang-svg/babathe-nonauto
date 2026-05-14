# 바바더닷컴 수기매체 자동화

매일 오전 8시(KST) GitHub Actions로 수기매체 데이터를 자동 수집해 Google Sheets **버티컬_raw** 탭에 적재합니다.

## 수집 매체

| 매체 | 캠페인 | 수집 지표 |
|------|--------|----------|
| 버즈빌UA | Buzzvil | 클릭수, 광고비 (2개 adgroup 합산) |
| ive | ive_cpa | 클릭수, 소진금액 |
| 네이버쇼핑 | 네이버쇼핑_PC | 노출수, 클릭수, 적용수수료 |
| 네이버쇼핑 | 네이버쇼핑_M | 노출수, 클릭수, 적용수수료 |
| 에디AI | AI상품매칭 | 노출수, 클릭수, 비용, 구매수, 매출 |
| 에디AI | 트렌드박스 | 노출수, 클릭수, 비용, 구매수, 매출 |

## 구조

```
babathe-nonauto/
├── .github/workflows/daily_crawl.yml  # 자동화 스케줄
├── crawlers/
│   ├── buzzvil.py        # 버즈빌UA
│   ├── iscreen.py        # ive(아이스크린)
│   ├── naver_shopping.py # 네이버쇼핑 PC/MO
│   └── ediai.py          # 에디AI
├── sheets/uploader.py    # Sheets 적재 (J/K 수식 자동 삽입)
├── utils/dates.py        # KST 전일자 날짜 계산
├── main.py               # 메인 실행
├── config.json           # 스프레드시트 ID 등 정적 설정
└── gas/                  # 수동 재실행 GAS 웹앱
    ├── Code.gs
    └── index.html
```

## GitHub Secrets 설정

| Secret | 설명 |
|--------|------|
| `BUZZVIL_EMAIL` | 버즈빌 로그인 이메일 |
| `BUZZVIL_PASSWORD` | 버즈빌 비밀번호 |
| `ISCREEN_ID` | 아이스크린 로그인 ID |
| `ISCREEN_PW` | 아이스크린 비밀번호 |
| `NAVER_ID` | 네이버 계정 ID |
| `NAVER_PW` | 네이버 비밀번호 |
| `NAVER_COOKIE` | (선택) 네이버 세션 쿠키 JSON — SMS 인증 우회용 |
| `EDIAI_ID` | 에디AI 로그인 ID |
| `EDIAI_PW` | 에디AI 비밀번호 |
| `GOOGLE_SERVICE_ACCOUNT` | GCP 서비스 계정 JSON 전체 |
| `SLACK_WEBHOOK_URL` | (선택) Slack 알림 웹훅 URL |

## 설정 탭 관리 (Google Sheets)

스프레드시트 내 **설정** 탭에서 동적 설정을 관리합니다.

| 키 | 기본값 | 설명 |
|----|--------|------|
| `buzzvil_adgroup_ids` | `55775,55776` | 버즈빌 adgroup ID (쉼표 구분) — **매달 업데이트** |

## 수동 재실행 (GAS 웹앱)

`gas/Code.gs`, `gas/index.html`을 Google Apps Script에 배포하면 날짜를 지정해 재실행할 수 있는 UI가 생성됩니다.

1. [script.google.com](https://script.google.com) → 새 프로젝트
2. `Code.gs`, `index.html` 내용 붙여넣기
3. 스크립트 속성 추가:
   - `GITHUB_TOKEN`: `repo + workflow` 권한의 PAT
   - `GITHUB_REPO`: `yjhwang-svg/babathe-nonauto`
4. 배포 → 웹앱 → 모든 사용자 액세스

## 네이버쇼핑 로그인 문제 발생 시

네이버 로그인에서 SMS 인증이 요구될 경우:
1. 브라우저에서 직접 네이버 로그인
2. 개발자 도구(F12) → Application → Cookies → `naver.com` 쿠키를 JSON 배열로 복사
3. `NAVER_COOKIE` Secret에 등록
