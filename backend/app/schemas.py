from uuid import UUID
from typing import Literal
from pydantic import BaseModel, Field

RetrievalMode = Literal["bm25", "bm25_rewrite", "dense", "hybrid_raw", "hybrid", "full"]

class KnowledgeBaseCreate(BaseModel): name:str=Field(min_length=1,max_length=200)
class DocumentIngest(BaseModel): source_uri:str; title:str; text:str; metadata:dict={}
class SearchRequest(BaseModel): query:str=Field(min_length=1); knowledge_base_id:UUID; top_k:int=Field(10,ge=1,le=50); retrieve_k:int=Field(30,ge=5,le=100); mode:RetrievalMode="bm25_rewrite"
class FeedbackCreate(BaseModel): user_id:str; knowledge_base_id:UUID|None=None; correction:str; reason:str; scope:str; confidence:float=Field(.8,ge=0,le=1); source_trace_id:str|None=Field(None,max_length=64)
class FeedbackReview(BaseModel): accepted:bool
class ChatRequest(BaseModel): user_id:str; knowledge_base_id:UUID; message:str; conversation_id:str|None=None
class EvalExample(BaseModel): query:str; relevant_chunk_ids:list[str]=[]; relevant_source_uris:list[str]=[]
class EvalRequest(BaseModel): knowledge_base_id:UUID; dataset_name:str; examples:list[EvalExample]; k:int=Field(10,ge=1,le=50); retrieve_k:int=Field(30,ge=5,le=100); mode:RetrievalMode="bm25_rewrite"
