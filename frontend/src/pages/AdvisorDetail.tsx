import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";

import { EChartBox } from "@/components/EChartBox";
import { useFilters } from "@/context/FilterContext";
import { fetchAdvisorFlows, fetchAdvisorSummary } from "@/lib/api";
import { formatCurrencyCompact, formatCurrencyExact, toNum } from "@/lib/format";

export function AdvisorDetail() {
  const { advisorId } = useParams<{ advisorId: string }>();
  const { period } = useFilters();

  const summaryQ = useQuery({
    queryKey: ["advisor-summary", advisorId, period.quarterCode],
    queryFn: () => fetchAdvisorSummary(advisorId!, period.quarterCode),
    enabled: Boolean(advisorId),
  });

  const flowsQ = useQuery({
    queryKey: ["advisor-flows", advisorId],
    queryFn: () => fetchAdvisorFlows(advisorId!),
    enabled: Boolean(advisorId),
  });

  const perf = summaryQ.data?.performance;

  const trendOpt = useMemo<EChartsOption>(() => {
    const rows = (flowsQ.data ?? []).filter((r) => r.period_code.includes("-"));
    return {
      grid: { left: 56, right: 16, top: 24, bottom: 32 },
      legend: { top: 0, right: 0, textStyle: { color: "#68777C", fontSize: 11 } },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: rows.map((r) => r.period_code), axisLabel: { fontSize: 10, color: "#68777C" } },
      yAxis: { type: "value", axisLabel: { fontSize: 10, color: "#68777C", formatter: (v: number) => formatCurrencyCompact(v) } },
      series: [
        { name: "Firm-Style NNA", type: "bar", data: rows.map((r) => toNum(r.firm_style_nna_usd)), itemStyle: { color: "#246B60" } },
        { name: "External Net Flows", type: "line", data: rows.map((r) => toNum(r.external_net_flows_usd)), lineStyle: { color: "#C59B64" }, itemStyle: { color: "#C59B64" } },
      ],
    };
  }, [flowsQ.data]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b border-[#E4E9E6] pb-4">
        <div>
          <Link to="/advisors" className="inline-flex items-center gap-1 text-xs font-medium text-[#246B60] hover:underline">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Advisor Explorer
          </Link>
          <h1 className="mt-1 text-2xl font-semibold text-[#122D33]">
            {perf ? `${perf.advisor_code} — ${perf.advisor_name}` : "Advisor Detail"}
          </h1>
          <p className="text-sm text-[#68777C]">{perf?.segment_name ?? ""} • {period.quarterCode}</p>
        </div>
        {perf && (
          <div className="inline-flex items-center gap-1.5 rounded border border-[#E4E9E6] bg-white px-3 py-1.5 text-xs font-medium text-[#246B60]">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Residual: {formatCurrencyExact(perf.unexplained_residual_usd, true)}
          </div>
        )}
      </div>

      {perf && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {[
            ["Opening Assets", formatCurrencyCompact(perf.opening_assets_usd)],
            ["Closing Assets", formatCurrencyCompact(perf.closing_assets_usd)],
            ["Gross Inflows", formatCurrencyCompact(perf.gross_inflows_usd, true)],
            ["Gross Outflows", formatCurrencyCompact(-toNum(perf.gross_outflows_usd))],
            ["Firm-Style NNA", formatCurrencyCompact(perf.firm_style_nna_usd, true)],
            ["Market Movement", formatCurrencyCompact(perf.market_movement_usd, true)],
          ].map(([label, val]) => (
            <div key={label} className="rounded-md border border-[#E4E9E6] bg-white p-3.5">
              <p className="text-xs text-[#68777C]">{label}</p>
              <p className="mt-1 text-lg font-semibold tabular-nums text-[#122D33]">{val}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="rounded-md border border-[#E4E9E6] bg-white p-5 lg:col-span-7">
          <h2 className="mb-3 text-sm font-semibold text-[#122D33]">Historical Flow Trend</h2>
          <EChartBox option={trendOpt} height={260} ariaLabel="Advisor Flow Trend" />
        </section>

        <section className="rounded-md border border-[#E4E9E6] bg-white p-5 lg:col-span-5">
          <h2 className="mb-3 text-sm font-semibold text-[#122D33]">Account-Type Distribution</h2>
          <div className="divide-y divide-[#E4E9E6] text-xs">
            {summaryQ.data?.account_distribution.map((a) => (
              <div key={a.account_type} className="flex items-center justify-between py-2.5">
                <div>
                  <p className="font-medium text-[#122D33]">{a.account_type}</p>
                  <p className="text-[11px] text-[#68777C]">{a.account_count} accounts</p>
                </div>
                <span className="font-mono font-semibold tabular-nums text-[#122D33]">
                  {formatCurrencyExact(a.total_aum_usd)}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="rounded-md border border-[#E4E9E6] bg-white">
        <div className="border-b border-[#E4E9E6] px-5 py-3.5">
          <h2 className="text-sm font-semibold text-[#122D33]">Top Contributing Client Households</h2>
          <p className="text-xs text-[#68777C]">Click any client to inspect accounts, positions, and transactions.</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[#68777C]">
              <tr>
                <th className="px-4 py-2.5">Client</th>
                <th className="px-4 py-2.5">Tier</th>
                <th className="px-4 py-2.5 text-right">Total AUM</th>
                <th className="px-4 py-2.5 text-right">Q3 Outflows</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E4E9E6]">
              {summaryQ.data?.top_clients.map((cl) => (
                <tr key={cl.client_id} className="hover:bg-[#F6F7F4]/70">
                  <td className="px-4 py-2.5">
                    <Link to={`/clients/${cl.client_id}`} className="font-medium text-[#246B60] hover:underline">
                      {cl.client_code} — {cl.full_name}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-[#68777C]">{cl.client_tier}</td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums">{formatCurrencyExact(cl.total_aum_usd)}</td>
                  <td className="px-4 py-2.5 text-right font-mono tabular-nums text-[#C45B51]">
                    {formatCurrencyExact(-toNum(cl.q3_outflows_usd))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
