import { createHash } from 'node:crypto';
import { playlistUrl } from './_auth.js';

export function parseM3U(text) {
  if (!text.replace(/^\uFEFF/, '').trimStart().startsWith('#EXTM3U'))
    throw new Error('Cabeçalho M3U ausente');
  const channels = [], seen = new Set();
  let meta = null;
  for (const value of text.split(/\r?\n/)) {
    const line = value.trim();
    if (line.startsWith('#EXTINF:')) { meta = line; continue; }
    if (!meta || !/^https?:\/\//i.test(line)) continue;
    const info = meta;
    meta = null;
    const comma = info.match(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/);
    if (!comma) continue;
    const name = info.slice(comma.index + 1).trim();
    if (!name || /pluto\s*tv|sportv|premiere|discovery\s*turbo/i.test(name + ' ' + info) ||
        /(?:^|\.)pluto\.tv$/.test(new URL(line).hostname) || /jmp2\.uk\/plu-/.test(line)) continue;
    const attr = key => (info.match(new RegExp(`${key}="([^"]*)"`, 'i')) || [,''])[1];
    const id = attr('tvg-id'), key = id || `${name}|${line}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const hash = createHash('sha256').update(key).digest().readUInt32BE(0) & 0x7fffffff;
    channels.push({ name, group: attr('group-title') || 'Outros', logo: attr('tvg-logo'),
                    epg_id: id, url: line, stream_id: hash || 1 });
  }
  if (!channels.length) throw new Error('Lista M3U vazia');
  return channels;
}
export async function loadChannels() {
  const response = await fetch(playlistUrl(), { cache: 'no-store', signal: AbortSignal.timeout(15000) });
  if (!response.ok) throw new Error('Lista indisponível');
  return parseM3U(await response.text());
}
export function categories(channels) {
  return [...new Set(channels.map(c => c.group))].map((name, i) => ({
    category_id: String(i + 1), category_name: name, parent_id: 0
  }));
}
export function streamUrl(base, username, password, channel) {
  return `${base.origin}/live/${encodeURIComponent(username)}/${encodeURIComponent(password)}/${channel.stream_id}.m3u8`;
}
export function renderM3U(channels, base, username, password) {
  const safe = value => String(value).replace(/["\r\n]/g, '');
  return '#EXTM3U\n' + channels.map(c =>
    `#EXTINF:-1 tvg-id="${safe(c.epg_id)}" tvg-logo="${safe(c.logo)}" group-title="${safe(c.group)}",${safe(c.name)}\n` +
    streamUrl(base, username, password, c)).join('\n') + '\n';
}
