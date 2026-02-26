#!/usr/bin/env python3
"""
pre-fetch.py — Fetch newsletters from Gmail and produce a compact JSON
that Haiku can read without context overflow.

Writes newsletter-inbox.json with just the fields needed for summarisation:
  threadId, messageId, source, subject, snippet, date

Usage: python3 pre-fetch.py
"""
import json, subprocess, sys, os, re

INBOX_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'newsletter-inbox.json')
ACCOUNT = os.environ.get('NEWSLETTER_ACCOUNT', 'your@gmail.com')

# Subject/sender substrings that mark an email as transactional (case-insensitive)
SKIP_SUBJECT_PATTERNS = [
    'your invoice', 'your receipt', 'your order',
    'payment confirmation', 'domain renewal', 'verify your email',
    'password reset', 'has been charged', 'has shipped',
    'subscription confirmed', 'unsubscribe confirmation',
    '[action needed]', 'action required',
    'account activity statement',
    "you've got new correspondence",
    'we sent your payout',
    "we've found you",        # Rightmove / Zoopla property alerts
    'new property alert',
    'property in ',           # "X properties in Town"
    'properties in ',
    'pre-order ',
    'simpler pricing',
    'data writes',
    'api access is turned off',
    'your claude api',
    'members info',           # venue/studio admin emails
    '72-hour reminder',
    'seiko',                  # eBay search alert for specific item
    '1 new!',                 # eBay search alert
    'suggested properties',   # property agent alerts
    'book now!',              # event/venue marketing
    'identity document expires',
    'document renewal',
    'renewal reminder',
    'account alert',
    'withdrawal privileges',
    'you have a new message from linkedin',
    'linkedin notification',
]

# Sender names/domains that are always transactional
SKIP_SENDERS = [
    'ebay', 'rightmove', 'zoopla', 'trading 212', 'tsb',
    'barclays', 'hsbc', 'natwest', 'lloyds',
    'amazon', 'paypal', 'stripe',
    'kucoin', 'locrating',
]

def is_transactional(subject, sender):
    subj = subject.lower()
    send = sender.lower()
    if any(p in subj for p in SKIP_SUBJECT_PATTERNS):
        return True
    if any(p in send for p in SKIP_SENDERS):
        return True
    return False

def get_sender_name(from_header):
    """Extract just the name from 'Name <email@example.com>'"""
    m = re.match(r'^"?([^"<]+)"?\s*(?:<[^>]+>)?$', from_header.strip())
    if m:
        name = m.group(1).strip().strip('"')
        return name if name else from_header
    return from_header

def main():
    print('Fetching newsletter list...', flush=True)
    try:
        r = subprocess.run(
            ['gog', 'gmail', 'search',
             'category:updates OR category:promotions newer_than:1d',
             '--account', ACCOUNT, '--max', '30', '--json'],
            capture_output=True, text=True, timeout=60
        )
        results = json.loads(r.stdout)
    except Exception as e:
        print(f'Error fetching email list: {e}', file=sys.stderr)
        sys.exit(1)

    threads = results if isinstance(results, list) else results.get('threads', results.get('messages', []))
    print(f'Found {len(threads)} emails. Filtering...', flush=True)

    newsletters = []
    seen_threads = set()

    for item in threads:
        tid = item.get('threadId') or item.get('id')
        if not tid or tid in seen_threads:
            continue
        seen_threads.add(tid)

        try:
            r2 = subprocess.run(
                ['gog', 'gmail', 'show', tid, '--account', ACCOUNT, '--json'],
                capture_output=True, text=True, timeout=30
            )
            raw = json.loads(r2.stdout)
        except Exception as e:
            print(f'  Skip {tid}: {e}', file=sys.stderr)
            continue

        msg = raw.get('message', raw)
        headers_list = msg.get('payload', {}).get('headers', [])
        headers = {h['name'].lower(): h['value'] for h in headers_list}

        subject = headers.get('subject', '(no subject)')
        from_raw = headers.get('from', '')
        source = get_sender_name(from_raw)
        date = headers.get('date', '')
        snippet = msg.get('snippet', '')

        if is_transactional(subject, source):
            print(f'  SKIP (transactional): {source} — {subject[:50]}')
            continue

        newsletters.append({
            'threadId': tid,
            'messageId': msg.get('id', tid),
            'source': source,
            'subject': subject,
            'snippet': snippet[:400],  # cap at 400 chars
            'date': date,
        })
        print(f'  KEEP: {source} — {subject[:60]}')

    output = {'count': len(newsletters), 'newsletters': newsletters}
    with open(INBOX_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f'\nDone. {len(newsletters)} newsletters written to newsletter-inbox.json')

if __name__ == '__main__':
    main()
