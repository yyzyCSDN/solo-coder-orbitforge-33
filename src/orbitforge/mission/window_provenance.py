from __future__ import annotations
from dataclasses import dataclass
from orbitforge.core.state import TimeWindow

@dataclass(frozen=True)
class ProvenanceStep:
    rule: str
    sources: tuple[str, ...]
    result: TimeWindow
    detail: str = ''

@dataclass(frozen=True)
class DerivedWindow:
    window: TimeWindow
    sources: frozenset[str]
    provenance: tuple[ProvenanceStep, ...] = ()

def leaf(source, window):
    step = ProvenanceStep('source', (source,), window)
    return DerivedWindow(window, frozenset({source}), (step,))

def _step(rule, sources, result, detail):
    return ProvenanceStep(rule, tuple(sorted(sources)), result, detail)

def intersect(a, b):
    start = max(a.window.start_tai_s, b.window.start_tai_s)
    end = min(a.window.end_tai_s, b.window.end_tai_s)
    if start >= end:
        return None
    sources = a.sources | b.sources
    window = TimeWindow(start, end)
    detail = f'overlap of [{a.window.start_tai_s}, {a.window.end_tai_s}] and [{b.window.start_tai_s}, {b.window.end_tai_s}]'
    return DerivedWindow(window, sources, a.provenance + b.provenance + (_step('intersect', sources, window, detail),))

def subtract(a, blocked):
    parts = [a]
    for b in blocked:
        nxt = []
        for p in parts:
            if b.window.end_tai_s <= p.window.start_tai_s or b.window.start_tai_s >= p.window.end_tai_s:
                nxt.append(p)
                continue
            sources = p.sources | b.sources
            provenance = p.provenance + b.provenance
            detail = f'excluded [{max(b.window.start_tai_s, p.window.start_tai_s)}, {min(b.window.end_tai_s, p.window.end_tai_s)}] from [{p.window.start_tai_s}, {p.window.end_tai_s}]'
            if b.window.start_tai_s > p.window.start_tai_s:
                window = TimeWindow(p.window.start_tai_s, b.window.start_tai_s)
                nxt.append(DerivedWindow(window, sources, provenance + (_step('subtract', sources, window, detail),)))
            if b.window.end_tai_s < p.window.end_tai_s:
                window = TimeWindow(b.window.end_tai_s, p.window.end_tai_s)
                nxt.append(DerivedWindow(window, sources, provenance + (_step('subtract', sources, window, detail),)))
        parts = nxt
    return parts

def clip(a, start, end, source=None):
    s = max(a.window.start_tai_s, start)
    e = min(a.window.end_tai_s, end)
    if s >= e:
        return None
    sources = a.sources | frozenset({source}) if source else a.sources
    window = TimeWindow(s, e)
    trimmed = []
    if s > a.window.start_tai_s:
        trimmed.append(f'start {a.window.start_tai_s} -> {s}')
    if e < a.window.end_tai_s:
        trimmed.append(f'end {a.window.end_tai_s} -> {e}')
    detail = '; '.join(trimmed) if trimmed else 'bounds unchanged'
    if source:
        detail += f' (bound: {source})'
    return DerivedWindow(window, sources, a.provenance + (_step('clip', sources, window, detail),))

def merge_touching(windows):
    ordered = sorted(windows, key=lambda x: x.window.start_tai_s)
    out = []
    for item in ordered:
        if not out or item.window.start_tai_s > out[-1].window.end_tai_s:
            out.append(item)
        else:
            previous = out[-1]
            sources = previous.sources | item.sources
            window = TimeWindow(previous.window.start_tai_s, max(previous.window.end_tai_s, item.window.end_tai_s))
            detail = f'absorbed adjacent [{item.window.start_tai_s}, {item.window.end_tai_s}]'
            out[-1] = DerivedWindow(window, sources, previous.provenance + item.provenance + (_step('merge', sources, window, detail),))
    return out

def source_usage(windows):
    counts = {}
    for item in windows:
        for source in item.sources:
            counts[source] = counts.get(source, 0) + 1
    return counts

def explain(window):
    lines = []
    for step in window.provenance:
        line = f"{step.rule}: [{step.result.start_tai_s}, {step.result.end_tai_s}] via {', '.join(step.sources)}"
        if step.detail:
            line += f' ({step.detail})'
        lines.append(line)
    return lines
