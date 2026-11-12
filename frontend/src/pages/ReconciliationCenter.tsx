import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpDown,
  CheckCircle2,
  Database,
  Download,
  FileSearch,
  ShieldCheck,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { useFilters } from "@/context/FilterContext";
import {
  acknowledgeReconciliationIssue,
  fetchOverview,
  fetchReconciliation,
  getTableauExportUrl,
  type ReconciliationIssue,
} from "@/lib/api";
import { formatCurrencyExact, toNum } from "@/lib/format";

function severityBadgeClass(severity: string): string {
  switch (severity.toUpperCase()) {
    case "CRITICAL":
    case "HIGH":
      return "border-[#C45B51]/40 bg-[#C45B51]/10 text-[#9B3B32]";
    case "MEDIUM":
      return "border-[#C59B64]/40 bg-[#C59B64]/15 text-[#7A5928]";
    default:
      return "border-[#E4E9E6] bg-[#F6F7F4] text-[#68777C]";
  }
}

function statusBadgeClass(status: string): string {
  if (status.toUpperCase() === "ACKNOWLEDGED" || status.toUpperCase() === "RESOLVED") {
    return "border-[#246B60]/30 bg-[#246B60]/10 text-[#246B60]";
  }
  return "border-[#C59B64]/40 bg-[#C59B64]/15 text-[#7A5928]";
}

function downloadIssueEvidenceCsv(issue: ReconciliationIssue) {
  const rows: string[][] = [
    [
      "issue_code",
      "issue_type",
      "severity",
      "affected_period",
      "affected_scope",
      "reported_amount_usd",
      "expected_amount_usd",
      "difference_usd",
      "likely_reason",
      "detection_rule",
      "status",
    ],
    [
      issue.issue_code,
      issue.issue_type,
      issue.severity,
      issue.affected_period,
      issue.affected_scope,
      issue.reported_amount_usd,
      issue.expected_amount_usd,
      issue.difference_usd,
      issue.likely_reason,
      issue.detection_rule ?? "",
      issue.status,
    ],
  ];

  if (issue.source_records && issue.source_records.length > 0) {
    rows.push([]);
    const keys = Object.keys(issue.source_records[0]);
    rows.push(["source_record", ...keys]);
    for (const rec of issue.source_records) {
      rows.push(["detail", ...keys.map((k) => String(rec[k] ?? ""))]);
    }
  }

  const csv = rows
    .map((r) =>
      r.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","),
    )
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${issue.issue_code}_evidence.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ReconciliationCenter() {
  const { period, segmentId } = useFilters();
  const queryClient = useQueryClient();

  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [periodFilter, setPeriodFilter] = useState<string>("ALL");
  const [sortDir, setSortDir] = useState<"desc" | "asc">("desc");
  const [selectedIssueId, setSelectedIssueId] = useState<string | null>(null);

  const reconQuery = useQuery({
    queryKey: ["reconciliation-issues"],
    queryFn: fetchReconciliation,
  });

  const overviewQuery = useQuery({
    queryKey: ["overview", period.startDate, period.endDate, segmentId],
    queryFn: () =>
      fetchOverview({
        startDate: period.startDate,
        endDate: period.endDate,
        segmentId: segmentId || undefined,
      }),
  });

  const ackMutation = useMutation({
    mutationFn: (issueId: string) => acknowledgeReconciliationIssue(issueId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reconciliation-issues"] });
      queryClient.invalidateQueries({ queryKey: ["overview"] });
    },
  });

  const issues = reconQuery.data ?? [];

  const availablePeriods = useMemo(() => {
    const set = new Set<string>();
    for (const i of issues) {
      if (i.affected_period) set.add(i.affected_period);
    }
    return Array.from(set).sort().reverse();
  }, [issues]);

  const filteredIssues = useMemo(() => {
    return issues
      .filter((i) =>
        severityFilter === "ALL"
          ? true
          : i.severity.toUpperCase() === severityFilter,
      )
      .filter((i) =>
        periodFilter === "ALL" ? true : i.affected_period === periodFilter,
      )
      .slice()
      .sort((a, b) => {
        const va = Math.abs(toNum(a.difference_usd));
        const vb = Math.abs(toNum(b.difference_usd));
        return sortDir === "desc" ? vb - va : va - vb;
      });
  }, [issues, severityFilter, periodFilter, sortDir]);

  const selectedIssue = useMemo(
    () => issues.find((i) => i.issue_id === selectedIssueId) ?? null,
    [issues, selectedIssueId],
  );

  const totalAbsVariance = useMemo(
    () => issues.reduce((acc, i) => acc + Math.abs(toNum(i.difference_usd)), 0),
    [issues],
  );
  const materialExceptions = useMemo(
    () =>
      issues.filter(
        (i) =>
          i.severity.toUpperCase() === "HIGH" ||
          i.severity.toUpperCase() === "CRITICAL",
      ).length,
    [issues],
  );

  const scopesChecked = 40;
  const affectedScopes = new Set(issues.map((i) => i.affected_scope)).size;
  const reconciledScopes = Math.max(0, scopesChecked - affectedScopes);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight text-[#122D33]">
              Financial Reconciliation Center
            </h1>
            <span className="rounded border border-[#246B60]/30 bg-[#246B60]/10 px-2 py-0.5 text-[11px] font-medium text-[#246B60]">
              SYNTHETIC · READ-ONLY FINANCIAL DATA
            </span>
          </div>
          <p className="mt-1 text-sm text-[#68777C]">
            Independent balance reconstruction versus management-reported snapshots.
            Variances remain visible until resolved at source.
          </p>
        </div>

        <a
          href={getTableauExportUrl("reconciliation_exceptions", {
            quarter_code: period.quarterCode,
          })}
          className="inline-flex items-center gap-2 rounded-md border border-[#E4E9E6] bg-white px-3 py-1.5 text-xs font-medium text-[#122D33] shadow-sm hover:bg-[#F6F7F4]"
        >
          <Download className="h-3.5 w-3.5 text-[#246B60]" />
          Export All Exceptions (CSV)
        </a>
      </div>

      {/* Top Summary KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-lg border border-[#E4E9E6] bg-white p-4">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[#68777C]">
            Reporting Scopes Checked
          </p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-[#122D33]">
            {scopesChecked}
          </p>
          <p className="mt-1 text-xs text-[#68777C]">Advisor reporting books</p>
        </div>

        <div className="rounded-lg border border-[#E4E9E6] bg-white p-4">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[#68777C]">
            Reconciled Scopes
          </p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-[#246B60]">
            {reconciledScopes} / {scopesChecked}
          </p>
          <p className="mt-1 text-xs text-[#68777C]">Zero unexplained residual</p>
        </div>

        <div className="rounded-lg border border-[#E4E9E6] bg-white p-4">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[#68777C]">
            Material Exceptions
          </p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-[#C45B51]">
            {materialExceptions}
          </p>
          <p className="mt-1 text-xs text-[#68777C]">
            {issues.length} total detected issues
          </p>
        </div>

        <div className="rounded-lg border border-[#E4E9E6] bg-white p-4">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[#68777C]">
            Total Absolute Variance
          </p>
          <p className="mt-1.5 text-2xl font-semibold tabular-nums text-[#122D33]">
            {formatCurrencyExact(totalAbsVariance)}
          </p>
          <p className="mt-1 text-xs text-[#68777C]">Reported vs reconstructed</p>
        </div>

        <div className="rounded-lg border border-[#E4E9E6] bg-white p-4">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[#68777C]">
            Latest Successful Run
          </p>
          <div className="mt-1.5 flex items-center gap-1.5">
            <ShieldCheck className="h-5 w-5 text-[#246B60]" />
            <span className="text-sm font-semibold text-[#122D33]">
              {overviewQuery.data?.period.end_date ?? period.endDate}
            </span>
          </div>
          <p className="mt-1 text-xs text-[#68777C]">
            Completeness:{" "}
            {overviewQuery.data?.reporting_completeness_pct
              ? `${overviewQuery.data.reporting_completeness_pct}%`
              : "EXCEPTIONS_FLAGGED"}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-[#E4E9E6] bg-white px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-medium text-[#68777C]">
            Severity
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="rounded border border-[#E4E9E6] bg-[#F6F7F4] px-2.5 py-1 text-xs text-[#122D33]"
            >
              <option value="ALL">All Severities</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
          </label>

          <label className="flex items-center gap-2 text-xs font-medium text-[#68777C]">
            Reporting Period
            <select
              value={periodFilter}
              onChange={(e) => setPeriodFilter(e.target.value)}
              className="rounded border border-[#E4E9E6] bg-[#F6F7F4] px-2.5 py-1 text-xs text-[#122D33]"
            >
              <option value="ALL">All Periods</option>
              {availablePeriods.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={() => setSortDir((d) => (d === "desc" ? "asc" : "desc"))}
          className="inline-flex items-center gap-1.5 rounded border border-[#E4E9E6] bg-[#F6F7F4] px-2.5 py-1 text-xs font-medium text-[#122D33] hover:bg-[#E4E9E6]/60"
        >
          <ArrowUpDown className="h-3.5 w-3.5 text-[#246B60]" />
          Sort by Variance ({sortDir === "desc" ? "Largest First" : "Smallest First"})
        </button>
      </div>

      {/* Exceptions Table */}
      <div className="overflow-hidden rounded-lg border border-[#E4E9E6] bg-white">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-[#E4E9E6] bg-[#F6F7F4] text-[11px] font-semibold uppercase tracking-wider text-[#68777C]">
              <tr>
                <th className="px-4 py-3">Issue ID</th>
                <th className="px-4 py-3">Period</th>
                <th className="px-4 py-3">Advisor / Scope</th>
                <th className="px-4 py-3 text-right">Reported Amount</th>
                <th className="px-4 py-3 text-right">Calculated Amount</th>
                <th className="px-4 py-3 text-right">Variance</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#E4E9E6]">
              {reconQuery.isLoading && (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-[#68777C]">
                    Loading reconciliation checks...
                  </td>
                </tr>
              )}
              {!reconQuery.isLoading && filteredIssues.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-4 py-8 text-center text-[#68777C]">
                    No reconciliation exceptions match the active filters.
                  </td>
                </tr>
              )}
              {filteredIssues.map((issue) => {
                const diff = toNum(issue.difference_usd);
                return (
                  <tr
                    key={issue.issue_id}
                    onClick={() => setSelectedIssueId(issue.issue_id)}
                    className={`cursor-pointer transition-colors hover:bg-[#F6F7F4] ${
                      selectedIssueId === issue.issue_id ? "bg-[#246B60]/5" : ""
                    }`}
                  >
                    <td className="px-4 py-3 font-mono font-medium text-[#122D33]">
                      {issue.issue_code}
                    </td>
                    <td className="px-4 py-3 tabular-nums text-[#122D33]">
                      {issue.affected_period}
                    </td>
                    <td className="px-4 py-3 font-medium text-[#122D33]">
                      {issue.affected_scope}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-[#122D33]">
                      {formatCurrencyExact(issue.reported_amount_usd)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-[#122D33]">
                      {formatCurrencyExact(issue.expected_amount_usd)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-semibold tabular-nums ${
                        diff < 0 ? "text-[#C45B51]" : "text-[#246B60]"
                      }`}
                    >
                      {formatCurrencyExact(issue.difference_usd, true)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded border px-2 py-0.5 text-[11px] font-semibold ${severityBadgeClass(
                          issue.severity,
                        )}`}
                      >
                        {issue.severity}
                      </span>
                    </td>
                    <td className="max-w-xs truncate px-4 py-3 text-[#68777C]">
                      {issue.likely_reason}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded border px-2 py-0.5 text-[11px] font-medium ${statusBadgeClass(
                          issue.status,
                        )}`}
                      >
                        {issue.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedIssueId(issue.issue_id);
                        }}
                        className="inline-flex items-center gap-1 rounded border border-[#E4E9E6] bg-white px-2 py-1 text-[11px] font-medium text-[#246B60] hover:bg-[#F6F7F4]"
                      >
                        <FileSearch className="h-3 w-3" />
                        Details
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Interactive Issue Detail Comparison Panel */}
      {selectedIssue && (
        <div className="rounded-lg border border-[#246B60]/30 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#E4E9E6] pb-4">
            <div>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-[#C45B51]" />
                <h2 className="text-base font-semibold text-[#122D33]">
                  {selectedIssue.issue_code} — {selectedIssue.issue_type.replace(/_/g, " ")}
                </h2>
                <span
                  className={`rounded border px-2 py-0.5 text-[11px] font-semibold ${severityBadgeClass(
                    selectedIssue.severity,
                  )}`}
                >
                  {selectedIssue.severity}
                </span>
              </div>
              <p className="mt-1 text-xs text-[#68777C]">
                Scope: <strong className="text-[#122D33]">{selectedIssue.affected_scope}</strong> ·
                Period: <strong className="text-[#122D33]">{selectedIssue.affected_period}</strong>
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => downloadIssueEvidenceCsv(selectedIssue)}
                className="inline-flex items-center gap-1.5 rounded border border-[#E4E9E6] bg-white px-3 py-1.5 text-xs font-medium text-[#122D33] hover:bg-[#F6F7F4]"
              >
                <Download className="h-3.5 w-3.5 text-[#246B60]" />
                Export Issue Evidence
              </button>

              {selectedIssue.status.toUpperCase() !== "ACKNOWLEDGED" ? (
                <button
                  type="button"
                  disabled={ackMutation.isPending}
                  onClick={() => ackMutation.mutate(selectedIssue.issue_id)}
                  className="inline-flex items-center gap-1.5 rounded bg-[#246B60] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#1c564d] disabled:opacity-50"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  {ackMutation.isPending ? "Acknowledging..." : "Acknowledge (Demo Flag)"}
                </button>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded border border-[#246B60]/30 bg-[#246B60]/10 px-3 py-1.5 text-xs font-medium text-[#246B60]">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Acknowledged
                </span>
              )}

              <button
                type="button"
                onClick={() => setSelectedIssueId(null)}
                aria-label="Close issue detail"
                className="rounded p-1 text-[#68777C] hover:bg-[#F6F7F4] hover:text-[#122D33]"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Reported vs Reconstructed Comparison */}
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="rounded border border-[#E4E9E6] bg-[#F6F7F4] p-3.5">
              <p className="text-[11px] font-medium uppercase tracking-wider text-[#68777C]">
                Reported Financial Balance
              </p>
              <p className="mt-1 text-lg font-semibold tabular-nums text-[#122D33]">
                {formatCurrencyExact(selectedIssue.reported_amount_usd)}
              </p>
              <p className="mt-0.5 text-[11px] text-[#68777C]">
                Source: raw.reported_asset_snapshots
              </p>
            </div>

            <div className="rounded border border-[#E4E9E6] bg-[#F6F7F4] p-3.5">
              <p className="text-[11px] font-medium uppercase tracking-wider text-[#68777C]">
                Reconstructed Financial Balance
              </p>
              <p className="mt-1 text-lg font-semibold tabular-nums text-[#246B60]">
                {formatCurrencyExact(selectedIssue.expected_amount_usd)}
              </p>
              <p className="mt-0.5 text-[11px] text-[#68777C]">
                Source: marts.mv_account_monthly_bridge
              </p>
            </div>

            <div className="rounded border border-[#C45B51]/30 bg-[#C45B51]/5 p-3.5">
              <p className="text-[11px] font-medium uppercase tracking-wider text-[#9B3B32]">
                Detected Variance
              </p>
              <p className="mt-1 text-lg font-semibold tabular-nums text-[#C45B51]">
                {formatCurrencyExact(selectedIssue.difference_usd, true)}
              </p>
              <p className="mt-0.5 text-[11px] text-[#68777C]">
                Classification: {selectedIssue.issue_type}
              </p>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded border border-[#E4E9E6] p-3.5">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[#122D33]">
                Evidence-Backed Diagnosis
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-[#122D33]">
                {selectedIssue.likely_reason}
              </p>
              <h4 className="mt-3 text-[11px] font-semibold uppercase tracking-wider text-[#68777C]">
                Detection Rule
              </h4>
              <p className="mt-1 font-mono text-[11px] text-[#246B60]">
                {selectedIssue.detection_rule ?? "Balance & Flow Integrity Check"}
              </p>
            </div>

            <div className="rounded border border-[#E4E9E6] p-3.5">
              <div className="flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-[#246B60]" />
                <h3 className="text-xs font-semibold uppercase tracking-wider text-[#122D33]">
                  SQL Lineage & Verification Query
                </h3>
              </div>
              <pre className="mt-2 overflow-x-auto rounded bg-[#F6F7F4] p-2.5 font-mono text-[11px] text-[#122D33]">
{`SELECT issue_code, issue_type, reported_amount_usd,
       expected_amount_usd, difference_usd
FROM raw.reconciliation_issues
WHERE issue_code = '${selectedIssue.issue_code}';`}
              </pre>
            </div>
          </div>

          {/* Contributing Source Records */}
          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[#122D33]">
              Contributing Source Records ({selectedIssue.source_records?.length ?? 0})
            </h3>
            {selectedIssue.source_records && selectedIssue.source_records.length > 0 ? (
              <div className="mt-2 overflow-x-auto rounded border border-[#E4E9E6]">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#F6F7F4] text-[11px] font-semibold text-[#68777C]">
                    <tr>
                      {Object.keys(selectedIssue.source_records[0]).map((col) => (
                        <th key={col} className="px-3 py-2">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#E4E9E6]">
                    {selectedIssue.source_records.map((rec, idx) => (
                      <tr key={idx}>
                        {Object.values(rec).map((val, cIdx) => (
                          <td
                            key={cIdx}
                            className="px-3 py-2 font-mono text-[11px] text-[#122D33]"
                          >
                            {typeof val === "object" && val !== null
                              ? JSON.stringify(val)
                              : String(val ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="mt-1 text-xs text-[#68777C]">
                No granular source records attached to this exception.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
