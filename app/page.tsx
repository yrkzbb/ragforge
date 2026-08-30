"use client";import{useCallback,useEffect,useRef,useState}from"react";import ReactMarkdown from"react-markdown";import remarkGfm from"remark-gfm";import{configuredKnowledgeBaseId,ragforgeApi}from"./ragforge-api";const nav=[["\u6982\u89C8","\u2302"],["\u77E5\u8BC6\u5E93","\u25B1"],["\u68C0\u7D22\u6D4B\u8BD5","\u2315"],["\u8BC4\u6D4B","\u25C7"],["\u94FE\u8DEF\u8FFD\u8E2A","\u2197"],["\u53CD\u9988\u8BB0\u5FC6","\u25CC"]];let activeChatId="1";const state=x=>x==="succeeded"?"\u5C31\u7EEA":x==="failed"?"\u5931\u8D25":x==="queued"?"\u6392\u961F\u4E2D":x?"\u7F16\u8BD1\u4E2D":"\u672A\u6784\u5EFA",label=x=>x==="pending"?"\u5F85\u5BA1\u6838":x==="accepted"?"\u5DF2\u91C7\u7EB3":"\u5DF2\u62D2\u7EDD";function Dot({off=!1}){return<span className={off?"status-dot offline":"status-dot"}/>}function Head({eye,title,sub,action}){return<header>
      <div>
        <p className="eyebrow">{eye}</p>
        <h1>{title}</h1>
        <p className="muted">{sub}</p>
      </div>
      {action}
    </header>}function EnhancedTraceTimeline({traceId}){const[allData,setAllData]=useState([]),[open,setOpen]=useState({}),[selected,setSelected]=useState(null),[err,setErr]=useState(""),business=t=>(t.spans||[]).some(s=>/agent\.|query_rewrite|retrieval|rerank|rrf_fusion|tool\.call|cross_encoder|\/api\/v1\/(chat|search)/.test(s.operationName||"")),load=useCallback(()=>ragforgeApi.traces(traceId).then(x=>{const rows=x.data||[],visible=traceId?rows:rows.filter(business);setAllData(rows),setOpen(visible[0]?{[visible[0].traceID]:!0}:{}),setErr("")}).catch(e=>{setAllData([]),setErr(String(e))}),[traceId]);useEffect(()=>{load()},[load]);const traces=traceId?allData:allData.filter(business),palette=(name,i)=>name.includes("http")?"#5686a8":name.includes("memory")?"#d866a4":name.includes("handoff")?"#9569d7":name.includes("retrieval")||name.includes("search")||name.includes("rewrite")?"#3bb4bf":name.includes("reason")?"#da9f22":["#579ee7","#43ba62","#9b70df","#da9f22","#eb5b55","#d866a4"][i%6];return<div className="trace-page enhanced">
      <div className="trace-top">
        <div>
          <span>OPENTELEMETRY / BUSINESS TRACES</span>
          <h1>Span 嵌套时间线</h1>
          <p>{traces.length} 条业务 Trace · 系统探针已隐藏</p>
        </div>
        <button onClick={load}>↻ 刷新</button>
      </div>
      {err&&<div className="trace-error">{err}</div>}
      <div className="trace-board">
        {traces.map(trace=>{const spans=trace.spans||[],start=Math.min(...spans.map(s=>s.startTime)),end=Math.max(...spans.map(s=>s.startTime+s.duration)),total=Math.max(end-start,1),ids=new Map(spans.map(s=>[s.spanID,s])),depth=s=>{let d=0,p=s.references?.find(r=>r.refType==="CHILD_OF")?.spanID;for(;p&&ids.has(p)&&d<6;)d++,p=ids.get(p)?.references?.find(r=>r.refType==="CHILD_OF")?.spanID;return d},root=spans.find(s=>depth(s)===0)||spans[0],failed=spans.some(s=>s.tags?.some(t=>t.key==="error"&&t.value===!0||t.key==="otel.status_code"&&String(t.value).toUpperCase()==="ERROR"));return<section className="trace-group"key={trace.traceID}>
              <button className="trace-summary"onClick={()=>setOpen(x=>({...x,[trace.traceID]:!x[trace.traceID]}))}>
                <span>{open[trace.traceID]?"\u25BE":"\u25B8"}</span>
                <b>trace-{trace.traceID.slice(0,6)}</b>
                <i>·</i>
                <strong>{root?.operationName||"trace"}</strong>
                <i>·</i>
                <em>{(total/1e3).toFixed(1)}ms</em>
                <i>·</i>
                <em>{spans.length} spans</em>
                <small className={failed?"trace-failed":"trace-ok"}>
                  {failed?"\u25B3 ERROR":"\u2713 OK"}
                </small>
              </button>
              {open[trace.traceID]&&<div className="trace-body">
                  <div className="trace-scale">
                    <span>0.0ms</span>
                    <span>{(total/4e3).toFixed(1)}ms</span>
                    <span>{(total/2e3).toFixed(1)}ms</span>
                    <span>{(total*3/4e3).toFixed(1)}ms</span>
                    <span>{(total/1e3).toFixed(1)}ms</span>
                  </div>
                  {[...spans].sort((a,b)=>a.startTime-b.startTime).map((s,i)=>{const d=depth(s),service=s.process?.serviceName||s.tags?.find(t=>t.key==="service.name")?.value||"ragforge",left=(s.startTime-start)/total*100,width=Math.max(.55,s.duration/total*100),technical=/http (send|receive)/.test(s.operationName),c=palette(s.operationName,i);return<button className={`timeline-row ${technical?"technical":""}`}key={s.spanID}onClick={()=>setSelected({...s,service,traceID:trace.traceID})}>
                          <div className="span-name"data-depth={d}style={{paddingLeft:`${d*22}px`}}title={`${s.operationName} \xB7 ${service}`}>
                            <span style={{background:c}}/>
                            <b>{s.operationName}</b>
                            <small>{String(service)}</small>
                          </div>
                          <div className="timeline-track">
                            <i style={{left:`${left}%`,width:`${Math.min(width,100-left)}%`,background:c}}>
                              <b className={width<7?"outside":""}>
                                {(s.duration/1e3).toFixed(1)}ms
                              </b>
                            </i>
                          </div>
                        </button>})}
                </div>}
            </section>})}
        {!traces.length&&!err&&<div className="trace-empty">
            暂无业务链路。请先在 Agent 对话中发送一个问题。
          </div>}
      </div>
      {selected&&<aside className="span-drawer">
          <div className="drawer-head">
            <div>
              <small>SPAN DETAILS</small>
              <h2>{selected.operationName}</h2>
            </div>
            <button onClick={()=>setSelected(null)}>×</button>
          </div>
          <dl>
            <dt>Trace ID</dt>
            <dd>{selected.traceID}</dd>
            <dt>Span ID</dt>
            <dd>{selected.spanID}</dd>
            <dt>服务</dt>
            <dd>{String(selected.service)}</dd>
            <dt>耗时</dt>
            <dd>{(selected.duration/1e3).toFixed(2)} ms</dd>
            <dt>开始时间</dt>
            <dd>{selected.startTime}</dd>
          </dl>
          <h3>Attributes</h3>
          <div className="attribute-list">
            {selected.tags?.map(t=><div key={t.key}>
                <span>{t.key}</span>
                <b>{String(t.value)}</b>
              </div>)}
            {!selected.tags?.length&&<p>无 Attributes</p>}
          </div>
        </aside>}
    </div>}function TraceTimeline({traceId}){const[allData,setAllData]=useState([]),[open,setOpen]=useState({}),[err,setErr]=useState(""),isBusiness=t=>(t.spans||[]).some(s=>/agent\.|query_rewrite|retrieval|rerank|rrf_fusion|tool\.call|cross_encoder|\/api\/v1\/(chat|search)/.test(s.operationName||"")),load=useCallback(()=>ragforgeApi.traces(traceId).then(x=>{const rows=x.data||[],business=traceId?rows:rows.filter(isBusiness);setAllData(rows),setOpen(business[0]?{[business[0].traceID]:!0}:{}),setErr("")}).catch(e=>{setAllData([]),setErr(String(e))}),[traceId]);useEffect(()=>{load()},[load]);const color=(name,i)=>name.includes("http")?"#56a2ef":name.includes("memory")?"#dd69aa":name.includes("handoff")?"#a678e7":name.includes("retrieval")||name.includes("search")?"#3fb6c2":name.includes("reason")?"#d69b20":["#56a2ef","#40bd61","#a678e7","#d69b20","#ef5a55","#dd69aa"][i%6],data=traceId?allData:allData.filter(isBusiness);return<div className="trace-page">
      <div className="trace-top">
        <div>
          <span>OPENTELEMETRY / LIVE</span>
          <h1>Span 嵌套时间线</h1>
          <p>{data.length} 条 Trace 历史记录 · 来自本机 Jaeger</p>
        </div>
        <button onClick={load}>↻ 刷新</button>
      </div>
      {err&&<div className="trace-error">{err}</div>}
      <div className="trace-board">
        {data.map(trace=>{const spans=trace.spans||[],start=spans.length?Math.min(...spans.map(s=>s.startTime)):0,end=spans.length?Math.max(...spans.map(s=>s.startTime+s.duration)):1,total=Math.max(end-start,1),ids=new Map(spans.map(s=>[s.spanID,s])),depth=s=>{let d=0,p=s.references?.find(r=>r.refType==="CHILD_OF")?.spanID;for(;p&&ids.has(p)&&d<6;)d++,p=ids.get(p)?.references?.find(r=>r.refType==="CHILD_OF")?.spanID;return d},failed=spans.some(s=>s.tags?.some(t=>t.key==="error"&&t.value===!0||t.key==="otel.status_code"&&String(t.value).toUpperCase()==="ERROR")),root=spans.find(s=>depth(s)===0)||spans[0];return<section className="trace-group"key={trace.traceID}>
              <button className="trace-summary"onClick={()=>setOpen(x=>({...x,[trace.traceID]:!x[trace.traceID]}))}>
                <span>{open[trace.traceID]?"\u25BE":"\u25B8"}</span>
                <b>trace-{trace.traceID.slice(0,6)}</b>
                <i>·</i>
                <strong>{root?.operationName||"trace"}</strong>
                <i>·</i>
                <em>总耗时 {(total/1e3).toFixed(1)}ms</em>
                <i>·</i>
                <em>{spans.length} spans</em>
                <small className={failed?"trace-failed":"trace-ok"}>
                  {failed?"\u25B3 ERROR":"\u2713 OK"}
                </small>
              </button>
              {open[trace.traceID]&&<div className="trace-body">
                  <div className="trace-scale">
                    <span>0.0ms</span>
                    <span>{(total/4e3).toFixed(1)}ms</span>
                    <span>{(total/2e3).toFixed(1)}ms</span>
                    <span>{(total*3/4e3).toFixed(1)}ms</span>
                    <span>{(total/1e3).toFixed(1)}ms</span>
                  </div>
                  {spans.sort((a,b)=>a.startTime-b.startTime).map((s,i)=>{const d=depth(s),service=s.process?.serviceName||s.tags?.find(t=>t.key==="service.name")?.value||s.tags?.find(t=>t.key==="component")?.value||"ragforge",left=(s.startTime-start)/total*100,width=Math.max(1.2,s.duration/total*100),c=failed&&i<spans.length-1?"#ef514c":color(s.operationName,i);return<div className="timeline-row"key={s.spanID}>
                          <div className="span-name"style={{paddingLeft:`${d*22}px`}}>
                            <span style={{background:c}}/>
                            <b>{s.operationName}</b>
                            <small>{String(service)}</small>
                          </div>
                          <div className="timeline-track">
                            <i style={{left:`${left}%`,width:`${Math.min(width,100-left)}%`,background:c}}>
                              <b>{(s.duration/1e3).toFixed(1)}ms</b>
                            </i>
                          </div>
                        </div>})}
                </div>}
            </section>})}
        {!data.length&&!err&&<div className="trace-empty">正在读取 Trace…</div>}
      </div>
    </div>}function ChatWorkspace({data,kbId,openTrace}){const[input,setInput]=useState(""),[busy,setBusy]=useState(!1),[picker,setPicker]=useState(null),[selectedKb,setSelectedKb]=useState(kbId),[messages,setMessages]=useState([{role:"assistant",text:`\u4F60\u597D\uFF0C\u6211\u662F RAGForge\u3002

\u6211\u53EF\u4EE5\u68C0\u7D22\u4F60\u7684\u672C\u5730\u77E5\u8BC6\u5E93\u3001\u5C55\u793A\u5F15\u7528\u6765\u6E90\uFF0C\u5E76\u628A\u6BCF\u6B21 Agent \u4EA4\u63A5\u548C\u68C0\u7D22\u94FE\u8DEF\u5B8C\u6574\u8BB0\u5F55\u4E0B\u6765\u3002\u4F60\u60F3\u5148\u4E86\u89E3\u4EC0\u4E48\uFF1F`}]),useItem=text=>{setInput(x=>`${x.replace(/[@/]$/,"")}${text} `),setPicker(null)},change=value=>{setInput(value);const last=value.at(-1);last==="@"?setPicker("knowledge"):last==="/"&&setPicker("skill")},send=async e=>{if(e.preventDefault(),!input.trim()||!selectedKb)return;const q=input;setInput(""),setPicker(null),setMessages(x=>[...x,{role:"user",text:q}]),setBusy(!0);try{const r=await ragforgeApi.chat(q,"web-user",selectedKb);setMessages(x=>[...x,{role:"assistant",traceId:r.trace_id,text:`${r.answer}

${r.sources.length} \u4E2A\u5F15\u7528\u6765\u6E90 \xB7 ${r.handoffs.length} \u6B21 Agent \u4EA4\u63A5 \xB7 ${r.iterations} \u6B21\u8FED\u4EE3`}])}catch(e2){setMessages(x=>[...x,{role:"assistant",text:`\u8C03\u7528\u5931\u8D25\uFF1A${String(e2)}`}])}finally{setBusy(!1)}},choices=picker==="knowledge"?data?.knowledge_bases.map(k=>({key:k.id,icon:"\u25B1",title:k.name,sub:`${k.documents} \u7BC7\u6587\u6863 \xB7 ${k.chunks} \u4E2A\u68C0\u7D22\u5757`,value:`@${k.name}`}))||[]:picker==="skill"?[["/\u68C0\u7D22","\u641C\u7D22\u77E5\u8BC6\u5E93\u5E76\u8FD4\u56DE\u5F15\u7528"],["/\u603B\u7ED3","\u603B\u7ED3\u5F53\u524D\u4E0A\u4E0B\u6587"],["/\u8BC4\u6D4B","\u8FD0\u884C RAG \u6548\u679C\u8BC4\u6D4B"],["/\u8FFD\u8E2A","\u67E5\u770B\u6700\u8FD1\u6267\u884C\u94FE\u8DEF"]].map(x=>({key:x[0],icon:"\u2318",title:x[0],sub:x[1],value:x[0]})):picker==="model"?[{key:"agent",icon:"\u25CF",title:"RAGForge Agent",sub:"Orchestrator \u2192 Retrieval \u2192 Answer",value:""}]:[{key:"upload",icon:"\uFF0B",title:"\u4E0A\u4F20\u672C\u5730\u6587\u4EF6",sub:"\u6DFB\u52A0\u4E3A\u672C\u6B21\u4EFB\u52A1\u7684\u4E0A\u4E0B\u6587",value:""}];return<div className="task-page">
      <div className="task-topbar">
        <h1>构建企业知识库问答助手</h1>
        <div>
          <span className="model-status">
            <Dot/>多 Agent RAG
          </span>
          <button onClick={()=>setPicker(p=>p==="model"?null:"model")}aria-label="任务设置">
            •••
          </button>
        </div>
      </div>
      <section className="conversation">
        <div className="conversation-stream">
          {messages.map((m,i)=><article className={`message ${m.role}`}key={i}>
              {m.role==="assistant"&&<div className="assistant-label">
                  <span>R</span>
                  <b>RAGForge</b>
                </div>}
              <div className="message-body">
                {m.text.split(`
`).map((p,j)=>p?<p key={j}>{p}</p>:<br key={j}/>)}
                {m.traceId&&<div className="result-artifact">
                    <div>
                      <span className="artifact-icon">↗</span>
                      <div>
                        <b>查看本次执行链路</b>
                        <small>检索、重排与 Agent 交接详情</small>
                      </div>
                    </div>
                    <button onClick={()=>openTrace(m.traceId)}>打开</button>
                  </div>}
              </div>
            </article>)}
          {busy&&<article className="message assistant thinking">
              <div className="assistant-label">
                <span>R</span>
                <b>RAGForge</b>
              </div>
              <div className="message-body">
                <p>
                  正在检索知识库并组织答案<span className="typing">•••</span>
                </p>
              </div>
            </article>}
        </div>
        <div className="composer-wrap">
          <form className="composer"onSubmit={send}>
            <textarea rows={2}value={input}disabled={!selectedKb||busy}onChange={e=>change(e.target.value)}onKeyDown={e=>{e.key==="Escape"&&setPicker(null),e.key==="Enter"&&!e.shiftKey&&(e.preventDefault(),e.currentTarget.form?.requestSubmit())}}placeholder={selectedKb?"\u4ECA\u5929\u5E2E\u4F60\u505A\u4E9B\u4EC0\u4E48\uFF1F  @ \u5F15\u7528\u77E5\u8BC6\u5E93\uFF0C/ \u8C03\u7528\u6280\u80FD\u4E0E\u6307\u4EE4":"\u8BF7\u5148\u5728\u9879\u76EE\u4E2D\u521B\u5EFA\u77E5\u8BC6\u5E93"}/>
            {picker&&<div className="command-picker">
                <strong>
                  {picker==="knowledge"?"@ \u5F15\u7528\u77E5\u8BC6\u5E93":picker==="skill"?"/ \u6280\u80FD\u4E0E\u6307\u4EE4":picker==="model"?"\u9009\u62E9 Agent":"\u6DFB\u52A0\u5185\u5BB9"}
                </strong>
                {choices.map(c=><button type="button"key={c.key}onClick={()=>{picker==="knowledge"&&setSelectedKb(c.key),picker==="attach"&&alert("\u672C\u5730\u6587\u4EF6\u4E0A\u4F20\u63A5\u53E3\u5C1A\u672A\u914D\u7F6E"),useItem(c.value)}}>
                    <span>{c.icon}</span>
                    <div>
                      <b>{c.title}</b>
                      <small>{c.sub}</small>
                    </div>
                  </button>)}
              </div>}
            <div className="composer-bottom">
              <button type="button"className="add-button"onClick={()=>setPicker(p=>p==="attach"?null:"attach")}aria-label="添加附件">
                ＋
              </button>
              <div>
                <button type="button"className="model-button"onClick={()=>setPicker(p=>p==="model"?null:"model")}>
                  ◉ RAGForge Agent⌄
                </button>
                <button className="send-button"disabled={!input.trim()||busy||!selectedKb}aria-label="发送">
                  ↑
                </button>
              </div>
            </div>
          </form>
          <p className="disclaimer">内容由 AI 生成，请核实重要信息</p>
        </div>
      </section>
    </div>}function TraceExplorer({traceId}){const[q,setQ]=useState(traceId||""),[target,setTarget]=useState(traceId||"");return<div className="trace-explorer">
      <form className="trace-lookup"onSubmit={e=>{e.preventDefault(),!q||/^[0-9a-f]{32}$/i.test(q)?setTarget(q):alert("Trace ID \u5E94\u4E3A 32 \u4F4D\u5341\u516D\u8FDB\u5236\u5B57\u7B26")}}>
        <div>
          <b>查询 Trace ID</b>
          <small>默认展示最近 20 条业务链路，也可以精确回放指定 Trace</small>
        </div>
        <input value={q}onChange={e=>setQ(e.target.value.trim())}placeholder="输入 32 位 Trace ID"/>
        <button>查询</button>
        <button type="button"onClick={()=>{setQ(""),setTarget("")}}>
          最近 20 条
        </button>
      </form>
      <EnhancedTraceTimeline key={target||"recent"}traceId={target||void 0}/>
    </div>}function KnowledgeExplorer({data,refresh,notify}){const[kb,setKb]=useState(""),[docs,setDocs]=useState([]),[selected,setSelected]=useState(null),file=useRef(null);useEffect(()=>{const id=kb||data?.knowledge_bases[0]?.id;id&&(setKb(id),ragforgeApi.documents(id).then(setDocs).catch(e=>notify(String(e))))},[data,kb,notify]);const upload=async f=>{const text=await f.text();await ragforgeApi.ingestDocument(kb,{source_uri:`upload://${Date.now()}/${f.name}`,title:f.name,text,metadata:{size:f.size}}),await ragforgeApi.compile(kb),notify("\u6587\u6863\u5DF2\u4E0A\u4F20\u5E76\u8FDB\u5165\u6784\u5EFA\u961F\u5217"),await refresh()};return<>
      <Head eye="KNOWLEDGE CONTENT"title="知识库内容"sub="浏览文档、查看分块内容并上传新资料。"action={<>
            <select className="kb-select"value={kb}onChange={e=>setKb(e.target.value)}>
              {data?.knowledge_bases.map(k=><option value={k.id}key={k.id}>
                  {k.name}
                </option>)}
            </select>
            <button className="primary"onClick={()=>file.current?.click()}>
              ＋ 上传文档
            </button>
            <input hidden ref={file}type="file"accept=".txt,.md,.json,.csv"onChange={e=>e.target.files?.[0]&&upload(e.target.files[0])}/>
          </>}/>
      <div className="knowledge-browser">
        <aside>
          {docs.map(d=><button className={selected?.id==d.id?"active":""}key={d.id}onClick={()=>setSelected(d)}>
              <b>{d.title}</b>
              <small>
                {d.chunks.length} Chunks · v{d.version}
              </small>
            </button>)}
          {!docs.length&&<p>暂无已构建文档</p>}
        </aside>
        <section>
          {selected?<>
              <div className="doc-heading">
                <div>
                  <h2>{selected.title}</h2>
                  <p>{selected.source_uri}</p>
                </div>
                <span>
                  {selected.chunks.reduce((n,c)=>n+c.token_count,0)}{" "}
                  tokens
                </span>
              </div>
              <div className="chunk-list">
                {selected.chunks.map(c=><article key={c.id}>
                    <header>
                      <b>Chunk #{c.ordinal+1}</b>
                      <span>{c.token_count} tokens</span>
                    </header>
                    <small>{c.breadcrumb}</small>
                    <p>{c.text}</p>
                  </article>)}
              </div>
            </>:<div className="empty-selection">选择左侧文档查看分块内容</div>}
        </section>
      </div>
    </>}function EvaluationExplorer({notify}){const[run,setRun]=useState(null),[set,setSet]=useState([]),[total,setTotal]=useState(0),[page,setPage]=useState(0);return useEffect(()=>{ragforgeApi.evaluations().then(x=>setRun(x[0]||null)),ragforgeApi.evalDataset(page*30,30).then(x=>{setSet(x.items),setTotal(x.total)}).catch(e=>notify(String(e)))},[page,notify]),<>
      <Head eye="RAG EVALUATION"title="300 条 QA 评测集"sub="浏览基准问题、标准答案与证据，并查看最近评测结果。"/>
      <div className="eval-summary">
        <div>
          <span>数据集</span>
          <b>{total} QA</b>
        </div>
        <div>
          <span>NDCG@10</span>
          <b>{run?.metrics?.ndcg_at_k?.toFixed(3)||"\u2014"}</b>
        </div>
        <div>
          <span>Recall@10</span>
          <b>{run?.metrics?.recall_at_k?.toFixed(3)||"\u2014"}</b>
        </div>
        <div>
          <span>最近状态</span>
          <b>{run?run.passed?"PASS":"CHECK":"\u672A\u8FD0\u884C"}</b>
        </div>
      </div>
      <div className="qa-table">
        <div className="qa-head">
          <span>编号</span>
          <span>问题 / 标准答案</span>
          <span>证据</span>
        </div>
        {set.map(x=><article key={x.qa_id}>
            <span>{x.qa_id}</span>
            <div>
              <b>{x.question}</b>
              <p>{x.answer}</p>
            </div>
            <p>{x.evidence}</p>
          </article>)}
      </div>
      <div className="pager">
        <button disabled={!page}onClick={()=>setPage(p=>p-1)}>
          上一页
        </button>
        <span>
          {page+1} / {Math.ceil(total/30)||1}
        </span>
        <button disabled={(page+1)*30>=total}onClick={()=>setPage(p=>p+1)}>
          下一页
        </button>
      </div>
    </>}function KnowledgeBodyExplorer({data,refresh,notify}){const[kb,setKb]=useState(""),[docs,setDocs]=useState([]),[selected,setSelected]=useState(null),[view,setView]=useState("original"),file=useRef(null),load=useCallback(id=>ragforgeApi.documents(id).then(rows=>{setDocs(rows),setSelected(current=>rows.find(x=>x.id===current?.id)||rows[0]||null)}).catch(e=>notify(String(e))),[notify]);useEffect(()=>{const id=kb||data?.knowledge_bases[0]?.id;id&&(kb||setKb(id),load(id))},[data,kb,load]);const upload=async f=>{const text=await f.text();await ragforgeApi.ingestDocument(kb,{source_uri:`upload://${Date.now()}/${f.name}`,title:f.name,text,metadata:{size:f.size,type:f.type}}),await ragforgeApi.compile(kb),notify("\u6587\u6863\u5DF2\u4E0A\u4F20\uFF0C\u5B8C\u6210\u6784\u5EFA\u540E\u5C06\u663E\u793A\u539F\u6587\u4E0E\u5206\u5757"),await refresh()};return<>
      <Head eye="KNOWLEDGE BODY"title="知识库本体"sub="查看完整原文、文档元数据与检索分块。"action={<>
            <select className="kb-select"value={kb}onChange={e=>{setKb(e.target.value),setSelected(null)}}>
              {data?.knowledge_bases.map(k=><option value={k.id}key={k.id}>
                  {k.name}
                </option>)}
            </select>
            <button className="ghost"onClick={()=>load(kb)}>
              ↻ 刷新
            </button>
            <button className="primary"onClick={()=>file.current?.click()}>
              ＋ 上传文档
            </button>
            <input hidden ref={file}type="file"accept=".txt,.md,.json,.csv"onChange={e=>e.target.files?.[0]&&upload(e.target.files[0])}/>
          </>}/>
      <div className="knowledge-browser body-browser">
        <aside>
          <div className="doc-count">{docs.length} 篇文档</div>
          {docs.map(d=><button className={selected?.id===d.id?"active":""}key={d.id}onClick={()=>{setSelected(d),setView("original")}}>
              <b>{d.title}</b>
              <small>
                {d.chunks.length} Chunks · v{d.version}
              </small>
            </button>)}
        </aside>
        <section>
          {selected?<>
              <div className="doc-heading">
                <div>
                  <h2>{selected.title}</h2>
                  <p>{selected.source_uri}</p>
                </div>
                <div className="doc-facts">
                  <span>v{selected.version}</span>
                  <span>{selected.original_text?.length||0} 字符</span>
                  <span>
                    {selected.chunks.reduce((n,c)=>n+c.token_count,0)}{" "}
                    tokens
                  </span>
                </div>
              </div>
              <div className="doc-tabs">
                <button className={view==="original"?"active":""}onClick={()=>setView("original")}>
                  原文
                </button>
                <button className={view==="chunks"?"active":""}onClick={()=>setView("chunks")}>
                  分块 · {selected.chunks.length}
                </button>
              </div>
              {view==="original"?<article className="original-document">
                  {selected.original_text?<pre>{selected.original_text}</pre>:<div className="legacy-original">
                      <b>该文档创建于原文持久化功能之前</b>
                      <p>
                        数据库中只有检索分块，无法可靠恢复原始排版。请重新上传原文件以查看知识本体。
                      </p>
                    </div>}
                </article>:<div className="chunk-list">
                  {selected.chunks.map(c=><article key={c.id}>
                      <header>
                        <b>Chunk #{c.ordinal+1}</b>
                        <span>{c.token_count} tokens</span>
                      </header>
                      <small>{c.breadcrumb}</small>
                      <p>{c.text}</p>
                    </article>)}
                </div>}
            </>:<div className="empty-selection">选择左侧文档查看知识本体</div>}
        </section>
      </div>
    </>}function ProductChat({data,kbId,openTrace}){const storage=`ragforge-chat-${activeChatId}`,[title,setTitle]=useState("\u65B0\u4EFB\u52A1"),[input,setInput]=useState(""),[busy,setBusy]=useState(!1),[picker,setPicker]=useState(null),[selectedKb,setSelectedKb]=useState(kbId),fileRef=useRef(null),[messages,setMessages]=useState([{role:"assistant",text:"\u4F60\u597D\uFF0C\u6211\u662F RAGForge\u3002\u4F60\u53EF\u4EE5\u76F4\u63A5\u63D0\u95EE\u3001@ \u5F15\u7528\u77E5\u8BC6\u5E93\uFF0C\u6216\u7528 / \u8C03\u7528\u6280\u80FD\u3002"}]),[restored,setRestored]=useState(!1);useEffect(()=>{try{const saved=localStorage.getItem(storage),savedTitle=localStorage.getItem(`${storage}-title`);saved&&setMessages(JSON.parse(saved)),savedTitle&&setTitle(savedTitle)}finally{setRestored(!0)}},[storage]),useEffect(()=>{restored&&(localStorage.setItem(storage,JSON.stringify(messages)),localStorage.setItem(`${storage}-title`,title))},[messages,title,storage,restored]);const send=async e=>{if(e.preventDefault(),!input.trim()||!selectedKb)return;const q=input;setInput(""),setMessages(x=>[...x,{role:"user",text:q}]),setBusy(!0);try{const r=await ragforgeApi.chat(q,"web-user",selectedKb,activeChatId);setMessages(x=>[...x,{role:"assistant",text:r.answer,traceId:r.trace_id,sources:r.sources.slice(0,3),usage:r.usage}])}catch(e2){setMessages(x=>[...x,{role:"assistant",text:`\u8C03\u7528\u5931\u8D25\uFF1A${String(e2)}`}])}finally{setBusy(!1)}},upload=async file=>{if(!selectedKb)return;const text=await file.text();await ragforgeApi.ingestDocument(selectedKb,{source_uri:`upload://${Date.now()}/${file.name}`,title:file.name,text,metadata:{size:file.size,type:file.type}}),await ragforgeApi.compile(selectedKb),alert(`${file.name} \u5DF2\u4E0A\u4F20\uFF0C\u77E5\u8BC6\u5E93\u6B63\u5728\u6784\u5EFA`)},change=v=>{setInput(v),v.endsWith("@")?setPicker("knowledge"):v.endsWith("/")&&setPicker("skill")};return<div className="task-page product-chat">
      <div className="task-topbar">
        <button className="editable-title"onClick={()=>{const next=prompt("\u91CD\u547D\u540D\u4EFB\u52A1",title);next?.trim()&&setTitle(next.trim())}}title="点击重命名">
          {title}
          <span>✎</span>
        </button>
        <div>
          <span className="model-status">
            <Dot/>多 Agent RAG
          </span>
        </div>
      </div>
      <section className="conversation">
        <div className="conversation-stream">
          {messages.map((m,i)=><article className={`message ${m.role}`}key={i}>
              {m.role==="assistant"&&<div className="assistant-label">
                  <span>R</span>
                  <b>RAGForge</b>
                </div>}
              <div className="message-body">
                <p>{m.text}</p>
                {m.sources&&m.sources.length>0&&<div className="source-stack">
                    <strong>知识库来源 · Top {m.sources.length}</strong>
                    {m.sources.map((s,n)=><button key={s.chunk_id}title={s.breadcrumb}>
                        <span>{n+1}</span>
                        <div>
                          <b>{s.breadcrumb||s.chunk_id}</b>
                          <small>相关度 {(s.score*100).toFixed(1)}%</small>
                        </div>
                      </button>)}
                  </div>}
                {m.traceId&&<div className="answer-meta">
                    <button onClick={()=>openTrace(m.traceId)}>
                      Trace {m.traceId.slice(0,10)}… ↗
                    </button>
                    <span>输入 {m.usage?.input_tokens||0} tokens</span>
                    <span>输出 {m.usage?.output_tokens||0} tokens</span>
                    <span>
                      ${Number(m.usage?.estimated_cost_usd||0).toFixed(5)}
                    </span>
                  </div>}
              </div>
            </article>)}
          {busy&&<article className="message assistant thinking">
              <div className="assistant-label">
                <span>R</span>
                <b>RAGForge</b>
              </div>
              <div className="message-body">
                <p>正在规划、检索并生成答案…</p>
              </div>
            </article>}
        </div>
        <div className="composer-wrap">
          <form className="composer"onSubmit={send}>
            <textarea rows={2}value={input}disabled={!selectedKb||busy}onChange={e=>change(e.target.value)}onKeyDown={e=>{e.key==="Escape"&&setPicker(null),e.key==="Enter"&&!e.shiftKey&&(e.preventDefault(),e.currentTarget.form?.requestSubmit())}}placeholder="今天帮你做些什么？  @ 引用知识库，/ 调用技能与指令"/>
            {picker&&<div className="command-picker">
                <strong>
                  {picker==="knowledge"?"@ \u5F15\u7528\u77E5\u8BC6\u5E93":"/ \u6280\u80FD\u4E0E\u6307\u4EE4"}
                </strong>
                {picker==="knowledge"?data?.knowledge_bases.map(k=><button type="button"key={k.id}onClick={()=>{setSelectedKb(k.id),setInput(x=>x.slice(0,-1)+`@${k.name} `),setPicker(null)}}>
                        <span>▱</span>
                        <div>
                          <b>{k.name}</b>
                          <small>
                            {k.documents} 文档 · {k.chunks} Chunks
                          </small>
                        </div>
                      </button>):[["/\u68C0\u7D22","\u68C0\u7D22\u5E76\u5F15\u7528\u77E5\u8BC6\u5E93"],["/\u603B\u7ED3","\u603B\u7ED3\u5F53\u524D\u4EFB\u52A1"],["/\u8BC4\u6D4B","\u8BC4\u4F30\u56DE\u7B54\u8D28\u91CF"],["/\u6267\u884C","\u89C4\u5212\u5E76\u6267\u884C\u4EFB\u52A1"]].map(x=><button type="button"key={x[0]}onClick={()=>{setInput(v=>v.slice(0,-1)+x[0]+" "),setPicker(null)}}>
                        <span>⌘</span>
                        <div>
                          <b>{x[0]}</b>
                          <small>{x[1]}</small>
                        </div>
                      </button>)}
              </div>}
            <input ref={fileRef}type="file"hidden accept=".txt,.md,.json,.csv"onChange={e=>e.target.files?.[0]&&upload(e.target.files[0])}/>
            <div className="composer-bottom">
              <button type="button"className="add-button"onClick={()=>fileRef.current?.click()}title="上传到知识库">
                ＋
              </button>
              <div>
                <button type="button"className="model-button">
                  ◉ RAGForge Agent
                </button>
                <button className="send-button"disabled={!input.trim()||busy||!selectedKb}>
                  ↑
                </button>
              </div>
            </div>
          </form>
          <p className="disclaimer">
            知识库无依据时将明确使用模型通用知识 · AI 内容请核实
          </p>
        </div>
      </section>
    </div>}function SourceAwareChat({data,kbId,openTrace}){const storage=`ragforge-chat-${activeChatId}`,greeting={role:"assistant",text:"\u4F60\u597D\uFF0C\u6211\u662F RAGForge\u3002\u4F60\u53EF\u4EE5\u76F4\u63A5\u63D0\u95EE\u3001@ \u5F15\u7528\u77E5\u8BC6\u5E93\uFF0C\u6216\u7528 / \u8C03\u7528\u6280\u80FD\u3002"},[title,setTitle]=useState("\u65B0\u4EFB\u52A1"),[input,setInput]=useState(""),[busy,setBusy]=useState(!1),[selectedKb,setSelectedKb]=useState(kbId),[messages,setMessages]=useState([greeting]),[restored,setRestored]=useState(!1),fileRef=useRef(null);useEffect(()=>{let cancelled=!1;return(async()=>{let localMessages=[greeting],localTitle="\u65B0\u4EFB\u52A1";try{const saved=localStorage.getItem(storage),savedTitle=localStorage.getItem(`${storage}-title`);localMessages=saved?JSON.parse(saved):[greeting],localTitle=savedTitle||"\u65B0\u4EFB\u52A1"}catch{}try{const remote=await ragforgeApi.conversation(activeChatId);cancelled||(setMessages(remote.messages?.length?remote.messages:localMessages),setTitle(remote.title||localTitle))}catch{cancelled||(setMessages(localMessages),setTitle(localTitle),selectedKb&&await ragforgeApi.saveConversation(activeChatId,{user_id:"web-user",knowledge_base_id:selectedKb,title:localTitle,messages:localMessages}).catch(()=>{}))}finally{cancelled||setRestored(!0)}})(),()=>{cancelled=!0}},[storage]),useEffect(()=>{restored&&(localStorage.setItem(storage,JSON.stringify(messages)),localStorage.setItem(`${storage}-title`,title))},[messages,restored,storage,title]),useEffect(()=>{kbId&&!selectedKb&&setSelectedKb(kbId)},[kbId,selectedKb]),useEffect(()=>{restored&&selectedKb&&ragforgeApi.saveConversation(activeChatId,{user_id:"web-user",knowledge_base_id:selectedKb,title,messages}).catch(()=>{})},[restored,selectedKb,storage]);const send=async e=>{e.preventDefault();const q=input.trim();if(!(!q||!selectedKb)){setInput(""),setMessages(x=>[...x,{role:"user",text:q}]),setBusy(!0);try{const r=await ragforgeApi.chat(q,"web-user",selectedKb,activeChatId);setMessages(x=>[...x,{role:"assistant",text:r.answer,traceId:r.trace_id,sources:r.sources,usage:r.usage,loopSteps:r.loop_steps,executionStatus:r.status}])}catch(error){setMessages(x=>[...x,{role:"assistant",text:`\u8C03\u7528\u5931\u8D25\uFF1A${String(error)}`}])}finally{setBusy(!1)}}},upload=async file=>{const text=await file.text();await ragforgeApi.ingestDocument(selectedKb,{source_uri:`upload://${Date.now()}/${file.name}`,title:file.name,text,metadata:{size:file.size,type:file.type}}),await ragforgeApi.compile(selectedKb),alert(`${file.name} \u5DF2\u4E0A\u4F20\uFF0C\u77E5\u8BC6\u5E93\u6B63\u5728\u6784\u5EFA`)},openSource=source=>{localStorage.setItem("ragforge-open-chunk",JSON.stringify({chunkId:source.chunk_id,sourceUri:source.source_uri})),window.dispatchEvent(new CustomEvent("ragforge:navigate",{detail:{section:"\u77E5\u8BC6\u5E93"}}))};return<div className="task-page product-chat">
      <div className="task-topbar">
        <button className="editable-title"onClick={()=>{const next=prompt("\u91CD\u547D\u540D\u4EFB\u52A1",title);if(next?.trim()){const renamed=next.trim();setTitle(renamed),ragforgeApi.renameConversation(activeChatId,renamed).catch(()=>{}),window.dispatchEvent(new CustomEvent("ragforge:task-renamed",{detail:{id:Number(activeChatId),title:renamed}}))}}}>
          {title}
          <span>✎</span>
        </button>
        <span className="model-status">
          <Dot/>多 Agent RAG
        </span>
      </div>
      <section className="conversation">
        <div className="conversation-stream">
          {messages.map((message,index)=><article className={`message ${message.role}`}key={index}>
              {message.role==="assistant"&&<div className="assistant-label">
                  <span>R</span>
                  <b>RAGForge</b>
                </div>}
              <div className="message-body">
                <div className="markdown-answer">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}components={{a:({children,...props})=><a{...props}target="_blank"rel="noreferrer">
                          {children}
                        </a>}}>
                    {message.text}
                  </ReactMarkdown>
                </div>
                {message.loopSteps?.length?<details className="agent-loop-card">
                    <summary><span className={`loop-status ${message.executionStatus}`}>{message.executionStatus==="completed"?"\u2713 \u5DF2\u5B8C\u6210":"\xD7 \u5931\u8D25"}</span><b>自主执行过程</b><small>{Math.max(...message.loopSteps.map(step=>step.iteration))} 轮迭代</small></summary>
                    <div className="agent-loop-steps">
                      {message.loopSteps.map((step,stepIndex)=><div className={`loop-step ${step.phase}`}key={`${step.iteration}-${step.phase}-${stepIndex}`}>
                          <span>{step.phase==="perceive"?"\u611F":step.phase==="think"?"\u601D":step.phase==="act"?"\u884C":step.phase==="observe"?"\u89C2":"\u2713"}</span>
                          <div><b>{step.title}</b><p>{step.detail}</p></div>
                          <small>{step.iteration?`\u7B2C ${step.iteration} \u8F6E`:"\u542F\u52A8"}</small>
                        </div>)}
                    </div>
                  </details>:null}
                {message.sources?.length?<div className="source-stack">
                    <strong>知识库依据 · Top {message.sources.length}</strong>
                    {message.sources.map((source,n)=><button key={source.chunk_id}title="打开知识库对应分块"onClick={()=>openSource(source)}>
                        <span>{n+1}</span>
                        <div>
                          <b>{source.breadcrumb||source.chunk_id}</b>
                          <small>
                            相关度{" "}
                            {Number.isFinite(source.relevance)?`${(Math.max(0,Math.min(1,source.relevance))*100).toFixed(1)}% \xB7 \u67E5\u770B\u5206\u5757 \u2197`:"\u65E7\u8BB0\u5F55 \xB7 \u76F8\u5173\u5EA6\u672A\u6821\u51C6"}
                          </small>
                        </div>
                      </button>)}
                  </div>:null}
                {message.traceId&&<div className="answer-meta">
                    <button onClick={()=>openTrace(message.traceId)}>
                      Trace {message.traceId.slice(0,10)}… ↗
                    </button>
                    <button className="feedback-trigger"onClick={()=>window.dispatchEvent(new CustomEvent("ragforge:feedback",{detail:{traceId:message.traceId,kbId:selectedKb,question:[...messages.slice(0,index)].reverse().find(item=>item.role==="user")?.text||"",answer:message.text}}))}>
                      ♡ 纠正回答
                    </button>
                    <span>输入 {message.usage?.input_tokens||0} tokens</span>
                    <span>输出 {message.usage?.output_tokens||0} tokens</span>
                    <span>
                      $
                      {Number(message.usage?.estimated_cost_usd||0).toFixed(5)}
                    </span>
                  </div>}
              </div>
            </article>)}
          {busy&&<article className="message assistant thinking">
              <div className="assistant-label">
                <span>R</span>
                <b>RAGForge</b>
              </div>
              <div className="message-body">
                <p>正在规划、检索并生成答案…</p>
              </div>
            </article>}
        </div>
        <div className="composer-wrap">
          <form className="composer"onSubmit={send}>
            <textarea rows={2}value={input}disabled={!selectedKb||busy}onChange={e=>setInput(e.target.value)}onKeyDown={e=>{e.key==="Enter"&&!e.shiftKey&&(e.preventDefault(),e.currentTarget.form?.requestSubmit())}}placeholder="今天帮你做些什么？  @ 引用知识库，/ 调用技能与指令"/>
            <input ref={fileRef}type="file"hidden accept=".txt,.md,.json,.csv"onChange={e=>e.target.files?.[0]&&upload(e.target.files[0])}/>
            <div className="composer-bottom">
              <button type="button"className="add-button"onClick={()=>fileRef.current?.click()}>
                ＋
              </button>
              <div>
                <select className="model-button"value={selectedKb}onChange={e=>setSelectedKb(e.target.value)}>
                  {data?.knowledge_bases.map(k=><option key={k.id}value={k.id}>
                      {k.name}
                    </option>)}
                </select>
                <button className="send-button"disabled={!input.trim()||busy||!selectedKb}>
                  ↑
                </button>
              </div>
            </div>
          </form>
          <p className="disclaimer">
            仅在知识库证据达到相关度门槛时展示来源 · AI 内容请核实
          </p>
        </div>
      </section>
    </div>}function NavigableKnowledgeBody({data,refresh,notify}){const[kb,setKb]=useState(""),[docs,setDocs]=useState([]),[selected,setSelected]=useState(null),[view,setView]=useState("original"),[target,setTarget]=useState(""),file=useRef(null),load=useCallback(async id=>{try{const rows=await ragforgeApi.documents(id);setDocs(rows),setSelected(current=>rows.find(x=>x.id===current?.id)||rows[0]||null)}catch(error){notify(String(error))}},[notify]);useEffect(()=>{const id=kb||data?.knowledge_bases[0]?.id;id&&(kb||setKb(id),load(id))},[data,kb,load]),useEffect(()=>{if(docs.length)try{const request=JSON.parse(localStorage.getItem("ragforge-open-chunk")||"null");if(!request?.chunkId)return;const doc=docs.find(item=>item.chunks.some(chunk=>chunk.id===request.chunkId));doc&&(setSelected(doc),setView("chunks"),setTarget(request.chunkId),setTimeout(()=>document.getElementById(`chunk-${request.chunkId}`)?.scrollIntoView({behavior:"smooth",block:"center"}),80),localStorage.removeItem("ragforge-open-chunk"))}catch{}},[docs]);const upload=async f=>{const text=await f.text();await ragforgeApi.ingestDocument(kb,{source_uri:`upload://${Date.now()}/${f.name}`,title:f.name,text,metadata:{size:f.size,type:f.type}}),await ragforgeApi.compile(kb),notify("\u6587\u6863\u5DF2\u4E0A\u4F20\u5E76\u8FDB\u5165\u6784\u5EFA\u961F\u5217"),await refresh(),await load(kb)};return<>
      <Head eye="KNOWLEDGE BODY"title="知识库本体"sub="查看完整原文、文档元数据与检索分块。"action={<>
            <select className="kb-select"value={kb}onChange={e=>{setKb(e.target.value),setSelected(null)}}>
              {data?.knowledge_bases.map(k=><option value={k.id}key={k.id}>
                  {k.name}
                </option>)}
            </select>
            <button className="ghost"onClick={()=>load(kb)}>
              ↻ 刷新
            </button>
            <button className="primary"onClick={()=>file.current?.click()}>
              ＋ 上传文档
            </button>
            <input hidden ref={file}type="file"accept=".txt,.md,.json,.csv"onChange={e=>e.target.files?.[0]&&upload(e.target.files[0])}/>
          </>}/>
      <div className="knowledge-browser body-browser">
        <aside>
          <div className="doc-count">{docs.length} 篇文档</div>
          {docs.map(doc=><button className={selected?.id===doc.id?"active":""}key={doc.id}onClick={()=>{setSelected(doc),setView("original"),setTarget("")}}>
              <b>{doc.title}</b>
              <small>
                {doc.chunks.length} Chunks · v{doc.version}
              </small>
            </button>)}
        </aside>
        <section>
          {selected?<>
              <div className="doc-heading">
                <div>
                  <h2>{selected.title}</h2>
                  <p>{selected.source_uri}</p>
                </div>
                <div className="doc-facts">
                  <span>v{selected.version}</span>
                  <span>{selected.original_text?.length||0} 字符</span>
                  <span>
                    {selected.chunks.reduce((n,c)=>n+c.token_count,0)}{" "}
                    tokens
                  </span>
                </div>
              </div>
              <div className="doc-tabs">
                <button className={view==="original"?"active":""}onClick={()=>setView("original")}>
                  原文
                </button>
                <button className={view==="chunks"?"active":""}onClick={()=>setView("chunks")}>
                  分块 · {selected.chunks.length}
                </button>
              </div>
              {view==="original"?<article className="original-document">
                  {selected.original_text?<pre>{selected.original_text}</pre>:<div className="legacy-original">
                      <b>该文档创建于原文持久化功能之前</b>
                      <p>
                        请重新上传原文件以查看知识本体；现有检索分块仍可浏览。
                      </p>
                    </div>}
                </article>:<div className="chunk-list">
                  {selected.chunks.map(chunk=><article id={`chunk-${chunk.id}`}className={target===chunk.id?"target-chunk":""}key={chunk.id}>
                      <header>
                        <b>Chunk #{chunk.ordinal+1}</b>
                        <span>{chunk.token_count} tokens</span>
                      </header>
                      <small>{chunk.breadcrumb}</small>
                      <p>{chunk.text}</p>
                    </article>)}
                </div>}
            </>:<div className="empty-selection">选择左侧文档查看知识本体</div>}
        </section>
      </div>
    </>}function Home(){const[section,setSection]=useState("Agent \u5BF9\u8BDD"),[traceTarget,setTraceTarget]=useState(""),[online,setOnline]=useState(!1),[data,setData]=useState(null),[feedback,setFeedback]=useState([]),[toast,setToast]=useState(""),[error,setError]=useState(""),[collapsed,setCollapsed]=useState(!1),[chatKey,setChatKey]=useState(1),[searching,setSearching]=useState(!1),[history,setHistory]=useState([{id:1,title:"\u6784\u5EFA\u4F01\u4E1A\u77E5\u8BC6\u5E93\u95EE\u7B54\u52A9\u624B",time:"\u521A\u521A"}]),refresh=useCallback(async()=>{try{await ragforgeApi.health();const[d,f]=await Promise.all([ragforgeApi.dashboard(),ragforgeApi.feedback()]);setData(d),setFeedback(f),setOnline(!0),setError("")}catch(e){setOnline(!1),setError(e instanceof Error?e.message:"\u8FDE\u63A5\u5931\u8D25")}},[]);useEffect(()=>{refresh();const saved=localStorage.getItem("ragforge-history"),active=localStorage.getItem("ragforge-active-chat");if(saved)try{setHistory(JSON.parse(saved))}catch{}active&&setChatKey(Number(active)),ragforgeApi.conversations().then(rows=>{rows.length&&setHistory(rows.map(row=>({id:Number(row.client_id),title:row.title,time:new Date(row.updated_at).toLocaleDateString()})))}).catch(()=>{});const navigate=event=>{const detail=event.detail;detail?.section&&setSection(detail.section)},rename=event=>{const detail=event.detail;detail?.id&&detail?.title&&setHistory(items=>items.map(item=>item.id===detail.id?{...item,title:detail.title}:item))};return window.addEventListener("ragforge:navigate",navigate),window.addEventListener("ragforge:task-renamed",rename),()=>{window.removeEventListener("ragforge:navigate",navigate),window.removeEventListener("ragforge:task-renamed",rename)}},[refresh]),useEffect(()=>{localStorage.setItem("ragforge-history",JSON.stringify(history)),localStorage.setItem("ragforge-active-chat",String(chatKey))},[history,chatKey]);const notify=s=>{setToast(s),setTimeout(()=>setToast(""),2200)},kbId=configuredKnowledgeBaseId||data?.knowledge_bases.reduce((best,k)=>k.documents>best.documents?k:best,data.knowledge_bases[0])?.id||"",openTrace=traceId=>{setTraceTarget(traceId),setSection("\u94FE\u8DEF\u8FFD\u8E2A")},newChat=()=>{const id=Date.now();ragforgeApi.saveConversation(String(id),{user_id:"web-user",knowledge_base_id:kbId||null,title:"\u65B0\u4EFB\u52A1",messages:[]}).catch(()=>{}),setHistory(x=>[{id,title:"\u65B0\u4EFB\u52A1",time:"\u521A\u521A"},...x]),setChatKey(id),setSection("Agent \u5BF9\u8BDD")},Chat2=SourceAwareChat,Tracing2=TraceExplorer,Knowledge2=NavigableKnowledgeBody,Evaluation2=EvaluationExplorer;return activeChatId=String(chatKey),<main className={`shell ${section==="Agent \u5BF9\u8BDD"?"conversation-mode":""} ${collapsed?"sidebar-collapsed":""}`}>
      <aside className="sidebar">
        <div className="sidebar-tools">
          <button onClick={()=>setCollapsed(x=>!x)}aria-label={collapsed?"\u5C55\u5F00\u4FA7\u680F":"\u6536\u8D77\u4FA7\u680F"}>
            ▯
          </button>
          <button onClick={()=>setSearching(x=>!x)}aria-label="搜索任务">
            ⌕
          </button>
        </div>
        {searching&&<input className="history-search"autoFocus placeholder="搜索最近任务…"/>}
        <button className="brand"onClick={()=>setSection("Agent \u5BF9\u8BDD")}>
          <span className="brand-mark">R</span>
          <span>RAGForge</span>
        </button>
        <button className="new-task"onClick={newChat}>
          <span>＋</span>
          <b>新建任务</b>
        </button>
        <div className="sidebar-section-label">工作区</div>
        <nav className="primary-nav"aria-label="工作区导航">
          {nav.map(([n,i])=><button key={n}className={section===n?"nav-item active":"nav-item"}onClick={()=>setSection(n)}>
              <span>{i}</span>
              <b>{n}</b>
            </button>)}
        </nav>
        <div className="recent">
          <h3>最近</h3>
          {history.map(h=><button key={h.id}className={section==="Agent \u5BF9\u8BDD"&&chatKey===h.id?"active":""}onClick={()=>{setChatKey(h.id),setSection("Agent \u5BF9\u8BDD")}}>
              <span>{h.title}</span>
              <time>{h.time}</time>
            </button>)}
        </div>
        <div className="profile">
          <span className="avatar">Y</span>
          <div>
            <b>本地工作区</b>
            <small>
              <Dot off={!online}/>
              {online?"\u670D\u52A1\u5DF2\u8FDE\u63A5":error||"\u6B63\u5728\u8FDE\u63A5"}
            </small>
          </div>
          <button onClick={refresh}>↻</button>
        </div>
      </aside>
      <section className="content">
        {section==="\u6982\u89C8"?<Overview data={data}refresh={refresh}notify={notify}/>:section==="\u77E5\u8BC6\u5E93"?<Knowledge2 data={data}refresh={refresh}notify={notify}/>:section==="\u68C0\u7D22\u6D4B\u8BD5"?<Retrieval kbId={kbId}/>:section==="Agent \u5BF9\u8BDD"?<Chat2 key={chatKey}data={data}kbId={kbId}openTrace={openTrace}/>:section==="\u53CD\u9988\u8BB0\u5FC6"?<Memories items={feedback}refresh={refresh}notify={notify}/>:section==="\u8BC4\u6D4B"?<Evaluation2 notify={notify}/>:<Tracing2 traceId={traceTarget}/>}
      </section>
      {toast&&<div className="toast">{toast}</div>}
    </main>}function Overview({data,refresh,notify}){const metric=data?.latest_evaluation?.metrics.ndcg_at_k,create=async()=>{const name=prompt("\u77E5\u8BC6\u5E93\u540D\u79F0");if(name)try{await ragforgeApi.createKnowledgeBase(name),await refresh(),notify("\u77E5\u8BC6\u5E93\u5DF2\u521B\u5EFA")}catch(e){notify(String(e))}};return<>
      <Head eye="WORKSPACE"title="概览"sub="知识库的运行状态与关键指标。"action={<button className="primary"onClick={create}>
            新建知识库
          </button>}/>
      <section className="hero-card">
        <div>
          <span className="live-pill">
            <i/> {data?"\u670D\u52A1\u6B63\u5E38":"\u8FDE\u63A5\u4E2D"}
          </span>
          <h2>
            {data?`${data.totals.knowledge_bases} \u4E2A\u77E5\u8BC6\u5E93\u6B63\u5728\u670D\u52A1`:"API \u5C1A\u672A\u5C31\u7EEA"}
          </h2>
          <p>
            {data?`\u5171 ${data.totals.documents} \u7BC7\u6587\u6863\uFF0C${data.totals.chunks} \u4E2A\u68C0\u7D22\u5757\u3002`:"\u8BF7\u68C0\u67E5\u540E\u7AEF\u670D\u52A1\u3002"}
          </p>
        </div>
        <div className="hero-score">
          <strong>
            {metric===void 0?"\u2014":(metric*100).toFixed(1)}
          </strong>
          <span>NDCG@10 {metric===void 0?"":"%"}</span>
        </div>
      </section>
      <div className="metric-grid">
        {[[data?.totals.knowledge_bases??"\u2014","\u77E5\u8BC6\u5E93"],[data?.totals.documents??"\u2014","\u6587\u6863"],[data?.totals.chunks??"\u2014","\u68C0\u7D22\u5757"],[data?.totals.pending_events??"\u2014","\u5F85\u5904\u7406"]].map(([v,n])=><article className="metric"key={n}>
            <div className="metric-top">
              <span>{n}</span>
            </div>
            <strong>{v}</strong>
          </article>)}
      </div>
      <article className="panel">
        <div className="panel-head">
          <div>
            <span className="kicker">BUILD STATUS</span>
            <h3>知识库</h3>
          </div>
          <button className="ghost"onClick={refresh}>
            刷新
          </button>
        </div>
        {data?.knowledge_bases.map(k=><div className="task-row"key={k.id}>
            <span className="file-icon">{k.name[0]}</span>
            <div>
              <b>{k.name}</b>
              <small>
                {k.documents} 篇文档 · {k.chunks} 个检索块 · v
                {k.image_version||0}
              </small>
            </div>
            <span className={k.build_state==="succeeded"?"success":"working"}>
              {state(k.build_state)}
            </span>
          </div>)}
      </article>
    </>}function Knowledge({data,refresh,notify}){const compile=async id=>{try{const r=await ragforgeApi.compile(id);notify(`\u4EFB\u52A1 ${r.job_id.slice(0,8)} \u5DF2\u5165\u961F`),await refresh()}catch(e){notify(String(e))}};return<>
      <Head eye="KNOWLEDGE"title="知识库"sub="管理文档、检索块和构建版本。"action={<button className="ghost"onClick={refresh}>
            刷新
          </button>}/>
      <div className="summary-strip">
        <div>
          <span>知识库</span>
          <strong>{data?.totals.knowledge_bases??"\u2014"}</strong>
        </div>
        <div>
          <span>文档</span>
          <strong>{data?.totals.documents??"\u2014"}</strong>
        </div>
        <div>
          <span>检索块</span>
          <strong>{data?.totals.chunks??"\u2014"}</strong>
        </div>
        <div>
          <span>待处理</span>
          <strong>{data?.totals.pending_events??"\u2014"}</strong>
        </div>
      </div>
      <section className="panel table-panel">
        <div className="data-table head">
          <span>知识库</span>
          <span>文档</span>
          <span>检索块</span>
          <span>状态</span>
          <span>操作</span>
        </div>
        {data?.knowledge_bases.map(k=><div className="data-table"key={k.id}>
            <span className="name-cell">
              <i className="db-icon">DB</i>
              <b>{k.name}</b>
            </span>
            <span>{k.documents}</span>
            <span>{k.chunks}</span>
            <span>{state(k.build_state)}</span>
            <button className="ghost"onClick={()=>compile(k.id)}>
              构建
            </button>
          </div>)}
      </section>
    </>}function Retrieval({kbId}){const[q,setQ]=useState("\u51FA\u5DEE\u62A5\u9500\u9700\u8981\u5728\u51E0\u5929\u5185\u63D0\u4EA4\uFF1F"),[results,setResults]=useState([]),[rewrite,setRewrite]=useState(""),[busy,setBusy]=useState(!1),[err,setErr]=useState(""),run=async()=>{if(!kbId)return setErr("\u8BF7\u5148\u521B\u5EFA\u77E5\u8BC6\u5E93");setBusy(!0);try{const r=await ragforgeApi.search(q,kbId);setResults(r.results),setRewrite(r.rewritten_query),setErr("")}catch(e){setErr(String(e))}finally{setBusy(!1)}};return<>
      <Head eye="RETRIEVAL LAB"title="真实检索实验室"sub="调用 Query Rewrite、BM25、pgvector、RRF 和 CrossEncoder。"/>
      <div className="search-box">
        <label>测试问题</label>
        <div>
          <input value={q}onChange={e=>setQ(e.target.value)}/>
          <button className="primary"onClick={run}>
            {busy?"\u68C0\u7D22\u4E2D\u2026":"\u8FD0\u884C\u68C0\u7D22"}
          </button>
        </div>
        {err&&<p className="working">{err}</p>}
      </div>
      <div className="retrieval-layout">
        <section className="panel stages">
          <div className="stage">
            <span>1</span>
            <div>
              <b>Query Rewrite</b>
              <small>{rewrite||"\u7B49\u5F85\u8FD0\u884C"}</small>
            </div>
          </div>
          <div className="stage">
            <span>2</span>
            <div>
              <b>Hybrid + RRF + Rerank</b>
              <small>
                {results.length?`${results.length} \u4E2A\u771F\u5B9E\u7ED3\u679C`:"\u7B49\u5F85\u8FD0\u884C"}
              </small>
            </div>
          </div>
        </section>
        <section className="panel result-panel">
          {results.length?results.map((r,i)=><div className="result"key={r.id}>
                <strong>{i+1}</strong>
                <div>
                  <b>{r.breadcrumb||"\u672A\u547D\u540D\u6587\u6863"}</b>
                  <p>{r.text}</p>
                  <span>
                    Dense {r.dense_score.toFixed(3)} · BM25{" "}
                    {r.bm25_score.toFixed(3)} · Rerank{" "}
                    {r.rerank_score.toFixed(3)}
                  </span>
                </div>
                <em>{r.score.toFixed(3)}</em>
              </div>):<p className="muted">运行后显示数据库中的真实命中。</p>}
        </section>
      </div>
    </>}function Chat({data,kbId,openTrace}){const[input,setInput]=useState(""),[busy,setBusy]=useState(!1),[messages,setMessages]=useState([{role:"assistant",text:`\u4F60\u597D\uFF0C\u6211\u662F RAGForge\u3002

\u6211\u53EF\u4EE5\u68C0\u7D22\u4F60\u7684\u672C\u5730\u77E5\u8BC6\u5E93\u3001\u5C55\u793A\u5F15\u7528\u6765\u6E90\uFF0C\u5E76\u628A\u6BCF\u6B21 Agent \u4EA4\u63A5\u548C\u68C0\u7D22\u94FE\u8DEF\u5B8C\u6574\u8BB0\u5F55\u4E0B\u6765\u3002\u4F60\u60F3\u5148\u4E86\u89E3\u4EC0\u4E48\uFF1F`}]),area=useRef(null),send=async e=>{if(e.preventDefault(),!input.trim()||!kbId)return;const q=input;setInput(""),setMessages(x=>[...x,{role:"user",text:q}]),setBusy(!0);try{const r=await ragforgeApi.chat(q,"web-user",kbId);setMessages(x=>[...x,{role:"assistant",traceId:r.trace_id,text:`${r.answer}

${r.sources.length} \u4E2A\u5F15\u7528\u6765\u6E90 \xB7 ${r.handoffs.length} \u6B21 Agent \u4EA4\u63A5 \xB7 ${r.iterations} \u6B21\u8FED\u4EE3`}])}catch(e2){setMessages(x=>[...x,{role:"assistant",text:`\u8C03\u7528\u5931\u8D25\uFF1A${String(e2)}`}])}finally{setBusy(!1)}},correct=async traceId=>{const correction=prompt("\u6B63\u786E\u7B54\u6848\u6216\u505A\u6CD5");if(!correction)return;const reason=prompt("\u7EA0\u6B63\u539F\u56E0\u6216\u4F9D\u636E")||"\u7528\u6237\u786E\u8BA4\u7EA0\u6B63",scope=prompt("\u9002\u7528\u8303\u56F4")||"\u5F53\u524D\u77E5\u8BC6\u5E93";try{await ragforgeApi.createFeedback({user_id:"web-user",knowledge_base_id:kbId,correction,reason,scope,confidence:.9,source_trace_id:traceId}),alert("\u7EA0\u6B63\u5DF2\u8FDB\u5165\u5F85\u5BA1\u6838\u961F\u5217")}catch(e){alert(`\u63D0\u4EA4\u5931\u8D25\uFF1A${String(e)}`)}};return<div className="task-page">
      <div className="task-topbar">
        <h1>构建企业知识库问答助手</h1>
        <div>
          <span className="model-status">
            <Dot/>多 Agent RAG
          </span>
          <button aria-label="任务菜单">•••</button>
        </div>
      </div>
      <section className="conversation">
        <div className="conversation-stream">
          {messages.map((m,i)=><article className={`message ${m.role}`}key={i}>
              {m.role==="assistant"&&<div className="assistant-label">
                  <span>R</span>
                  <b>RAGForge</b>
                </div>}
              <div className="message-body">
                {m.text.split(`
`).map((p,j)=>p?<p key={j}>{p}</p>:<br key={j}/>)}
                {m.traceId&&<div className="result-artifact">
                    <div>
                      <span className="artifact-icon">↗</span>
                      <div>
                        <b>查看本次执行链路</b>
                        <small>检索、重排与 Agent 交接详情</small>
                      </div>
                    </div>
                    <button onClick={()=>openTrace(m.traceId)}>打开</button>
                  </div>}
                {m.traceId&&<div className="message-actions">
                    <button>▢</button>
                    <button onClick={()=>correct(m.traceId)}>♡</button>
                    <button>↻</button>
                    <time>刚刚</time>
                  </div>}
              </div>
            </article>)}
          {busy&&<article className="message assistant thinking">
              <div className="assistant-label">
                <span>R</span>
                <b>RAGForge</b>
              </div>
              <div className="message-body">
                <p>
                  正在检索知识库并组织答案<span className="typing">•••</span>
                </p>
              </div>
            </article>}
        </div>
        <div className="composer-wrap">
          <form className="composer"onSubmit={send}>
            <textarea ref={area}rows={2}value={input}disabled={!kbId||busy}onChange={e=>setInput(e.target.value)}onKeyDown={e=>{e.key==="Enter"&&!e.shiftKey&&(e.preventDefault(),e.currentTarget.form?.requestSubmit())}}placeholder={kbId?"\u4ECA\u5929\u5E2E\u4F60\u505A\u4E9B\u4EC0\u4E48\uFF1F  @ \u5F15\u7528\u77E5\u8BC6\u5E93\uFF0C/ \u8C03\u7528\u6280\u80FD\u4E0E\u6307\u4EE4":"\u8BF7\u5148\u5728\u9879\u76EE\u4E2D\u521B\u5EFA\u77E5\u8BC6\u5E93"}/>
            <div className="composer-bottom">
              <button type="button"className="add-button"aria-label="添加附件">
                ＋
              </button>
              <div>
                <button type="button"className="model-button">
                  ◉ RAGForge Agent⌄
                </button>
                <button className="send-button"disabled={!input.trim()||busy||!kbId}aria-label="发送">
                  ↑
                </button>
              </div>
            </div>
          </form>
          <p className="disclaimer">内容由 AI 生成，请核实重要信息</p>
        </div>
      </section>
    </div>}function Memories({items,refresh,notify}){const review=async(id,accepted)=>{try{await ragforgeApi.reviewFeedback(id,accepted),await refresh(),notify(accepted?"\u5DF2\u5199\u5165\u771F\u5B9E\u8BB0\u5FC6":"\u5DF2\u62D2\u7EDD")}catch(e){notify(String(e))}};return<>
      <Head eye="FEEDBACK MEMORY"title="反馈记忆"sub="数据库真实记录；采纳会生成并保存 Embedding。"action={<button className="primary"onClick={refresh}>
            ↻ 刷新
          </button>}/>
      <div className="summary-strip">
        {[["\u603B\u6570",items.length],["\u5F85\u5BA1\u6838",items.filter(x=>x.state==="pending").length],["\u5DF2\u91C7\u7EB3",items.filter(x=>x.state==="accepted").length],["\u5DF2\u62D2\u7EDD",items.filter(x=>x.state==="rejected").length]].map(([n,v])=><div key={n}>
            <span>{n}</span>
            <strong>{v}</strong>
          </div>)}
      </div>
      <div className="feedback-list">
        {items.map(x=><article className="panel feedback-card"key={x.id}>
            <div className="feedback-main">
              <div className="quote-mark">“</div>
              <div>
                <span className={x.state==="accepted"?"success":"working"}>
                  {label(x.state)}
                </span>
                <h3>{x.correction}</h3>
                <p>{x.reason}</p>
                <div className="meta-row">
                  <span>{x.scope}</span>
                  <span>置信度 {x.confidence.toFixed(2)}</span>
                </div>
              </div>
            </div>
            {x.state==="pending"?<div className="feedback-actions">
                <button className="ghost"onClick={()=>review(x.id,!1)}>
                  忽略
                </button>
                <button className="primary"onClick={()=>review(x.id,!0)}>
                  采纳为记忆
                </button>
              </div>:<div className="memory-injected">{label(x.state)}</div>}
          </article>)}
        {!items.length&&<article className="panel">
            <p className="muted">暂无反馈记录。</p>
          </article>}
      </div>
    </>}function Evaluation({notify}){const[run,setRun]=useState(null),load=()=>ragforgeApi.evaluations().then(x=>{setRun(x[0]||null),notify(x.length?"\u5DF2\u8F7D\u5165\u771F\u5B9E\u8BC4\u6D4B":"\u6682\u65E0\u8BC4\u6D4B")}).catch(e=>notify(String(e)));useEffect(()=>{load()},[]);const rows=[["Recall@10","recall_at_k"],["Precision@10","precision_at_k"],["MRR","mrr"],["NDCG@10","ndcg_at_k"]];return<>
      <Head eye="RAG EVALUATION"title="评测中心"sub="仅展示持久化 EvalRun。"action={<button className="primary"onClick={load}>
            ↻ 刷新
          </button>}/>
      <section className="panel metric-table">
        <div className="data-table eval-head">
          <span>指标</span>
          <span>结果</span>
          <span>来源</span>
          <span>状态</span>
          <span>样本</span>
        </div>
        {rows.map(([n,k])=><div className="data-table"key={k}>
            <span>
              <b>{n}</b>
            </span>
            <span>
              <strong>{run?.metrics[k]?.toFixed(3)??"\u2014"}</strong>
            </span>
            <span>EvalRun</span>
            <span className={run?.passed?"up":"working"}>
              {run?run.passed?"PASS":"CHECK":"\u2014"}
            </span>
            <span>{run?.config.examples??"\u2014"}</span>
          </div>)}
      </section>
    </>}function Tracing({traceId}){const[data,setData]=useState([]),[selected,setSelected]=useState(0),[err,setErr]=useState(""),load=useCallback(()=>ragforgeApi.traces(traceId).then(x=>{setData(x.data||[]),setSelected(0),setErr("")}).catch(e=>{setData([]),setErr(String(e))}),[traceId]);useEffect(()=>{load()},[load]);const trace=data[selected],spans=trace?.spans||[],start=spans.length?Math.min(...spans.map(s=>s.startTime)):0,duration=Math.max(...spans.map(s=>s.duration),1);return<>
      <Head eye="OPENTELEMETRY"title="链路追踪"sub={traceId?`\u6309 Trace ID \u7CBE\u786E\u56DE\u653E\uFF1A${traceId}`:"\u5B9E\u65F6\u8BFB\u53D6\u672C\u673A Jaeger\u3002"}action={<button className="ghost"onClick={load}>
            ↻ 刷新
          </button>}/>
      {err&&<p className="working">{err}</p>}
      <div className="trace-layout">
        <section className="panel trace-list">
          {data.map((t,i)=><button key={t.traceID}className={selected===i?"trace-item selected":"trace-item"}onClick={()=>setSelected(i)}>
              <Dot/>
              <div>
                <b>{t.spans[0]?.operationName||"trace"}</b>
                <small>{t.traceID}</small>
              </div>
            </button>)}
        </section>
        <section className="panel waterfall">
          {spans.map((s,i)=><div className="span-row"key={s.spanID}>
              <div>
                <b>{s.operationName}</b>
                <small>{s.spanID.slice(0,10)}</small>
              </div>
              <div className="bar-track">
                <i style={{left:`${(s.startTime-start)/duration*100}%`,width:`${Math.max(2,s.duration/duration*100)}%`,background:["#165c43","#6c5c92","#287b91"][i%3]}}/>
              </div>
              <em>{(s.duration/1e3).toFixed(0)}ms</em>
            </div>)}
        </section>
      </div>
    </>}export{Home as default};
