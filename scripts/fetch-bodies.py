#!/usr/bin/env python3
"""
fetch-bodies.py — post-processing step for the newsletter digest.
Reads newsletter-today.json, fetches full HTML bodies for any stories
missing them, and writes the file back.

Usage: python3 fetch-bodies.py
"""
import json, subprocess, base64, re, sys, os

STORIES_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'newsletter-today.json')
ACCOUNT = os.environ.get('NEWSLETTER_ACCOUNT', 'your@gmail.com')

def find_html(payload):
    mime = payload.get('mimeType', '')
    if mime == 'text/html':
        data = payload.get('body', {}).get('data', '')
        if data:
            return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')
    for part in payload.get('parts', []):
        result = find_html(part)
        if result:
            return result
    return None

def clean_html(html):
    # Remove scripts
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.IGNORECASE)
    # Remove 1x1 tracking pixels
    html = re.sub(r'<img[^>]*(width=["\']?1["\']?|height=["\']?1["\']?)[^>]*/?>',
                  '', html, flags=re.IGNORECASE)
    # Clamp oversized table widths
    html = re.sub(r'(width\s*=\s*["\']?)(\d{4,})', lambda m: m.group(1) + '100%', html)
    return html

def fetch_body(thread_id):
    try:
        r = subprocess.run(
            ['gog', 'gmail', 'show', thread_id, '--account', ACCOUNT, '--json'],
            capture_output=True, text=True, timeout=30
        )
        raw = json.loads(r.stdout)
        html = find_html(raw.get('message', {}).get('payload', {}))
        return clean_html(html) if html else None
    except Exception as e:
        print(f'  Error fetching {thread_id}: {e}', file=sys.stderr)
        return None

def main():
    if not os.path.exists(STORIES_FILE):
        print('No stories file found — run the digest first.', file=sys.stderr)
        sys.exit(1)

    with open(STORIES_FILE) as f:
        data = json.load(f)

    stories = data.get('stories', [])
    cache = {}
    updated = 0

    for story in stories:
        tid = story.get('threadId')
        if not tid:
            continue
        body = story.get('body', '')
        # Skip if body already looks like real HTML (>500 chars)
        if body and len(body) > 500:
            continue
        print(f'  Fetching body: {story.get("source", tid)}...', end=' ', flush=True)
        if tid in cache:
            story['body'] = cache[tid]
            print('(cached)')
        else:
            html = fetch_body(tid)
            if html:
                story['body'] = html
                cache[tid] = html
                print(f'✅ {len(html):,} chars')
                updated += 1
            else:
                print('⚠️  no HTML found')

    with open(STORIES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print(f'\nDone. Updated {updated} stories.')

if __name__ == '__main__':
    main()
