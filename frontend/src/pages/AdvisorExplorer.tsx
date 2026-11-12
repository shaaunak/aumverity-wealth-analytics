import { useQuery } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useFilters } from "@/context/FilterContext";
import { type AdvisorRow, fetchAdvisors } from "@/lib/api";
import { formatCurrencyCompact, toNum } from "@/lib/format";

const col = createColumnHelper<AdvisorRow>();

export function AdvisorExplorer() {
  const { period, segmentId, search } = useFilters();
  const [sorting, setSorting] = useState<SortingState>([
    { id: "firm_style_nna_usd", desc: true },
  ]);

  const advisorsQ = useQuery({
    queryKey: ["advisors-explorer", period.quarterCode, segmentId, search],
    queryFn: () =>
      fetchAdvisors({
        quarterCode: period.quarterCode,
        segmentId: segmentId || undefined,
        search: search || undefined,
        pageSize: 50,
      }),
  });

  const columns = useMemo(
    () => [
      col.accessor("advisor_code", {
        header: "Advisor ID",
        cell: (i) => (
          <Link
            to={`/advisors/${i.row.original.advisor_id}`}
            className="inline-flex items-center gap-1 font-mono font-semibold text-[#246B60] hover:underline"
          >
            {i.getValue()}
            <ChevronRight className="h-3 w-3" />
          </Link>
        ),
      }),
      col.accessor("advisor_name", { header: "Advisor Name" }),
      col.accessor("segment_name", {
        header: "Segment",
        cell: (i) => <span className="text-[#68777C]">{i.getValue()}</span>,
      }),
      col.accessor("opening_assets_usd", {
        header: "Opening Assets",
        cell: (i) => <span className="tabular-nums">{formatCurrencyCompact(i.getValue())}</span>,
      }),
      col.accessor("closing_assets_usd", {
        header: "Closing Assets",
        cell: (i) => <span className="font-medium tabular-nums">{formatCurrencyCompact(i.getValue())}</span>,
      }),
      col.accessor("gross_inflows_usd", {
        header: "Gross Inflows",
        cell: (i) => <span className="tabular-nums text-[#246B60]">{formatCurrencyCompact(i.getValue(), true)}</span>,
      }),
      col.accessor("gross_outflows_usd", {
        header: "Gross Outflows",
        cell: (i) => <span className="tabular-nums text-[#C45B51]">{formatCurrencyCompact(-toNum(i.getValue()))}</span>,
      }),
      col.accessor("external_net_flows_usd", {
        header: "Net Flows",
        cell: (i) => {
          const n = toNum(i.getValue());
          return (
            <span className={n >= 0 ? "tabular-nums text-[#246B60]" : "tabular-nums text-[#C45B51]"}>
              {formatCurrencyCompact(n, true)}
            </span>
          );
        },
      }),
      col.accessor("firm_style_nna_usd", {
        header: "Firm-Style NNA",
        cell: (i) => {
          const n = toNum(i.getValue());
          return (
            <span className={n >= 0 ? "font-medium tabular-nums text-[#246B60]" : "font-medium tabular-nums text-[#C45B51]"}>
              {formatCurrencyCompact(n, true)}
            </span>
          );
        },
      }),
      col.accessor("market_movement_usd", {
        header: "Market Movement",
        cell: (i) => <span className="tabular-nums">{formatCurrencyCompact(i.getValue(), true)}</span>,
      }),
      col.accessor("aum_growth_usd", {
        header: "Period Growth",
        cell: (i) => <span className="tabular-nums">{formatCurrencyCompact(i.getValue(), true)}</span>,
      }),
      col.accessor("nna_rank", {
        header: "NNA Rank",
        cell: (i) => <span className="font-mono text-[#68777C]">#{i.getValue()}</span>,
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

  return (
    <div className="space-y-5">
      <div className="border-b border-[#E4E9E6] pb-4">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[#246B60]">
          Module 03 • {period.quarterCode}
        </span>
        <h1 className="mt-0.5 text-2xl font-semibold text-[#122D33]">Advisor Explorer</h1>
        <p className="mt-0.5 text-sm text-[#68777C]">
          Rankings, flows, market attribution, and drill-down into advisor books.
        </p>
      </div>

      <section className="rounded-md border border-[#E4E9E6] bg-white">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-[#E4E9E6] bg-[#F6F7F4]">
                  {hg.headers.map((h) => (
                    <th key={h.id} className="whitespace-nowrap px-3.5 py-2.5 font-semibold text-[#68777C]">
                      <button
                        type="button"
                        onClick={h.column.getToggleSortingHandler()}
                        className="inline-flex items-center gap-1 hover:text-[#122D33]"
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        <ArrowUpDown className="h-3 w-3 opacity-60" />
                      </button>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-[#E4E9E6]">
              {advisorsQ.isLoading ? (
                <tr>
                  <td colSpan={12} className="px-4 py-8 text-center text-[#68777C]">
                    Loading advisor books...
                  </td>
                </tr>
              ) : (
                table.getRowModel().rows.map((row) => (
                  <tr key={row.id} className="hover:bg-[#F6F7F4]/70">
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="whitespace-nowrap px-3.5 py-2.5 text-[#122D33]">
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
    </div>
  );
}
