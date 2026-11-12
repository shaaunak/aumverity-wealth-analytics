import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { ArrowLeft, ChevronRight, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { EChartBox } from "@/components/EChartBox";
import {
  fetchAccountDetails,
  fetchAccountTransactions,
  fetchClientDetail,
  fetchClients,
} from "@/lib/api";
import { formatCurrencyCompact, formatCurrencyExact, toNum } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ClientAccountExplorer() {
  const { clientId } = useParams<{ clientId: string }>();
  const [clientSearch, setClientSearch] = useState("");
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);

  const clientsQ = useQuery({
    queryKey: ["clients-list", clientSearch],
    queryFn: () => fetchClients({ search: clientSearch || undefined, pageSize: 25 }),
    enabled: !clientId,
  });

  const clientDetailQ = useQuery({
    queryKey: ["client-detail", clientId],
    queryFn: () => fetchClientDetail(clientId!),
    enabled: Boolean(clientId),
  });

  useEffect(() => {
    const firstAcct = clientDetailQ.data?.accounts[0]?.account_id;
    if (firstAcct && !selectedAccountId) {
      setSelectedAccountId(firstAcct);
    }
  }, [clientDetailQ.data, selectedAccountId]);

  const acctDetailQ = useQuery({
    queryKey: ["account-detail", selectedAccountId],
    queryFn: () => fetchAccountDetails(selectedAccountId!),
    enabled: Boolean(selectedAccountId),
  });

  const acctTxQ = useQuery({
    queryKey: ["account-txs", selectedAccountId],
    queryFn: () => fetchAccountTransactions(selectedAccountId!, 1, 20),
    enabled: Boolean(selectedAccountId),
  });

  const valChartOpt = useMemo<EChartsOption>(() => {
    const vals = acctDetailQ.data?.valuations ?? [];
    return {
      grid: { left: 56, right: 16, top: 16, bottom: 28 },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: vals.map((v) => v.as_of_date), axisLabel: { fontSize: 10, color: "#68777C" } },
      yAxis: { type: "value", scale: true, axisLabel: { fontSize: 10, color: "#68777C", formatter: (v: number) => formatCurrencyCompact(v) } },
      series: [
        {
          name: "Total AUM",
          type: "line",
          data: vals.map((v) => toNum(v.total_aum_usd)),
          lineStyle: { color: "#246B60", width: 2 },
          itemStyle: { color: "#246B60" },
        },
      ],
    };
  }, [acctDetailQ.data]);

  if (!clientId) {
    return (
      <div className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3 border-b border-[#E4E9E6] pb-4">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[#246B60]">
              Module 04 • Synthetic Client Identities
            </span>
            <h1 className="mt-0.5 text-2xl font-semibold text-[#122D33]">Clients &amp; Accounts</h1>
            <p className="text-sm text-[#68777C]">
              Investigate client households, account valuations, holdings, and transaction lineage.
            </p>
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-[#68777C]" />
            <input
              type="search"
              value={clientSearch}
              onChange={(e) => setClientSearch(e.target.value)}
              placeholder="Search client code or name..."
              className="w-60 rounded-md border border-[#E4E9E6] bg-white py-1.5 pl-8 pr-3 text-xs text-[#122D33]"
            />
          </div>
        </div>

        <div className="overflow-x-auto rounded-md border border-[#E4E9E6] bg-white">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[#68777C]">
              <tr>
                <th className="px-4 py-2.5">Client Code</th>
                <th className="px-4 py-2.5">Synthetic Name</th>
                <th className="px-4 py-2.5">Tier</th>
                <th className="px-4 py-2.5">Risk Profile</th>
                <th className="px-4 py-2.5 text-right">Accounts</th>
                <th className="px-4 py-2.5 text-right">Total AUM</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E4E9E6]">
              {clientsQ.data?.items.map((c) => (
                <tr key={c.client_id} className="hover:bg-[#F6F7F4]/70">
                  <td className="px-4 py-2.5">
                    <Link to={`/clients/${c.client_id}`} className="inline-flex items-center gap-1 font-mono font-semibold text-[#246B60] hover:underline">
                      {c.client_code} <ChevronRight className="h-3 w-3" />
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 font-medium text-[#122D33]">{c.full_name}</td>
                  <td className="px-4 py-2.5 text-[#68777C]">{c.client_tier}</td>
                  <td className="px-4 py-2.5 text-[#68777C]">{c.risk_profile}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{c.account_count}</td>
                  <td className="px-4 py-2.5 text-right font-mono font-semibold tabular-nums">{formatCurrencyExact(c.total_aum_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  const cl = clientDetailQ.data;
  const acct = acctDetailQ.data;

  return (
    <div className="space-y-6">
      <div className="border-b border-[#E4E9E6] pb-4">
        <Link to="/clients" className="inline-flex items-center gap-1 text-xs font-medium text-[#246B60] hover:underline">
          <ArrowLeft className="h-3.5 w-3.5" /> All Clients
        </Link>
        <h1 className="mt-1 text-2xl font-semibold text-[#122D33]">
          {cl ? `${cl.client_code} — ${cl.full_name}` : "Client Intelligence"}
        </h1>
        {cl && (
          <p className="text-xs text-[#68777C]">
            {cl.client_tier} • {cl.risk_profile} • Onboarded {cl.onboarding_date}
          </p>
        )}
      </div>

      {/* Account Selector */}
      <div className="flex flex-wrap gap-2">
        {cl?.accounts.map((a) => (
          <button
            key={a.account_id}
            type="button"
            onClick={() => setSelectedAccountId(a.account_id)}
            className={cn(
              "rounded-md border px-3.5 py-2 text-left text-xs transition-colors",
              selectedAccountId === a.account_id
                ? "border-[#246B60] bg-[#246B60]/8 text-[#122D33]"
                : "border-[#E4E9E6] bg-white text-[#68777C] hover:border-[#246B60]/50",
            )}
          >
            <div className="font-mono font-semibold text-[#122D33]">{a.account_number}</div>
            <div>{a.account_type} • {formatCurrencyCompact(a.latest_aum_usd)}</div>
          </button>
        ))}
      </div>

      {acct && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <section className="rounded-md border border-[#E4E9E6] bg-white p-5 lg:col-span-7">
            <h2 className="mb-1 text-sm font-semibold text-[#122D33]">Historical Account Valuation</h2>
            <p className="mb-3 text-xs text-[#68777C]">
              Advisor:{" "}
              <Link to={`/advisors/${acct.account.advisor_id}`} className="font-medium text-[#246B60] hover:underline">
                {acct.account.advisor_code} ({acct.account.advisor_name})
              </Link>{" "}
              • {acct.account.segment_name}
            </p>
            <EChartBox option={valChartOpt} height={240} ariaLabel="Account Historical Valuation" />
          </section>

          <section className="rounded-md border border-[#E4E9E6] bg-white p-5 lg:col-span-5">
            <h2 className="mb-3 text-sm font-semibold text-[#122D33]">Asset Composition (As of 2026-09-30)</h2>
            <div className="divide-y divide-[#E4E9E6] text-xs">
              {acct.positions.map((p) => (
                <div key={p.ticker} className="flex items-center justify-between py-2">
                  <div>
                    <p className="font-mono font-semibold text-[#122D33]">{p.ticker}</p>
                    <p className="text-[11px] text-[#68777C]">{p.asset_class_name}</p>
                  </div>
                  <div className="text-right font-mono tabular-nums">
                    <p className="font-medium text-[#122D33]">{formatCurrencyExact(p.market_value_usd)}</p>
                    <p className="text-[11px] text-[#68777C]">{Number(p.quantity).toFixed(2)} sh</p>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}

      {/* Source Transactions */}
      <section className="rounded-md border border-[#E4E9E6] bg-white">
        <div className="border-b border-[#E4E9E6] px-5 py-3.5">
          <h2 className="text-sm font-semibold text-[#122D33]">Source Transaction Events</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[#68777C]">
              <tr>
                <th className="px-4 py-2">Ref</th>
                <th className="px-4 py-2">Effective Date</th>
                <th className="px-4 py-2">Posted Date</th>
                <th className="px-4 py-2">Event Type</th>
                <th className="px-4 py-2">Classification</th>
                <th className="px-4 py-2 text-right">Net Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E4E9E6]">
              {acctTxQ.data?.items.map((tx) => (
                <tr key={tx.event_id} className="hover:bg-[#F6F7F4]/70">
                  <td className="px-4 py-2 font-mono text-[11px]">{tx.external_ref}</td>
                  <td className="px-4 py-2 tabular-nums">{tx.effective_date}</td>
                  <td className="px-4 py-2 tabular-nums">{tx.posted_date}</td>
                  <td className="px-4 py-2">{tx.event_type}</td>
                  <td className="px-4 py-2 text-[#68777C]">{tx.flow_classification}</td>
                  <td className="px-4 py-2 text-right font-mono tabular-nums">{formatCurrencyExact(tx.net_amount, true)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
