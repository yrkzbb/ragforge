import math
import re
from collections import Counter
from dataclasses import dataclass

@dataclass
class Candidate:
    id:str; text:str; breadcrumb:str=""; parent_text:str=""; source_uri:str=""; score:float=0.0; bm25_score:float=0.0; dense_score:float=0.0; rerank_score:float=0.0

def tokenize(text:str)->list[str]: return re.findall(r"[\u4e00-\u9fff]|[a-z0-9_]+",text.lower())

def bm25(query:str,documents:list[Candidate],k1:float=1.5,b:float=.75)->list[Candidate]:
    tokens=[tokenize(d.text+" "+d.breadcrumb) for d in documents];avg=sum(map(len,tokens))/max(len(tokens),1);q=tokenize(query)
    df=Counter(t for ts in tokens for t in set(ts));n=len(documents)
    for d,ts in zip(documents,tokens):
        tf=Counter(ts);score=0.0
        for term in q:
            idf=math.log(1+(n-df[term]+.5)/(df[term]+.5));freq=tf[term]
            score+=idf*(freq*(k1+1))/(freq+k1*(1-b+b*len(ts)/max(avg,1)))
        d.bm25_score=score
    return sorted(documents,key=lambda x:x.bm25_score,reverse=True)

def rrf(rankings:list[list[Candidate]],k:int=60)->list[Candidate]:
    merged:dict[str,Candidate]={};scores=Counter()
    for ranking in rankings:
        for rank,item in enumerate(ranking,1): merged[item.id]=item;scores[item.id]+=1/(k+rank)
    for key,item in merged.items(): item.score=scores[key]
    return sorted(merged.values(),key=lambda x:x.score,reverse=True)

def cosine(a:list[float],b:list[float])->float:
    dot=sum(x*y for x,y in zip(a,b));den=math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b));return dot/den if den else 0

def precision_at_k(retrieved:list[str],relevant:set[str],k:int)->float:return sum(x in relevant for x in retrieved[:k])/k
def recall_at_k(retrieved:list[str],relevant:set[str],k:int)->float:return sum(x in relevant for x in retrieved[:k])/max(len(relevant),1)
def reciprocal_rank(retrieved:list[str],relevant:set[str])->float:return next((1/i for i,x in enumerate(retrieved,1) if x in relevant),0.0)
def ndcg_at_k(retrieved:list[str],relevant:set[str],k:int)->float:
    dcg=sum((1 if x in relevant else 0)/math.log2(i+1) for i,x in enumerate(retrieved[:k],1));ideal=sum(1/math.log2(i+1) for i in range(1,min(k,len(relevant))+1));return dcg/ideal if ideal else 0
