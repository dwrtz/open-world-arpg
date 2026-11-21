#!/usr/bin/env python3
"""Compact copies of the renders (WebP) and a stats table for the gallery page.
python3 web.py  ->  out/web/*.webp, out/web/stats.json"""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assets            # noqa: E402
import scenes            # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'out', 'renders')
DST = os.path.join(HERE, 'out', 'web')


def convert():
    os.makedirs(DST, exist_ok=True)
    for root, _, files in os.walk(SRC):
        for f in sorted(files):
            if not f.endswith('.png'):
                continue
            im = Image.open(os.path.join(root, f)).convert('RGB')
            out = os.path.join(DST, f[:-4] + '.webp')
            if f == 'slices_sheet.png':
                im.save(out, 'WEBP', lossless=True)
            else:
                im.save(out, 'WEBP', quality=90, method=6)
            print(f'{f:28s} {os.path.getsize(os.path.join(root, f)) // 1024:6d} KB -> {os.path.getsize(out) // 1024:5d} KB')


def stats():
    rows = []
    seen = set()
    for (name, params, label, *_rest) in scenes.lineup():
        if label in seen:
            continue
        seen.add(label)
        v = assets.build(name, **params)
        Z, Y, X = v.idx.shape
        layers = int(v.occ.any(axis=(1, 2)).sum())
        rows.append(dict(label=label.title(), w=int(X), d=int(Y), layers=layers, voxels=v.count(),
                         sheet_kb=round(X * Y * layers * 4 / 1024, 1)))
    with open(os.path.join(DST, 'stats.json'), 'w') as f:
        json.dump(rows, f, indent=1)
    return rows


if __name__ == '__main__':
    convert()
    for r in stats():
        print(r)
