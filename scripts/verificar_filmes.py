"""Check movie playback without storing or printing provider credentials."""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

AGENT = 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36'


def parse_movies(text):
    entries, meta = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('#EXTINF:'):
            meta = line
        elif meta and line and not line.startswith('#'):
            comma = re.search(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', meta)
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', meta))
            if comma and line.startswith(('https://', 'http://')):
                parsed = urllib.parse.urlparse(line)
                name = meta[comma.end():].strip()
                file_id = parsed.path.rsplit('/', 1)[-1]
                key = f'movie|{name}|{file_id}'
                movie_id = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], 'big') & 0x7fffffff
                entries.append({'name': name, 'group': attrs.get('group-title') or 'Filmes',
                                'logo': attrs.get('tvg-logo', ''), 'stream_id': movie_id or 1,
                                'provider_host': parsed.hostname, 'provider_port': parsed.port,
                                'provider_movie_id': file_id, '_url': line})
            meta = None
    return entries


def inspect_movie(entry, timeout):
    out = {k: v for k, v in entry.items() if not k.startswith('_')}
    out.update(checked_at=dt.datetime.now(dt.timezone.utc).isoformat(), ok=False,
               request_attempted=True, decode_ok=False)
    start = time.monotonic()
    phase = 'request'
    url = entry['_url']
    try:
        req = urllib.request.Request(url, headers={'User-Agent': AGENT, 'Range': 'bytes=0-2097151', 'Accept': '*/*'})
        with urllib.request.urlopen(req, timeout=timeout) as res:
            out.update(http_status=res.status, content_type=res.headers.get('Content-Type', ''))
            total_match = re.search(r'/(\d+)$', res.headers.get('Content-Range', ''))
            total = int(total_match[1]) if total_match else int(res.headers.get('Content-Length', '0') or 0)
            body = res.read(2097152)
            out.update(sample_bytes=len(body), range_supported=res.status == 206)
        if len(body) < 1000 or body.lstrip().startswith((b'<!DOCTYPE', b'<html', b'{', b'#EXTM3U')):
            raise ValueError('The endpoint did not return a playable movie file')
        phase = 'probe'
        with tempfile.TemporaryDirectory(prefix='movie-check-') as folder:
            sample = pathlib.Path(folder) / 'movie.bin'
            sample.write_bytes(body)
            if b'ftyp' in body[:32] and b'moov' not in body and total > len(body):
                tail_start = max(len(body), total - 2097152)
                req = urllib.request.Request(url, headers={'User-Agent': AGENT, 'Range': f'bytes={tail_start}-{total-1}'})
                with urllib.request.urlopen(req, timeout=timeout) as res:
                    if res.status != 206:
                        raise ValueError('Movie index is at the end and byte seeking is unavailable')
                    tail = res.read(2097152)
                with sample.open('r+b') as f:
                    f.seek(tail_start)
                    f.write(tail)
                out['tail_sample_bytes'] = len(tail)
            probe = subprocess.run(['ffprobe', '-v', 'error', '-probesize', '2097152',
                                    '-analyzeduration', '2000000', '-show_entries',
                                    'format=duration,format_name:stream=codec_type,codec_name,width,height',
                                    '-of', 'json', str(sample)], capture_output=True, text=True, timeout=15)
            data = json.loads(probe.stdout or '{}')
            streams = data.get('streams', [])
            video = next((s for s in streams if s.get('codec_type') == 'video'), None)
            audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
            if probe.returncode or not video or not audio:
                raise ValueError('Could not identify video and audio')
            phase = 'decode'
            dec = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(sample),
                                  '-map', '0:v:0', '-map', '0:a:0', '-t', '1', '-f', 'null', '-'],
                                 capture_output=True, timeout=15)
            if dec.returncode:
                raise ValueError('Movie audio/video decoding failed')
            fmt = data.get('format', {})
            out.update(ok=True, decode_ok=True, video_codec=video.get('codec_name'),
                       audio_codec=audio.get('codec_name'), width=video.get('width'), height=video.get('height'),
                       duration_seconds=float(fmt.get('duration', '0') or 0), format_name=fmt.get('format_name'))
    except urllib.error.HTTPError as exc:
        out.update(http_status=exc.code, failed_phase=phase, error='HTTP request failed')
    except ValueError as exc:
        out.update(failed_phase=phase, error=str(exc))
    except Exception as exc:
        out.update(failed_phase=phase, error=type(exc).__name__)
    out['elapsed_seconds'] = round(time.monotonic() - start, 2)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--playlist', default='filmes1.m3u')
    parser.add_argument('--git-ref')
    parser.add_argument('--output', required=True)
    parser.add_argument('--catalog')
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.git_ref:
        text = subprocess.check_output(['git', 'show', f'{args.git_ref}:{args.playlist}']).decode('utf-8-sig')
    else:
        text = pathlib.Path(args.playlist).read_text(encoding='utf-8-sig')
    entries = parse_movies(text)
    if args.limit:
        entries = entries[:args.limit]
    output = pathlib.Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    results = []
    print(json.dumps({'total': len(entries), 'workers': args.workers, 'timeout_seconds': args.timeout}), flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = [pool.submit(inspect_movie, entry, args.timeout) for entry in entries]
        for future in concurrent.futures.as_completed(pending):
            results.append(future.result())
            if len(results) % 24 == 0 or len(results) == len(entries):
                output.write_text(json.dumps({'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                                  'total': len(entries), 'tested': len(results),
                                  'passed': sum(x['ok'] for x in results),
                                  'timeout_seconds': args.timeout, 'movies': results}, ensure_ascii=False, indent=2) + '\n')
                print(json.dumps({'tested': len(results), 'total': len(entries),
                                  'passed': sum(x['ok'] for x in results)}), flush=True)
    if args.catalog:
        movies = []
        for item in results:
            if not item['ok']:
                continue
            fmt = item.get('format_name', '')
            extension = 'mp4' if 'mp4' in fmt else 'mkv' if 'matroska' in fmt else 'ts' if 'mpegts' in fmt else pathlib.PurePosixPath(item['provider_movie_id']).suffix.lstrip('.')
            movies.append({k: item[k] for k in ['stream_id', 'name', 'group', 'logo', 'duration_seconds', 'video_codec', 'audio_codec', 'width', 'height']} | {'container_extension': extension, 'verified_at': item['checked_at']})
        path = pathlib.Path(args.catalog)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'verified_at': dt.datetime.now(dt.timezone.utc).isoformat(),
                                   'source_playlist': args.playlist, 'total_checked': len(results),
                                   'movies': movies}, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
