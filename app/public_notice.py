"""Public operating notice. Operator details stay in deployment configuration."""
from html import escape

NOTICE_VERSION = "2026-11-05"


def render_notice(settings) -> str:
    operator = escape(settings.operator_name)
    affiliation = escape(settings.operator_affiliation)
    contact = escape(settings.support_email, quote=True)
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport"
content="width=device-width,initial-scale=1">
<title>ClassBridge 이용·개인정보 안내</title><link rel="stylesheet"
href="/static/css/app.css"></head>
<body><main class="view"><article class="panel">
<h1>ClassBridge 이용·개인정보 안내</h1><p>시행일: {NOTICE_VERSION}</p>
<h2>운영 및 문의</h2><p>개인 운영자: {operator} · 소속:
{affiliation}</p>
<p>상담 예약과 상담 기록 관리를 위한 서비스입니다. Google 로그인은 계정 소유를 확인하며, 재학
여부를 인증하지는 않습니다.</p>
<p>문의·열람·정정·삭제·동의 철회 요청: <a
href="mailto:{contact}">{contact}</a>. 요청자의 본인 여부를 확인한 뒤
처리합니다.</p>
<h2>수집·이용 항목과 목적</h2>
<ul><li>로그인 및 계정 관리: Google 계정 식별자, 인증된 이메일, 이름, 역할, 로그인
시각.</li>
<li>상담 예약 및 진행: 예약 시간, 신청자 이름, 학번·학년 등 이용자가 입력한 정보, 상담
유형·방식·주제, 변경·취소·완료 상태와 처리 이력.</li>
<li>상담 지원: 교수자가 작성하는 상담 기록. 학생에게 다른 학생의 정보나 교수자 전용 상담 기록을
공개하지 않습니다.</li>
<li>접근 보호: 로그인 세션과 안내 동의 버전·시각, 관리자 작업 이력. Google 비밀번호는
ClassBridge가 받거나 저장하지 않습니다.</li></ul>
<h2>열람 범위와 보관기간</h2><p>학생은 자신의 예약을 확인합니다. 담당 교수자와 관리자는 업무에
필요한 예약·상담 정보를 확인합니다.</p>
<p>예약·상담 기록과 연결된 처리 이력은 상담 예정일로부터 365일 보관 후 삭제합니다. 계정 정보와 동의
이력은 계정 이용 기간 동안 보관하며, 탈퇴·동의 철회 요청 시 관련 기록의 보관 필요
여부를 확인해 처리합니다.</p>
<p>운영자는 기간이 지난 기록을 관리하며, 복구용 사본도 같은 보관 원칙에 따라 관리합니다.</p>
<h2>서비스 제공업체 및 국외 처리 안내</h2>
<p>Render(웹서비스 실행)와 Neon(데이터베이스 저장)을 이용하며, 현재 앱·DB 서버 지역은
싱가포르입니다. 위 계정·예약·상담 정보가 서비스 이용 시 암호화된 통신으로 해당 서버에
전송·저장됩니다. 처리 목적과 보관기간은 위 안내와 같습니다.</p>
<p>제공업체의 처리방침·문의: <a
href="https://render.com/privacy">Render</a>, <a
href="https://neon.com/privacy-policy">Neon</a>. Google 로그인은
<a
href="https://policies.google.com/privacy">Google의
개인정보처리방침</a>도 적용됩니다.</p>
<p>수집·이용 및 국외 처리에 동의하지 않을 수 있습니다. 동의하지 않으면 이 온라인 예약 서비스에
로그인할 수 없으며, 대체 상담 방법은 위 문의처에 요청할 수 있습니다.</p>
<h2>사용 시 유의사항</h2><p>주민등록번호, 비밀번호 등 상담에 불필요한 정보는 입력하지 마세요.
로그인 쿠키는 계정 보호와 로그인 유지에 사용됩니다. 현재 외부 AI 분석·설문·건의 기능은
운영하지 않습니다.</p>
<p><a href="/">서비스로
돌아가기</a></p></article></main></body></html>'''
