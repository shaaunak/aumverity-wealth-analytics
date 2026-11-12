import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { Layers, ShieldCheck } from "lucide-react";
import { useMemo } from "react";

import { EChartBox } from "@/components/EChartBox";
import { useFilters } from "@/context/FilterContext";
import { fetchAssetBridge } from "@/lib/api";
import { formatCurrencyCompact, formatCurrencyExact, toNum } from "@/lib/format";

export function AssetBridgePage() {
  const { period, segmentId } = useFilters();

  const bridgeQuery = useQuery({
    queryKey: ["asset-bridge", period.startDate, period.endDate, segmentId],
    queryFn: () =>
      fetchAssetBridge({
        startDate: period.startDate,
        endDate: period.endDate,
        segmentId: segmentId || undefined,
      }),
  });

  const steps = bridgeQuery.data?.steps ?? [];

  const waterfallOption: EChartsOption = useMemo(() => {
    const labels = steps.map((s) => s.label);
    const helper: number[] = [];
    const positive: (number | string)[] = [];
    const negative: (number | string)[] = [];
    const total: (number | string)[] = [];

    let running = 0;
    for (const s of steps) {
      const val = toNum(s.amount_usd);
      if (s.step_type === "total") {
        helper.push(0);
        positive.push("-");
        negative.push("-");
        total.push(val);
        running = val;
      } else if (val >= 0) {
        helper.push(running);
        positive.push(val);
        negative.push("-");
        total.push("-");
        running += val;
      } else {
        running += val;
        helper.push(running);
        positive.push("-");
        negative.push(Math.abs(val));
        total.push("-");
      }
    }

    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
      },
      grid: { top: 24, left: 68, right: 20, bottom: 52 },
      xAxis: {
        type: "category",
        data: labels,
        axisLabel: { color: "#68777C", fontSize: 11, interval: 0, rotate: 15 },
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
          name: "Base",
          type: "bar",
          stack: "Total",
          itemStyle: { borderColor: "transparent", color: "transparent" },
          emphasis: { itemStyle: { borderColor: "transparent", color: "transparent" } },
          data: helper,
        },
        {
          name: "Increase",
          type: "bar",
          stack: "Total",
          itemStyle: { color: "#246B60", borderRadius: [3, 3, 0, 0] },
          data: positive,
        },
        {
          name: "Decrease",
          type: "bar",
          stack: "Total",
          itemStyle: { color: "#C45B51", borderRadius: [3, 3, 0, 0] },
          data: negative,
        },
        {
          name: "Balance",
          type: "bar",
          stack: "Total",
          itemStyle: { color: "#122D33", borderRadius: [3, 3, 0, 0] },
          data: total,
        },
      ],
    };
  }, [steps]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-[#122D33]">
              Asset Movement Bridge
            </h1>
            <span className="rounded border border-[#246B60]/30 bg-[#246B60]/10 px-2 py-0.5 text-[11px] font-medium text-[#246B60]">
              SYNTHETIC
            </span>
          </div>
          <p className="mt-1 text-sm text-[#68777C]">
            Full-perimeter reconciliation from Opening Assets to Closing Assets for{" "}
            <strong className="text-[#122D33]">{period.label}</strong>. Unexplained
            residual is explicitly isolated.
          </p>
        </div>

        <div className="flex items-center gap-2 rounded-lg border border-[#E4E9E6] bg-white px-3.5 py-2 text-xs">
          <ShieldCheck className="h-4 w-4 text-[#246B60]" />
          <span className="text-[#68777C]">Unexplained Residual:</span>
          <span className="font-semibold tabular-nums text-[#122D33]">
            {formatCurrencyExact(bridgeQuery.data?.unexplained_residual_usd ?? "0")}
          </span>
          <span className="rounded bg-[#F6F7F4] px-2 py-0.5 text-[11px] font-medium text-[#246B60]">
            {bridgeQuery.data?.reconciliation_status ?? "VERIFIED"}
          </span>
        </div>
      </div>

      {/* Waterfall Chart */}
      <div className="rounded-lg border border-[#E4E9E6] bg-white p-5">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-[#246B60]" />
          <h2 className="text-sm font-semibold text-[#122D33]">
            Opening-to-Closing Asset Bridge Waterfall (USD)
          </h2>
        </div>
        <div className="mt-3">
          <EChartBox
            option={waterfallOption}
            height={340}
            ariaLabel="Asset movement bridge waterfall chart"
          />
        </div>
      </div>

      {/* Bridge Reconciliation Table */}
      <div className="overflow-hidden rounded-lg border border-[#E4E9E6] bg-white">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[11px] font-semibold uppercase tracking-wider text-[#68777C]">
            <tr>
              <th className="px-4 py-3">Bridge Step</th>
              <th className="px-4 py-3">Step Key</th>
              <th className="px-4 py-3">Classification</th>
              <th className="px-4 py-3 text-right">Amount (USD)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E4E9E6]">
            {bridgeQuery.isLoading && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-[#68777C]">
                  Computing SQL asset movement bridge...
                </td>
              </tr>
            )}
            {steps.map((s) => {
              const amt = toNum(s.amount_usd);
              return (
                <tr key={s.step_key} className="hover:bg-[#F6F7F4]">
                  <td className="px-4 py-3 font-medium text-[#122D33]">{s.label}</td>
                  <td className="px-4 py-3 font-mono text-[11px] text-[#68777C]">
                    {s.step_key}
                  </td>
                  <td className="px-4 py-3 uppercase text-[11px] text-[#68777C]">
                    {s.step_type}
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-semibold tabular-nums ${
                      s.step_type === "total"
                        ? "text-[#122D33]"
                        : amt < 0
                          ? "text-[#C45B51]"
                          : "text-[#246B60]"
                    }`}
                  >
                    {formatCurrencyExact(
                      s.amount_usd,
                      s.step_type !== "total",
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
