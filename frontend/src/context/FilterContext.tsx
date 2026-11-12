import { createContext, useContext, useState, type ReactNode } from "react";

export interface PeriodPreset {
  key: string;
  label: string;
  startDate: string;
  endDate: string;
  quarterCode: string;
}

export const PERIOD_PRESETS: PeriodPreset[] = [
  {
    key: "2026-Q3",
    label: "Q3 2026 (Jul – Sep)",
    startDate: "2026-07-01",
    endDate: "2026-09-30",
    quarterCode: "2026-Q3",
  },
  {
    key: "2026-Q2",
    label: "Q2 2026 (Apr – Jun)",
    startDate: "2026-04-01",
    endDate: "2026-06-30",
    quarterCode: "2026-Q2",
  },
  {
    key: "2026-YTD",
    label: "YTD 2026 (Jan – Sep)",
    startDate: "2026-01-01",
    endDate: "2026-09-30",
    quarterCode: "2026-Q3",
  },
  {
    key: "FULL-24M",
    label: "Full 24M (Oct 2024 – Sep 2026)",
    startDate: "2024-10-01",
    endDate: "2026-09-30",
    quarterCode: "2026-Q3",
  },
];

interface FilterContextValue {
  period: PeriodPreset;
  setPeriodKey: (key: string) => void;
  segmentId: string;
  setSegmentId: (id: string) => void;
  search: string;
  setSearch: (s: string) => void;
}

const FilterContext = createContext<FilterContextValue | null>(null);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [periodKey, setPeriodKey] = useState("2026-Q3");
  const [segmentId, setSegmentId] = useState("");
  const [search, setSearch] = useState("");

  const period = PERIOD_PRESETS.find((p) => p.key === periodKey) ?? PERIOD_PRESETS[0];

  return (
    <FilterContext.Provider
      value={{ period, setPeriodKey, segmentId, setSegmentId, search, setSearch }}
    >
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters() {
  const ctx = useContext(FilterContext);
  if (!ctx) throw new Error("useFilters must be used within FilterProvider");
  return ctx;
}
