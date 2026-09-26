from orbitforge.core.state import TimeWindow
from orbitforge.mission.window_provenance import clip, explain, intersect, leaf, merge_touching, source_usage, subtract

def test_intersect_records_constraints_and_rule():
    a = leaf('station', TimeWindow(0, 10)); b = leaf('eclipse_free', TimeWindow(5, 15))
    out = intersect(a, b)
    assert out.window == TimeWindow(5, 10)
    assert out.sources == {'station', 'eclipse_free'}
    assert [s.rule for s in out.provenance] == ['source', 'source', 'intersect']
    assert out.provenance[-1].result == TimeWindow(5, 10)

def test_subtract_preserves_sources_and_chain():
    a = leaf('pass', TimeWindow(0, 10)); b = leaf('keepout', TimeWindow(3, 5))
    parts = subtract(a, [b])
    assert [p.window for p in parts] == [TimeWindow(0, 3), TimeWindow(5, 10)]
    assert all(p.sources == {'pass', 'keepout'} for p in parts)
    assert all(p.provenance[-1].rule == 'subtract' for p in parts)

def test_subtract_disjoint_keeps_original():
    a = leaf('pass', TimeWindow(0, 10)); b = leaf('keepout', TimeWindow(20, 30))
    assert subtract(a, [b]) == [a]

def test_clip_trims_edges_and_keeps_sources():
    a = leaf('pass', TimeWindow(0, 10))
    out = clip(a, 2, 8, source='ops_day')
    assert out.window == TimeWindow(2, 8)
    assert out.sources == {'pass', 'ops_day'}
    assert out.provenance[-1].rule == 'clip'
    assert clip(a, 20, 30) is None

def test_merge_keeps_all_sources_and_history():
    a = leaf('x', TimeWindow(0, 5)); b = leaf('y', TimeWindow(5, 9))
    merged = merge_touching([b, a])
    assert len(merged) == 1 and merged[0].window == TimeWindow(0, 9)
    assert merged[0].sources == {'x', 'y'}
    assert [s.rule for s in merged[0].provenance] == ['source', 'source', 'merge']

def test_explain_renders_full_chain():
    part = subtract(leaf('pass', TimeWindow(0, 10)), [leaf('keepout', TimeWindow(4, 6))])[0]
    clipped = clip(part, 1, 4)
    text = explain(clipped)
    assert [line.split(':')[0] for line in text] == ['source', 'source', 'subtract', 'clip']
    assert any('keepout' in line for line in text)
    assert source_usage([clipped]) == {'pass': 1, 'keepout': 1}
