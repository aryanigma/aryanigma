#!/usr/bin/env python3
import argparse
from pathlib import Path

# This script creates the character-by-character typing effect (Creator 2 style)
# You can replace this ASCII array with your own generated 2D pixel art or portrait converted to ASCII
ASCII_ART = [
    "      :::   :::   :::   :::   ::::::::  ",
    "    :+:+: :+:+:  :+:   :+:  :+:    :+: ",
    "  +:+ +:+:+ +:+  +:+ +:+   +:+         ",
    " +#+  +:+  +#+   +#++:     +#++:++#++  ",
    "+#+       +#+    +#+             +#+   ",
    "#+#       #+#    #+#      #+#    #+#   ",
    "###       ###    ###       ########    ",
    "                                       ",
    " > SYSTEM.BOOT(aryanalikhan)           ",
    " > KERNEL LOADED                       ",
    " > INITIALIZING CHRONO RIFT ENGINE...  ",
    " > CONNECTION ESTABLISHED              "
]

def generate_typing_svg(out_path):
    svg_w, svg_h = 600, 300
    lines = len(ASCII_ART)
    
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}">',
        '''<style>
            .terminal { font-family: 'Fira Code', monospace; font-size: 14px; fill: #5ee1ff; }
            .line { white-space: pre; overflow: hidden; border-right: 2px solid #5ee1ff; animation: typing 2s steps(40, end) forwards, blink 0.75s step-end infinite; opacity: 0; }
            @keyframes typing { from { width: 0; opacity: 1; } to { width: 100%; opacity: 1; } }
            @keyframes blink { from, to { border-color: transparent; } 50% { border-color: #5ee1ff; } }
        </style>''',
        f'<rect width="100%" height="100%" fill="#0d1117" rx="10"/>'
    ]
    
    y_offset = 40
    delay = 0.0
    for line in ASCII_ART:
        # Each line types out one after another, creating that Creator 2 cinematic effect
        parts.append(
            f'<g transform="translate(20, {y_offset})">'
            f'<text class="terminal line" style="animation-delay: {delay}s; width: 0;">{line}</text>'
            f'</g>'
        )
        y_offset += 20
        delay += 0.4 

    parts.append("</svg>")
    
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Generated typing SVG at {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=str, default="assets/hero.svg")
    args = parser.parse_args()
    generate_typing_svg(args.out)
