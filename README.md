# 공공기관 SNS 트렌드 리포트 (데모)

매주 지정된 시각에 알림 메일을 받고, 메일 안의 "리포트 생성 시작" 버튼을 누르면
5개 공공기관(고용노동부, 국가유산청, 국립중앙박물관, 보건복지부, 코레일)의
유튜브·인스타그램 최신 콘텐츠를 수집해 큐레이션하고, 완성된 리포트를 메일로 다시 보내주는 파이프라인입니다.

## 전체 구조

```
[GitHub Actions: 매주 월요일 09시(KST) 스케줄]
        │
        ▼
[알림 이메일 발송] --- "리포트 생성 시작" 버튼 ---
        │ (클릭)
        ▼
[Cloudflare Worker] -- 토큰 검증 후 GitHub API 호출 (repository_dispatch)
        │
        ▼
[GitHub Actions: 파이프라인 실행]
   1. YouTube Data API로 5개 채널 최신 영상 수집 (collect_youtube.py)
   2. Playwright로 Instagram 최신 게시물 스냅샷 수집 (collect_instagram.py, best-effort)
   3. 조회수/좋아요 기준 큐레이션 (curate.py)
   4. HTML 리포트 생성 (generate_report.py)
   5. 리포트 이메일 발송 (send_email.py)
```

## ⚠️ 알아두어야 할 한계 (특히 Instagram)

- Instagram 공식 API는 **본인이 관리자로 등록된 계정**에서만 인사이트(좋아요·조회수)를 제공합니다.
  타 기관 계정의 지표를 공식 API로 가져오는 방법은 없습니다.
- 이 데모의 `collect_instagram.py`는 브라우저 자동화로 공개 프로필 페이지에 접속해
  게시물 URL과 캡션 일부를 **최선을 다해(best-effort)** 가져옵니다. 좋아요/조회수는
  비로그인 상태에서 보통 노출되지 않아 `null`로 남을 수 있습니다.
- Instagram이 로그인을 요구하거나 접근을 차단하면 해당 회차는 실패로 표시되고,
  파이프라인 전체가 죽지 않도록 예외 처리되어 있습니다 (`continue-on-error: true`).
- 운영 단계로 넘어갈 때는 Rival IQ, Meltwater, Sprout Social 같은 정식 라이선스
  소셜 리스닝 API로 교체하는 것을 권장합니다.

## 설정 순서

### 1. 이 코드를 새 GitHub 저장소에 push

```bash
git init
git add .
git commit -m "init: sns trend report demo"
git remote add origin https://github.com/<your-org>/sns-trend-report.git
git push -u origin main
```

### 2. YouTube Data API 키 발급

Google Cloud Console에서 프로젝트 생성 → "YouTube Data API v3" 활성화 → API 키 발급.

### 3. SendGrid 계정 및 발신자 인증

SendGrid 가입(무료 티어 월 100통으로 주 1회 발송엔 충분) → Sender Authentication에서
발신 이메일 주소 인증 → API Key 발급 (Mail Send 권한).

### 4. GitHub Secrets 등록

저장소의 **Settings > Secrets and variables > Actions**에서 아래 값을 등록합니다.

| Secret 이름 | 설명 |
|---|---|
| `YOUTUBE_API_KEY` | 2번에서 발급한 키 |
| `SENDGRID_API_KEY` | 3번에서 발급한 키 |
| `MAIL_FROM` | SendGrid에서 인증한 발신 주소 |
| `MAIL_TO` | 리포트를 받을 주소 (콤마로 여러 명 가능) |
| `TRIGGER_SECRET` | 임의의 긴 랜덤 문자열 (Cloudflare Worker와 동일한 값 공유) |
| `TRIGGER_BASE_URL` | 5번에서 배포한 Cloudflare Worker의 `/trigger` 전체 URL |

### 5. Cloudflare Worker 배포 (이메일 버튼 클릭 수신기)

```bash
cd serverless/cloudflare-worker
npm install -g wrangler
wrangler login
wrangler deploy

# 배포 후 secret 등록 (TRIGGER_SECRET은 4번의 GitHub Secret과 반드시 동일해야 함)
wrangler secret put TRIGGER_SECRET
wrangler secret put GITHUB_TOKEN     # repo 권한을 가진 GitHub Personal Access Token
wrangler secret put GITHUB_OWNER     # 예: your-org
wrangler secret put GITHUB_REPO      # 예: sns-trend-report
```

배포가 끝나면 `https://sns-trend-report-trigger.<your-subdomain>.workers.dev/trigger`
형태의 URL이 나옵니다. 이 값을 4번의 `TRIGGER_BASE_URL` Secret에 등록하세요.

### 6. 채널 정보 확인 및 보정

`config/channels.yaml`의 유튜브 채널은 데모 단계라 일부 `username`/`search` 방식으로
채널을 찾도록 되어 있습니다. 정확도를 높이려면 각 기관의 YouTube Studio에서
정확한 채널 ID(`UC...`로 시작하는 24자리)를 확인해 `resolve_by: channel_id`로 교체하세요.

### 7. 테스트 실행

- **알림 메일 테스트**: Actions 탭 > `Weekly Notify` > `Run workflow` (수동 실행)
- **파이프라인 단독 테스트**: Actions 탭 > `Run Pipeline` > `Run workflow` (버튼 클릭 없이 바로 테스트)

두 워크플로우 모두 `workflow_dispatch`를 지원하므로, 매주 월요일을 기다리지 않고
언제든 수동으로 즉시 실행해볼 수 있습니다.

## 로컬에서 개별 스크립트 테스트

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env   # 값 채운 뒤
export $(cat .env | xargs)

python scripts/collect_youtube.py
python scripts/collect_instagram.py
python scripts/curate.py
python scripts/generate_report.py
# 생성된 data/report.html을 브라우저로 열어 확인
```

## 향후 확장 아이디어

- `config/channels.yaml`에 기관 추가만 하면 됨 (코드 수정 불필요)
- Instagram을 정식 소셜 리스닝 API(Rival IQ 등)로 교체
- 큐레이션 로직 고도화 (예: 게시일 가중치를 둔 참여율 계산)
- Slack 알림 채널 추가 (이미 설계된 Cloudflare Worker 구조 재사용 가능)
