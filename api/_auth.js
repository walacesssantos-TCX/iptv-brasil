export function checkAccess(username, password) {
  const raw = process.env.SESSIONS_JSON || "{}";
  let sessions = {};
  try { sessions = JSON.parse(raw); } catch { return false; }
  return typeof username === "string" &&
    typeof password === "string" &&
    sessions[username] === password;
}

export function playlistUrl() {
  return process.env.PLAYLIST_URL ||
    "https://raw.githubusercontent.com/walacesssantos-TCX/iptv-brasil/main/canais.m3u";
}
