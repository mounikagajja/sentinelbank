import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateTime, money, scoreClass } from "../lib/format";
import type { FlaggedTransaction, FlagExplanation, Transaction } from "../lib/types";

const WINDOW_MS = 24 * 60 * 60 * 1000;

export default function FlagDetail() {
  const { flagId } = useParams();
  const id = Number(flagId);
  const { user } = useAuth();
  const isAnalyst = user?.role === "analyst";

  const [item, setItem] = useState<FlaggedTransaction | null>(null);
  const [explanation, setExplanation] = useState<FlagExplanation | null>(null);
  const [nearby, setNearby] = useState<Transaction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const flagged = await api.getFlag(id);
      setItem(flagged);

      const [explained, page] = await Promise.all([
        api.explainFlag(id),
        api.listTransactions(flagged.transaction.account_id, 200),
      ]);
      setExplanation(explained);

      const center = new Date(flagged.transaction.occurred_at).getTime();
      setNearby(
        page.items
          .filter((t) => Math.abs(new Date(t.occurred_at).getTime() - center) <= WINDOW_MS)
          .sort((a, b) => a.occurred_at.localeCompare(b.occurred_at)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load flag");
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function review(status: "confirmed" | "dismissed") {
    setBusy(true);
    setError(null);
    try {
      await api.reviewFlag(id, status, note || undefined);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed");
    } finally {
      setBusy(false);
    }
  }

  if (error && !item) {
    return <p className="text-red-300">{error}</p>;
  }
  if (!item) {
    return <p className="text-slate-400">Loading...</p>;
  }

  const { flag, transaction: t } = item;
  const maxWeight = Math.max(
    ...(explanation?.top_contributions.map((c) => Math.abs(c.contribution)) ?? [1]),
  );

  return (
    <div className="space-y-6">
      <Link to="/flags" className="text-sm text-slate-400 hover:text-slate-200">
        Back to queue
      </Link>

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm text-slate-400">
              Flag {flag.id} · Transaction {t.id} · Account {t.account_id}
            </p>
            <h2 className="mt-1 text-2xl font-semibold">
              {money(t.amount)} at {t.merchant_name}
            </h2>
            <p className="mt-1 text-slate-300">
              {t.merchant_category} · {t.channel} · {t.city}, {t.country} ·{" "}
              {dateTime(t.occurred_at)}
            </p>
          </div>
          <div className="text-right">
            <span
              className={`inline-block rounded border px-3 py-1 font-mono text-lg ${scoreClass(flag.fraud_score)}`}
            >
              {flag.fraud_score.toFixed(4)}
            </span>
            <p className="mt-1 text-xs text-slate-500">model {flag.model_version}</p>
            <p className="mt-1 text-sm capitalize text-slate-300">{flag.status}</p>
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h3 className="font-medium">Why the model flagged it</h3>
          <p className="mt-1 text-xs text-slate-500">
            Per-feature contribution to this prediction, in log-odds. Red raises the score, blue
            lowers it. These explain this one transaction, not general rules.
          </p>
          {!explanation ? (
            <p className="mt-4 text-sm text-slate-400">Loading explanation...</p>
          ) : (
            <ul className="mt-4 space-y-3">
              {explanation.top_contributions.map((c) => (
                <li key={c.feature}>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-300">{c.feature}</span>
                    <span className="font-mono text-slate-400">
                      {c.value.toPrecision(4)} · {c.contribution > 0 ? "+" : ""}
                      {c.contribution.toFixed(3)}
                    </span>
                  </div>
                  <div className="mt-1 h-2 rounded bg-slate-800">
                    <div
                      className={`h-2 rounded ${c.contribution > 0 ? "bg-red-500" : "bg-sky-500"}`}
                      style={{ width: `${(Math.abs(c.contribution) / maxWeight) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <h3 className="font-medium">Account activity within 24 hours</h3>
          <ul className="mt-4 space-y-2 text-sm">
            {nearby.map((n) => (
              <li
                key={n.id}
                className={`flex justify-between rounded px-2 py-1 ${
                  n.id === t.id ? "bg-slate-800 ring-1 ring-sky-600" : ""
                }`}
              >
                <span className="text-slate-400">{dateTime(n.occurred_at)}</span>
                <span className="text-slate-300">{n.merchant_name}</span>
                <span className="font-mono">{money(n.amount)}</span>
              </li>
            ))}
            {nearby.length === 0 && <li className="text-slate-500">No nearby activity.</li>}
          </ul>
        </section>
      </div>

      <section className="rounded-xl border border-slate-800 bg-slate-900 p-6">
        <h3 className="font-medium">Decision</h3>
        {flag.status !== "open" ? (
          <p className="mt-2 text-sm text-slate-300">
            This flag was {flag.status}
            {flag.reviewed_at ? ` on ${dateTime(flag.reviewed_at)}` : ""}.
          </p>
        ) : !isAnalyst ? (
          <p className="mt-2 text-sm text-slate-400">
            Only analysts can close a flag. You are signed in as a viewer.
          </p>
        ) : (
          <>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional note, for example: customer confirmed they made the purchase"
              maxLength={500}
              rows={2}
              className="mt-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm outline-none focus:border-sky-500"
            />
            <div className="mt-3 flex gap-3">
              <button
                onClick={() => review("confirmed")}
                disabled={busy}
                className="rounded-lg bg-red-700 px-4 py-2 text-sm font-medium hover:bg-red-600 disabled:bg-slate-700"
              >
                Confirm fraud
              </button>
              <button
                onClick={() => review("dismissed")}
                disabled={busy}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium hover:bg-slate-800 disabled:opacity-50"
              >
                Dismiss as false alarm
              </button>
            </div>
          </>
        )}
        {error && item && <p className="mt-3 text-sm text-red-300">{error}</p>}
      </section>
    </div>
  );
}