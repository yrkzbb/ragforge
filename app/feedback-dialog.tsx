"use client";

import { FormEvent, useEffect, useState } from "react";
import { ragforgeApi } from "./ragforge-api";

type Target = { traceId: string; kbId: string; question: string; answer: string };

export default function FeedbackDialogHost() {
  const [target, setTarget] = useState<Target | null>(null);
  const [correction, setCorrection] = useState("");
  const [reason, setReason] = useState("");
  const [scope, setScope] = useState("当前知识库");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const open = (event: Event) => {
      setTarget((event as CustomEvent<Target>).detail);
      setCorrection("");
      setReason("");
      setScope("当前知识库");
      setError("");
    };
    window.addEventListener("ragforge:feedback", open);
    return () => window.removeEventListener("ragforge:feedback", open);
  }, []);

  if (!target) return null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!correction.trim() || !reason.trim()) {
      setError("请填写正确答案和纠正依据");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await ragforgeApi.createFeedback({
        user_id: "web-user",
        knowledge_base_id: target.kbId,
        correction: correction.trim(),
        reason: reason.trim(),
        scope: scope.trim() || "当前知识库",
        confidence: 0.9,
        source_trace_id: target.traceId,
      });
      setTarget(null);
      window.dispatchEvent(new CustomEvent("ragforge:feedback-created"));
      window.dispatchEvent(new CustomEvent("ragforge:navigate", { detail: { section: "反馈记忆" } }));
      setTimeout(() => {
        const refreshButton = Array.from(document.querySelectorAll<HTMLButtonElement>(".content header button")).find((button) => button.textContent?.includes("刷新"));
        refreshButton?.click();
      }, 100);
    } catch (submissionError) {
      setError(`提交失败：${String(submissionError)}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="feedback-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="feedback-title"
      onMouseDown={(event) => event.target === event.currentTarget && setTarget(null)}
    >
      <form className="feedback-dialog" onSubmit={submit}>
        <header>
          <div><small>FEEDBACK MEMORY</small><h2 id="feedback-title">纠正这次回答</h2></div>
          <button type="button" onClick={() => setTarget(null)} aria-label="关闭">×</button>
        </header>
        <div className="feedback-context">
          <b>原问题</b><p>{target.question || "未记录"}</p>
          <b>原回答</b><p>{target.answer}</p>
        </div>
        <label>正确答案或做法<textarea autoFocus rows={4} value={correction} onChange={(event) => setCorrection(event.target.value)} placeholder="填写系统以后应采用的正确回答" /></label>
        <label>纠正原因或依据<textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="例如：依据最新制度第 3 条" /></label>
        <label>适用范围<input value={scope} onChange={(event) => setScope(event.target.value)} /></label>
        {error && <p className="feedback-error">{error}</p>}
        <footer><button type="button" className="ghost" onClick={() => setTarget(null)}>取消</button><button className="primary" disabled={saving}>{saving ? "提交中…" : "提交待审核"}</button></footer>
      </form>
    </div>
  );
}
