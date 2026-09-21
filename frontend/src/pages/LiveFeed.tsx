import { useEffect, useState } from "react";

import { getToken } from "../lib/api";
import { dateTime, money, scoreClass } from "../lib/format";

interface ScoreEvent {
  transaction_id: number;
  account_id: number;
  amount: number;
  merchant_name: string;
  merchant_category: string;
  channel: string;
  city: string;
  country: string;
  occurred_at: string;
  score: number;
  flagged: boolean;
  model_version: string;
}

const MAX_ROWS = 100;

export default function LiveFeed() {
  const [events, setEvents] = useState<ScoreEvent[]>([]);
  const [status, setStatus] = useState<"connecting" | "live" | "disconnected">("connecting");
  const [counts, setCounts] = useState({ seen: 0, flagged: 0 });

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    const source = new EventSource(`/api/v1/stream/scores?token=${encodeURIComponent(token)}`);
    source.onopen = () => setStatus("live");
    source.onerror = () => setStatus("disconnected");
    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as ScoreEvent;
      setEvents((prev) => [event, ...prev].slice(0, MAX_ROWS));
      setCounts((c) => ({ seen: c.seen + 1, flagged: c.flagged + (event.flagged ? 1 : 0) }));
    };

    return () => source.close();
  }, []);

  const dot =
    status === "live" ? "bg-emerald-500" : status === "connecting" ? "bg-amber-500" : "bg-red-500";

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">Live scoring</h2>
          <p className="text-sm text-slate-400">
            Every transaction the consumer scores, as it happens.
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-slate-400">
            {counts.seen} scored · <span className="text-red-300">{counts.flagged} flagged</span>
          </span>
          <span className="flex items-center gap-2 text-slate-300">
            <span className={`h-2 w-2 rounded-full ${dot}`} />
            {status}
          </span>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900 text-slate-400">
            <tr>
              <th className="px-4 py-3 font-medium">Score</th>
              <th className="px-4 py-3 font-medium">Amount</th>
              <th className="px-4 py-3 font-medium">Merchant</th>
              <th className="px-4 py-3 font-medium">Location</th>
              <th className="px-4 py-3 font-medium">When</th>
              <th className="px-4 py-3 font-medium">Account</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {events.map((e) => (
              <tr key={e.transaction_id} className={e.flagged ? "bg-red-950/30" : ""}>
                <td className="px-4 py-2">
                  <span
                    className={`inline-block rounded border px-2 py-0.5 font-mono text-xs ${scoreClass(e.score)}`}
                  >
                    {e.score.toFixed(2)}
                  </span>
                </td>
                <td className="px-4 py-2 font-mono">{money(e.amount)}</td>
                <td className="px-4 py-2">
                  {e.merchant_name}
                  <span className="ml-2 text-xs text-slate-500">
                    {e.merchant_category} · {e.channel}
                  </span>
                </td>
                <td className="px-4 py-2 text-slate-300">
                  {e.city}, {e.country}
                </td>
                <td className="px-4 py-2 text-slate-300">{dateTime(e.occurred_at)}</td>
                <td className="px-4 py-2 font-mono text-slate-400">{e.account_id}</td>
              </tr>
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  Waiting for transactions. Start the consumer and the producer to see them here.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}