/**
 * 바바더닷컴 수기매체 자동화 - 날짜 지정 재실행 웹앱
 *
 * [배포 방법]
 * 1. script.google.com → 새 프로젝트
 * 2. Code.gs, index.html 파일을 붙여넣기
 * 3. 프로젝트 설정(톱니바퀴) → 스크립트 속성 → 아래 두 값 추가
 *    GITHUB_TOKEN  : ghp_xxxx (repo + workflow 권한)
 *    GITHUB_REPO   : yjhwang-svg/babathe-nonauto
 * 4. 배포 → 새 배포 → 웹앱
 *    - 실행 계정 : 나(스크립트 소유자)
 *    - 액세스 권한 : 모든 사용자
 * 5. 배포 URL을 팀 Slack 채널에 고정 메시지로 공유
 */

var WORKFLOW_FILE = "daily_crawl.yml";

function doGet() {
  return HtmlService.createHtmlOutputFromFile("index")
    .setTitle("바바더닷컴 수기매체 재실행")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/**
 * 단일 날짜 재실행. index.html에서 호출.
 * @param {string} targetDate - "YYYY-MM-DD"
 */
function triggerWorkflow(targetDate) {
  return _dispatch({ target_date: targetDate, allow_partial_upload: "1" });
}

/**
 * 기간 재실행. index.html에서 호출.
 * @param {string} dateFrom - "YYYY-MM-DD"
 * @param {string} dateTo   - "YYYY-MM-DD"
 */
function triggerWorkflowRange(dateFrom, dateTo) {
  return _dispatch({ date_from: dateFrom, date_to: dateTo, allow_partial_upload: "1" });
}

function _dispatch(inputs) {
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty("GITHUB_TOKEN");
  var repo  = props.getProperty("GITHUB_REPO") || "yjhwang-svg/babathe-nonauto";

  if (!token) {
    return { success: false, message: "GITHUB_TOKEN이 스크립트 속성에 없습니다." };
  }

  var url = "https://api.github.com/repos/" + repo
          + "/actions/workflows/" + WORKFLOW_FILE + "/dispatches";

  var response = UrlFetchApp.fetch(url, {
    method: "post",
    headers: {
      "Authorization": "Bearer " + token,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json"
    },
    payload: JSON.stringify({ ref: "main", inputs: inputs }),
    muteHttpExceptions: true
  });

  var code = response.getResponseCode();
  if (code === 204) {
    var label = inputs.target_date
      ? inputs.target_date + " 단일 날짜"
      : inputs.date_from + " ~ " + inputs.date_to + " 기간";
    return { success: true, message: label + " 재실행이 시작됐습니다.\n약 5~10분 후 완료됩니다." };
  } else {
    return { success: false, message: "실행 실패 (HTTP " + code + ")\n" + response.getContentText() };
  }
}
