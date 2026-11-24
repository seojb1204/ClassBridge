"""Isolated, send-only calendar experiment. No app imports, DB or queue access.
Run --self-test for offline unit tests. Secrets are read only from environment.
"""
import argparse
import base64
import fcntl
import html
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import format_datetime, make_msgid
import unittest
import uuid
from zoneinfo import ZoneInfo

class ExperimentError(ValueError):
    pass


STATE = Path(__file__).with_name('.invite_state.json')
SCOPE = 'https://www.googleapis.com/auth/gmail.send'
KST = ZoneInfo('Asia/Seoul')


def address(value):
    if not re.fullmatch(r'[A-Za-z0-9_.+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', value):
        raise ExperimentError('단일 이메일 주소만 허용합니다.')
    return value.lower()


def canonical(value):
    local, domain = value.split('@')
    if domain in ('gmail.com', 'googlemail.com'):
        return local.split('+')[0].replace('.', '') + '@gmail.com'
    return value


def initial(sender, recipient, now):
    return dict(uid=str(uuid.uuid4())+'@classbridge.test', sequence=0,
                start=(now+timedelta(minutes=40)).isoformat(), sender=sender,
                recipient=recipient, sent=0, phase='new')


def advance(state, command):
    s = dict(state)
    expected = {'request': 'new', 'update': 'request', 'cancel': 'update'}
    if s['phase'] != expected[command] or s['sent'] >= 3:
        raise ExperimentError('순서 오류 또는 3통 한도: 재발송하지 않습니다.')
    if command != 'request':
        s['sequence'] += 1
    if command == 'update':
        s['start'] = (datetime.fromisoformat(s['start'])+timedelta(minutes=15)).isoformat()
    s['phase'] = command
    return s


def folded(line):
    lines, part = [], ''
    for c in line:
        if len((part+c).encode('utf-8')) > 75:
            lines.append(part)
            part = ' '
        part += c
    return '\r\n'.join(lines+[part])


def build_ics(s, now):
    def utc(t):
        if t.tzinfo is None:
            raise ExperimentError('Timezone required')
        return t.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    start = datetime.fromisoformat(s['start'])
    method = 'CANCEL' if s['phase'] == 'cancel' else 'REQUEST'
    lines = ['BEGIN:VCALENDAR', 'PRODID:-//ClassBridge//Isolated Invite Test//KO',
             'VERSION:2.0', 'CALSCALE:GREGORIAN', 'METHOD:'+method,
             'BEGIN:VEVENT', 'UID:'+s['uid'], 'SEQUENCE:'+str(s['sequence']),
             'DTSTAMP:'+utc(now), 'DTSTART:'+utc(start),
             'DTEND:'+utc(start+timedelta(minutes=30)),
             'SUMMARY:[시험] ClassBridge 상담', 'LOCATION:m205',
             'DESCRIPTION:이 메일은 개발자 본인 대상 시험 발송입니다.',
             'ORGANIZER:mailto:'+s['sender'],
             'ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:'+s['recipient'],
             'STATUS:'+('CANCELLED' if method == 'CANCEL' else 'CONFIRMED'),
             'BEGIN:VALARM', 'TRIGGER:-PT30M', 'ACTION:DISPLAY',
             'DESCRIPTION:상담 시작 30분 전입니다.', 'END:VALARM', 'END:VEVENT', 'END:VCALENDAR']
    return ('\r\n'.join(folded(line) for line in lines)+'\r\n').encode('utf-8')


def build_message(s, now):
    data = build_ics(s, now)
    method = 'CANCEL' if s['phase'] == 'cancel' else 'REQUEST'
    start = datetime.fromisoformat(s['start']).astimezone(KST)
    end = start+timedelta(minutes=30)
    label = {'request':'확정', 'update':'변경', 'cancel':'취소'}[s['phase']]
    weekday = '월화수목금토일'[start.weekday()]
    body = (f'상담 예약이 {label}되었습니다. {start.month}월 {start.day}일({weekday}) '
            f'{start:%H:%M}–{end:%H:%M} · m205 (한국시간). 이 메일은 시험 발송입니다.')
    msg = EmailMessage(policy=SMTP)
    msg['From'], msg['To'] = s['sender'], s['recipient']
    msg['Subject'] = f'[시험] ClassBridge 상담 {label}'
    msg['Date'], msg['Message-ID'] = format_datetime(now), make_msgid(domain='classbridge.test')
    msg.set_content(body)
    msg.add_alternative('<p>'+html.escape(body)+'</p>', subtype='html')
    msg.add_alternative(data.decode('utf-8'), subtype='calendar', charset='utf-8',
                        params={'method':method}, cte='base64')
    msg.add_attachment(data, maintype='application', subtype='ics', filename='invite.ics')
    return msg, data


def save(s):
    temp = STATE.with_suffix('.tmp')
    with os.fdopen(os.open(temp, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600), 'w') as f:
        json.dump(s, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, STATE)


def transmit(msg, sender):
    import httpx
    keys = ['GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET', 'GMAIL_REFRESH_TOKEN']
    if any(not os.environ.get(k) for k in keys):
        raise ExperimentError('발신 인증 환경변수가 없습니다. 값은 출력하지 않습니다.')
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        try:
            r = client.post('https://oauth2.googleapis.com/token', data={
                'client_id':os.environ[keys[0]], 'client_secret':os.environ[keys[1]],
                'refresh_token':os.environ[keys[2]], 'grant_type':'refresh_token'})
            if r.status_code != 200:
                raise ExperimentError('기존 인증 갱신 실패. 응답 본문은 출력하지 않습니다.')
            token = r.json()
            if set(token.get('scope','').split()) != {SCOPE}:
                raise ExperimentError('메일 발송 전용 권한 확인 실패.')
            # A single attempt; uncertain outcomes must never auto-retry.
            r = client.post(f'https://gmail.googleapis.com/gmail/v1/users/{sender}/messages/send',
                            headers={'Authorization':'Bearer '+token['access_token']},
                            json={'raw':base64.urlsafe_b64encode(msg.as_bytes()).decode()})
            if r.status_code != 200 or not r.json().get('id'):
                raise ExperimentError('발송 결과를 확정할 수 없습니다. 자동 재시도하지 않습니다.')
        except (httpx.HTTPError, KeyError, TypeError):
            raise ExperimentError('인증/네트워크 결과 불명. 비밀값은 출력하지 않습니다.') from None


class OfflineTests(unittest.TestCase):
    def test_lifecycle_and_mime(self):
        from icalendar import Calendar
        now = datetime(2026, 11, 24, 0, 0, tzinfo=timezone.utc)
        s = initial('sender@example.com','recipient@example.com', now)
        uid, original = s['uid'], datetime.fromisoformat(s['start'])
        for seq, cmd in enumerate(('request','update','cancel')):
            s = advance(s, cmd)
            msg, data = build_message(s, now)
            cal = Calendar.from_ical(data)
            event = cal.walk('VEVENT')[0]
            self.assertEqual(str(event['UID']), uid)
            self.assertEqual(int(event['SEQUENCE']), seq)
            self.assertEqual(str(cal['METHOD']), 'CANCEL' if cmd=='cancel' else 'REQUEST')
            self.assertEqual(event.decoded('DTSTART'), original+timedelta(minutes=0 if seq==0 else 15))
            self.assertEqual(event.decoded('DTEND')-event.decoded('DTSTART'), timedelta(minutes=30))
            self.assertEqual(cal.walk('VALARM')[0].decoded('TRIGGER'),timedelta(minutes=-30))
            self.assertEqual(str(cal.walk('VALARM')[0]['ACTION']), 'DISPLAY')
            self.assertIn(b'Z\r\n', data)
            self.assertNotIn(b'\n',data.replace(b'\r\n',b''))
            self.assertTrue(all(len(line)<=75 for line in data.split(b'\r\n')))
            self.assertEqual(msg.get_content_type(),'multipart/mixed')
            self.assertEqual(msg.get_payload(0).get_content_type(),'multipart/alternative')
            self.assertEqual(list(msg.iter_attachments())[0].get_payload(decode=True),data)
            calendar_part = msg.get_payload(0).get_payload(2)
            self.assertEqual(calendar_part.get_param('method'), str(cal['METHOD']))
            parsed_inline = Calendar.from_ical(calendar_part.get_payload(decode=True))
            self.assertEqual(str(parsed_inline.walk('VEVENT')[0]['UID']),uid)
            self.assertEqual(str(event['ORGANIZER']), 'mailto:sender@example.com')
            self.assertEqual(str(event['ATTENDEE']), 'mailto:recipient@example.com')
            self.assertEqual(event['ATTENDEE'].params['RSVP'], 'TRUE')
            if cmd=='cancel': self.assertEqual(str(event['STATUS']), 'CANCELLED')
            s['sent'] += 1
        with self.assertRaises(ExperimentError): advance(s,'request')

    def test_addresses_folding_and_order(self):
        for invalid in ('', 'a@example.com,b@example.com', 'a@example.com\nBcc:x@y.com'):
            with self.assertRaises(ExperimentError): address(invalid)
        self.assertEqual(canonical('s.ender+test@gmail.com'),canonical('sender@gmail.com'))
        text = 'SUMMARY:'+'한글'*100
        wire = folded(text)
        self.assertEqual(wire.replace('\r\n ',''),text)
        self.assertTrue(all(len(x.encode())<=75 for x in wire.split('\r\n')))
        with self.assertRaises(ExperimentError):
            advance(initial('a@b.com','c@d.com',datetime.now(timezone.utc)),'cancel')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', choices=['request','update','cancel'])
    parser.add_argument('--to')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--send', action='store_true')
    group.add_argument('--dry-run', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(OfflineTests))
        return 0 if result.wasSuccessful() else 1
    if not args.command or not args.to:
        parser.error('command와 --to 단일 수신자가 필요합니다.')
    sender = address(os.environ.get('GMAIL_SENDER_EMAIL',''))
    recipient = address(args.to)
    if canonical(sender) == canonical(recipient):
        raise ExperimentError('발신자와 수신자는 달라야 합니다.')
    now = datetime.now(timezone.utc).replace(microsecond=0)
    # Dry runs do not create/change state; preview the full chain synthetically.
    if not args.send:
        s = initial(sender, recipient, now)
        s['uid'] = 'dry-run-preview@classbridge.test'
        for cmd in ('request','update','cancel'):
            s = advance(s,cmd)
            if cmd == args.command: break
            s['sent'] += 1
        msg, data = build_message(s,now)
        from icalendar import Calendar
        Calendar.from_ical(data)
        print('\r\n'.join(f'{k}: {v}' for k,v in msg.items()))
        print(data.decode('utf-8'),end='')
        return 0
    with open(str(STATE)+'.lock','a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        s = json.loads(STATE.read_text()) if STATE.exists() else initial(sender,recipient,now)
        if s['sender']!=sender or s['recipient']!=recipient or s.get('uncertain'):
            raise ExperimentError('계정 불일치 또는 이전 발송 결과 불명: 중단합니다.')
        s = advance(s,args.command)
        if any(not os.environ.get(k) for k in ('GMAIL_CLIENT_ID','GMAIL_CLIENT_SECRET','GMAIL_REFRESH_TOKEN')):
            raise ExperimentError('기존 발신 인증을 작업 환경에 연결해야 합니다. 상태는 변경하지 않았습니다.')
        msg, _ = build_message(s,now)
        s['sent'] += 1
        s['uncertain'] = True
        save(s)  # Persist before network: crash/timeout must not duplicate sends.
        transmit(msg,sender)
        s['uncertain'] = False
        save(s)
        print(f"Gmail 접수 성공: {args.command}, 누적 {s['sent']}/3통. 폰 수신/알림은 별도 확인 필요.")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        # Never print arbitrary provider exception strings or response bodies.
        print(str(exc) if isinstance(exc, ExperimentError) else '시험 중단: 내부 오류. 자동 재시도하지 않습니다.', file=sys.stderr)
        sys.exit(1)
