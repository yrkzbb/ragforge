import re
from dataclasses import dataclass

@dataclass(frozen=True)
class ChunkDraft:
    level:str; ordinal:int; breadcrumb:str; text:str; parent_ordinal:int|None=None

def _tokens(text:str)->list[str]:
    return re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+",text.lower())

def parent_child_chunks(text:str,title:str,parent_size:int=700,child_size:int=220,overlap:int=40)->list[ChunkDraft]:
    """Structure-aware chunks. Headings become breadcrumbs; children point to a larger parent."""
    lines=[x.strip() for x in text.replace("\r","").split("\n")]
    sections:list[tuple[str,str]]=[]; breadcrumb=[title]; buffer=[]
    def flush():
        if buffer:
            sections.append((" › ".join(breadcrumb),"\n".join(buffer).strip()));buffer.clear()
    for line in lines:
        match=re.match(r"^(#{1,4})\s+(.+)$",line)
        if match:
            flush();depth=len(match.group(1));breadcrumb[:depth]=breadcrumb[:depth];breadcrumb[depth:]=[match.group(2)]
        elif line: buffer.append(line)
    flush()
    drafts=[]; ordinal=0
    for crumb,body in sections or [(title,text)]:
        words=_tokens(body)
        for pstart in range(0,len(words),parent_size):
            parent=" ".join(words[pstart:pstart+parent_size]);parent_ord=ordinal
            drafts.append(ChunkDraft("parent",ordinal,crumb,parent));ordinal+=1
            step=max(1,child_size-overlap)
            for start in range(0,len(_tokens(parent)),step):
                child=" ".join(_tokens(parent)[start:start+child_size])
                if child:drafts.append(ChunkDraft("child",ordinal,crumb,child,parent_ord));ordinal+=1
    return drafts

