import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { BookmarkPlus, Download, Play, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { EChartBox } from "@/components/EChartBox";
import { useFilters } from "@/context/FilterContext";
import {
  fetchAdvisorSummary,
  fetchInvestigationTemplates,
  fetchSavedInvestigations,
  parseInvestigationIntent,
  runInvestigation,
  saveInvestigation,
} from "@/lib/api";
import { formatCurrencyCompact, formatCurrencyExact, toNum } from "@/lib/format";
import { cn } from "@/lib/utils";

export function InvestigationWorkspace() {
  const { period } = useFilters();
  const queryClient = useQueryClient();

  const [selectedTemplate, setSelectedTemplate] = useState("top5_outflow_advisors");
  const [intentInput, setIntentInput] = useState(
    "Show the five advisors with the largest net outflows in Q3 2026.",
  );
  const [intentFeedback, setIntentFeedback] = useState<string | null>(null);
  const [selectedAdvisorId, setSelectedAdvisorId] = useState<string | null>(null);

  const templatesQ = useQuery({
    queryKey: ["investigation-templates"],
    queryFn: fetchInvestigationTemplates,
  });

  const savedQ = useQuery({
    queryKey: ["saved-investigations"],
    queryFn: fetchSavedInvestigations,
  });

  const invQ = useQuery({
    queryKey: ["investigation-run", selectedTemplate, period.quarterCode],
    queryFn: () =>
      runInvestigation({
        template_id: selectedTemplate,
        quarter_code: period.quarterCode,
        limit: 10,
      }),
  });

  const firstAdvisorId = useMemo(() => {
    const first = invQ.data?.rows[0];
    return (first?.advisor_id as string | undefined) ?? null;
  }, [invQ.data]);

  const activeAdvisorId = selectedAdvisorId || firstAdvisorId;

  const advisorSummaryQ = useQuery({
    queryKey: ["inv-advisor-summary", activeAdvisorId, period.quarterCode],
    queryFn: () => fetchAdvisorSummary(activeAdvisorId!, period.quarterCode),
    enabled: Boolean(activeAdvisorId),
  });

  const parseMut = useMutation({
    mutationFn: parseInvestigationIntent,
    onSuccess: (res) => {
      setIntentFeedback(res.message);
      if (res.supported && res.template_id) {
        setSelectedTemplate(res.template_id);
        setSelectedAdvisorId(null);
      }
    },
  });

  const saveMut = useMutation({
    mutationFn: saveInvestigation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["saved-investigations"] });
    },
  });

  const chartOpt = useMemo<EChartsOption>(() => {
    const rows = (invQ.data?.rows ?? []).slice(0, 8);
    if (!rows.length) return {};
    const labelKey =
      "advisor_code" in rows[0]
        ? "advisor_code"
        : "segment_name" in rows[0]
          ? "segment_name"
          : "client_code" in rows[0]
            ? "client_code"
            : Object.keys(rows[0])[0];
    const valKey =
      "external_net_flows_usd" in rows[0]
        ? "external_net_flows_usd"
        : "total_growth_usd" in rows[0]
          ? "total_growth_usd"
          : "gross_outflows_usd" in rows[0]
            ? "gross_outflows_usd"
            : "market_movement_usd" in rows[0]
              ? "market_movement_usd"
              : Object.keys(rows[0]).find((k) => k.endsWith("_usd")) || Object.keys(rows[0])[1];

    return {
      grid: { left: 90, right: 20, top: 16, bottom: 28 },
      tooltip: { trigger: "axis" },
      xAxis: {
        type: "value",
        axisLabel: { fontSize: 10, color: "#68777C", formatter: (v: number) => formatCurrencyCompact(v) },
      },
      yAxis: {
        type: "category",
        data: rows.map((r) => String(r[labelKey] ?? "")),
        axisLabel: { fontSize: 10, color: "#122D33" },
      },
      series: [
        {
          type: "bar",
          barMaxWidth: 20,
          data: rows.map((r) => {
            const v = toNum(r[valKey] as string | number);
            return {
              value: v,
              itemStyle: { color: v < 0 ? "#C45B51" : "#246B60" },
            };
          }),
        },
      ],
    };
  }, [invQ.data]);

  const exportCsv = () => {
    const rows = invQ.data?.rows ?? [];
    if (!rows.length) return;
    const headers = Object.keys(rows[0]);
    const csv = [
      headers.join(","),
      ...rows.map((r) => headers.map((h) => JSON.stringify(r[h] ?? "")).join(",")),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `aumverity_${selectedTemplate}_${period.quarterCode}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns = invQ.data?.rows[0] ? Object.keys(invQ.data.rows[0]).filter((k) => !k.endsWith("_id")) : [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-[#E4E9E6] pb-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[#246B60]">
            Module 07 • Predefined &amp; Validated SQL Investigations
          </span>
          <h1 className="mt-0.5 text-2xl font-semibold text-[#122D33]">Investigation Workspace</h1>
          <p className="text-sm text-[#68777C]">
            Constrained analytical intents grounded in PostgreSQL marts. Zero arbitrary SQL execution.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() =>
              saveMut.mutate({
                name: invQ.data?.title || selectedTemplate,
                template_id: selectedTemplate,
                quarter_code: period.quarterCode,
              })
            }
            className="inline-flex items-center gap-1.5 rounded-md border border-[#E4E9E6] bg-white px-3 py-1.5 text-xs font-medium text-[#122D33] hover:bg-[#F6F7F4]"
          >
            <BookmarkPlus className="h-3.5 w-3.5 text-[#246B60]" /> Save Investigation
          </button>
          <button
            type="button"
            onClick={exportCsv}
            className="inline-flex items-center gap-1.5 rounded-md border border-[#E4E9E6] bg-white px-3 py-1.5 text-xs font-medium text-[#122D33] hover:bg-[#F6F7F4]"
          >
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
        </div>
      </div>

      {/* Constrained Intent Query Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          parseMut.mutate(intentInput);
        }}
        className="flex flex-wrap items-center gap-2 rounded-md border border-[#E4E9E6] bg-white p-3"
      >
        <Search className="h-4 w-4 text-[#68777C]" />
        <input
          type="text"
          value={intentInput}
          onChange={(e) => setIntentInput(e.target.value)}
          aria-label="Constrained analytical question"
          className="min-w-[260px] flex-1 bg-transparent text-xs text-[#122D33] focus:outline-none"
        />
        <button
          type="submit"
          className="inline-flex items-center gap-1.5 rounded-md bg-[#246B60] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#1d564d]"
        >
          <Play className="h-3 w-3" /> Run Intent
        </button>
      </form>
      {intentFeedback && (
        <div className="rounded border border-[#E4E9E6] bg-white px-3.5 py-2 text-xs text-[#122D33]">
          {intentFeedback}
        </div>
      )}

      {/* 3-Column Investigation Layout */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        {/* LEFT: Questions & History */}
        <aside className="space-y-4 lg:col-span-3">
          <div className="rounded-md border border-[#E4E9E6] bg-white p-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#68777C]">
              Validated Questions
            </h2>
            <div className="mt-2.5 space-y-1.5">
              {templatesQ.data?.map((tpl) => (
                <button
                  key={tpl.template_id}
                  type="button"
                  onClick={() => {
                    setSelectedTemplate(tpl.template_id);
                    setSelectedAdvisorId(null);
                  }}
                  className={cn(
                    "w-full rounded-md border px-3 py-2 text-left text-xs transition-colors",
                    selectedTemplate === tpl.template_id
                      ? "border-[#246B60] bg-[#246B60]/8 font-semibold text-[#122D33]"
                      : "border-[#E4E9E6] bg-white text-[#68777C] hover:border-[#246B60]/40",
                  )}
                >
                  {tpl.title}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-md border border-[#E4E9E6] bg-white p-4">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#68777C]">
              Saved Investigations
            </h2>
            <div className="mt-2 space-y-1.5 text-xs">
              {savedQ.data?.length ? (
                savedQ.data.slice(0, 5).map((s) => (
                  <button
                    key={s.investigation_id}
                    type="button"
                    onClick={() => setSelectedTemplate(s.template_id)}
                    className="block w-full truncate rounded border border-[#E4E9E6] bg-[#F6F7F4] px-2.5 py-1.5 text-left text-[11px] text-[#122D33] hover:border-[#246B60]"
                  >
                    {s.name} ({s.quarter_code})
                  </button>
                ))
              ) : (
                <p className="text-[11px] text-[#68777C]">No saved investigations yet.</p>
              )}
            </div>
          </div>
        </aside>

        {/* CENTER: Chart + Ranked Results */}
        <section className="space-y-4 lg:col-span-5">
          <div className="rounded-md border border-[#E4E9E6] bg-white p-4">
            <h2 className="text-sm font-semibold text-[#122D33]">{invQ.data?.title ?? "Results"}</h2>
            <p className="text-xs text-[#68777C]">{invQ.data?.description}</p>
            <div className="mt-3">
              <EChartBox option={chartOpt} height={220} ariaLabel="Investigation Results Chart" />
            </div>
          </div>

          <div className="overflow-x-auto rounded-md border border-[#E4E9E6] bg-white">
            <table className="w-full border-collapse text-left text-[11px]">
              <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[#68777C]">
                <tr>
                  {columns.slice(0, 5).map((c) => (
                    <th key={c} className="whitespace-nowrap px-3 py-2 font-semibold">
                      {c.replace(/_usd$/g, "").replace(/_/g, " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E4E9E6]">
                {invQ.data?.rows.map((row, idx) => (
                  <tr
                    key={idx}
                    onClick={() => {
                      if (row.advisor_id) setSelectedAdvisorId(String(row.advisor_id));
                    }}
                    className={cn(
                      "cursor-pointer hover:bg-[#F6F7F4]",
                      row.advisor_id && row.advisor_id === activeAdvisorId && "bg-[#246B60]/5",
                    )}
                  >
                    {columns.slice(0, 5).map((c) => (
                      <td key={c} className="whitespace-nowrap px-3 py-2 font-mono tabular-nums text-[#122D33]">
                        {c.endsWith("_usd") ? formatCurrencyCompact(row[c] as string, true) : String(row[c] ?? "—")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* RIGHT: Evidence & Deterministic Explanation */}
        <aside className="space-y-4 lg:col-span-4">
          <div className="rounded-md border border-[#E4E9E6] bg-white p-4 text-xs">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#68777C]">
              Deterministic Evidence
            </h2>
            <p className="mt-2 leading-relaxed text-[#122D33]">{invQ.data?.narrative}</p>
            {advisorSummaryQ.data && (
              <div className="mt-3 space-y-2 border-t border-[#E4E9E6] pt-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#122D33]">
                    Selected: {advisorSummaryQ.data.performance.advisor_code}
                  </span>
                  <Link
                    to={`/advisors/${advisorSummaryQ.data.performance.advisor_id}`}
                    className="font-semibold text-[#246B60] hover:underline"
                  >
                    Full Advisor View &rarr;
                  </Link>
                </div>
                <p className="text-[#68777C]">
                  Gross Outflows:{" "}
                  <span className="font-mono font-semibold text-[#C45B51]">
                    {formatCurrencyExact(-toNum(advisorSummaryQ.data.performance.gross_outflows_usd))}
                  </span>{" "}
                  • NNA:{" "}
                  <span className="font-mono font-semibold text-[#122D33]">
                    {formatCurrencyExact(advisorSummaryQ.data.performance.firm_style_nna_usd, true)}
                  </span>
                </p>
                <div className="mt-2">
                  <p className="mb-1 font-semibold text-[#68777C]">Top Client Households (by Q3 Outflows)</p>
                  <div className="divide-y divide-[#E4E9E6] rounded border border-[#E4E9E6]">
                    {advisorSummaryQ.data.top_clients.slice(0, 5).map((cl) => (
                      <div key={cl.client_id} className="flex items-center justify-between px-2.5 py-1.5">
                        <Link to={`/clients/${cl.client_id}`} className="font-medium text-[#246B60] hover:underline">
                          {cl.client_code}
                        </Link>
                        <span className="font-mono tabular-nums text-[#C45B51]">
                          {formatCurrencyExact(-toNum(cl.q3_outflows_usd))}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
