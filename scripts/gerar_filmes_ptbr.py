#!/usr/bin/env python3
import json
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "filmes.m3u"
DB = ROOT / "vendor" / "movies-deluxe" / "data" / "movies.json"

UA = "iptv-brasil-public-domain-builder/1.0"

LANG_HINT_RE = re.compile(
    r"(pt[-_ ]?br|ptbr|por(?:tugu[eê]s)?|portugu[eê]s(?: do brasil)?|"
    r"brazilian portuguese|brasil(?:eiro|eira)?|dublad[oa])",
    re.I,
)

GENRE_MAP = {
    "action": "Ação",
    "adventure": "Ação e Aventura",
    "comedy": "Comédia",
    "sci-fi": "Ficção Científica",
    "science fiction": "Ficção Científica",
    "horror": "Terror",
    "thriller": "Suspense",
    "mystery": "Mistério",
    "drama": "Drama",
    "animation": "Animação",
    "family": "Família",
    "crime": "Crime",
    "film-noir": "Film Noir",
    "film noir": "Film Noir",
    "western": "Faroeste",
    "documentary": "Documentário",
    "romance": "Romance",
    "fantasy": "Fantasia",
    "war": "Guerra",
    "music": "Musical",
    "musical": "Musical",
}

def safe_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def is_ptbr_movie(movie, source):
    pieces = []
    md = movie.get("metadata") or {}
    for key in ("Language", "Country", "Title", "Plot"):
        v = md.get(key)
        if v:
            pieces.append(str(v))
    for key in ("language", "title", "description"):
        v = source.get(key)
        if isinstance(v, list):
            pieces.extend(map(str, v))
        elif v:
            pieces.append(str(v))
    text = " ".join(pieces)
    # Prefer explicit Brazilian Portuguese / dubbed markers.
    if LANG_HINT_RE.search(text):
        return True
    # Accept Portuguese-language works from Brazil as useful PT-BR VOD.
    lang = str(md.get("Language") or "").lower()
    country = str(md.get("Country") or "").lower()
    return ("portuguese" in lang or "português" in lang or "portugues" in lang) and "brazil" in country

def genre_for(movie):
    md = movie.get("metadata") or {}
    raw = str(md.get("Genre") or "")
    genres = [g.strip().lower() for g in raw.split(",") if g.strip()]
    for g in genres:
        if g in GENRE_MAP:
            return GENRE_MAP[g]
    for g in genres:
        for k, v in GENRE_MAP.items():
            if k in g:
                return v
    return "Outros Filmes"

def title_for(movie):
    md = movie.get("metadata") or {}
    title = (md.get("Title") or movie.get("title") or "").strip()
    year = movie.get("year") or (md.get("Year") or "").strip()
    if year and year not in title:
        title = f"{title} ({year})"
    return title or "Filme"

def pick_mp4(identifier):
    try:
        meta_url = "https://archive.org/metadata/" + urllib.parse.quote(identifier, safe="")
        data = json.loads(safe_get(meta_url).decode("utf-8", "replace"))
    except Exception:
        return None

    files = data.get("files") or []
    candidates = []
    for f in files:
        name = str(f.get("name") or "")
        fmt = str(f.get("format") or "").lower()
        lower = name.lower()
        if not lower.endswith((".mp4", ".m4v")):
            continue
        if any(x in lower for x in ("trailer", "sample", "thumb", "preview")):
            continue
        score = 0
        if "h.264" in fmt or "h264" in fmt:
            score += 50
        if "mpeg4" in fmt or "mpeg-4" in fmt:
            score += 40
        if "512kb" not in lower:
            score += 10
        try:
            size = int(f.get("size") or 0)
        except Exception:
            size = 0
        score += min(size // (50 * 1024 * 1024), 20)
        candidates.append((score, size, name))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    name = candidates[0][2]
    return "https://archive.org/download/{}/{}".format(
        urllib.parse.quote(identifier, safe=""),
        urllib.parse.quote(name, safe="/")
    )

def parse_existing(text):
    entries = []
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF"):
            current = line
        elif current and re.match(r"^https?://", line):
            entries.append((current, line))
            current = None
    return entries

def extinf(title, group, poster, movie_id):
    attrs = [
        f'tvg-id="{movie_id}"',
        f'group-title="{group}"',
        'type="movie"',
    ]
    if poster:
        attrs.append(f'tvg-logo="{poster}"')
    return "#EXTINF:-1 " + " ".join(attrs) + "," + title.replace("\n", " ").strip()

def main():
    if not DB.exists():
        raise SystemExit("Base movies-deluxe não encontrada")

    existing_text = TARGET.read_text("utf-8") if TARGET.exists() else "#EXTM3U\n"
    existing = parse_existing(existing_text)
    seen_urls = {u for _, u in existing}
    seen_ids = set()
    for meta, _ in existing:
        m = re.search(r'tvg-id="([^"]+)"', meta)
        if m:
            seen_ids.add(m.group(1))

    with DB.open("r", encoding="utf-8") as fh:
        db = json.load(fh)

    candidates = []
    for key, movie in db.items():
        if not isinstance(movie, dict) or key.startswith("_"):
            continue
        sources = movie.get("sources") or []
        for source in sources:
            if not isinstance(source, dict):
                continue
            channel_id = str(source.get("channelId") or "")
            source_id = str(source.get("sourceId") or source.get("id") or "")
            # Archive.org only. This avoids temporary YouTube IDs and keeps VOD direct.
            if channel_id != "archive.org" or not source_id:
                continue
            if not is_ptbr_movie(movie, source):
                continue
            candidates.append((key, movie, source_id))
            break

    # Stable deterministic order, useful for reproducible commits.
    candidates.sort(key=lambda x: (genre_for(x[1]), title_for(x[1]).lower(), x[0]))

    new_entries = []
    # Guardrail: one run resolves up to 800 candidates to keep GitHub Actions bounded.
    # Subsequent scheduled runs will preserve already-added entries and continue.
    resolved_this_run = 0
    for movie_id, movie, identifier in candidates:
        if movie_id in seen_ids:
            continue
        if resolved_this_run >= 800:
            break
        resolved_this_run += 1
        url = pick_mp4(identifier)
        if not url or url in seen_urls:
            continue

        poster = "https://archive.org/services/img/" + urllib.parse.quote(identifier, safe="")
        meta = extinf(title_for(movie), genre_for(movie), poster, movie_id)
        new_entries.append((meta, url))
        seen_urls.add(url)
        seen_ids.add(movie_id)

        # Be polite to Archive.org.
        time.sleep(0.05)

    lines = ["#EXTM3U"]
    lines += [
        "# Biblioteca VOD - filmes de acesso aberto / domínio público",
        "# Atualizada automaticamente a partir de bases públicas e do Internet Archive",
        "# Filtro: português/pt-BR indicado nos metadados da fonte",
        "",
    ]

    all_entries = existing + new_entries
    # Deduplicate while preserving order.
    dedup = []
    used = set()
    for meta, url in all_entries:
        if url in used:
            continue
        used.add(url)
        dedup.append((meta, url))

    for meta, url in dedup:
        lines.append(meta)
        lines.append(url)
        lines.append("")

    TARGET.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Filmes existentes: {len(existing)}")
    print(f"Candidatos PT-BR: {len(candidates)}")
    print(f"Novos adicionados nesta execução: {len(new_entries)}")
    print(f"Total no filmes.m3u: {len(dedup)}")

if __name__ == "__main__":
    main()
