import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { dateTime, money, scoreClass } from "../lib/format";
import type { FlaggedTransaction } from "../lib/types";

const STATUSES = ["open", "confirmed", "dismissed"] as const;

export default function FlagQueue() {
  const [status, setStatus] = useState<(typeof STATUSES)[number]>("open");
  const [items, setItems] = useState<FlaggedTransaction[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .listFlags({ status, limit: 100 })
      .then((page) => {
        if (cancelled) return;
        const sorted = [...page.items].sort((a, b) => b.flag.fraud_score - a.flag.fraud_score);
        setItems(sorted);
        setTotal(page.total);
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [status]);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium">Flag queue</h2>
          <p className="text-sm text-slate-400">
            {loading ? "Loading..." : `${total} ${status} flag${total === 1 ? "" : "s"}`}
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-slate-800 p-1">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={`rounded-md px-3 py-1 text-sm capitalize ${
                status === s ? "bg-slate-800 text-slate-100" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="mt-4 rounded-lg border border-red-900 bg-red-950 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

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
            {items.map(({ flag, transaction: t }) => (
              <tr key={flag.id} className="hover:bg-slate-900">
                <td className="px-4 py-3">
                  <Link to={`/flags/${flag.id}`}>
                    <span
                      className={`inline-block rounded border px-2 py-0.5 font-mono text-xs ${scoreClass(flag.fraud_score)}`}
                    >
                      {flag.fraud_score.toFixed(2)}
                    </span>
                  </Link>
                </td>
                <td className="px-4 py-3 font-mono">{money(t.amount)}</td>
                <td className="px-4 py-3">
                  <Link to={`/flags/${flag.id}`} className="hover:text-sky-400">
                    {t.merchant_name}
                  </Link>
                  <span className="ml-2 text-xs text-slate-500">
                    {t.merchant_category} · {t.channel}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-300">
                  {t.city}, {t.country}
                </td>
                <td className="px-4 py-3 text-slate-300">{dateTime(t.occurred_at)}</td>
                <td className="px-4 py-3 font-mono text-slate-400">{t.account_id}</td>
              </tr>
            ))}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No {status} flags.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}