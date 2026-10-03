import { checkAccess, playlistUrl } from "./_auth.js";

function parseM3U(text) {
  const lines = text.split(/\r?\n/);
  const channels = [];
  let meta = null;

  for (const line of lines) {
    if (line.startsWith("#EXTINF:")) {
      meta = line;
      continue;
    }
    if (meta && /^https?:\/\//i.test(line.trim())) {
      const name = (meta.split(",").pop() || "Canal").trim();
      const group = (meta.match(/group-title="([^"]*)"/i) || [,"Outros"])[1] || "Outros";
      const logo = (meta.match(/tvg-logo="([^"]*)"/i) || [,""])[1] || "";
      channels.push({ name, group, logo, url: line.trim() });
      meta = null;
    }
  }
  return channels;
}

async function loadChannels() {
  const r = await fetch(playlistUrl(), { cache: "no-store" });
  if (!r.ok) throw new Error("playlist");
  return parseM3U(await r.text());
}

export default async function handler(req, res) {
  const { username, password, action } = req.query;

  if (!checkAccess(username, password)) {
    return res.status(200).json({
      user_info: { auth: 0, status: "Disabled" }
    });
  }

  const now = Math.floor(Date.now() / 1000);

  if (!action) {
    const proto = req.headers["x-forwarded-proto"] || "https";
    const host = req.headers.host;
    return res.status(200).json({
      user_info: {
        username,
        password,
        message: "Acesso IPTV autorizado",
        auth: 1,
        status: "Active",
        exp_date: null,
        is_trial: "0",
        active_cons: "0",
        created_at: String(now),
        max_connections: "1",
        allowed_output_formats: ["m3u8"]
      },
      server_info: {
        url: host,
        port: proto === "https" ? "443" : "80",
        https_port: "443",
        server_protocol: proto,
        rtmp_port: "0",
        timezone: "America/Sao_Paulo",
        timestamp_now: now,
        time_now: new Date().toISOString()
      }
    });
  }

  let channels;
  try {
    channels = await loadChannels();
  } catch {
    return res.status(502).json({ error: "playlist_indisponivel" });
  }

  const groups = [...new Set(channels.map(c => c.group))];

  if (action === "get_live_categories") {
    return res.status(200).json(groups.map((g, i) => ({
      category_id: String(i + 1),
      category_name: g,
      parent_id: 0
    })));
  }

  if (action === "get_live_streams") {
    const categoryMap = new Map(groups.map((g, i) => [g, String(i + 1)]));
    return res.status(200).json(channels.map((c, i) => ({
      num: i + 1,
      name: c.name,
      stream_type: "live",
      stream_id: i + 1,
      stream_icon: c.logo,
      epg_channel_id: null,
      added: String(now),
      category_id: categoryMap.get(c.group),
      custom_sid: "",
      tv_archive: 0,
      direct_source: c.url,
      tv_archive_duration: 0
    })));
  }

  return res.status(200).json([]);
}
