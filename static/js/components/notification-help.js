export function notificationHelp(item) {
  const code = item.error_code || '';
  if (code === 'token_rejected') return 'Google 발송 인증이 만료되거나 거부됐습니다. 발송용 클라이언트 설정을 확인하고 같은 발신 계정으로 재인증한 뒤 Refresh token을 서버에 등록하세요. 로그인용 설정은 변경하지 마세요.';
  if (code === 'scope_unverified') return '발송 권한을 확인하지 못했습니다. gmail.send 권한만으로 다시 인증하세요.';
  if (code === 'push_key_rejected') return '휴대폰 알림 인증키가 거부됐습니다. 서버의 알림키 쌍을 확인하고 교수자 기기에서 다시 등록하세요.';
  if (code === 'recipient_config_changed') return '기존 알림과 현재 발신·수신 계정이 다릅니다. 수신자를 확인하기 전에는 재발송하지 마세요.';
  if (code === 'daily_quota_exceeded') return 'Gmail의 하루 발송 한도에 도달했습니다. 한도가 회복된 후 확인하고 재시도하세요.';
  if (item.status === 'uncertain') return '이미 전달됐을 수 있습니다. 발신함·수신 기기를 먼저 확인하세요. 재시도하면 중복 전달될 수 있습니다.';
  if (item.status === 'reauth') return '발송 권한 또는 인증 설정을 확인해야 합니다. 설정 복구 후 재시도하세요.';
  if (item.status === 'failed') return '자동 발송이 중단됐습니다. 오류와 수신 대상을 확인한 뒤 재시도하세요.';
  if (code) return '일시적인 연결 또는 발송 제한 문제입니다. 자동 재시도를 기다리고, 오래 지속되면 서버 상태를 확인하세요.';
  return '서버에서 순서대로 발송합니다.';
}
