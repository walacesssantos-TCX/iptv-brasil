import { checkAccess, prepareResponse, serverUrl } from './_auth.js';
import { loadChannels, renderM3U } from './_playlist.js';
export default async function handler(req, res) {
  if (prepareResponse(req, res)) return;
  const { username, password } = req.query || {};
  if (!checkAccess(username, password)) return res.status(401).send('Acesso negado');
  try {
    const body = renderM3U(await loadChannels(), serverUrl(req), username, password);
    res.setHeader('Content-Type', 'audio/x-mpegurl; charset=utf-8');
    return res.status(200).send(body);
  } catch { return res.status(502).send('Falha ao carregar playlist'); }
}
