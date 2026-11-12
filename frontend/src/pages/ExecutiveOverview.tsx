import { useQuery } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import type { EChartsOption } from "echarts";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpDown,
  ArrowUpRight,
  CheckCircle2,
  Info,
  Minus,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { EChartBox } from "@/components/EChartBox";
import { KpiDetailDrawer } from "@/components/KpiDetailDrawer";
import { useFilters } from "@/context/FilterContext";
import {
  type AdvisorRow,
  fetchAdvisors,
  fetchAssetBridge,
  fetchFlows,
  fetchOverview,
  fetchReconciliation,
  fetchSegments,
} from "@/lib/api";
import {
  formatCurrencyCompact,
  formatCurrencyExact,
  formatPct,
  toNum,
} from "@/lib/format";
import { cn } from "@/lib/utils";

type TrendMetricKey =
  | "closing_assets_usd"
  | "firm_style_nna_usd"
  | "external_net_flows_usd"
  | "market_driven_movement_usd";

const TREND_OPTIONS: { key: TrendMetricKey; label: string }[] = [
  { key: "closing_assets_usd", label: "Total client assets" },
  { key: "firm_style_nna_usd", label: "NNA" },
  { key: "external_net_flows_usd", label: "External net flows" },
  { key: "market_driven_movement_usd", label: "Market movement" },
];

const columnHelper = createColumnHelper<AdvisorRow>();

function SignBadge({ value, unit = "USD" }: { value: string | number | null; unit?: "USD" | "PCT" }) {
  const num = toNum(value);
  const isPos = num > 0;
  const isNeg = num < 0;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
        isPos ? "text-[#246B60]" : isNeg ? "text-[#C45B51]" : "text-[#68777C]",
      )}
    >
      {isPos ? (
        <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
      ) : isNeg ? (
        <ArrowDownRight className="h-3.5 w-3.5" aria-hidden="true" />
      ) : (
        <Minus className="h-3.5 w-3.5" aria-hidden="true" />
      )}
      {unit === "PCT" ? formatPct(num, true) : formatCurrencyCompact(num, true)}
    </span>
  );
}

export function ExecutiveOverview() {
  const { period, segmentId, search } = useFilters();
  const [selectedMetricId, setSelectedMetricId] = useState<string | null>(null);
  const [trendKey, setTrendKey] = useState<TrendMetricKey>("closing_assets_usd");
  const [sorting, setSorting] = useState<SortingState>([
    { id: "firm_style_nna_usd", desc: true },
  ]);

  const overviewQ = useQuery({
    queryKey: ["overview", period.startDate, period.endDate, segmentId],
    queryFn: () =>
      fetchOverview({
        startDate: period.startDate,
        endDate: period.endDate,
        segmentId: segmentId || undefined,
      }),
  });

  const bridgeQ = useQuery({
    queryKey: ["asset-bridge", period.startDate, period.endDate, segmentId],
    queryFn: () =>
      fetchAssetBridge({
        startDate: period.startDate,
        endDate: period.endDate,
        segmentId: segmentId || undefined,
      }),
  });

  const flowsQ = useQuery({
    queryKey: ["flows", period.startDate, period.endDate, segmentId],
    queryFn: () =>
      fetchFlows({
        startDate: period.startDate,
        endDate: period.endDate,
        segmentId: segmentId || undefined,
      }),
  });

  const segmentsQ = useQuery({
    queryKey: ["segments", period.quarterCode],
    queryFn: () => fetchSegments(period.quarterCode),
  });

  const advisorsQ = useQuery({
    queryKey: ["advisors", period.quarterCode, segmentId, search],
    queryFn: () =>
      fetchAdvisors({
        quarterCode: period.quarterCode,
        segmentId: segmentId || undefined,
        search: search || undefined,
        pageSize: 40,
      }),
  });

  const reconQ = useQuery({
    queryKey: ["reconciliation"],
    queryFn: fetchReconciliation,
  });

  const ov = overviewQ.data;
  const openIssues = reconQ.data?.filter((i) => i.status === "OPEN") ?? [];
  const criticalOrHigh = openIssues.filter(
    (i) => i.severity === "CRITICAL" || i.severity === "HIGH",
  );

  // 1. Client Asset Trend ECharts Option
  const trendOption = useMemo<EChartsOption>(() => {
    const rows = flowsQ.data ?? [];
    const xData = rows.map((r) => r.period_code);
    const yData = rows.map((r) => toNum(r[trendKey]));
    return {
      grid: { left: 64, right: 20, top: 20, bottom: 32 },
      tooltip: {
        trigger: "axis",
        backgroundColor: "#FFFFFF",
        borderColor: "#E4E9E6",
        textStyle: { color: "#122D33", fontSize: 12 },
        formatter: (params: unknown) => {
          const arr = Array.isArray(params) ? params : [params];
          const p = arr[0] as { name: string; value: number };
          return `<div style="font-weight:600;margin-bottom:2px">${p.name}</div><div>${formatCurrencyExact(p.value, trendKey !== "closing_assets_usd")}</div>`;
        },
      },
      xAxis: {
        type: "category",
        data: xData,
        axisLine: { lineStyle: { color: "#E4E9E6" } },
        axisLabel: { color: "#68777C", fontSize: 11 },
      },
      yAxis: {
        type: "value",
        scale: trendKey === "closing_assets_usd",
        splitLine: { lineStyle: { color: "#E4E9E6", type: "dashed" } },
        axisLabel: {
          color: "#68777C",
          fontSize: 11,
          formatter: (val: number) => formatCurrencyCompact(val),
        },
      },
      series: [
        {
          type: "line",
          data: yData,
          smooth: false,
          symbolSize: 6,
          lineStyle: { color: "#246B60", width: 2.5 },
          itemStyle: { color: "#246B60" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(36, 107, 96, 0.16)" },
                { offset: 1, color: "rgba(36, 107, 96, 0.01)" },
              ],
            },
          },
        },
      ],
    };
  }, [flowsQ.data, trendKey]);

  // 2. Asset Movement Waterfall ECharts Option
  const waterfallOption = useMemo<EChartsOption>(() => {
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
      grid: { left: 64, right: 16, top: 20, bottom: 56 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "#FFFFFF",
        borderColor: "#E4E9E6",
        textStyle: { color: "#122D33", fontSize: 12 },
        formatter: (params: unknown) => {
          const arr = Array.isArray(params) ? params : [];
          const vis = arr[1] as { name: string; data: { rawAmount: number } } | undefined;
          if (!vis) return "";
          return `<div style="font-weight:600">${vis.name}</div><div>${formatCurrencyExact(vis.data.rawAmount, true)}</div>`;
        },
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLine: { lineStyle: { color: "#E4E9E6" } },
        axisLabel: { color: "#68777C", fontSize: 10, interval: 0, rotate: 22 },
      },
      yAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "#E4E9E6", type: "dashed" } },
        axisLabel: {
          color: "#68777C",
          fontSize: 11,
          formatter: (val: number) => formatCurrencyCompact(val),
        },
      },
      series: [
        {
          name: "Base",
          type: "bar",
          stack: "total",
          itemStyle: { borderColor: "transparent", color: "transparent" },
          emphasis: { itemStyle: { borderColor: "transparent", color: "transparent" } },
          data: bases,
        },
        {
          name: "Movement",
          type: "bar",
          stack: "total",
          barMaxWidth: 34,
          data: values,
        },
      ],
    };
  }, [bridgeQ.data]);

  // 3. Segment Horizontal Bar ECharts Option
  const segmentOption = useMemo<EChartsOption>(() => {
    const segs = segmentsQ.data ?? [];
    const names = segs.map((s) => s.segment_name);
    const nnaVals = segs.map((s) => toNum(s.firm_style_nna_usd));
    const mktVals = segs.map((s) => toNum(s.market_movement_usd));
    return {
      grid: { left: 175, right: 24, top: 32, bottom: 28 },
      legend: { top: 0, right: 0, textStyle: { color: "#68777C", fontSize: 11 } },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: "#FFFFFF",
        borderColor: "#E4E9E6",
        textStyle: { color: "#122D33", fontSize: 12 },
      },
      xAxis: {
        type: "value",
        splitLine: { lineStyle: { color: "#E4E9E6", type: "dashed" } },
        axisLabel: {
          color: "#68777C",
          fontSize: 11,
          formatter: (val: number) => formatCurrencyCompact(val),
        },
      },
      yAxis: {
        type: "category",
        data: names,
        axisLine: { lineStyle: { color: "#E4E9E6" } },
        axisLabel: { color: "#122D33", fontSize: 11 },
      },
      series: [
        {
          name: "Firm-Style NNA",
          type: "bar",
          data: nnaVals,
          itemStyle: { color: "#246B60" },
          barMaxWidth: 16,
        },
        {
          name: "Market Movement",
          type: "bar",
          data: mktVals,
          itemStyle: { color: "#C59B64" },
          barMaxWidth: 16,
        },
      ],
    };
  }, [segmentsQ.data]);

  // 4. Advisor Performance TanStack Table
  const columns = useMemo(
    () => [
      columnHelper.accessor("advisor_name", {
        header: "Advisor",
        cell: (info) => (
          <div>
            <span className="font-medium text-[#122D33]">{info.row.original.advisor_code}</span>
            <span className="ml-1.5 text-xs text-[#68777C]">{info.getValue()}</span>
          </div>
        ),
      }),
      columnHelper.accessor("segment_name", {
        header: "Segment",
        cell: (info) => <span className="text-xs text-[#68777C]">{info.getValue()}</span>,
      }),
      columnHelper.accessor("opening_assets_usd", {
        header: "Opening Assets",
        cell: (info) => (
          <span className="tabular-nums">{formatCurrencyCompact(info.getValue())}</span>
        ),
      }),
      columnHelper.accessor("closing_assets_usd", {
        header: "Closing Assets",
        cell: (info) => (
          <span className="font-medium tabular-nums">{formatCurrencyCompact(info.getValue())}</span>
        ),
      }),
      columnHelper.accessor("gross_inflows_usd", {
        header: "Gross Inflows",
        cell: (info) => (
          <span className="tabular-nums text-[#246B60]">{formatCurrencyCompact(info.getValue(), true)}</span>
        ),
      }),
      columnHelper.accessor("gross_outflows_usd", {
        header: "Gross Outflows",
        cell: (info) => (
          <span className="tabular-nums text-[#C45B51]">
            {formatCurrencyCompact(-toNum(info.getValue()))}
          </span>
        ),
      }),
      columnHelper.accessor("firm_style_nna_usd", {
        header: "NNA",
        cell: (info) => <SignBadge value={info.getValue()} />,
      }),
      columnHelper.accessor("market_movement_usd", {
        header: "Market Impact",
        cell: (info) => <SignBadge value={info.getValue()} />,
      }),
      columnHelper.accessor("aum_growth_usd", {
        header: "Period Growth",
        cell: (info) => <SignBadge value={info.getValue()} />,
      }),
    ],
    [],
  );

  const table = useReactTable({
    data: advisorsQ.data?.items ?? [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const kpiCards = [
    {
      metricId: "closing_assets",
      label: "Total Client Assets",
      value: ov ? formatCurrencyCompact(ov.closing_assets_usd) : "—",
      exact: ov ? formatCurrencyExact(ov.closing_assets_usd) : "",
      sub: ov ? <SignBadge value={ov.total_asset_growth_pct} unit="PCT" /> : null,
      context: "vs. period start",
      tooltip: "End-of-period market value of cash, sweep balances, and securities.",
    },
    {
      metricId: "firm_style_nna",
      label: "Net New Assets (NNA)",
      value: ov ? formatCurrencyCompact(ov.firm_style_nna_usd, true) : "—",
      exact: ov ? formatCurrencyExact(ov.firm_style_nna_usd, true) : "",
      sub: ov ? <SignBadge value={ov.firm_style_nna_usd} /> : null,
      context: "includes credited income",
      tooltip: "Eligible inflows + credited interest/dividends + in-kind acquisitions - outflows.",
    },
    {
      metricId: "external_net_flows",
      label: "External Net Flows",
      value: ov ? formatCurrencyCompact(ov.external_net_flows_usd, true) : "—",
      exact: ov ? formatCurrencyExact(ov.external_net_flows_usd, true) : "",
      sub: ov ? <SignBadge value={ov.external_net_flows_usd} /> : null,
      context: "external cash & ACAT",
      tooltip: "External deposits/transfers in minus external withdrawals/transfers out.",
    },
    {
      metricId: "market_driven_movement",
      label: "Market Contribution",
      value: ov ? formatCurrencyCompact(ov.market_driven_movement_usd, true) : "—",
      exact: ov ? formatCurrencyExact(ov.market_driven_movement_usd, true) : "",
      sub: ov ? <SignBadge value={ov.market_driven_movement_usd} /> : null,
      context: "position price impact",
      tooltip: "Independent position-level price appreciation (never a residual plug).",
    },
    {
      metricId: "fee_based_assets",
      label: "Fee-Based Assets",
      value: ov ? formatCurrencyCompact(ov.fee_based_assets_usd) : "—",
      exact: ov ? formatCurrencyExact(ov.fee_based_assets_usd) : "",
      sub: ov ? (
        <span className="text-xs tabular-nums text-[#68777C]">
          Fees: -{formatCurrencyCompact(ov.fees_and_commissions_usd)}
        </span>
      ) : null,
      context: "advisory perimeter",
      tooltip: "Closing AUM held in Fee-based advisory accounts.",
    },
    {
      metricId: "reporting_completeness",
      label: "Reconciliation Status",
      value: ov?.reporting_completeness_pct ? formatPct(ov.reporting_completeness_pct) : "—",
      exact: `${openIssues.length} open feed issue(s)`,
      sub: (
        <span className="inline-flex items-center gap-1 text-xs font-medium text-[#C59B64]">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
          {openIssues.length} open
        </span>
      ),
      context: "feed completeness",
      tooltip: "Percentage of reporting feed snapshots reconciled without anomalies.",
    },
  ];

  // Deterministic business insights derived from API data
  const topSeg = useMemo(() => {
    const segs = segmentsQ.data ?? [];
    if (!segs.length) return null;
    return [...segs].sort(
      (a, b) => toNum(b.total_growth_usd) - toNum(a.total_growth_usd),
    )[0];
  }, [segmentsQ.data]);

  const topOutflowAdv = useMemo(() => {
    const advs = advisorsQ.data?.items ?? [];
    if (!advs.length) return null;
    return [...advs].sort(
      (a, b) => toNum(a.external_net_flows_usd) - toNum(b.external_net_flows_usd),
    )[0];
  }, [advisorsQ.data]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-2 border-b border-[#E4E9E6] pb-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#246B60]">
            Reporting period: {period.label}
          </span>
          <h1 className="mt-0.5 text-2xl font-semibold tracking-tight text-[#122D33]">
            Executive Overview
          </h1>
          <p className="mt-0.5 text-sm text-[#68777C]">
            Understand the movements behind your client assets.
          </p>
        </div>
        {ov && (
          <div className="text-right text-xs text-[#68777C]">
            <span>Model: </span>
            <span className="font-mono font-medium text-[#122D33]">{ov.query_version}</span>
            <span className="mx-1.5">•</span>
            <span>Currency: </span>
            <span className="font-mono font-medium text-[#122D33]">{ov.currency}</span>
          </div>
        )}
      </div>

      {/* Error State */}
      {overviewQ.isError && (
        <div
          role="alert"
          className="rounded-md border border-[#C45B51]/40 bg-white p-4 text-sm text-[#C45B51]"
        >
          Unable to load overview metrics from backend API. Verify that FastAPI is running on port 8000.
        </div>
      )}

      {/* 6 KPI Cards */}
      <section aria-label="Key Performance Indicators" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {kpiCards.map((card) => (
          <button
            key={card.metricId}
            type="button"
            onClick={() => setSelectedMetricId(card.metricId)}
            title={card.tooltip}
            className="group flex flex-col justify-between rounded-md border border-[#E4E9E6] bg-white p-4 text-left transition-colors hover:border-[#246B60] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#246B60]"
          >
            <div className="flex items-center justify-between gap-1">
              <span className="text-xs font-medium text-[#68777C]">{card.label}</span>
              <Info className="h-3.5 w-3.5 text-[#68777C]/60 group-hover:text-[#246B60]" aria-hidden="true" />
            </div>
            <div className="mt-2">
              {overviewQ.isLoading ? (
                <div className="h-7 w-24 animate-pulse rounded bg-[#F6F7F4]" />
              ) : (
                <div
                  className="text-xl font-semibold tracking-tight tabular-nums text-[#122D33]"
                  title={card.exact}
                >
                  {card.value}
                </div>
              )}
            </div>
            <div className="mt-2 flex items-center justify-between border-t border-[#E4E9E6] pt-2">
              {card.sub}
              <span className="text-[11px] text-[#68777C]">{card.context}</span>
            </div>
          </button>
        ))}
      </section>

      {/* Main Charts Row: Trend + Waterfall */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="rounded-md border border-[#E4E9E6] bg-white p-5 lg:col-span-7">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-[#122D33]">Client Asset Trend</h2>
              <p className="text-xs text-[#68777C]">Monthly historical progression (USD)</p>
            </div>
            <div className="inline-flex rounded-md border border-[#E4E9E6] bg-[#F6F7F4] p-0.5">
              {TREND_OPTIONS.map((opt) => (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setTrendKey(opt.key)}
                  className={cn(
                    "rounded px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#246B60]",
                    trendKey === opt.key
                      ? "bg-white text-[#122D33] shadow-sm"
                      : "text-[#68777C] hover:text-[#122D33]",
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          {flowsQ.isLoading ? (
            <div className="h-[290px] animate-pulse rounded bg-[#F6F7F4]" />
          ) : (
            <EChartBox option={trendOption} height={290} ariaLabel="Client Asset Trend Chart" />
          )}
        </section>

        <section className="rounded-md border border-[#E4E9E6] bg-white p-5 lg:col-span-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-[#122D33]">Asset Movement Waterfall</h2>
              <p className="text-xs text-[#68777C]">Opening assets to closing assets bridge</p>
            </div>
            {bridgeQ.data && (
              <span className="rounded border border-[#E4E9E6] bg-[#F6F7F4] px-2 py-0.5 font-mono text-[11px] text-[#122D33]">
                Residual: {formatCurrencyCompact(bridgeQ.data.unexplained_residual_usd, true)}
              </span>
            )}
          </div>
          {bridgeQ.isLoading ? (
            <div className="h-[290px] animate-pulse rounded bg-[#F6F7F4]" />
          ) : (
            <EChartBox option={waterfallOption} height={290} ariaLabel="Asset Movement Waterfall Chart" />
          )}
        </section>
      </div>

      {/* Segment Breakdown + Business Insights + Data Quality Summary */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <section className="rounded-md border border-[#E4E9E6] bg-white p-5 lg:col-span-6">
          <div className="mb-3">
            <h2 className="text-sm font-semibold text-[#122D33]">Business Segment Breakdown</h2>
            <p className="text-xs text-[#68777C]">
              Firm-Style NNA vs. Price-Driven Market Movement ({period.quarterCode})
            </p>
          </div>
          {segmentsQ.isLoading ? (
            <div className="h-[240px] animate-pulse rounded bg-[#F6F7F4]" />
          ) : (
            <EChartBox option={segmentOption} height={240} ariaLabel="Business Segment Breakdown Chart" />
          )}
        </section>

        <section className="flex flex-col justify-between rounded-md border border-[#E4E9E6] bg-white p-5 lg:col-span-3">
          <div>
            <h2 className="text-sm font-semibold text-[#122D33]">Business Insight Panel</h2>
            <p className="text-xs text-[#68777C]">Deterministic facts derived from SQL marts</p>
            <div className="mt-4 space-y-3 text-xs leading-relaxed text-[#122D33]">
              {ov && <p className="rounded border border-[#E4E9E6] bg-[#F6F7F4] p-3">{ov.narrative}</p>}
              {topSeg && (
                <p>
                  <span className="font-semibold">{topSeg.segment_name}</span> led segment growth in{" "}
                  {period.quarterCode} with {formatCurrencyCompact(topSeg.total_growth_usd, true)}{" "}
                  (NNA: {formatCurrencyCompact(topSeg.firm_style_nna_usd, true)}, Market:{" "}
                  {formatCurrencyCompact(topSeg.market_movement_usd, true)}).
                </p>
              )}
              {topOutflowAdv && toNum(topOutflowAdv.external_net_flows_usd) < 0 && (
                <p>
                  <span className="font-semibold">{topOutflowAdv.advisor_code}</span> recorded the
                  largest net external outflows ({formatCurrencyCompact(topOutflowAdv.external_net_flows_usd)})
                  in {period.quarterCode}.
                </p>
              )}
            </div>
          </div>
          <Link
            to="/investigations"
            className="mt-4 inline-flex items-center text-xs font-semibold text-[#246B60] hover:underline"
          >
            Open Investigation Workspace &rarr;
          </Link>
        </section>

        <section className="flex flex-col justify-between rounded-md border border-[#E4E9E6] bg-white p-5 lg:col-span-3">
          <div>
            <h2 className="text-sm font-semibold text-[#122D33]">Data Quality Summary</h2>
            <p className="text-xs text-[#68777C]">Source-to-reporting feed verification</p>
            <dl className="mt-4 space-y-2.5 text-xs">
              <div className="flex items-center justify-between border-b border-[#E4E9E6] pb-2">
                <dt className="text-[#68777C]">Reporting Completeness</dt>
                <dd className="font-semibold tabular-nums text-[#122D33]">
                  {ov?.reporting_completeness_pct ? formatPct(ov.reporting_completeness_pct) : "—"}
                </dd>
              </div>
              <div className="flex items-center justify-between border-b border-[#E4E9E6] pb-2">
                <dt className="text-[#68777C]">Open Feed Issues</dt>
                <dd className="font-semibold tabular-nums text-[#C45B51]">{openIssues.length}</dd>
              </div>
              <div className="flex items-center justify-between border-b border-[#E4E9E6] pb-2">
                <dt className="text-[#68777C]">Material (High/Critical)</dt>
                <dd className="font-semibold tabular-nums text-[#C45B51]">{criticalOrHigh.length}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-[#68777C]">Latest Baseline</dt>
                <dd className="inline-flex items-center gap-1 font-medium text-[#246B60]">
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                  2026-09-30
                </dd>
              </div>
            </dl>
          </div>
          <Link
            to="/reconciliation"
            className="mt-4 inline-flex items-center text-xs font-semibold text-[#246B60] hover:underline"
          >
            Inspect Reconciliation Exceptions &rarr;
          </Link>
        </section>
      </div>

      {/* Advisor Performance Table */}
      <section className="rounded-md border border-[#E4E9E6] bg-white">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#E4E9E6] px-5 py-4">
          <div>
            <h2 className="text-sm font-semibold text-[#122D33]">Advisor Performance</h2>
            <p className="text-xs text-[#68777C]">
              {advisorsQ.data?.pagination.total_items ?? 0} advisors • Click column headers to sort
            </p>
          </div>
          <Link to="/advisors" className="text-xs font-semibold text-[#246B60] hover:underline">
            Full Advisor Explorer &rarr;
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-[#E4E9E6] bg-[#F6F7F4]">
                  {hg.headers.map((header) => (
                    <th
                      key={header.id}
                      scope="col"
                      className="whitespace-nowrap px-4 py-2.5 font-semibold text-[#68777C]"
                    >
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className="inline-flex items-center gap-1 hover:text-[#122D33] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#246B60]"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        <ArrowUpDown className="h-3 w-3 opacity-60" aria-hidden="true" />
                      </button>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-[#E4E9E6]">
              {advisorsQ.isLoading ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-[#68777C]">
                    Loading advisor performance...
                  </td>
                </tr>
              ) : table.getRowModel().rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-[#68777C]">
                    No advisors match the current segment or search filter.
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.slice(0, 15).map((row) => (
                  <tr key={row.id} className="hover:bg-[#F6F7F4]/70">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="whitespace-nowrap px-4 py-2.5 text-[#122D33]">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <KpiDetailDrawer
        metricId={selectedMetricId}
        onClose={() => setSelectedMetricId(null)}
      />
    </div>
  );
}
