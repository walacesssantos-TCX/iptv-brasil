#!/usr/bin/env python3
import concurrent.futures
import difflib
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
CURATED = ROOT / "data" / "filmes_recentes_oficiais.json"

UA = "iptv-brasil-ssiptv-builder/2.0"
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "24"))
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "20"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "750"))
RETRY_AFTER = int(os.getenv("RETRY_AFTER", "21600"))
MIN_RELEASE_YEAR = int(os.getenv("MIN_RELEASE_YEAR", "2000"))
if min(MAX_WORKERS, TIMEOUT, BATCH_SIZE, RETRY_AFTER) < 1:
    raise ValueError("MAX_WORKERS, HTTP_TIMEOUT, BATCH_SIZE e RETRY_AFTER devem ser positivos")

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
    # Archive's H.264 derivatives are more suitable for TVs than unknown originals.
    if source_low == "derivative":
        score += 30
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
    if "stereo" in low:
        score += 20
    if "surround" in low:
        score -= 20
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
        if item.get("private") in (True, "true", "1", 1):
            continue
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

def license_evidence(metadata):
    """Require an explicit public-domain or CC license in the item metadata."""
    raw = metadata.get("licenseurl") or []
    values = raw if isinstance(raw, list) else [raw]
    for value in values:
        url = str(value).strip()
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.hostname not in ("creativecommons.org", "www.creativecommons.org"):
            continue
        path = parsed.path.lower().rstrip("/")
        if (path in ("/licenses/publicdomain", "/publicdomain/zero/1.0",
                     "/publicdomain/mark/1.0") or
                re.fullmatch(r"/licenses/(by|by-sa|by-nd|by-nc|by-nc-sa|by-nc-nd)/[1-4]\.0(?:/[^/]+)?", path)):
            return url
    return ""

def extract_year(value):
    match = re.search(r"\b(?:18|19|20)\d{2}\b", str(value or ""))
    return int(match.group()) if match else 0

def release_year(movie):
    metadata = movie.get("metadata") or {}
    return extract_year(metadata.get("Year") or (movie.get("ai") or {}).get("year") or movie.get("year"))

def matching_title(movie, actual_title):
    expected = str((movie.get("metadata") or {}).get("Title") or movie.get("title") or "")
    def normalized(title):
        title = re.sub(r"\s*[-:]?\s*blender\s+open\s+movie.*$", "", title, flags=re.I)
        title = re.sub(r"\b(?:18|19|20)\d{2}\b", "", title.casefold())
        title = re.sub(r"\b(?:the|movie|film|colorized|version)\b", "", title)
        return re.sub(r"[^\w]+", "", title)
    left, right = normalized(expected), normalized(str(actual_title or ""))
    return bool(left and right and difflib.SequenceMatcher(None, left, right).ratio() >= 0.75)

def validate_video_url(url):
    # Read a small prefix only, even when a server ignores the Range header.
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Range": "bytes=0-4095", "Accept": "video/*",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        prefix = response.read(4096)
        if response.status not in (200, 206):
            return False
        # MP4/M4V use the ISO base media container (ftyp box).
        return len(prefix) >= 12 and prefix[4:8] == b"ftyp"

def resolve_identifier(identifier):
    result = {"status": "retry", "url": "", "checked_at": int(time.time())}
    try:
        qid = urllib.parse.quote(identifier, safe="")
        data = json.loads(request_bytes(f"https://archive.org/metadata/{qid}"))
        metadata = data.get("metadata") or {}
        if not metadata:
            return dict(result, error="Item sem metadados")
        result["item_title"] = str(metadata.get("title") or "")
        if re.search(r"\b(?:trailer|teaser|preview|review|analysis|clip|behind.the.scenes)\b", result["item_title"], re.I):
            return dict(result, status="not_movie")
        if metadata.get("is_dark") or metadata.get("access-restricted-item") in (True, "true", "1"):
            return dict(result, status="restricted")
        evidence = license_evidence(metadata)
        if not evidence:
            return dict(result, status="unlicensed")
        # A third-party Public Domain Mark alone does not establish release
        # permission for a modern film. Require a CC license or CC0 instead.
        if "/publicdomain/mark/" in evidence or "/licenses/publicdomain" in evidence:
            return dict(result, status="unlicensed")
        result["licenseurl"] = evidence
        result["creator"] = metadata.get("creator") or ""
        # Cross-check against the actual item, never its upload timestamp.
        years = [extract_year(metadata.get(key)) for key in ("year", "date")]
        years = [year for year in years if year]
        result["release_year"] = min(years) if years else 0
        if result["release_year"] < MIN_RELEASE_YEAR:
            return dict(result, status="old_or_undated")
        files = list(data.get("files") or [])
        for _ in range(3):
            name = choose_from_files(files)
            if not name:
                return dict(result, status="no_video" if _ == 0 else "retry")
            url = f"https://archive.org/download/{qid}/{urllib.parse.quote(name, safe='/')}"
            if validate_video_url(url):
                return dict(result, status="ok", url=url)
            files = [item for item in files if item.get("name") != name]
        return dict(result, error="Nenhum candidato respondeu como MP4/M4V")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError,
            ValueError, ET.ParseError) as exc:
        # Transport failures must not become permanent negative cache hits.
        return dict(result, error=str(exc)[:200])

def cache_url(entry):
    if (isinstance(entry, dict) and entry.get("status") == "ok" and
            int_value(entry.get("release_year")) >= MIN_RELEASE_YEAR):
        return entry.get("url") or ""
    return ""

def needs_resolution(entry, now):
    # Old string-only cache records have no license or availability evidence.
    if not isinstance(entry, dict):
        return True
    if entry.get("status") == "ok" and (not entry.get("release_year") or not entry.get("item_title")):
        return True
    if entry.get("status") == "retry":
        return now - int_value(entry.get("checked_at")) >= RETRY_AFTER
    return entry.get("status") not in ("ok", "no_video", "unlicensed", "restricted", "old_or_undated", "not_movie")

def load_cache():
    if not CACHE.exists():
        return {}
    try:
        data = json.loads(CACHE.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as exc:
        raise RuntimeError("Cache inválido; abortando para preservar a playlist") from exc

def save_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CACHE.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(cache, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(CACHE)

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

def curated_entries():
    if not CURATED.exists():
        return []
    entries = []
    catalog = json.loads(CURATED.read_text("utf-8"))
    for movie in sorted(catalog, key=lambda item: (-int_value(item.get("year")), item.get("title", ""))):
        if int_value(movie.get("year")) < MIN_RELEASE_YEAR:
            continue
        url = movie["url"]
        if not re.match(r"^https://[^\s]+\.(?:mp4|m4v)$", url, re.I):
            raise ValueError("Fonte oficial deve usar URL direta MP4/M4V")
        title = re.sub(r"[\r\n]+", " ", movie["title"])
        group = str(movie.get("group") or "Filmes Independentes").replace('"', "'")
        meta = f'#EXTINF:0 type="video" group-title="{group}",{title} ({movie["year"]})'
        credit = re.sub(r"[\r\n]+", " ", str(movie.get("creator") or ""))
        source = str(movie.get("source_page") or "")
        license_url = str(movie.get("licenseurl") or movie.get("rights_basis") or "")
        entries.append((f'# Fonte: {source}; Licença: {license_url}; Autor: {credit}\n{meta}', url))
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
        if release_year(movie) < MIN_RELEASE_YEAR:
            continue
        ids = []
        for source in movie.get("sources") or []:
            if not isinstance(source, dict):
                continue
            channel_id = str(source.get("channelId") or "")
            source_type = str(source.get("type") or "")
            identifier = str(source.get("sourceId") or source.get("id") or "").strip()
            # Prevent same-name remakes from being matched to old Archive items.
            source_year = extract_year(source.get("title") or identifier)
            if source_year and source_year < MIN_RELEASE_YEAR:
                continue
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
    now = int(time.time())
    newest_year = {}
    for _, movie, ids in movies:
        for identifier in ids:
            newest_year[identifier] = max(newest_year.get(identifier, 0), release_year(movie))
    missing_all = sorted(
        (identifier for identifier in archive_ids if needs_resolution(cache.get(identifier), now)),
        key=lambda identifier: (identifier in cache, -newest_year[identifier], identifier),
    )
    missing = missing_all[:BATCH_SIZE]
    print(f"Já resolvidos no cache: {len(archive_ids) - len(missing_all)}")
    print(f"Pendentes totais: {len(missing_all)}")
    print(f"Identificadores neste lote: {len(missing)}")

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
                    cache[identifier] = future.result()
                except Exception as exc:
                    cache[identifier] = {"status": "retry", "url": "", "checked_at": int(time.time()), "error": str(exc)[:200]}
                completed += 1
                if completed % 50 == 0 or completed == len(missing):
                    ok = sum(1 for identifier in archive_ids if cache_url(cache.get(identifier)))
                    print(f"Resolução: {completed}/{len(missing)} consultados; {ok} com vídeo direto")
                    save_cache(cache)

    save_cache(cache)

    archive_entries = []
    seen_urls = set()
    seen_movies = set()
    curated_movie_keys = set()
    if CURATED.exists():
        curated_movie_keys = {
            (str(item.get("title") or "").casefold(), int_value(item.get("year")))
            for item in json.loads(CURATED.read_text("utf-8"))
        }

    for movie_id, movie, identifiers in movies:
        raw_title = str((movie.get("metadata") or {}).get("Title") or movie.get("title") or "")
        if (raw_title.casefold(), release_year(movie)) in curated_movie_keys:
            continue
        chosen_id = None
        chosen_url = None
        for identifier in identifiers:
            url = cache_url(cache.get(identifier))
            if url and not matching_title(movie, cache[identifier].get("item_title")):
                continue
            if url and int_value(cache[identifier].get("release_year")) != release_year(movie):
                # Conflicting release years indicate an unreliable title match.
                continue
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
            cache[chosen_id],
        ))

    archive_entries.sort(key=lambda row: (row[0], row[1]))

    manual_entries = curated_entries()
    manual_seen = set()
    preserved = []
    for meta, url in manual_entries:
        if url in manual_seen:
            continue
        manual_seen.add(url)
        preserved.append((meta, url))
    archive_entries = [row for row in archive_entries if row[3] not in manual_seen]

    lines = [
        '#EXTM3U size="medium"',
        '# Biblioteca VOD - SS IPTV',
        f'# Apenas filmes de {MIN_RELEASE_YEAR} em diante; fontes oficiais e licenciadas',
        '# Archive.org: licença CC/domínio público declarada nos metadados do item',
        '# URLs MP4/M4V verificadas por leitura parcial; reprodução depende da TV',
        f'# Registros Movies Deluxe lidos: {total_records}',
        f'# Filmes Archive.org com vídeo direto: {len(archive_entries)}',
        '',
    ]

    for meta, url in preserved:
        lines.extend([meta, url, ""])

    for _, _, meta, url, evidence in archive_entries:
        creator = re.sub(r"[\r\n]+", " ", str(evidence.get("creator") or ""))
        lines.extend([f'# Licença: {evidence["licenseurl"]}; Autor: {creator}', meta, url, ""])

    temporary = OUT.with_suffix(".tmp")
    temporary.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    temporary.replace(OUT)

    print(f"Entradas externas preservadas: {len(preserved)}")
    print(f"Entradas Movies Deluxe/Archive.org: {len(archive_entries)}")
    print(f"TOTAL filmes1.m3u: {len(preserved) + len(archive_entries)}")

if __name__ == "__main__":
    main()
