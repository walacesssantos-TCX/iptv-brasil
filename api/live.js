import { checkAccess, playlistUrl } from "./_auth.js";

function parseUrls(text) {
  const lines = text.split(/\r?\n/);
  const urls = [];
  let armed = false;
  for (const line of lines) {
    if (line.startsWith("#EXTINF:")) { armed = true; continue; }
    if (armed && /^https?:\/\//i.test(line.trim())) {
      urls.push(line.trim());
      armed = false;
    }
  }
  return urls;
}

export default async function handler(req, res) {
  const { username, password, stream } = req.query;
  if (!checkAccess(username, password)) return res.status(401).send("Acesso negado");

  const id = Number(String(stream || "").replace(/\.m3u8$/i, ""));
  if (!Number.isInteger(id) || id < 1) return res.status(400).send("Canal inválido");

  try {
    const r = await fetch(playlistUrl(), { cache: "no-store" });
    if (!r.ok) return res.status(502).send("Playlist indisponível");
    const urls = parseUrls(await r.text());
    const target = urls[id - 1];
    if (!target) return res.status(404).send("Canal não encontrado");
    return res.redirect(302, target);
  } catch {
    return res.status(502).send("Falha ao carregar canal");
  }
}
