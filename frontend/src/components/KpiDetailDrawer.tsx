import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Code2,
  Database,
  Download,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { EChartBox } from "@/components/EChartBox";
import { useFilters } from "@/context/FilterContext";
import {
  fetchAssetBridge,
  fetchExplainableMetric,
  fetchMetricEvidence,
} from "@/lib/api";
import { formatCurrencyCompact, formatCurrencyExact, formatPct, toNum } from "@/lib/format";
import { cn } from "@/lib/utils";

interface KpiDetailDrawerProps {
  metricId: string | null;
  onClose: () => void;
}

type TabKey = "explanation" | "bridge" | "lineage" | "evidence";

export function KpiDetailDrawer({ metricId, onClose }: KpiDetailDrawerProps) {
  const { period, segmentId } = useFilters();
  const [activeTab, setActiveTab] = useState<TabKey>("explanation");
  const [evidencePage, setEvidencePage] = useState(1);

  const query = useQuery({
    queryKey: ["metric-detail", metricId, period.startDate, period.endDate, segmentId],
    queryFn: () =>
      fetchExplainableMetric({
        metricId: metricId!,
        startDate: period.startDate,
        endDate: period.endDate,
        segmentId: segmentId || undefined,
      }),
    enabled: Boolean(metricId),
  });

  const bridgeQ = useQuery({
    queryKey: ["asset-bridge", period.startDate, period.endDate, segmentId],
    queryFn: () =>
      fetchAssetBridge({
        startDate: period.startDate,
        endDate: period.endDate,
        segmentId: segmentId || undefined,
      }),
    enabled: Boolean(metricId) && activeTab === "bridge",
  });

  const evidenceQ = useQuery({
    queryKey: ["metric-evidence", metricId, period.startDate, period.endDate, segmentId, evidencePage],
    queryFn: () =>
      fetchMetricEvidence({
        metricId: metricId!,
        startDate: period.startDate,
        endDate: period.endDate,
        segmentId: segmentId || undefined,
        page: evidencePage,
        pageSize: 15,
      }),
    enabled: Boolean(metricId) && activeTab === "evidence",
  });

  const bridgeChartOpt = useMemo<EChartsOption>(() => {
    const steps = bridgeQ.data?.steps ?? [];
    const labels = steps.map((s) => s.label);
    const bases: number[] = [];
    const values: { value: number; itemStyle: { color: string }; rawAmount: number }[] = [];
    let running = 0;
    for (const s of steps) {
      const amt = toNum(s.amount_usd);
      if (s.step_type === "BALANCE") {
        bases.push(0);
        values.push({ value: amt, itemStyle: { color: "#122D33" }, rawAmount: amt });
        running = amt;
      } else if (amt >= 0) {
        bases.push(running);
        values.push({ value: amt, itemStyle: { color: "#246B60" }, rawAmount: amt });
        running += amt;
      } else {
        running += amt;
        bases.push(running);
        values.push({ value: Math.abs(amt), itemStyle: { color: "#C45B51" }, rawAmount: amt });
      }
    }
    return {
      grid: { left: 56, right: 12, top: 16, bottom: 56 },
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const arr = Array.isArray(params) ? params : [];
          const vis = arr[1] as { name: string; data: { rawAmount: number } } | undefined;
          return vis ? `${vis.name}: ${formatCurrencyExact(vis.data.rawAmount, true)}` : "";
        },
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: "#68777C", fontSize: 10, interval: 0, rotate: 24 },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#68777C", fontSize: 10, formatter: (v: number) => formatCurrencyCompact(v) },
      },
      series: [
        { type: "bar", stack: "total", itemStyle: { color: "transparent" }, data: bases },
        { type: "bar", stack: "total", barMaxWidth: 28, data: values },
      ],
    };
  }, [bridgeQ.data]);

  if (!metricId) return null;
  const data = query.data;

  const exportEvidenceCsv = () => {
    const rows = evidenceQ.data?.items ?? [];
    if (!rows.length) return;
    const headers = ["external_ref", "account_number", "effective_date", "posted_date", "event_type", "flow_classification", "gross_amount", "fee_amount", "net_amount"];
    const csv = [
      headers.join(","),
      ...rows.map((r) => headers.map((h) => JSON.stringify(r[h as keyof typeof r] ?? "")).join(",")),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `aumverity_${metricId}_evidence.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-[#122D33]/25"
      role="dialog"
      aria-modal="true"
      aria-label="Explain This KPI"
    >
      <div className="flex h-full w-full max-w-2xl flex-col border-l border-[#E4E9E6] bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-[#E4E9E6] px-6 py-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[#246B60]">
              Explain This KPI
            </p>
            <h2 className="mt-0.5 text-base font-semibold text-[#122D33]">
              {data?.metric_name ?? metricId}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close metric details"
            className="rounded-md border border-[#E4E9E6] p-1.5 text-[#68777C] hover:bg-[#F6F7F4] hover:text-[#122D33]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* 4 Tabs */}
        <div className="flex border-b border-[#E4E9E6] bg-[#F6F7F4] px-6 text-xs font-medium">
          {(
            [
              ["explanation", "1. Business Explanation"],
              ["bridge", "2. Financial Bridge"],
              ["lineage", "3. SQL & Lineage"],
              ["evidence", "4. Source Evidence"],
            ] as [TabKey, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setActiveTab(key)}
              className={cn(
                "border-b-2 px-3 py-2.5 transition-colors",
                activeTab === key
                  ? "border-[#246B60] font-semibold text-[#122D33]"
                  : "border-transparent text-[#68777C] hover:text-[#122D33]",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto p-6 text-sm">
          {query.isLoading && <div className="h-24 animate-pulse rounded bg-[#F6F7F4]" />}

          {data && activeTab === "explanation" && (
            <>
              <div className="rounded-md border border-[#E4E9E6] bg-[#F6F7F4] p-4">
                <div className="flex items-baseline justify-between text-xs text-[#68777C]">
                  <span>
                    Observed Value ({data.period.start_date} to {data.period.end_date})
                  </span>
                  <span className="font-mono">{data.query_version}</span>
                </div>
                <div className="mt-1 text-2xl font-semibold tabular-nums text-[#122D33]">
                  {data.unit === "PCT" ? formatPct(data.value) : formatCurrencyExact(data.value)}
                </div>
                <p className="mt-2 text-xs leading-relaxed text-[#68777C]">{data.narrative}</p>
              </div>

              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[#68777C]">
                  Business Definition &amp; Formula
                </h3>
                <p className="mt-1.5 text-xs leading-relaxed text-[#122D33]">{data.definition}</p>
                <div className="mt-2 rounded border border-[#E4E9E6] bg-[#F6F7F4] px-3 py-2 font-mono text-xs text-[#122D33]">
                  {data.formula}
                </div>
              </div>

              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[#68777C]">
                  Contributor Concentration
                </h3>
                <div className="mt-2 divide-y divide-[#E4E9E6] rounded-md border border-[#E4E9E6]">
                  {data.top_drivers.map((drv) => (
                    <div key={drv.label} className="flex items-center justify-between px-3.5 py-2.5 text-xs">
                      <div>
                        <p className="font-medium text-[#122D33]">{drv.label}</p>
                        <p className="text-[11px] text-[#68777C]">{drv.explanation}</p>
                      </div>
                      <div className="text-right tabular-nums">
                        <p className="font-medium text-[#122D33]">{formatCurrencyExact(drv.value, true)}</p>
                        {drv.share_pct !== null && (
                          <p className="text-[11px] text-[#68777C]">{formatPct(drv.share_pct)} share</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between rounded-md border border-[#E4E9E6] p-3.5 text-xs">
                <span className="font-semibold text-[#68777C]">Reconciliation Status</span>
                <span className="inline-flex items-center gap-1 font-medium text-[#246B60]">
                  {data.reconciliation.status === "RECONCILED" ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertTriangle className="h-3.5 w-3.5 text-[#C59B64]" />
                  )}
                  {data.reconciliation.status} (Residual:{" "}
                  {formatCurrencyExact(data.reconciliation.unexplained_residual_usd, true)})
                </span>
              </div>
            </>
          )}

          {data && activeTab === "bridge" && (
            <div className="space-y-4">
              <EChartBox option={bridgeChartOpt} height={240} ariaLabel="KPI Financial Bridge Waterfall" />
              <div className="divide-y divide-[#E4E9E6] rounded-md border border-[#E4E9E6] text-xs">
                {bridgeQ.data?.steps.map((s) => (
                  <div key={s.step_key} className="flex items-center justify-between px-4 py-2">
                    <span className="font-medium text-[#122D33]">{s.label}</span>
                    <span className="font-mono tabular-nums text-[#122D33]">
                      {formatCurrencyExact(s.amount_usd, s.step_type !== "BALANCE")}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data && activeTab === "lineage" && (
            <div className="space-y-4 text-xs">
              <div className="rounded-md border border-[#E4E9E6] bg-[#F6F7F4] p-3.5">
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-[#68777C]">
                  End-to-End Source Lineage
                </p>
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-medium">
                  <span className="rounded border border-[#E4E9E6] bg-white px-2 py-1">Raw transaction</span>
                  <ArrowRight className="h-3 w-3 text-[#68777C]" />
                  <span className="rounded border border-[#E4E9E6] bg-white px-2 py-1">Staging classification</span>
                  <ArrowRight className="h-3 w-3 text-[#68777C]" />
                  <span className="rounded border border-[#246B60]/40 bg-[#246B60]/10 px-2 py-1 text-[#246B60]">
                    {data.lineage.sql_model}
                  </span>
                  <ArrowRight className="h-3 w-3 text-[#68777C]" />
                  <span className="rounded border border-[#E4E9E6] bg-white px-2 py-1">{data.metric_name}</span>
                </div>
              </div>

              <div className="rounded-md border border-[#E4E9E6] p-3.5 space-y-1.5">
                <p><span className="font-semibold">Source Tables:</span> <span className="font-mono">{data.lineage.source_tables.join(", ")}</span></p>
                <p><span className="font-semibold">Bound Parameters:</span> <span className="font-mono">start_date={period.startDate}, end_date={period.endDate}, segment_id={segmentId || "ALL"}</span></p>
                <p><span className="font-semibold">Calculation Version:</span> <span className="font-mono">{data.query_version}</span></p>
                <p><span className="font-semibold">Included:</span> {data.lineage.inclusion_policy}</p>
                <p><span className="font-semibold">Excluded:</span> {data.lineage.exclusion_policy}</p>
              </div>

              <div className="rounded-md border border-[#E4E9E6] bg-[#122D33] p-3.5 font-mono text-[11px] text-[#F6F7F4]">
                <div className="mb-1 flex items-center gap-1 text-[10px] uppercase tracking-wider text-[#C59B64]">
                  <Code2 className="h-3 w-3" /> Versioned SQL Query
                </div>
                <pre className="overflow-x-auto whitespace-pre-wrap">{data.lineage.sql_template}</pre>
              </div>
            </div>
          )}

          {data && activeTab === "evidence" && (
            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-[#68777C]">
                  <Database className="mr-1 inline h-3.5 w-3.5" />
                  {evidenceQ.data?.pagination.total_items.toLocaleString() ?? "—"} source transactions
                </span>
                <button
                  type="button"
                  onClick={exportEvidenceCsv}
                  className="inline-flex items-center gap-1 rounded border border-[#E4E9E6] px-2.5 py-1 font-medium text-[#122D33] hover:bg-[#F6F7F4]"
                >
                  <Download className="h-3.5 w-3.5" /> Export CSV
                </button>
              </div>
              <div className="overflow-x-auto rounded-md border border-[#E4E9E6]">
                <table className="w-full border-collapse text-left text-[11px]">
                  <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[#68777C]">
                    <tr>
                      <th className="px-2.5 py-2">Account</th>
                      <th className="px-2.5 py-2">Effective</th>
                      <th className="px-2.5 py-2">Type</th>
                      <th className="px-2.5 py-2 text-right">Net Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E4E9E6]">
                    {evidenceQ.data?.items.map((tx) => (
                      <tr key={tx.event_id}>
                        <td className="px-2.5 py-1.5 font-mono">{tx.account_number}</td>
                        <td className="px-2.5 py-1.5 tabular-nums">{tx.effective_date}</td>
                        <td className="px-2.5 py-1.5">{tx.event_type}</td>
                        <td className="px-2.5 py-1.5 text-right font-mono tabular-nums">
                          {formatCurrencyExact(tx.net_amount, true)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  disabled={evidencePage <= 1}
                  onClick={() => setEvidencePage((p) => Math.max(1, p - 1))}
                  className="rounded border border-[#E4E9E6] px-2.5 py-1 disabled:opacity-40"
                >
                  Previous
                </button>
                <span className="text-[#68777C]">
                  Page {evidencePage} of {evidenceQ.data?.pagination.total_pages ?? 1}
                </span>
                <button
                  type="button"
                  disabled={evidencePage >= (evidenceQ.data?.pagination.total_pages ?? 1)}
                  onClick={() => setEvidencePage((p) => p + 1)}
                  className="rounded border border-[#E4E9E6] px-2.5 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
