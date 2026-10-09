import { checkAccess, prepareResponse, serverUrl } from './_auth.js';
import { loadChannels, categories } from './_playlist.js';

export default async function handler(req, res) {
  if (prepareResponse(req, res)) return;
  const { username, password, action, category_id } = req.query || {};
  if (!checkAccess(username, password))
    return res.status(200).json({ user_info: { auth: 0, status: 'Disabled', message: 'Usuário ou senha inválidos' } });
  const now = Math.floor(Date.now() / 1000);
  if (!action) {
    const base = serverUrl(req);
    return res.status(200).json({
      user_info: { username, password, message: 'IPTV WCS — canais públicos verificados',
        auth: 1, status: 'Active', exp_date: null, is_trial: '0', active_cons: '0',
        created_at: String(now), max_connections: '1', allowed_output_formats: ['m3u8'] },
      server_info: { url: base.hostname, port: base.port || (base.protocol === 'https:' ? '443' : '80'),
        https_port: '443', server_protocol: base.protocol.slice(0, -1), rtmp_port: '0',
        timezone: 'America/Sao_Paulo', timestamp_now: now,
        time_now: new Date().toLocaleString('sv-SE', { timeZone: 'America/Sao_Paulo' }) }
    });
  }
  if (['get_vod_categories', 'get_vod_streams', 'get_series_categories', 'get_series'].includes(action))
    return res.status(200).json([]);
  try {
    const channels = await loadChannels(), groups = categories(channels);
    if (action === 'get_live_categories') return res.status(200).json(groups);
    if (action === 'get_live_streams') {
      const groupMap = new Map(groups.map(g => [g.category_name, g.category_id]));
      const streams = channels.map((c, i) => ({
        num: i + 1, name: c.name, stream_type: 'live', stream_id: c.stream_id,
        stream_icon: c.logo, epg_channel_id: c.epg_id || null, added: String(now),
        category_id: groupMap.get(c.group), custom_sid: '', tv_archive: 0,
        direct_source: '', tv_archive_duration: 0, container_extension: 'm3u8'
      }));
      return res.status(200).json(category_id ? streams.filter(c => c.category_id === String(category_id)) : streams);
    }
    return res.status(200).json([]);
  } catch { return res.status(502).json({ error: 'playlist_indisponivel' }); }
}
