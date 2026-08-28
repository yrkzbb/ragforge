from app.services.memory import _lexical_relevance


class Item:
    scope = "密码重置"
    reason = "旧流程已废止"
    correction = "必须通过安全服务台提交"


def test_feedback_memory_lexical_scope_filter():
    assert _lexical_relevance("密码怎么重置", Item()) > _lexical_relevance("采购发票怎么报销", Item())
