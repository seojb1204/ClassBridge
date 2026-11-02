# 데이터베이스

마이그레이션: Alembic (`migrations/versions/0001_initial_schema.py`). 모델과 마이그레이션 결과가 일치하는지는 SQLite·PostgreSQL 각각에서 `compare_metadata == []`로 테스트한다. 업그레이드와 다운그레이드도 함께 검증한다.

```
users ─┬─< auth_sessions            (세션: 토큰 해시만 저장, 사용자 삭제 시 CASCADE)
       ├─< slots (created_by)
       ├─< bookings (student_id, created_by_id) >─ slots
       │      └─< booking_events     (예약 변경 이력)
       ├─< blackouts (created_by)
       ├─< surveys (created_by) ─< survey_questions
       │      ├─< survey_participations (survey_id, user_id)   ← 참여 사실만, 시각 없음
       │      └─< survey_responses (UUID) ─< survey_answers (UUID)   ← user_id·시각 없음
       └─< audit_logs (actor_id)
suggestions (UUID, category, content, submitted_on DATE, status)   ← 사용자와 무관
app_settings (key, JSON value)
```

## 주요 제약

| 테이블 | 제약 | 목적 |
|---|---|---|
| slots | `CHECK booked_count BETWEEN 0 AND capacity` | 정원 초과 최종 차단 |
| slots | `CHECK kind='group' OR capacity=1` | 개인 상담 정원 1 |
| slots | `CHECK end_at > start_at` | 시간 순서 |
| bookings | `UNIQUE (student_id) WHERE status='booked'` | 학생 1명당 활성 예약 1건 |
| survey_participations | `PK (survey_id, user_id)` | 중복 참여 방지 |
| users | `UNIQUE google_sub`, `UNIQUE email`, `CHECK role IN (...)` | 신원 고정 |

## 시간

모든 시각은 UTC `timestamptz`로 저장한다(`UTCDateTime` 타입이 naive datetime 저장을 거부). 입력과 표시는 Asia/Seoul 기준이다. 상담 불가일과 건의 제출일은 한국 날짜(`DATE`)로 저장한다.

## 새 마이그레이션 만들기

```bash
DATABASE_URL=postgresql+psycopg://... alembic revision --autogenerate -m "설명"
# 생성된 파일을 사람이 검토 (특히 drop/alter) → 테스트 → 커밋
alembic upgrade head
```

운영 데이터가 있는 상태에서 컬럼 삭제나 타입 변경 같은 **파괴적 마이그레이션**은 사용자 승인을 받는다. "새 컬럼 추가 → 코드 전환 → 이전 컬럼 제거"처럼 단계를 나눠 진행한다.

## DB 계정 (FastAPI 직접 접속 구조)

이 서비스는 Supabase Data API(PostgREST)를 **사용하지 않는다**. FastAPI가 PostgreSQL에 직접 접속한다. 따라서 RLS보다 다음이 핵심이다.

1. Supabase 프로젝트 설정에서 Data API를 끄거나, `public` 스키마의 `anon`·`authenticated` 권한을 회수한다:
   ```sql
   REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
   REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
   ```
2. 앱 전용 계정은 DML 권한만 갖고, 마이그레이션 계정은 따로 분리한다(권장):
   ```sql
   CREATE ROLE classbridge_app LOGIN PASSWORD '...';
   GRANT USAGE ON SCHEMA public TO classbridge_app;
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO classbridge_app;
   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO classbridge_app;
   ```
3. 연결 문자열에는 `sslmode=require`를 사용한다.

위 SQL은 **실제 Supabase에서 실행해 검증하지 않았다**(계정 필요). 적용 후 `anon` 키로 REST 조회가 거부되는지 확인해야 한다.
