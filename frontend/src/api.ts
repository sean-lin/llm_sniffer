import type { Session, RequestSummary, RequestDetail } from './types';

const BASE = '';

export async function fetchSessions(): Promise<Session[]> {
  const res = await fetch(`${BASE}/api/sessions`);
  return res.json();
}

export async function fetchSessionRequests(sessionId: string): Promise<RequestSummary[]> {
  const res = await fetch(`${BASE}/api/sessions/${sessionId}/requests`);
  return res.json();
}

export async function fetchRequestDetail(requestId: number): Promise<RequestDetail> {
  const res = await fetch(`${BASE}/api/requests/${requestId}`);
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/api/sessions/${sessionId}`, { method: 'DELETE' });
}

export function mediaUrl(path: string): string {
  return `${BASE}/api/media/${path}`;
}
