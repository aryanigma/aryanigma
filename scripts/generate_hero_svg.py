#!/usr/bin/env python3
"""
generate_hero_svg.py — IgnisCore-style hero visual for github.com/aryanigma

Simulates a wildfire propagation sweep (Dijkstra, terrain-weighted) across a
procedurally generated grid, then resolves an A* triage corridor from base
camp to the extraction point that stays clear of the burn window. The whole
thing renders as a single self-animating SVG — CSS keyframes plus a per-cell
animation-delay stagger, no JS, no external assets.

GitHub strips <script> tags and most inline styling from README HTML, but an
SVG referenced via <img src="..."> is handled as a standalone image document,
so its own <style> block (CSS keyframes / animations) still plays. That's the
whole trick — see the README for more on this.

Run manually:
    python3 scripts/generate_hero_svg.py

Run with a fixed seed (for a reproducible preview instead of "today"):
    python3 scripts/generate_hero_svg.py --seed 42

The GitHub Actions workflow calls this daily with the UTC date as the seed,
so the terrain, the fire, and the resolved route are different every day.
"""

import argparse
import heapq
import math
import random
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------- geometry --

COLS, ROWS = 44, 16
CELL = 18
MARGIN_X = 24
MARGIN_TOP = 64
MARGIN_BOTTOM = 34

GRID_W = COLS * CELL
GRID_H = ROWS * CELL
SVG_W = GRID_W + MARGIN_X * 2
SVG_H = GRID_H + MARGIN_TOP + MARGIN_BOTTOM

# ------------------------------------------------------------------ theme --

BG = "#04060a"
GRID_LINE = "#11161d"
STEEL = ["#141a22", "#1b232d", "#232c38"]   # cost tiers 1 / 2 / 4, unburned
EMBER_MID = "#ffb020"
EMBER_END = "#7a1f0d"
ACCENT = "#5ee1ff"          # icy cyan — route + HUD accent
TEXT_DIM = "#5b6472"
TEXT_BRIGHT = "#c9d3dc"

COST_TIERS = [1, 2, 4]

FIRE_SPAN = 3.6          # seconds — full ignition sweep across the burn window
FIRE_HOLD = 0.6          # seconds — a single cell's burn-in duration
ROUTE_DELAY = FIRE_SPAN + 0.35
ROUTE_DURATION = 1.6
SAFE_PERCENTILE = 0.62   # fraction of cells (nearest the source) treated as "in the burn window"


def cell_center(c, r):
    x = MARGIN_X + c * CELL + CELL / 2
    y = MARGIN_TOP + r * CELL + CELL / 2
    return x, y


def neighbors(c, r):
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nc, nr = c + dc, r + dr
        if 0 <= nc < COLS and 0 <= nr < ROWS:
            yield nc, nr


def build_terrain(rng):
    """Cost tier per cell. Purely shapes how the fire blob spreads — heavier
    cost tiers (rock/firebreak) slow Dijkstra's arrival time, which is what
    keeps the burn window an organic shape instead of a perfect diamond."""
    grid = {}
    for r in range(ROWS):
        for c in range(COLS):
            grid[(c, r)] = rng.choices(COST_TIERS, weights=[5, 3, 2])[0]
    return grid


def dijkstra(source, cost):
    dist = {source: 0.0}
    pq = [(0.0, source)]
    while pq:
        d, node = heapq.heappop(pq)
        if d > dist.get(node, math.inf):
            continue
        for nb in neighbors(*node):
            nd = d + cost[nb]
            if nd < dist.get(nb, math.inf):
                dist[nb] = nd
                heapq.heappush(pq, (nd, nb))
    return dist


def a_star(start, goal, traverse_cost):
    """traverse_cost[cell] -> movement weight. Burn-window cells are heavily
    penalized (not blocked), so the route is guaranteed to resolve even in
    an unlucky topology — it just prefers to go around."""

    def h(node):
        return abs(node[0] - goal[0]) + abs(node[1] - goal[1])

    g = {start: 0.0}
    came_from = {}
    pq = [(h(start), start)]
    visited = set()
    while pq:
        _, node = heapq.heappop(pq)
        if node in visited:
            continue
        visited.add(node)
        if node == goal:
            break
        for nb in neighbors(*node):
            ng = g[node] + traverse_cost[nb]
            if ng < g.get(nb, math.inf):
                g[nb] = ng
                came_from[nb] = node
                heapq.heappush(pq, (ng + h(nb), nb))

    path = [goal]
    node = goal
    while node != start:
        node = came_from[node]
        path.append(node)
    path.reverse()
    return path


def build_scene(seed):
    rng = random.Random(seed)
    terrain = build_terrain(rng)

    fire_row = rng.randrange(ROWS)
    source = (1, fire_row)
    camp = (COLS - 3, ROWS - 2)
    extraction = (COLS - 2, 1)

    t_fire = dijkstra(source, terrain)
    max_t = max(t_fire.values()) or 1.0

    ordered = sorted(t_fire.items(), key=lambda kv: kv[1])
    cutoff_idx = int(len(ordered) * SAFE_PERCENTILE)
    burn_window = {cell for cell, _ in ordered[:cutoff_idx]}

    traverse_cost = {cell: (1 if cell not in burn_window else 28) for cell in t_fire}
    route = a_star(camp, extraction, traverse_cost)

    return {
        "terrain": terrain,
        "t_fire": t_fire,
        "max_t": max_t,
        "burn_window": burn_window,
        "source": source,
        "camp": camp,
        "extraction": extraction,
        "route": route,
    }


def render(scene, seed_label):
    terrain = scene["terrain"]
    t_fire = scene["t_fire"]
    max_t = scene["max_t"]
    burn_window = scene["burn_window"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_W} {SVG_H}" '
        f'width="{SVG_W}" height="{SVG_H}" role="img" '
        f'aria-label="IgnisCore sector sweep: wildfire propagation and triage routing">'
    ]

    parts.append(f"""
    <style>
      text {{ font-family: 'JetBrains Mono','SFMono-Regular',Consolas,monospace; }}
      .cursor {{ animation: blink 1.1s steps(1) infinite; }}
      @keyframes blink {{ 0%,49% {{ opacity: 1; }} 50%,100% {{ opacity: 0; }} }}
      .route {{
        stroke-dasharray: var(--len);
        stroke-dashoffset: var(--len);
        animation: draw {ROUTE_DURATION}s ease-in-out {ROUTE_DELAY}s forwards;
      }}
      @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
      .pulse {{
        animation: pulse 2.4s ease-in-out {ROUTE_DELAY + ROUTE_DURATION}s infinite;
      }}
      @keyframes pulse {{ 0%,100% {{ opacity:.55; }} 50% {{ opacity:1; }} }}""")
    for i, base in enumerate(STEEL):
        parts.append(f"""
      .fire-{i} {{ animation: ignite-{i} {FIRE_HOLD}s ease-out forwards; }}
      @keyframes ignite-{i} {{
        0% {{ fill: {base}; }}
        45% {{ fill: {EMBER_MID}; }}
        100% {{ fill: {EMBER_END}; }}
      }}""")
    parts.append("\n    </style>")

    parts.append(f'<rect x="0" y="0" width="{SVG_W}" height="{SVG_H}" fill="{BG}"/>')

    parts.append(
        f'<text x="{MARGIN_X}" y="26" fill="{TEXT_BRIGHT}" font-size="15" '
        f'font-weight="700" letter-spacing="1.5">IGNISCORE // SECTOR SWEEP</text>'
    )
    parts.append(
        f'<text x="{MARGIN_X}" y="44" fill="{TEXT_DIM}" font-size="11" letter-spacing="0.5">'
        f"dijkstra propagation &#183; a* triage corridor &#183; sector-{seed_label}"
        f'<tspan class="cursor">_</tspan></text>'
    )
    parts.append(
        f'<text x="{SVG_W - MARGIN_X}" y="26" fill="{TEXT_DIM}" font-size="11" '
        f'text-anchor="end">aryanigma / ignis-core</text>'
    )

    for (c, r), tier in terrain.items():
        x = MARGIN_X + c * CELL
        y = MARGIN_TOP + r * CELL
        tier_idx = COST_TIERS.index(tier)
        base_color = STEEL[tier_idx]
        cell = (c, r)
        if cell in burn_window:
            delay = (t_fire[cell] / max_t) * FIRE_SPAN
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL - 1.4}" height="{CELL - 1.4}" '
                f'rx="2" fill="{base_color}" class="fire-{tier_idx}" '
                f'style="animation-delay:{delay:.2f}s"/>'
            )
        else:
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{CELL - 1.4}" height="{CELL - 1.4}" '
                f'rx="2" fill="{base_color}"/>'
            )

    parts.append(
        f'<rect x="{MARGIN_X}" y="{MARGIN_TOP}" width="{GRID_W}" height="{GRID_H}" '
        f'fill="none" stroke="{GRID_LINE}" stroke-width="1"/>'
    )

    route_pts = [cell_center(c, r) for c, r in scene["route"]]
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in route_pts)
    length = sum(math.dist(route_pts[i], route_pts[i + 1]) for i in range(len(route_pts) - 1))
    parts.append(
        f'<path d="{d}" fill="none" stroke="{ACCENT}" stroke-width="2.4" '
        f'stroke-linecap="round" stroke-linejoin="round" class="route" '
        f'style="--len:{length:.1f}"/>'
    )

    def marker(cell, label, dy):
        x, y = cell_center(*cell)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{ACCENT}" class="pulse"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y + dy:.1f}" fill="{TEXT_BRIGHT}" font-size="9.5" '
            f'text-anchor="middle" letter-spacing="0.5">{label}</text>'
        )

    marker(scene["camp"], "CAMP", -10)
    marker(scene["extraction"], "EXTRACTION", -10)
    sx, sy = cell_center(*scene["source"])
    parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="{EMBER_MID}"/>')

    parts.append(
        f'<text x="{MARGIN_X}" y="{SVG_H - 12}" fill="{TEXT_DIM}" font-size="10">'
        f"regenerated daily via github actions &#183; propagation cost = terrain resistance"
        f"</text>"
    )

    parts.append("</svg>")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=str, default=None, help="fixed seed; defaults to today's UTC date")
    ap.add_argument("--out", type=str, default="assets/hero.svg")
    args = ap.parse_args()

    seed_label = args.seed or datetime.now(timezone.utc).strftime("%Y%m%d")

    scene = build_scene(seed_label)
    svg = render(scene, seed_label)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(svg, encoding="utf-8")
    print(f"wrote {out_path} (seed={seed_label})")


if __name__ == "__main__":
    main()
