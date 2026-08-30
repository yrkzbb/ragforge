from app.services.retrieval import Candidate,bm25,ndcg_at_k,precision_at_k,recall_at_k,reciprocal_rank,rrf

def test_bm25_and_rrf_rank_relevant_first():
    docs=[Candidate("a","企业版 支持 SAML 单点登录"),Candidate("b","个人版 账号密码"),Candidate("c","部署 数据库")]
    lexical=bm25("企业版 SAML",docs)
    assert lexical[0].id=="a"
    assert rrf([lexical,[docs[1],docs[0]]])[0].id in {"a","b"}

def test_weighted_rrf_can_prefer_the_trusted_ranking():
    a,b=Candidate("a","a"),Candidate("b","b")
    assert rrf([[a,b],[b,a]],weights=[0.75,0.25])[0].id=="a"

def test_ir_metrics():
    got=["a","x","b","y"];relevant={"a","b"}
    assert recall_at_k(got,relevant,4)==1
    assert precision_at_k(got,relevant,4)==.5
    assert reciprocal_rank(got,relevant)==1
    assert 0<ndcg_at_k(got,relevant,4)<=1

def test_source_level_deduplication_keeps_metrics_bounded():
    got=list(dict.fromkeys(["doc-a","doc-a","doc-b"]));relevant={"doc-a"}
    assert recall_at_k(got,relevant,10)==1
    assert 0<=ndcg_at_k(got,relevant,10)<=1
