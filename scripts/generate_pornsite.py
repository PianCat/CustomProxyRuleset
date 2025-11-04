#!/usr/bin/env python3
"""Generate PornSite/PornSite.list and publish/PornSite.list from v2fly domain-list-community data/category-porn

Behavior:
- Prefer using local community/data/ files if present (CI checks out the repo into ./community).
- Otherwise fetch raw files from GitHub raw URL.
- Recursively follow include: directives, preserve include order from main file.
- Skip comments and lines starting with 'regexp:'.
- Transform rules:
  - full:<value> -> DOMAIN,<value> (if contains '.') else DOMAIN-KEYWORD,<value>
  - plain with '.' -> DOMAIN-SUFFIX,<value>
  - plain without '.' -> DOMAIN-KEYWORD,<value>
- Deduplicate globally and group output by '# <include-name>' blocks, with '# others' for main-file own rules.
"""
from __future__ import annotations

import os
import sys
import urllib.request
import collections
from typing import Dict, Set

BASE_RAW = 'https://raw.githubusercontent.com/v2fly/domain-list-community/master/data'
START = 'category-porn'


def fetch_remote(name: str) -> str:
    url = f"{BASE_RAW}/{name}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Warning: failed to fetch {url}: {e}", file=sys.stderr)
        return ''


def read_local(base_dir: str, name: str) -> str:
    path = os.path.join(base_dir, name)
    if not os.path.isfile(path):
        return ''
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: failed to read {path}: {e}", file=sys.stderr)
        return ''


def load_all(base_dir: str | None) -> Dict[str, str]:
    """BFS collect files starting from START. If base_dir is provided and contains files, use local reads, else fetch remote."""
    queue = collections.deque([START])
    seen: Set[str] = set()
    contents: Dict[str, str] = {}

    while queue:
        name = queue.popleft()
        if name in seen:
            continue
        seen.add(name)
        if base_dir:
            txt = read_local(base_dir, name)
        else:
            txt = fetch_remote(name)
        contents[name] = txt
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith('include:'):
                inc = line.split(':', 1)[1].strip()
                # Skip ehentai includes entirely; user will include ehentai separately
                if inc and 'ehentai' not in inc.lower() and inc not in seen:
                    queue.append(inc)

    return contents


def transform(line: str) -> str | None:
    l = line.strip()
    if not l or l.startswith('#'):
        return None
    if l.startswith('include:'):
        return None
    if l.startswith('regexp:'):
        return None
    # Skip any lines referencing ehentai; user will include it separately
    if 'ehentai' in l.lower():
        return None
    if l.startswith('full:'):
        v = l.split(':', 1)[1].strip()
        if '.' in v:
            return f"DOMAIN,{v}"
        else:
            return f"DOMAIN-KEYWORD,{v}"
    # plain entry
    v = l
    if '.' in v:
        return f"DOMAIN-SUFFIX,{v}"
    return f"DOMAIN-KEYWORD,{v}"


def main() -> int:
    repo_dir = os.getcwd()
    local_data_dir = os.path.join(repo_dir, 'community', 'data')
    use_local = os.path.isdir(local_data_dir)

    if use_local:
        print(f"Using local community data at {local_data_dir}")
        contents = load_all(local_data_dir)
    else:
        print("Local community data not found; fetching remote files")
        contents = load_all(None)

    main_txt = contents.get(START, '')
    include_order = []
    for line in main_txt.splitlines():
        line = line.strip()
        if line.startswith('include:'):
            inc = line.split(':', 1)[1].strip()
            if inc:
                include_order.append(inc)

    seen_rules: Set[str] = set()
    out_lines: list[str] = []

    for inc in include_order:
        if inc not in contents:
            continue
        out_lines.append('# ' + inc)
        for line in contents[inc].splitlines():
            t = transform(line)
            if t and t not in seen_rules:
                out_lines.append(t)
                seen_rules.add(t)
        out_lines.append('')

    out_lines.append('# others')
    for line in main_txt.splitlines():
        if line.strip().startswith('include:'):
            continue
        t = transform(line)
        if t and t not in seen_rules:
            out_lines.append(t)
            seen_rules.add(t)

    # Ensure output dir exists and write the PornSite list only
    td = os.path.join(repo_dir, 'PornSite')
    os.makedirs(td, exist_ok=True)
    outpath = os.path.join(td, 'PornSite.list')
    try:
        with open(outpath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out_lines))
        print(f"Wrote {outpath} ({len(out_lines)} lines)")
    except Exception as e:
        print(f"Error writing {outpath}: {e}", file=sys.stderr)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
