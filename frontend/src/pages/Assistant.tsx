import { useEffect, useRef, useState, type FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { api } from "../lib/api";
import type { PendingAction } from "../lib/types";

interface Message {
  role: "user" | "assistant" | "system";
  text: string;
}

const SUGGESTIONS = [
  "What open fraud flags need review?",
  "Explain flag 18. Is it really fraud?",
  "Freeze account 887, the card was reported stolen.",
];

export default function Assistant() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [threadId, setThreadId] = useState<string | undefined>();
  const [pending, setPending] = useState<PendingAction[]>([]);
  const [pendingReason, setPendingReason] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending, busy]);

  function add(role: Message["role"], text: string) {
    setMessages((prev) => [...prev, { role, text }]);
  }

  function handleResponse(res: Awaited<ReturnType<typeof api.chat>>) {
    setThreadId(res.thread_id);
    if (res.awaiting_approval) {
      setPending(res.actions);
      setPendingReason(res.reason);
    } else {
      setPending([]);
      setPendingReason(null);
      if (res.reply) add("assistant", res.reply);
    }
  }

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy || pending.length) return;
    add("user", message);
    setInput("");
    setBusy(true);
    try {
      handleResponse(await api.chat(message, threadId));
    } catch (err) {
      add("system", err instanceof Error ? err.message : "The assistant failed to respond.");
    } finally {
      setBusy(false);
    }
  }

  async function decide(approved: boolean) {
    if (!threadId) return;
    const decisions = pending.map((a) => ({
      action_id: a.id,
      approved,
      note: approved ? undefined : notes[a.id] || "Declined by analyst",
    }));
    add(
      "system",
      `${approved ? "Approved" : "Declined"}: ${pending.map((a) => a.summary).join(", ")}`,
    );
    setPending([]);
    setBusy(true);
    try {
      handleResponse(await api.approve(threadId, decisions));
    } catch (err) {
      add("system", err instanceof Error ? err.message : "Approval failed.");
    } finally {
      setBusy(false);
      setNotes({});
    }
  }

  function reset() {
    setMessages([]);
    setThreadId(undefined);
    setPending([]);
    setPendingReason(null);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    send(input);
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-8rem)] max-w-3xl flex-col">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">Fraud assistant</h2>
          <p className="text-sm text-slate-400">
            Investigates freely. Any change to an account or flag waits for your approval.
          </p>
        </div>
        {messages.length > 0 && (
          <button onClick={reset} className="text-sm text-slate-400 hover:text-slate-200">
            New conversation
          </button>
        )}
      </div>

      <div className="mt-4 flex-1 space-y-4 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900 p-4">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-slate-500">Try one of these:</p>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="block w-full rounded-lg border border-slate-800 px-3 py-2 text-left text-sm text-slate-300 hover:border-slate-600"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
            {m.role === "system" ? (
              <p className="text-center text-xs text-slate-500">{m.text}</p>
            ) : (
              <div
                className={`max-w-[85%] rounded-xl px-4 py-2 text-sm ${
                  m.role === "user" ? "bg-sky-700 text-white" : "bg-slate-800 text-slate-100"
                }`}
              >
                {m.role === "user" ? (
                  <span className="whitespace-pre-wrap">{m.text}</span>
                ) : (
                  <div className="markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {pending.length > 0 && (
          <div className="rounded-xl border border-amber-800 bg-amber-950/40 p-4">
            <p className="text-sm font-medium text-amber-200">Approval needed</p>
            <p className="mt-1 text-xs text-amber-300/80">{pendingReason}</p>
            {pending.map((a) => (
              <div key={a.id} className="mt-3 rounded-lg bg-slate-950 p-3">
                <p className="font-mono text-sm text-slate-100">{a.tool}</p>
                <ul className="mt-1 text-sm text-slate-300">
                  {Object.entries(a.args).map(([k, v]) => (
                    <li key={k}>
                      <span className="text-slate-500">{k}:</span> {String(v)}
                    </li>
                  ))}
                </ul>
                <input
                  value={notes[a.id] ?? ""}
                  onChange={(e) => setNotes((n) => ({ ...n, [a.id]: e.target.value }))}
                  placeholder="Reason if declining (optional)"
                  className="mt-2 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-sm outline-none focus:border-sky-500"
                />
              </div>
            ))}
            <div className="mt-3 flex gap-3">
              <button
                onClick={() => decide(true)}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-amber-500"
              >
                Approve
              </button>
              <button
                onClick={() => decide(false)}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm hover:bg-slate-800"
              >
                Decline
              </button>
            </div>
          </div>
        )}

        {busy && <p className="text-sm text-slate-500">Thinking...</p>}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={onSubmit} className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={busy || pending.length > 0}
          placeholder={
            pending.length ? "Approve or decline the pending action first" : "Ask about a flag or account"
          }
          maxLength={2000}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={busy || !input.trim() || pending.length > 0}
          className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium hover:bg-sky-500 disabled:bg-slate-700"
        >
          Send
        </button>
      </form>
    </div>
  );
}