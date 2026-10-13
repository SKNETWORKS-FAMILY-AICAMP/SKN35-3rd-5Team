import json

from cosmetic_agent.domain.rules import RuleEngine


def test_configured_patterns_match_and_unrelated_text_does_not():
    engine = RuleEngine()
    assert engine.check_banned_terms("피부   재생", "일반")[0] == 2
    assert engine.check_banned_terms("부드러운 사용감", "일반") == (0, [])
    assert engine.get_ladder_ceiling("보습")["claim"] == "보습"
    assert engine.get_ladder_ceiling("unknown") == {}


def test_scope_filters_rules(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps([{"pattern": "fixture", "scope": "일반", "level": 2}]), encoding="utf-8")
    engine = RuleEngine(banned_terms_path=path)
    assert engine.check_banned_terms("fixture", "기능성") == (0, [])
    assert engine.check_banned_terms("fixture", "일반")[0] == 2
