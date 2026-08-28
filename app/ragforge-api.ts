const baseUrl = process.env.NEXT_PUBLIC_RAGFORGE_API_URL || "";
export const configuredKnowledgeBaseId = process.env.NEXT_PUBLIC_RAGFORGE_KB_ID || "";
async function call<T>(path:string,options?:RequestInit):Promise<T>{
  if(!baseUrl) throw new Error("API_NOT_CONFIGURED");
  const response=await fetch(`${baseUrl}${path}`,{...options,headers:{"Content-Type":"application/json",...(options?.headers||{})}});
  if(!response.ok) throw new Error((await response.text())||`HTTP ${response.status}`);
  return response.json() as Promise<T>;
}
export const ragforgeApi={
  health:()=>call<{status:string}>("/health"),
  search:(query:string,knowledgeBaseId=configuredKnowledgeBaseId)=>call<{rewritten_query:string;results:Array<{id:string;text:string;breadcrumb:string;score:number;bm25_score:number;dense_score:number;rerank_score:number}>}>("/api/v1/search",{method:"POST",body:JSON.stringify({query,knowledge_base_id:knowledgeBaseId,top_k:10,retrieve_k:30})}),
  chat:(message:string,userId="web-user",knowledgeBaseId=configuredKnowledgeBaseId)=>call<{answer:string;sources:Array<{chunk_id:string;breadcrumb:string;score:number}>;usage:Record<string,number>;trace_id:string}>("/api/v1/chat",{method:"POST",body:JSON.stringify({message,user_id:userId,knowledge_base_id:knowledgeBaseId})}),
  compile:(knowledgeBaseId=configuredKnowledgeBaseId)=>call<{job_id:string;status:string}>(`/api/v1/knowledge-bases/${knowledgeBaseId}/compile`,{method:"POST"}),
  evaluations:()=>call<Array<{id:string;dataset_name:string;config:{examples:number};metrics:Record<string,number>;passed:boolean;created_at:string}>>("/api/v1/evaluations"),
  traces:()=>call<{data:Array<{traceID:string;spans:Array<{spanID:string;operationName:string;startTime:number;duration:number;tags:Array<{key:string;value:unknown}>}>}>}>("/api/v1/traces?limit=20"),
  feedback:()=>call<Array<{id:string;correction:string;reason:string;scope:string;confidence:number;state:string}>>("/api/v1/feedback"),
};
