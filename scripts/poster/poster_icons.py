#!/usr/bin/env python3
"""Fetches the poster's icons from Phosphor Icons (duotone, MIT) at a pinned version and renders each, in the poster's navy,
to a transparent PNG for the conference poster.

One family, one colour: the author chose Phosphor's duotone weight (a line drawing with a light fill of the same colour)
from three single-colour families shown side by side (winter-conference-2026-poster/ICON-OPTIONS-2026-11-17.png), after
rejecting thin line icons in tinted circles and multicoloured drawings. Each key names the concept the icon stands for on
the poster; the SVGs are kept with Phosphor's licence in winter-conference-2026-poster/icons/phosphor/, and the PNGs
(512 px, transparent, navy) in winter-conference-2026-poster/icons/png/ are what scripts/poster/winter_poster_2026.py places.
Rendering uses headless Google Chrome, as the paper's figures do.

Usage: python3 scripts/poster/poster_icons.py            (fetches what is missing, renders every PNG anew)
"""
import pathlib, re, shutil, subprocess, sys, tempfile, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
DIR = ROOT / 'winter-conference-2026-poster' / 'icons'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
PACKAGE = '@phosphor-icons/core@2.1.1'
URL = 'https://unpkg.com/' + PACKAGE + '/{}'
NAVY = '#13365A'

# concept on the poster: Phosphor icon name (duotone weight)
ICONS = {
    'device_phone': 'device-mobile', 'device_laptop': 'laptop', 'device_bulb': 'lightbulb',
    'data_locked': 'lock', 'server': 'cloud',
    'leaking': 'eye', 'poisoning': 'skull', 'attacker': 'skull', 'fake_members': 'mask-happy', 'free_riding': 'user-minus',
    'privacy': 'eye-slash', 'security': 'magnifying-glass', 'gap': 'target',
    'block': 'cube', 'validator': 'seal-check', 'gateway': 'wifi-high', 'open_issue': 'warning',
    'learn': 'brain', 'split': 'puzzle-piece', 'mark': 'list-checks', 'add_up': 'sigma', 'record': 'book-open',
    'measured': 'timer', 'compared': 'scales', 'run_on': 'cell-tower',
    'people': 'users-three', 'research': 'flask',
    'backdoor': 'door', 'zk_proofs': 'key', 'erasure': 'trash',
}


def svg_path(name):
    return DIR / 'phosphor' / f'{name}-duotone.svg'


def fetch():
    (DIR / 'phosphor').mkdir(parents=True, exist_ok=True)
    lic = DIR / 'phosphor' / 'LICENSE'
    if not lic.exists():
        lic.write_bytes(urllib.request.urlopen(URL.format('LICENSE')).read())
    for name in sorted(set(ICONS.values())):
        out = svg_path(name)
        if not out.exists():
            data = urllib.request.urlopen(URL.format(f'assets/duotone/{name}-duotone.svg')).read()
            if b'<svg' not in data[:400] or b'<script' in data:
                sys.exit(f'{name}: not a plain SVG')
            out.write_bytes(data)
    (DIR / 'phosphor' / 'SOURCE.txt').write_text(
        f'Phosphor Icons, duotone weight, npm package {PACKAGE} (MIT), via {URL.format("assets/duotone/")}\n\n'
        + '\n'.join(f'{key}\t{name}' for key, name in ICONS.items()) + '\n')


def render(px=512):
    out_dir = DIR / 'png'
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        for key, name in ICONS.items():
            svg = re.sub(r'<\?xml[^>]*>', '', svg_path(name).read_text())
            head, rest = svg.split('>', 1)
            head = re.sub(r'\s(width|height|fill|style)="[^"]*"', '', head)
            svg = head + f' width="{px}" height="{px}" fill="currentColor" style="color:{NAVY}">' + rest
            html = pathlib.Path(tmp) / f'{key}.html'
            html.write_text(f'<html><body style="margin:0;background:transparent">{svg}</body></html>')
            subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--default-background-color=00000000',
                            f'--window-size={px},{px}', f'--screenshot={out_dir / (key + ".png")}', html.as_uri()],
                           check=True, capture_output=True, timeout=60)
    print(f'{len(ICONS)} icons in {out_dir}')


if __name__ == '__main__':
    fetch()
    render()
