import { checkAccess, playlistUrl } from "./_auth.js";

export default async function handler(req, res) {
  const { username, password } = req.query;

  if (!checkAccess(username, password)) {
    return res.status(401).send("Acesso negado");
  }

  try {
    const upstream = await fetch(playlistUrl(), { cache: "no-store" });
    if (!upstream.ok) return res.status(502).send("Playlist indisponível");

    const body = await upstream.text();
    res.setHeader("Content-Type", "audio/x-mpegurl; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).send(body);
  } catch {
    return res.status(502).send("Falha ao carregar playlist");
  }
}
