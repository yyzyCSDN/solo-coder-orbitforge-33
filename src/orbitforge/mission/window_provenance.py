from __future__ import annotations
from dataclasses import dataclass
from orbitforge.core.state import TimeWindow

@dataclass(frozen=True)
class Derivation:
    rule: str
    constraints: tuple[str, ...] = ()
    parents: tuple[Derivation, ...] = ()

@dataclass(frozen=True)
class DerivedWindow:
    window: TimeWindow
    sources: frozenset[str]
    derivation: Derivation

def leaf(window, source):
    return DerivedWindow(window, frozenset({source}), Derivation(rule='source', constraints=(source,)))

def intersect(a, b):
    start = max(a.window.start_tai_s, b.window.start_tai_s)
    end = min(a.window.end_tai_s, b.window.end_tai_s)
    if start >= end:
        return None
    constraints = tuple(sorted(a.sources | b.sources))
    return DerivedWindow(TimeWindow(start, end), a.sources | b.sources, Derivation(rule='intersect', constraints=constraints, parents=(a.derivation, b.derivation)))

def subtract(base, blocked):
    result = []
    for w in base:
        parts = [w]
        for b in blocked:
            nxt = []
            for p in parts:
                if b.window.end_tai_s <= p.window.start_tai_s or b.window.start_tai_s >= p.window.end_tai_s:
                    nxt.append(p)
                    continue
                if b.window.start_tai_s > p.window.start_tai_s:
                    nxt.append(_subtract_piece(p, TimeWindow(p.window.start_tai_s, b.window.start_tai_s), b))
                if b.window.end_tai_s < p.window.end_tai_s:
                    nxt.append(_subtract_piece(p, TimeWindow(b.window.end_tai_s, p.window.end_tai_s), b))
            parts = nxt
        result.extend(parts)
    return result

def _subtract_piece(part, window, blocked):
    return DerivedWindow(window, part.sources, Derivation(rule='subtract', constraints=tuple(sorted(blocked.sources)), parents=(part.derivation, blocked.derivation)))

def clip(w, start_tai_s=None, end_tai_s=None, constraint=None):
    lo = w.window.start_tai_s if start_tai_s is None else max(start_tai_s, w.window.start_tai_s)
    hi = w.window.end_tai_s if end_tai_s is None else min(end_tai_s, w.window.end_tai_s)
    if lo >= hi:
        return None
    if lo == w.window.start_tai_s and hi == w.window.end_tai_s:
        return w
    constraints = []
    if constraint is not None:
        constraints.append(constraint)
    if lo > w.window.start_tai_s:
        constraints.append(f'start>={lo}')
    if hi < w.window.end_tai_s:
        constraints.append(f'end<={hi}')
    return DerivedWindow(TimeWindow(lo, hi), w.sources, Derivation(rule='clip', constraints=tuple(constraints), parents=(w.derivation,)))

def clip_all(windows, start_tai_s=None, end_tai_s=None, constraint=None):
    out = []
    for w in windows:
        clipped = clip(w, start_tai_s, end_tai_s, constraint)
        if clipped is not None:
            out.append(clipped)
    return out

def merge_touching(windows):
    ordered = sorted(windows, key=lambda x: x.window.start_tai_s)
    out = []
    for item in ordered:
        if not out or item.window.start_tai_s > out[-1].window.end_tai_s:
            out.append(item)
        else:
            previous = out[-1]
            merged = TimeWindow(previous.window.start_tai_s, max(previous.window.end_tai_s, item.window.end_tai_s))
            sources = previous.sources | item.sources
            out[-1] = DerivedWindow(merged, sources, Derivation(rule='merge', constraints=tuple(sorted(sources)), parents=(previous.derivation, item.derivation)))
    return out

def explain(w):
    ordered = []
    seen = set()
    def visit(d):
        if d in seen:
            return
        seen.add(d)
        for parent in d.parents:
            visit(parent)
        ordered.append(d)
    visit(w.derivation)
    return ordered

def trace_summary(w):
    chain = explain(w)
    return {'window': (w.window.start_tai_s, w.window.end_tai_s), 'sources': sorted(w.sources), 'rules': [d.rule for d in chain], 'constraints': sorted({c for d in chain for c in d.constraints})}

def source_usage(windows):
    counts = {}
    for item in windows:
        for source in item.sources:
            counts[source] = counts.get(source, 0) + 1
    return counts
