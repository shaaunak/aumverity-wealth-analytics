import { useIsFetching, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowLeftRight,
  BookOpen,
  Briefcase,
  CheckCircle2,
  Download,
  FileSearch,
  LayoutDashboard,
  Menu,
  RefreshCw,
  Scale,
  Search,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { PERIOD_PRESETS, useFilters } from "@/context/FilterContext";
import { fetchHealth, fetchReadiness, fetchSegments } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/bridge", label: "Asset Bridge", icon: ArrowLeftRight },
  { to: "/advisors", label: "Advisor Explorer", icon: Briefcase },
  { to: "/clients", label: "Clients & Accounts", icon: Users },
  { to: "/flows", label: "Flow Analytics", icon: Activity },
  { to: "/reconciliation", label: "Reconciliation", icon: Scale },
  { to: "/investigations", label: "Investigations", icon: FileSearch },
  { to: "/exports", label: "Reports", icon: Download },
  { to: "/lineage", label: "Metric Dictionary", icon: BookOpen },
];

export function AppShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<string>("Live");
  const { period, setPeriodKey, segmentId, setSegmentId, search, setSearch } = useFilters();
  const queryClient = useQueryClient();
  const isFetching = useIsFetching();
  const location = useLocation();

  const currentNav =
    NAV_ITEMS.find((n) => (n.end ? location.pathname === n.to : location.pathname.startsWith(n.to))) ??
    NAV_ITEMS[0];

  const healthQuery = useQuery({
    queryKey: ["system", "health"],
    queryFn: fetchHealth,
    retry: false,
    refetchInterval: 60_000,
  });

  const readyQuery = useQuery({
    queryKey: ["system", "ready"],
    queryFn: fetchReadiness,
    retry: false,
    refetchInterval: 60_000,
  });

  const segmentsQuery = useQuery({
    queryKey: ["segments", "2026-Q3"],
    queryFn: () => fetchSegments("2026-Q3"),
  });

  const handleRefresh = async () => {
    await queryClient.invalidateQueries();
    const now = new Date();
    setLastRefreshed(now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
  };

  const isBackendUp = healthQuery.isSuccess && healthQuery.data.status === "ok";
  const isDbConnected = readyQuery.isSuccess && readyQuery.data.database === "connected";

  return (
    <div className="flex min-h-screen bg-[#F6F7F4] text-[#122D33]">
      {/* Desktop Left Navigation (240px) */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-60 flex-col border-r border-[#E4E9E6] bg-white transition-transform lg:static lg:translate-x-0",
          mobileNavOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-start justify-between border-b border-[#E4E9E6] px-5 py-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-[#246B60]" />
              <span className="text-sm font-bold tracking-[0.14em] text-[#122D33]">
                AUMVERITY
              </span>
            </div>
            <p className="mt-1 text-[11px] leading-snug text-[#68777C]">
              Wealth Intelligence &amp; Asset Movement
            </p>
          </div>
          <button
            type="button"
            onClick={() => setMobileNavOpen(false)}
            aria-label="Close navigation menu"
            className="rounded p-1 text-[#68777C] hover:bg-[#F6F7F4] lg:hidden"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 px-3 py-4" aria-label="Primary Navigation">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setMobileNavOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#246B60]",
                  isActive
                    ? "border-l-2 border-[#246B60] bg-[#246B60]/8 text-[#122D33] font-semibold"
                    : "text-[#68777C] hover:bg-[#F6F7F4] hover:text-[#122D33]",
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-[#E4E9E6] px-4 py-3.5 text-[11px] text-[#68777C]">
          <p className="italic leading-relaxed text-[#68777C]">
            &ldquo;Every asset movement explained. Every number verified.&rdquo;
          </p>
          <div className="mt-2.5 flex items-center justify-between border-t border-[#E4E9E6] pt-2">
            <span>Model Version</span>
            <span className="font-mono font-medium text-[#122D33]">
              {healthQuery.data?.calculation_version ?? "v1.0.0"}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span>System Status</span>
            <span className="inline-flex items-center gap-1 font-medium text-[#122D33]">
              <CheckCircle2
                className={cn(
                  "h-3 w-3",
                  isBackendUp && isDbConnected ? "text-[#246B60]" : "text-[#C45B51]",
                )}
              />
              {isBackendUp && isDbConnected ? "Verified" : "Offline"}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Clean Top Contextual Toolbar */}
        <header className="sticky top-0 z-30 border-b border-[#E4E9E6] bg-white/95 backdrop-blur-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 lg:px-6">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation menu"
                className="rounded-md border border-[#E4E9E6] p-1.5 text-[#122D33] hover:bg-[#F6F7F4] lg:hidden"
              >
                <Menu className="h-4 w-4" />
              </button>
              <span className="text-sm font-semibold text-[#122D33]">{currentNav.label}</span>
              <span className="inline-flex items-center rounded border border-[#C59B64]/50 bg-[#C59B64]/10 px-2 py-0.5 text-[10px] font-semibold tracking-wider text-[#8C6835]">
                SYNTHETIC DATA
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-2.5 text-xs">
              <label className="sr-only" htmlFor="period-select">
                Reporting Period
              </label>
              <select
                id="period-select"
                value={period.key}
                onChange={(e) => setPeriodKey(e.target.value)}
                className="rounded-md border border-[#E4E9E6] bg-white px-2.5 py-1.5 text-xs font-medium text-[#122D33] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#246B60]"
              >
                {PERIOD_PRESETS.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.label}
                  </option>
                ))}
              </select>

              <label className="sr-only" htmlFor="segment-select">
                Business Segment
              </label>
              <select
                id="segment-select"
                value={segmentId}
                onChange={(e) => setSegmentId(e.target.value)}
                className="rounded-md border border-[#E4E9E6] bg-white px-2.5 py-1.5 text-xs font-medium text-[#122D33] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#246B60]"
              >
                <option value="">All Segments</option>
                {segmentsQuery.data?.map((seg) => (
                  <option key={seg.segment_id} value={seg.segment_id}>
                    {seg.segment_name}
                  </option>
                ))}
              </select>

              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-[#68777C]" />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search advisor..."
                  aria-label="Global advisor search"
                  className="w-40 rounded-md border border-[#E4E9E6] bg-[#F6F7F4] py-1.5 pl-8 pr-2.5 text-xs text-[#122D33] placeholder:text-[#68777C] focus:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#246B60]"
                />
              </div>

              <div className="hidden items-center gap-2 border-l border-[#E4E9E6] pl-2.5 text-[11px] text-[#68777C] xl:flex">
                <span className="font-mono font-semibold text-[#122D33]">USD</span>
                <span>•</span>
                <span>As of 2026-09-30</span>
                <span>•</span>
                <span>{lastRefreshed}</span>
              </div>

              <button
                type="button"
                onClick={handleRefresh}
                aria-label="Refresh analytical data"
                className="inline-flex items-center gap-1.5 rounded-md border border-[#E4E9E6] bg-white px-2.5 py-1.5 text-xs font-medium text-[#122D33] hover:bg-[#F6F7F4] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#246B60]"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", isFetching > 0 && "animate-spin")} />
                <span className="hidden sm:inline">Refresh</span>
              </button>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1440px] flex-1 p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
