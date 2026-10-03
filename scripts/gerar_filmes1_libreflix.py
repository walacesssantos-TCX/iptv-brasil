#!/usr/bin/env python3
import re, html, urllib.request, urllib.parse, time
from pathlib import Path

OUT = Path("filmes1.m3u")
UA = "Mozilla/5.0 IPTV-Brasil/1.0"

def get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def exists(url, timeout=12):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400
    except Exception:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Range":"bytes=0-0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return 200 <= r.status < 400
        except Exception:
            return False

def title_from(page, slug):
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', page, re.I)
    if not m:
        m = re.search(r'<title>(.*?)</title>', page, re.I|re.S)
    title = html.unescape(m.group(1)).strip() if m else slug.replace("-"," ").title()
    title = re.sub(r'\s*\|\s*Libreflix.*$', '', title, flags=re.I)
    title = re.sub(r'\s*\(\d{4}\)\s*$', '', title)
    return title

def poster_from(page):
    for pat in [
        r'https://vdn\.libreflix\.org/(?:covers/)?media/[^"\'<> ]+\.(?:jpg|jpeg|png|webp)',
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)'
    ]:
        m = re.search(pat, page, re.I)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    return ""

def category_from(page):
    p = page.lower()
    if "animação" in p or "animacao" in p or "kids" in p:
        return "Animação e Família"
    if "sci-fi" in p or "ficção científica" in p or "ficcao cientifica" in p:
        return "Ficção Científica"
    if "terror" in p or "horror" in p:
        return "Terror"
    if "comédia" in p or "comedia" in p:
        return "Comédia"
    if "aventura" in p:
        return "Aventura"
    if "document" in p or ">docs<" in p:
        return "Documentários"
    if "drama" in p:
        return "Drama"
    if "suspense" in p or "thriller" in p:
        return "Suspense"
    return "Filmes Brasileiros"

def find_video(page, slug):
    urls = re.findall(r'https://vdn\.libreflix\.org/video/[^"\'<> ]+?\.mp4', page, re.I)
    # Prefer higher quality without needing another request.
    for u in sorted(set(urls), key=lambda x: ("1080" in x, "720" in x, "480" in x, "360" in x), reverse=True):
        if exists(u):
            return u
    base = f"https://vdn.libreflix.org/video/{slug}/{slug}"
    for q in ("1080","720","480","360","240"):
        u = f"{base}.{q}.mp4"
        if exists(u):
            return u
    return None

def main():
    explore = get("https://libreflix.org/explore/country/BR")
    slugs = []
    # Capture any direct item links and de-duplicate preserving order.
    for s in re.findall(r'href=["\']/i/([^"\'/?#]+)', explore, re.I):
        if s not in slugs:
            slugs.append(s)

    entries=[]
    for n, slug in enumerate(slugs, 1):
        try:
            page = get("https://libreflix.org/i/" + urllib.parse.quote(slug))
        except Exception:
            continue

        # Respect current availability signalled by the official site.
        if "Conteúdo Indisponível para Assistir" in page or "Conteudo Indisponivel para Assistir" in page:
            # Still allow if page itself exposes an active direct source.
            exposed = re.findall(r'https://vdn\.libreflix\.org/video/[^"\'<> ]+?\.mp4', page, re.I)
            video = next((u for u in exposed if exists(u)), None)
            if not video:
                continue
        else:
            video = find_video(page, slug)
            if not video:
                continue

        title = title_from(page, slug)
        cat = category_from(page)
        poster = poster_from(page)
        entries.append((cat, title, poster, video))
        time.sleep(0.03)

    # De-duplicate by playable URL.
    seen=set(); clean=[]
    for e in entries:
        if e[3] in seen: continue
        seen.add(e[3]); clean.append(e)

    clean.sort(key=lambda e:(e[0].lower(), e[1].lower()))

    lines = [
        '#EXTM3U size="medium"',
        '# Biblioteca VOD em português - SS IPTV',
        '# Fonte: catálogo brasileiro do LibreFlix; somente links diretos validados',
        ''
    ]
    for cat,title,poster,url in clean:
        attrs = [f'group-title="{cat}"', 'type="video"']
        if poster:
            attrs.append(f'tvg-logo="{poster}"')
        safe_title = title.replace("\n"," ").replace("\r"," ").strip()
        lines.append('#EXTINF:0 ' + ' '.join(attrs) + ',' + safe_title)
        lines.append(url)
        lines.append('')

    OUT.write_text("\n".join(lines).rstrip()+"\n", encoding="utf-8")
    print("Itens BR encontrados:", len(slugs))
    print("Filmes com vídeo direto válido:", len(clean))

if __name__ == "__main__":
    main()
