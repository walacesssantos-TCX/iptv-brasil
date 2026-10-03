#!/usr/bin/env python3
import concurrent.futures
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "vendor" / "movies.json"
OUT = ROOT / "filmes1.m3u"
CACHE = ROOT / "data" / "archive_direct_cache.json"

UA = "iptv-brasil-ssiptv-builder/2.0"
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "24"))
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))

GENRE_MAP = {
    "action": "Ação",
    "adventure": "Aventura",
    "animation": "Animação",
    "biography": "Biografia",
    "comedy": "Comédia",
    "crime": "Crime",
    "documentary": "Documentários",
    "drama": "Drama",
    "family": "Família",
    "fantasy": "Fantasia",
    "film-noir": "Film Noir",
    "film noir": "Film Noir",
    "history": "História",
    "horror": "Terror",
    "music": "Musical",
    "musical": "Musical",
    "mystery": "Mistério",
    "romance": "Romance",
    "sci-fi": "Ficção Científica",
    "science fiction": "Ficção Científica",
    "sport": "Esportes",
    "thriller": "Suspense",
    "war": "Guerra",
    "western": "Faroeste",
}

BAD_FILE_HINTS = (
    "trailer", "sample", "preview", "thumb", "thumbnail",
    "spectrogram", "waveform", "clip."
)

def request_bytes(url, timeout=TIMEOUT):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "*/*",
            "Connection": "close",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def int_value(value):
    try:
        return int(value or 0)
    except Exception:
        return 0

def score_video(name, fmt, source, size):
    low = name.lower()
    fmt_low = (fmt or "").lower()
    source_low = (source or "").lower()
    score = 0
    if source_low == "original":
        score += 120
    if "h.264" in fmt_low or "h264" in fmt_low:
        score += 90
    if "mpeg4" in fmt_low or "mpeg-4" in fmt_low or "mpeg4" in low:
        score += 70
    if low.endswith(".mp4"):
        score += 60
    elif low.endswith(".m4v"):
        score += 40
    if "512kb" in low:
        score -= 15
    if "1080" in low:
        score += 25
    elif "720" in low:
        score += 18
    elif "480" in low:
        score += 10
    score += min(size // (100 * 1024 * 1024), 40)
    return score

def choose_from_files(files):
    candidates = []
    for item in files:
        name = str(item.get("name") or "")
        if not name:
            continue
        low = name.lower()
        if not low.endswith((".mp4", ".m4v")):
            continue
        if any(hint in low for hint in BAD_FILE_HINTS):
            continue
        size = int_value(item.get("size"))
        if 0 < size < 2 * 1024 * 1024:
            continue
        fmt = str(item.get("format") or "")
        source = str(item.get("source") or "")
        candidates.append((score_video(name, fmt, source, size), size, name))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]

def files_from_xml(identifier):
    qid = urllib.parse.quote(identifier, safe="")
    qxml = urllib.parse.quote(identifier + "_files.xml", safe="")
    url = f"https://archive.org/download/{qid}/{qxml}"
    raw = request_bytes(url)
    root = ET.fromstring(raw)
    files = []
    for node in root.findall("file"):
        files.append({
            "name": node.attrib.get("name", ""),
            "source": node.attrib.get("source", ""),
            "format": node.findtext("format") or "",
            "size": node.findtext("size") or "0",
        })
    return files

def files_from_metadata(identifier):
    qid = urllib.parse.quote(identifier, safe="")
    raw = request_bytes(f"https://archive.org/metadata/{qid}")
    data = json.loads(raw.decode("utf-8", "replace"))
    return data.get("files") or []

def resolve_identifier(identifier):
    for attempt in range(3):
        try:
            try:
                files = files_from_xml(identifier)
            except Exception:
                files = files_from_metadata(identifier)
            name = choose_from_files(files)
            if not name:
                return ""
            qid = urllib.parse.quote(identifier, safe="")
            qname = urllib.parse.quote(name, safe="/")
            return f"https://archive.org/download/{qid}/{qname}"
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, ET.ParseError):
            if attempt < 2:
                time.sleep(1.0 + attempt * 2.0)
    return ""

def load_cache():
    if not CACHE.exists():
        return {}
    try:
        data = json.loads(CACHE.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def save_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

def genre_for(movie):
    md = movie.get("metadata") or {}
    raw = str(md.get("Genre") or "")
    genres = [g.strip().lower() for g in raw.split(",") if g.strip()]
    for genre in genres:
        if genre in GENRE_MAP:
            return GENRE_MAP[genre]
    for genre in genres:
        for key, translated in GENRE_MAP.items():
            if key in genre:
                return translated
    return "Outros Filmes"

def title_for(movie):
    md = movie.get("metadata") or {}
    ai = movie.get("ai") or {}
    title = str(md.get("Title") or ai.get("title") or movie.get("title") or "Filme").strip()
    year = str(md.get("Year") or ai.get("year") or movie.get("year") or "").strip()
    if year and year not in title:
        title = f"{title} ({year})"
    return re.sub(r"[\r\n]+", " ", title).strip()

def parse_existing_non_archive():
    if not OUT.exists():
        return []
    entries = []
    current = None
    for raw in OUT.read_text("utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF"):
            current = line
        elif current and re.match(r"^https?://", line, re.I):
            if "archive.org/" not in line.lower():
                entries.append((current, line))
            current = None
    return entries

def extinf(movie_id, title, group, identifier):
    poster = "https://archive.org/services/img/" + urllib.parse.quote(identifier, safe="")
    safe_title = title.replace('"', "'")
    safe_group = group.replace('"', "'")
    safe_id = str(movie_id).replace('"', "'")
    return (
        f'#EXTINF:0 tvg-id="{safe_id}" group-title="{safe_group}" '
        f'type="video" tvg-logo="{poster}",{safe_title}'
    )

def main():
    if not DB.exists():
        raise SystemExit("Base Movies Deluxe não encontrada em vendor/movies.json")

    print("Carregando base Movies Deluxe...")
    with DB.open("r", encoding="utf-8") as fh:
        db = json.load(fh)

    movies = []
    archive_ids = set()
    total_records = 0

    for movie_id, movie in db.items():
        if not isinstance(movie, dict) or str(movie_id).startswith("_"):
            continue
        total_records += 1
        ids = []
        for source in movie.get("sources") or []:
            if not isinstance(source, dict):
                continue
            channel_id = str(source.get("channelId") or "")
            source_type = str(source.get("type") or "")
            identifier = str(source.get("sourceId") or source.get("id") or "").strip()
            if identifier and (channel_id == "archive.org" or source_type == "archive.org"):
                if identifier not in ids:
                    ids.append(identifier)
                    archive_ids.add(identifier)
        if ids:
            movies.append((str(movie_id), movie, ids))

    print(f"Registros no banco: {total_records}")
    print(f"Filmes com fonte Archive.org: {len(movies)}")
    print(f"Identificadores Archive.org únicos: {len(archive_ids)}")

    cache = load_cache()
    # Reuse both successful and previously checked-without-MP4 identifiers.
    missing = sorted(identifier for identifier in archive_ids if identifier not in cache)
    print(f"Já resolvidos no cache: {len(archive_ids) - len(missing)}")
    print(f"Identificadores a consultar agora: {len(missing)}")

    if missing:
        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {
                executor.submit(resolve_identifier, identifier): identifier
                for identifier in missing
            }
            for future in concurrent.futures.as_completed(future_map):
                identifier = future_map[future]
                try:
                    cache[identifier] = future.result() or ""
                except Exception:
                    cache[identifier] = ""
                completed += 1
                if completed % 250 == 0 or completed == len(missing):
                    ok = sum(1 for identifier in archive_ids if cache.get(identifier))
                    print(f"Resolução: {completed}/{len(missing)} consultados; {ok} com vídeo direto")
                    save_cache(cache)

    save_cache(cache)

    archive_entries = []
    seen_urls = set()
    seen_movies = set()

    for movie_id, movie, identifiers in movies:
        chosen_id = None
        chosen_url = None
        for identifier in identifiers:
            url = cache.get(identifier) or ""
            if url:
                chosen_id = identifier
                chosen_url = url
                break
        if not chosen_url or movie_id in seen_movies or chosen_url in seen_urls:
            continue
        seen_movies.add(movie_id)
        seen_urls.add(chosen_url)
        group = genre_for(movie)
        title = title_for(movie)
        archive_entries.append((
            group.lower(),
            title.lower(),
            extinf(movie_id, title, group, chosen_id),
            chosen_url,
        ))

    archive_entries.sort(key=lambda row: (row[0], row[1]))

    manual_entries = parse_existing_non_archive()
    manual_seen = set()
    preserved = []
    for meta, url in manual_entries:
        if url in manual_seen:
            continue
        manual_seen.add(url)
        preserved.append((meta, url))

    lines = [
        '#EXTM3U size="medium"',
        '# Biblioteca VOD - SS IPTV',
        '# Fontes de acesso aberto / domínio público: Movies Deluxe + Internet Archive',
        '# Links Archive.org resolvidos diretamente para arquivos MP4/M4V',
        f'# Registros Movies Deluxe lidos: {total_records}',
        f'# Filmes Archive.org com vídeo direto: {len(archive_entries)}',
        '',
    ]

    for meta, url in preserved:
        lines.extend([meta, url, ""])

    for _, _, meta, url in archive_entries:
        lines.extend([meta, url, ""])

    OUT.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"Entradas externas preservadas: {len(preserved)}")
    print(f"Entradas Movies Deluxe/Archive.org: {len(archive_entries)}")
    print(f"TOTAL filmes1.m3u: {len(preserved) + len(archive_entries)}")

if __name__ == "__main__":
    main()
