from orbitforge.core.state import TimeWindow
from orbitforge.mission.window_provenance import (
    leaf, intersect, subtract, clip, clip_all, merge_touching,
    explain, trace_summary, source_usage,
)

def _chain(w):
    return [d.rule for d in explain(w)]

def test_intersect_records_rule_constraints_and_parents():
    a = leaf(TimeWindow(0, 10), 'visibility')
    b = leaf(TimeWindow(5, 15), 'eclipse-free')
    out = intersect(a, b)
    assert out.window == TimeWindow(5, 10)
    assert out.sources == {'visibility', 'eclipse-free'}
    assert out.derivation.rule == 'intersect'
    assert out.derivation.constraints == ('eclipse-free', 'visibility')
    assert _chain(out) == ['source', 'source', 'intersect']

def test_intersect_empty_returns_none():
    assert intersect(leaf(TimeWindow(0, 1), 'a'), leaf(TimeWindow(2, 3), 'b')) is None

def test_subtract_keeps_sources_and_records_blocker():
    base = [leaf(TimeWindow(0, 10), 'visibility')]
    blocked = [leaf(TimeWindow(4, 6), 'radiation')]
    out = subtract(base, blocked)
    assert [p.window for p in out] == [TimeWindow(0, 4), TimeWindow(6, 10)]
    for p in out:
        assert p.sources == {'visibility'}
        step = p.derivation
        assert step.rule == 'subtract'
        assert step.constraints == ('radiation',)
        assert _chain(p) == ['source', 'source', 'subtract']

def test_subtract_disjoint_passes_through_unchanged():
    base = [leaf(TimeWindow(0, 10), 'visibility')]
    out = subtract(base, [leaf(TimeWindow(20, 30), 'radiation')])
    assert out == base

def test_clip_trims_edges_and_keeps_sources():
    w = leaf(TimeWindow(0, 100), 'visibility')
    out = clip(w, 10, 90, constraint='planning-horizon')
    assert out.window == TimeWindow(10, 90)
    assert out.sources == {'visibility'}
    assert out.derivation.rule == 'clip'
    assert out.derivation.constraints == ('planning-horizon', 'start>=10', 'end<=90')
    assert _chain(out) == ['source', 'clip']

def test_clip_noop_returns_same_window():
    w = leaf(TimeWindow(10, 90), 'visibility')
    assert clip(w, 0, 100) is w

def test_clip_outside_returns_none():
    assert clip(leaf(TimeWindow(0, 10), 'v'), 20, 30) is None
    assert clip_all([leaf(TimeWindow(0, 10), 'v'), leaf(TimeWindow(20, 30), 'v')], 5, 25)[0].window == TimeWindow(5, 10)

def test_merge_touching_preserves_sources_and_chains():
    a = leaf(TimeWindow(0, 10), 'visibility')
    b = leaf(TimeWindow(10, 20), 'uplink')
    out = merge_touching([b, a])
    assert len(out) == 1 and out[0].window == TimeWindow(0, 20)
    assert out[0].sources == {'visibility', 'uplink'}
    assert out[0].derivation.rule == 'merge'
    assert set(out[0].derivation.constraints) == {'visibility', 'uplink'}
    assert _chain(out[0]) == ['source', 'source', 'merge']

def test_merge_touching_keeps_disjoint_apart():
    out = merge_touching([leaf(TimeWindow(0, 5), 'a'), leaf(TimeWindow(6, 9), 'b')])
    assert [w.window for w in out] == [TimeWindow(0, 5), TimeWindow(6, 9)]

def test_full_pipeline_is_traceable():
    vis = leaf(TimeWindow(0, 100), 'visibility')
    dark = leaf(TimeWindow(20, 80), 'eclipse-free')
    feasible = intersect(vis, dark)
    cut = subtract([feasible], [leaf(TimeWindow(50, 60), 'radiation')])
    trimmed = clip_all(cut, 25, 75, constraint='planning-horizon')
    assert [w.window for w in trimmed] == [TimeWindow(25, 50), TimeWindow(60, 75)]
    merged = merge_touching(trimmed + [leaf(TimeWindow(75, 120), 'visibility')])
    assert [w.window for w in merged] == [TimeWindow(25, 50), TimeWindow(60, 120)]
    summary = trace_summary(merged[-1])
    assert summary['sources'] == ['eclipse-free', 'visibility']
    assert 'intersect' in summary['rules'] and 'subtract' in summary['rules']
    assert 'clip' in summary['rules'] and 'merge' in summary['rules']
    assert 'radiation' in summary['constraints']
    assert 'planning-horizon' in summary['constraints']
    assert source_usage(merged) == {'eclipse-free': 2, 'visibility': 2}
