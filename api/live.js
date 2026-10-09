import { checkAccess, prepareResponse } from './_auth.js';
import { loadChannels } from './_playlist.js';
export default async function handler(req, res) {
  if (prepareResponse(req, res)) return;
  const { username, password, stream } = req.query || {};
  if (!checkAccess(username, password)) return res.status(401).send('Acesso negado');
  if (typeof stream !== 'string' || !/^\d+(?:\.(?:m3u8|ts))?$/.test(stream))
    return res.status(400).send('Canal inválido');
  const id = Number(stream.replace(/\.(?:m3u8|ts)$/, ''));
  if (!Number.isSafeInteger(id) || id < 1) return res.status(400).send('Canal inválido');
  try {
    const channel = (await loadChannels()).find(c => c.stream_id === id);
    if (!channel) return res.status(404).send('Canal não encontrado');
    return res.redirect(302, channel.url);
  } catch { return res.status(502).send('Falha ao carregar canal'); }
}
