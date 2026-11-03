// 로그인 사용자 상태. 화면 표시용일 뿐, 권한 판단은 항상 서버가 한다.
export const state = { me: null };

export function can(perm) {
  return !!state.me && state.me.permissions.includes(perm);
}

export function feature(name) {
  return state.me?.features?.[name];
}
