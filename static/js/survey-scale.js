export const AGREEMENT_SCALE = ["전혀 그렇지 않다", "그렇지 않다", "보통이다", "그렇다", "매우 그렇다"];
export const LEGACY_SCALE = ["매우 불만", "불만", "보통", "만족", "매우 만족"];
export const scaleLabels = (q) => q.options?.length === 5 ? q.options : LEGACY_SCALE;
