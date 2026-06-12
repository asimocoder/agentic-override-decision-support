"""Smoke test for Researcher.extract_go_nogo — no LLM calls required."""
import sys
import types

import pytest

# Stub out heavy imports so we can import agents.py without API keys or .env
for mod in [
    "langchain_core.messages", "langchain_openai", "langchain_anthropic",
    "langgraph.graph.message", "tools",
]:
    sys.modules[mod] = types.ModuleType(mod)

sys.modules["langchain_core.messages"].AIMessage = object
sys.modules["langchain_core.messages"].HumanMessage = object
sys.modules["langchain_core.messages"].SystemMessage = object
sys.modules["langchain_openai"].ChatOpenAI = lambda **kw: None
sys.modules["langchain_anthropic"].ChatAnthropic = lambda **kw: None
sys.modules["langgraph.graph.message"].add_messages = None
sys.modules["tools"].news_search = None
sys.modules["tools"].court_search = None
sys.modules["tools"].industry_outlook = None

from agents import GoNoGo, Researcher  # noqa: E402

_researcher = Researcher.__new__(Researcher)


def _resp(content):
    m = types.SimpleNamespace()
    m.content = content
    return m


CASES = [
    ("GO — canonical",           "some text\nRECOMMENDED STANCE: GO",                         GoNoGo.GO),
    ("NOGO — canonical",         "some text\nRECOMMENDED STANCE: NOGO",                       GoNoGo.NOGO),
    ("NOGO before GO substring", "RECOMMENDED STANCE: NOGO",                                  GoNoGo.NOGO),
    ("NEEDS FURTHER RESEARCH",   "RECOMMENDED STANCE: NEEDS FURTHER RESEARCH",                GoNoGo.NEEDSMORE),
    ("NEED FURTHER RESEARCH",    "RECOMMENDED STANCE: NEED FURTHER RESEARCH",                 GoNoGo.NEEDSMORE),
    ("NEEDS MORE RESEARCH",      "RECOMMENDED STANCE: NEEDS MORE RESEARCH",                   GoNoGo.NEEDSMORE),
    ("trailing period",          "RECOMMENDED STANCE: GO.",                                   GoNoGo.GO),
    ("mixed case",               "Recommended Stance: Go",                                    GoNoGo.GO),
    ("no stance line",           "The company looks fine overall.",                           GoNoGo.NEEDSMORE),
    ("empty string",             "",                                                          GoNoGo.NEEDSMORE),
    ("non-string content (list)","__LIST__",                                                  GoNoGo.NEEDSMORE),
]


@pytest.mark.parametrize("desc,raw_content,expected", CASES, ids=[c[0] for c in CASES])
def test_extract_go_nogo(desc, raw_content, expected):
    if raw_content == "__LIST__":
        resp = _resp([{"type": "text", "text": "RECOMMENDED STANCE: GO"}])
    else:
        resp = _resp(raw_content)
    assert _researcher.extract_go_nogo(resp) == expected
