import { createHash, timingSafeEqual } from 'node:crypto';

export function checkAccess(username, password) {
  if (typeof username !== 'string' || typeof password !== 'string' ||
      !username || !password || username.length > 64 || password.length > 256) return false;
  let sessions;
  try { sessions = JSON.parse(process.env.SESSIONS_JSON || '{}'); } catch { return false; }
  if (!sessions || typeof sessions !== 'object' || Array.isArray(sessions) ||
      !Object.hasOwn(sessions, username) || typeof sessions[username] !== 'string' ||
      !sessions[username]) return false;
  const digest = value => createHash('sha256').update(value).digest();
  return timingSafeEqual(digest(sessions[username]), digest(password));
}
export function playlistUrl() {
  return process.env.PLAYLIST_URL ||
    'https://raw.githubusercontent.com/walacesssantos-TCX/iptv-brasil/main/canais.m3u';
}
export function prepareResponse(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Range');
  res.setHeader('Cache-Control', 'no-store');
  if (req.method === 'OPTIONS') { res.status(204).end(); return true; }
  if (req.method && !['GET', 'HEAD'].includes(req.method)) {
    res.setHeader('Allow', 'GET, HEAD, OPTIONS');
    res.status(405).send('Método não permitido');
    return true;
  }
  return false;
}
export function serverUrl(req) {
  if (process.env.PUBLIC_BASE_URL) return new URL(process.env.PUBLIC_BASE_URL);
  const forwarded = String(req.headers?.['x-forwarded-proto'] || '').split(',')[0].trim();
  const protocol = forwarded === 'http' ? 'http' : 'https';
  return new URL(`${protocol}://${req.headers?.host || 'localhost'}`);
}
