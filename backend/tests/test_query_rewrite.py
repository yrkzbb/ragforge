from app.services.llm import LLMService


def test_query_normalization_expands_enterprise_aliases_and_preserves_identifier():
    assert LLMService.normalize_query("办理HR一号事项") == "办理人力资源01号事项"
    assert LLMService.normalize_query("数据防护十号流程") == "信息安全10号流程"
