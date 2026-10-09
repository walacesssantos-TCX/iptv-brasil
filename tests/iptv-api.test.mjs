import test from 'node:test';
import assert from 'node:assert/strict';
import { checkAccess, serverUrl } from '../api/_auth.js';
import { parseM3U } from '../api/_playlist.js';
import playerApi from '../api/player_api.js';
import getPlaylist from '../api/get.js';
import live from '../api/live.js';

const text = '#EXTM3U\n#EXTINF:-1 tvg-id="A.br" group-title="Abertos Brasil",Canal A\nhttps://example.com/a.m3u8\n#EXTINF:-1 tvg-id="B.br" group-title="Cristãos",Canal B\nhttps://example.com/b.m3u8\n';
process.env.SESSIONS_JSON = JSON.stringify({ wcs: '01234567' });
function response() {
  return { headers: {}, code: null, body: null,
    setHeader(k, v) { this.headers[k] = v; },
    status(v) { this.code = v; return this; },
    json(v) { this.body = v; return this; },
    send(v) { this.body = v; return this; },
    end() { return this; },
    redirect(code, url) { this.code = code; this.body = url; return this; }
  };
}
const request = (query = {}, method = 'GET') => ({
  query: { username: 'wcs', password: '01234567', ...query }, method,
  headers: { host: 'iptv.example.com', 'x-forwarded-proto': 'https' }
});
global.fetch = async () => ({ ok: true, text: async () => text });

test('Login accepts eight digits including leading zeros and rejects invalid credentials', () => {
  assert.equal(checkAccess('wcs', '01234567'), true);
  assert.equal(checkAccess('wcs', '1234567'), false);
  assert.equal(checkAccess('other', '01234567'), false);
  assert.equal(checkAccess('__proto__', {}), false);
  assert.equal(checkAccess(['wcs'], '01234567'), false);
});
test('Invalid environment configuration denies access', () => {
  const old = process.env.SESSIONS_JSON;
  for (const value of ['{', 'null', '[]', '{"wcs":""}']) {
    process.env.SESSIONS_JSON = value;
    assert.equal(checkAccess('wcs', '01234567'), false);
  }
  process.env.SESSIONS_JSON = old;
});
test('Channel IDs remain stable when list ordering changes; excluded entries are filtered', () => {
  const a = parseM3U(text);
  const b = parseM3U(text + '#EXTINF:-1,Premiere\nhttps://example.com/pay.m3u8\n');
  assert.equal(b.length, 2);
  const reversed = parseM3U('#EXTM3U\n' + text.split('#EXTINF:').slice(1).reverse().map(s => '#EXTINF:' + s).join(''));
  assert.equal(a[0].stream_id, reversed[1].stream_id);
  assert.throws(() => parseM3U('<html>Error</html>'));
});
test('Prime authentication reports active access and the correct public host', async () => {
  const res = response(); await playerApi(request(), res);
  assert.equal(res.body.user_info.auth, 1);
  assert.equal(res.body.server_info.url, 'iptv.example.com');
  assert.equal(res.body.server_info.port, '443');
  const bad = response(); await playerApi(request({password:'incorrect'}), bad);
  assert.equal(bad.body.user_info.auth, 0);
});
test('Live categories and category filtering work', async () => {
  const cats = response(); await playerApi(request({action:'get_live_categories'}), cats);
  assert.equal(cats.body.length, 2);
  const streams = response(); await playerApi(request({action:'get_live_streams',category_id:'2'}), streams);
  assert.equal(streams.body.length, 1);
  assert.equal(streams.body[0].name, 'Canal B');
});
test('Authenticated M3U uses stable stream IDs and rejects wrong credentials', async () => {
  const res = response(); await getPlaylist(request(), res);
  assert.ok(res.body.startsWith('#EXTM3U\n'));
  const id = parseM3U(text)[0].stream_id;
  assert.ok(res.body.includes(`/live/wcs/01234567/${id}.m3u8`));
  const denied = response(); await getPlaylist(request({password:'wrong'}), denied);
  assert.equal(denied.code, 401);
});
test('Stream redirection handles IDs, bad credentials and missing channels', async () => {
  const id = parseM3U(text)[0].stream_id;
  const res = response(); await live(request({stream:`${id}.m3u8`}), res);
  assert.equal(res.code, 302); assert.equal(res.body, 'https://example.com/a.m3u8');
  const missing = response(); await live(request({stream:'2147483647.m3u8'}), missing);
  assert.equal(missing.code, 404);
  const invalid = response(); await live(request({stream:'1oops'}), invalid);
  assert.equal(invalid.code, 400);
  const denied = response(); await live(request({stream:`${id}.ts`, password:'wrong'}), denied);
  assert.equal(denied.code, 401);
});
test('Preflight needs no credential and upstream failures are reported', async () => {
  const preflight = response(); await getPlaylist(request({}, 'OPTIONS'), preflight);
  assert.equal(preflight.code, 204);
  assert.equal(preflight.headers['Access-Control-Allow-Origin'], '*');
  const old = global.fetch; global.fetch = async () => ({ok:false});
  const failed = response(); await playerApi(request({action:'get_live_streams'}), failed);
  assert.equal(failed.code, 502); global.fetch = old;
  assert.equal(serverUrl(request()).origin, 'https://iptv.example.com');
});
