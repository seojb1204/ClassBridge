# 실제 공개 배포 전 사용자 작업 목록

코드로 해결할 수 없고 **사람의 결정이나 승인이 필요한** 항목이다. 모두 끝나기 전에는 실제 학생 개인정보를 받지 않는다.

## A. 정책·승인 (필수)
- [ ] **개인정보 처리 근거와 동의 방식** 결정 (수집 항목: Google 이메일·이름, 상담 예약·기록, 설문 참여 사실)
- [ ] **보유기간** 결정 (예: 학기 종료 후 N개월 뒤 파기). 결정되면 파기 기능 구현을 요청할 것 (현재 미구현)
- [ ] 학교·교수자의 서비스 운영 승인
- [ ] 학생용 안내문 작성: 익명 범위와 한계([anonymity.md](anonymity.md) 3장), 상담 기록 열람 범위, 문의처
- [ ] 외부 서비스(Render·Neon·Google, 외부 AI 사용 시 AI 제공사) 이용 및 국외 이전 검토
- [ ] 외부 AI 사용 여부 결정 (기본은 비활성. `AI_MODE=external`은 검토 후)
- [ ] 익명 설문·건의함 운영 활성화 결정 (`FEATURE_SURVEYS`, `FEATURE_SUGGESTIONS`는 운영 기본값이 꺼져 있음)

## B. 계정·설정
- [ ] Google Cloud OAuth 클라이언트 생성, 동의 화면 설정
- [ ] ClassBridge 전용 Neon 무료 프로젝트 생성 → 새 DB에서 마이그레이션 0001~0004와 RLS/테이블 접근 검증. 기존 프로젝트 DB 사용 금지
- [ ] Render 무료 서비스(사용 가능 여부·요금 확인 후) 생성, Neon pooled/direct URL을 비밀 환경변수로 설정
- [ ] 관리자·교수 Google 계정 2단계 인증 활성화
- [ ] 학생 개인 Gmail 로그인 정책 확인: `ALLOWED_EMAIL_DOMAINS`는 빈 값. 링크를 받은 사람이 실제 수강생인지 Google 로그인만으로는 검증할 수 없음을 운영 주체에게 안내
- [ ] 백업 일정과 보관 위치 결정

## C. 검증
- [ ] 비공개 스테이징에서 [deployment.md](deployment.md) 10장 스모크 테스트
- [ ] `STAGING_MODE=true`, `STAGING_ALLOWED_EMAILS`로 시험 계정만 허용하는지 확인 (그 외 Google 계정 거부)
- [ ] 실제 Google 로그인 3개 역할 확인 (자동 테스트는 가짜 검증기를 사용함)
- [ ] 실제 iOS Safari / Android Chrome 기기에서 예약 흐름 확인 (자동 테스트는 Chromium 모바일 화면 크기만 확인)
- [ ] 수업 규모로 부하 확인 (동시 접속 수십 명 수준)

## D. Git
- [ ] 이 코드를 `seojb1204/ClassBridge`에 푸시할지 결정 (현재 저장소는 **public**. 코드에 비밀값은 없지만 공개 여부 확인)
