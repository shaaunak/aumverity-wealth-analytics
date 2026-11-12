import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { ArrowDownRight, ArrowUpRight, GitCompare, TrendingUp } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { EChartBox } from "@/components/EChartBox";
import { useFilters } from "@/context/FilterContext";
import {
  fetchAdvisors,
  fetchFlows,
  fetchPeriodCompare,
  fetchSegments,
} from "@/lib/api";
import {
  formatCurrencyCompact,
  formatCurrencyExact,
  formatPct,
  toNum,
} from "@/lib/format";

export function FlowAnalytics() {
  const { period, segmentId } = useFilters();
  const [currentQuarter, setCurrentQuarter] = useState("2026-Q3");
  const [priorQuarter, setPriorQuarter] = useState("2026-Q2");

  const compareQuery = useQuery({
    queryKey: ["period-compare", currentQuarter, priorQuarter],
    queryFn: () => fetchPeriodCompare(currentQuarter, priorQuarter),
  });

  const flowsQuery = useQuery({
    queryKey: ["flows", period.startDate, period.endDate, segmentId],
    queryFn: () =>
      fetchFlows({
        startDate: period.startDate,
        endDate: period.endDate,
        segmentId: segmentId || undefined,
      }),
  });

  const segmentsQuery = useQuery({
    queryKey: ["segments", period.quarterCode],
    queryFn: () => fetchSegments(period.quarterCode),
  });

  const advisorsQuery = useQuery({
    queryKey: ["advisors-outflow-top", period.quarterCode, segmentId],
    queryFn: () =>
      fetchAdvisors({
        quarterCode: period.quarterCode,
        segmentId: segmentId || undefined,
        sortBy: "gross_outflows_usd",
        sortDir: "desc",
        page: 1,
        pageSize: 40,
      }),
  });

  const flows = flowsQuery.data ?? [];
  const segments = segmentsQuery.data ?? [];
  const advisors = advisorsQuery.data?.items ?? [];

  const flowTrendOption: EChartsOption = useMemo(() => {
    const labels = flows.map((f) => f.period_code);
    return {
      tooltip: { trigger: "axis" },
      legend: {
        data: [
          "External Net Flows",
          "Firm-Style NNA",
          "Market Movement",
          "Fees & Commissions",
        ],
        bottom: 0,
        textStyle: { color: "#68777C", fontSize: 11 },
      },
      grid: { top: 20, left: 56, right: 20, bottom: 48 },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: "#68777C", fontSize: 11 },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: "#68777C",
          fontSize: 11,
          formatter: (v: number) => formatCurrencyCompact(v),
        },
        splitLine: { lineStyle: { color: "#E4E9E6" } },
      },
      series: [
        {
          name: "External Net Flows",
          type: "bar",
          data: flows.map((f) => toNum(f.external_net_flows_usd)),
          itemStyle: { color: "#122D33", borderRadius: [2, 2, 0, 0] },
        },
        {
          name: "Firm-Style NNA",
          type: "bar",
          data: flows.map((f) => toNum(f.firm_style_nna_usd)),
          itemStyle: { color: "#246B60", borderRadius: [2, 2, 0, 0] },
        },
        {
          name: "Market Movement",
          type: "line",
          smooth: true,
          data: flows.map((f) => toNum(f.market_driven_movement_usd)),
          itemStyle: { color: "#C59B64" },
          lineStyle: { width: 2 },
        },
        {
          name: "Fees & Commissions",
          type: "line",
          smooth: true,
          data: flows.map((f) => -Math.abs(toNum(f.fees_and_commissions_usd))),
          itemStyle: { color: "#C45B51" },
          lineStyle: { width: 1.5, type: "dashed" },
        },
      ],
    };
  }, [flows]);

  const positiveAumNegativeNnaAdvisors = useMemo(
    () =>
      advisors.filter(
        (a) =>
          toNum(a.aum_growth_usd) > 0 && toNum(a.firm_style_nna_usd) < 0,
      ),
    [advisors],
  );

  const totalOutflows = useMemo(
    () => advisors.reduce((acc, a) => acc + Math.abs(toNum(a.gross_outflows_usd)), 0),
    [advisors],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-[#122D33]">
              Flow &amp; Period Compare Analytics
            </h1>
            <span className="rounded border border-[#246B60]/30 bg-[#246B60]/10 px-2 py-0.5 text-[11px] font-medium text-[#246B60]">
              SYNTHETIC
            </span>
          </div>
          <p className="mt-1 text-sm text-[#68777C]">
            Quarter-over-quarter attribution, External Net Flows vs. Firm-Style NNA,
            outflow concentration, and market-masked attrition detection.
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-lg border border-[#E4E9E6] bg-white px-3 py-2 text-xs">
          <GitCompare className="h-3.5 w-3.5 text-[#246B60]" />
          <span className="text-[#68777C]">Compare</span>
          <select
            value={currentQuarter}
            onChange={(e) => setCurrentQuarter(e.target.value)}
            className="rounded border border-[#E4E9E6] bg-[#F6F7F4] px-2 py-1 font-medium text-[#122D33]"
          >
            <option value="2026-Q3">2026-Q3</option>
            <option value="2026-Q2">2026-Q2</option>
            <option value="2026-Q1">2026-Q1</option>
          </select>
          <span className="text-[#68777C]">vs</span>
          <select
            value={priorQuarter}
            onChange={(e) => setPriorQuarter(e.target.value)}
            className="rounded border border-[#E4E9E6] bg-[#F6F7F4] px-2 py-1 font-medium text-[#122D33]"
          >
            <option value="2026-Q2">2026-Q2</option>
            <option value="2026-Q1">2026-Q1</option>
            <option value="2025-Q4">2025-Q4</option>
          </select>
        </div>
      </div>

      {/* Period Compare Table & Ranking Shifts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-lg border border-[#E4E9E6] bg-white p-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[#122D33]">
              Period Comparison: {currentQuarter} vs {priorQuarter}
            </h2>
            <span className="text-[11px] text-[#68777C]">
              All figures in USD · Exact SQL aggregation
            </span>
          </div>

          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[11px] font-semibold uppercase tracking-wider text-[#68777C]">
                <tr>
                  <th className="px-3 py-2.5">Metric</th>
                  <th className="px-3 py-2.5 text-right">{priorQuarter}</th>
                  <th className="px-3 py-2.5 text-right">{currentQuarter}</th>
                  <th className="px-3 py-2.5 text-right">Abs Change</th>
                  <th className="px-3 py-2.5 text-right">% Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E4E9E6]">
                {compareQuery.isLoading && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-[#68777C]">
                      Computing period comparison...
                    </td>
                  </tr>
                )}
                {(compareQuery.data?.metrics ?? []).map((row) => {
                  const chg = toNum(row.abs_change_usd);
                  return (
                    <tr key={row.metric} className="hover:bg-[#F6F7F4]">
                      <td className="px-3 py-2.5 font-medium text-[#122D33]">
                        {row.metric}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-[#68777C]">
                        {formatCurrencyExact(row.prior_usd)}
                      </td>
                      <td className="px-3 py-2.5 text-right font-medium tabular-nums text-[#122D33]">
                        {formatCurrencyExact(row.current_usd)}
                      </td>
                      <td
                        className={`px-3 py-2.5 text-right font-semibold tabular-nums ${
                          chg < 0 ? "text-[#C45B51]" : "text-[#246B60]"
                        }`}
                      >
                        {formatCurrencyExact(row.abs_change_usd, true)}
                      </td>
                      <td className="px-3 py-2.5 text-right tabular-nums text-[#122D33]">
                        {row.pct_change === null
                          ? "N/A"
                          : formatPct(row.pct_change, true)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {compareQuery.data?.methodology && (
            <p className="mt-3 rounded border border-[#E4E9E6] bg-[#F6F7F4] px-3 py-2 text-[11px] text-[#68777C]">
              <strong className="text-[#122D33]">Comparison Methodology:</strong>{" "}
              {compareQuery.data.methodology}
            </p>
          )}
        </div>

        {/* Top Advisor Ranking Shifts */}
        <div className="rounded-lg border border-[#E4E9E6] bg-white p-5">
          <h2 className="text-sm font-semibold text-[#122D33]">
            Top Advisor NNA Ranking Shifts
          </h2>
          <p className="mt-0.5 text-xs text-[#68777C]">
            Rank movement between {priorQuarter} and {currentQuarter}
          </p>
          <div className="mt-3 divide-y divide-[#E4E9E6]">
            {(compareQuery.data?.ranking_changes ?? []).slice(0, 8).map((r) => (
              <div
                key={r.advisor_code}
                className="flex items-center justify-between py-2 text-xs"
              >
                <div>
                  <p className="font-medium text-[#122D33]">{r.advisor_name}</p>
                  <p className="font-mono text-[11px] text-[#68777C]">
                    {r.advisor_code} · #{r.prior_rank} → #{r.current_rank}
                  </p>
                </div>
                <div className="text-right">
                  <span
                    className={`inline-flex items-center gap-0.5 font-semibold tabular-nums ${
                      r.rank_improvement > 0
                        ? "text-[#246B60]"
                        : r.rank_improvement < 0
                          ? "text-[#C45B51]"
                          : "text-[#68777C]"
                    }`}
                  >
                    {r.rank_improvement > 0 ? (
                      <ArrowUpRight className="h-3.5 w-3.5" />
                    ) : r.rank_improvement < 0 ? (
                      <ArrowDownRight className="h-3.5 w-3.5" />
                    ) : null}
                    {r.rank_improvement > 0
                      ? `+${r.rank_improvement}`
                      : r.rank_improvement}
                  </span>
                  <p className="text-[11px] tabular-nums text-[#68777C]">
                    {formatCurrencyCompact(r.current_nna_usd, true)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* External Net Flows vs Firm-Style NNA Trend */}
      <div className="rounded-lg border border-[#E4E9E6] bg-white p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-[#122D33]">
              External Net Flows vs. Firm-Style NNA &amp; Fee Drag
            </h2>
            <p className="mt-0.5 text-xs text-[#68777C]">
              Active window: {period.label} ({period.startDate} to {period.endDate})
            </p>
          </div>
          <TrendingUp className="h-4 w-4 text-[#246B60]" />
        </div>
        <div className="mt-3">
          <EChartBox
            option={flowTrendOption}
            height={300}
            ariaLabel="Monthly external net flows vs firm-style NNA and market movement"
          />
        </div>
      </div>

      {/* Segment Growth Attribution & Outflow Concentration / Market-Masked Attrition */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-[#E4E9E6] bg-white p-5">
          <h2 className="text-sm font-semibold text-[#122D33]">
            Segment Growth Attribution ({period.quarterCode})
          </h2>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[11px] font-semibold uppercase tracking-wider text-[#68777C]">
                <tr>
                  <th className="px-3 py-2">Segment</th>
                  <th className="px-3 py-2 text-right">Closing AUM</th>
                  <th className="px-3 py-2 text-right">Firm-Style NNA</th>
                  <th className="px-3 py-2 text-right">Market Movement</th>
                  <th className="px-3 py-2 text-right">AUM Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E4E9E6]">
                {segments.map((s) => (
                  <tr key={s.segment_id} className="hover:bg-[#F6F7F4]">
                    <td className="px-3 py-2 font-medium text-[#122D33]">
                      {s.segment_name}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-[#122D33]">
                      {formatCurrencyCompact(s.closing_assets_usd)}
                    </td>
                    <td
                      className={`px-3 py-2 text-right font-medium tabular-nums ${
                        toNum(s.firm_style_nna_usd) < 0
                          ? "text-[#C45B51]"
                          : "text-[#246B60]"
                      }`}
                    >
                      {formatCurrencyCompact(s.firm_style_nna_usd, true)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-[#122D33]">
                      {formatCurrencyCompact(s.market_movement_usd, true)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-[#68777C]">
                      {s.segment_aum_share_pct ? `${s.segment_aum_share_pct}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-lg border border-[#E4E9E6] bg-white p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-[#122D33]">
                Positive AUM Growth / Negative NNA Advisors
              </h2>
              <p className="mt-0.5 text-xs text-[#68777C]">
                Market appreciation masking net client outflows ({positiveAumNegativeNnaAdvisors.length} flagged)
              </p>
            </div>
            <span className="text-[11px] tabular-nums text-[#68777C]">
              Total Outflows: {formatCurrencyCompact(totalOutflows)}
            </span>
          </div>

          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[11px] font-semibold uppercase tracking-wider text-[#68777C]">
                <tr>
                  <th className="px-3 py-2">Advisor</th>
                  <th className="px-3 py-2 text-right">AUM Growth</th>
                  <th className="px-3 py-2 text-right">Firm-Style NNA</th>
                  <th className="px-3 py-2 text-right">Outflow Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E4E9E6]">
                {positiveAumNegativeNnaAdvisors.slice(0, 6).map((a) => {
                  const share =
                    totalOutflows > 0
                      ? (Math.abs(toNum(a.gross_outflows_usd)) / totalOutflows) * 100
                      : 0;
                  return (
                    <tr key={a.advisor_id} className="hover:bg-[#F6F7F4]">
                      <td className="px-3 py-2">
                        <Link
                          to={`/advisors/${a.advisor_id}`}
                          className="font-medium text-[#246B60] hover:underline"
                        >
                          {a.advisor_name}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#246B60]">
                        {formatCurrencyCompact(a.aum_growth_usd, true)}
                      </td>
                      <td className="px-3 py-2 text-right font-medium tabular-nums text-[#C45B51]">
                        {formatCurrencyCompact(a.firm_style_nna_usd, true)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-[#68777C]">
                        {share.toFixed(1)}%
                      </td>
                    </tr>
                  );
                })}
                {positiveAumNegativeNnaAdvisors.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-3 py-4 text-center text-[#68777C]">
                      No advisors with positive AUM growth and negative NNA in this slice.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
