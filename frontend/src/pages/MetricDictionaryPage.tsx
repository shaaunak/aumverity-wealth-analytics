import { useQuery } from "@tanstack/react-query";
import { BookOpen, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { fetchMetricDictionary } from "@/lib/api";

export function MetricDictionaryPage() {
  const [queryText, setQueryText] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");

  const dictQuery = useQuery({
    queryKey: ["metric-dictionary"],
    queryFn: fetchMetricDictionary,
  });

  const items = dictQuery.data ?? [];

  const categories = useMemo(() => {
    const s = new Set<string>();
    for (const item of items) {
      if (item.category) s.add(item.category);
    }
    return Array.from(s).sort();
  }, [items]);

  const filtered = useMemo(() => {
    const q = queryText.trim().toLowerCase();
    return items.filter((item) => {
      if (categoryFilter !== "ALL" && item.category !== categoryFilter) {
        return false;
      }
      if (!q) return true;
      return (
        item.metric_id.toLowerCase().includes(q) ||
        item.display_name.toLowerCase().includes(q) ||
        item.formula_expression.toLowerCase().includes(q) ||
        item.sql_view_name.toLowerCase().includes(q)
      );
    });
  }, [items, queryText, categoryFilter]);

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight text-[#122D33]">
            Metric Dictionary &amp; SQL Lineage
          </h1>
          <span className="rounded border border-[#246B60]/30 bg-[#246B60]/10 px-2 py-0.5 text-[11px] font-medium text-[#246B60]">
            GOVERNED DEFINITIONS
          </span>
        </div>
        <p className="mt-1 text-sm text-[#68777C]">
          Explicit formulas, inclusion/exclusion policies, ownership, and backing SQL
          warehouse views for every KPI in AUMVERITY.
        </p>
      </div>

      {/* Search & Category Filter */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[#E4E9E6] bg-white px-4 py-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-[#68777C]" />
          <input
            type="text"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            placeholder="Search metric ID, formula, or SQL view..."
            className="w-full rounded border border-[#E4E9E6] bg-[#F6F7F4] py-1.5 pl-8 pr-3 text-xs text-[#122D33] placeholder:text-[#68777C]"
          />
        </div>

        <label className="flex items-center gap-2 text-xs font-medium text-[#68777C]">
          Category
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded border border-[#E4E9E6] bg-[#F6F7F4] px-2.5 py-1.5 text-xs text-[#122D33]"
          >
            <option value="ALL">All Categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>

      {/* Dictionary Cards */}
      <div className="space-y-3">
        {dictQuery.isLoading && (
          <div className="rounded-lg border border-[#E4E9E6] bg-white p-8 text-center text-xs text-[#68777C]">
            Loading governed metric definitions...
          </div>
        )}
        {filtered.map((m) => (
          <div
            key={m.metric_id}
            className="rounded-lg border border-[#E4E9E6] bg-white p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-[#246B60]" />
                <h2 className="text-sm font-semibold text-[#122D33]">
                  {m.display_name}
                </h2>
                <span className="rounded bg-[#F6F7F4] px-2 py-0.5 font-mono text-[11px] text-[#68777C]">
                  {m.metric_id}
                </span>
              </div>
              <div className="flex items-center gap-2 text-[11px] text-[#68777C]">
                <span className="rounded border border-[#E4E9E6] px-2 py-0.5 font-medium text-[#122D33]">
                  {m.category}
                </span>
                <span>Owner: {m.owner}</span>
              </div>
            </div>

            <div className="mt-3 rounded bg-[#F6F7F4] px-3 py-2 font-mono text-xs text-[#122D33]">
              {m.formula_expression}
            </div>

            <div className="mt-3 grid grid-cols-1 gap-3 text-xs md:grid-cols-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[#246B60]">
                  Inclusion Policy
                </p>
                <p className="mt-0.5 text-[#122D33]">{m.inclusion_policy}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[#C45B51]">
                  Exclusion Policy
                </p>
                <p className="mt-0.5 text-[#122D33]">{m.exclusion_policy}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-[#68777C]">
                  SQL Source Model
                </p>
                <p className="mt-0.5 font-mono text-[11px] text-[#122D33]">
                  {m.sql_view_name}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
