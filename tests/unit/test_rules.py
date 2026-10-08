"""
[tests/unit/test_rules.py]
규칙 엔진 단위 테스트.
"""
from cosmetic_agent.domain.rules import RuleEngine


def test_rule_engine_initialization():
    engine = RuleEngine()
    assert isinstance(engine.banned_terms, list)
