import { Download, FileSpreadsheet, FileText, Table2 } from "lucide-react";

import { useFilters } from "@/context/FilterContext";
import { getExcelExportUrl, getTableauExportUrl } from "@/lib/api";

const TABLEAU_DATASETS: {
  id:
    | "advisor_performance"
    | "asset_movement"
    | "segment_performance"
    | "monthly_flows"
    | "reconciliation_exceptions";
  title: string;
  filename: string;
  description: string;
  granularity: string;
}[] = [
  {
    id: "advisor_performance",
    title: "Advisor Performance Extract",
    filename: "advisor_performance.csv",
    description:
      "Advisor-level opening/closing AUM, gross inflows/outflows, external net flows, firm-style NNA, market movement, and NNA rank.",
    granularity: "1 row per advisor per quarter",
  },
  {
    id: "asset_movement",
    title: "Asset Movement Bridge Extract",
    filename: "asset_movement.csv",
    description:
      "Account/segment monthly asset bridge components: opening, NNA, market movement, fees, other adjustments, residual.",
    granularity: "Monthly bridge components",
  },
  {
    id: "segment_performance",
    title: "Segment Performance Extract",
    filename: "segment_performance.csv",
    description:
      "Business segment AUM share, NNA growth rate, external net flows, and market attribution.",
    granularity: "1 row per segment per quarter",
  },
  {
    id: "monthly_flows",
    title: "Monthly Flows Time Series",
    filename: "monthly_flows.csv",
    description:
      "24-month historical flow series comparing External Net Flows, Firm-Style NNA, Market Movement, and Fees.",
    granularity: "1 row per month (Oct 2024 – Sep 2026)",
  },
  {
    id: "reconciliation_exceptions",
    title: "Reconciliation Exceptions Extract",
    filename: "reconciliation_exceptions.csv",
    description:
      "Detected reporting exceptions with reported vs reconstructed balances, variance, severity, and root-cause classification.",
    granularity: "1 row per detected exception",
  },
];

const EXCEL_SHEETS = [
  "01 Executive Summary",
  "02 Asset Movement Bridge",
  "03 Advisor Performance",
  "04 Business Segments",
  "05 Client Flow Analysis",
  "06 Reconciliation Exceptions",
  "07 Source Data",
  "08 Metric Definitions",
  "09 Report Metadata",
];

export function ReportsPage() {
  const { period } = useFilters();

  const excelUrl = getExcelExportUrl({
    quarter_code: period.quarterCode,
  });

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight text-[#122D33]">
            Management Reports &amp; BI Exports
          </h1>
          <span className="rounded border border-[#246B60]/30 bg-[#246B60]/10 px-2 py-0.5 text-[11px] font-medium text-[#246B60]">
            SYNTHETIC · LIVE SQL EXPORTS
          </span>
        </div>
        <p className="mt-1 text-sm text-[#68777C]">
          Generate board-ready Excel workbooks with live formulas and Tableau-ready CSV
          extracts for <strong className="text-[#122D33]">{period.quarterCode}</strong>.
          All exported totals reconcile directly to warehouse SQL models.
        </p>
      </div>

      {/* Excel Management Workbook Card */}
      <div className="rounded-lg border border-[#E4E9E6] bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-[#246B60]" />
              <h2 className="text-base font-semibold text-[#122D33]">
                AUMVerity Quarterly Wealth Management Report (.xlsx)
              </h2>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-[#68777C]">
              9-worksheet institutional workbook built with <code className="font-mono">openpyxl</code>,
              featuring frozen header rows, auto-filters, accounting currency formatting{" "}
              (<code className="font-mono">$#,##0.00;($#,##0.00);"-"</code>), and live
              Excel reconciliation formulas (<code className="font-mono">Closing = Opening + Movements</code>).
            </p>
          </div>

          <a
            href={excelUrl}
            className="inline-flex items-center gap-2 rounded-md bg-[#246B60] px-4 py-2 text-xs font-medium text-white shadow-sm hover:bg-[#1c564d]"
          >
            <Download className="h-4 w-4" />
            Download Excel Workbook ({period.quarterCode})
          </a>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {EXCEL_SHEETS.map((sheet) => (
            <div
              key={sheet}
              className="rounded border border-[#E4E9E6] bg-[#F6F7F4] px-3 py-2 text-[11px] font-medium text-[#122D33]"
            >
              {sheet}
            </div>
          ))}
        </div>
      </div>

      {/* Tableau CSV Extracts */}
      <div className="rounded-lg border border-[#E4E9E6] bg-white p-6">
        <div className="flex items-center gap-2">
          <Table2 className="h-5 w-5 text-[#246B60]" />
          <h2 className="text-base font-semibold text-[#122D33]">
            Tableau-Ready CSV Extracts
          </h2>
        </div>
        <p className="mt-1 text-xs text-[#68777C]">
          Normalized flat extracts formatted for Tableau Desktop / Public ingestion. See{" "}
          <code className="font-mono">docs/TABLEAU_INTEGRATION.md</code> for the 4-dashboard
          workbook specification and calculated field formulas.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {TABLEAU_DATASETS.map((ds) => (
            <div
              key={ds.id}
              className="flex flex-col justify-between rounded-lg border border-[#E4E9E6] bg-[#F6F7F4]/60 p-4"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs font-semibold text-[#122D33]">
                    {ds.title}
                  </h3>
                  <FileText className="h-3.5 w-3.5 text-[#68777C]" />
                </div>
                <p className="mt-1 font-mono text-[11px] text-[#246B60]">
                  {ds.filename}
                </p>
                <p className="mt-2 text-xs leading-relaxed text-[#68777C]">
                  {ds.description}
                </p>
              </div>

              <div className="mt-4 flex items-center justify-between border-t border-[#E4E9E6] pt-3">
                <span className="text-[11px] text-[#68777C]">{ds.granularity}</span>
                <a
                  href={getTableauExportUrl(ds.id, {
                    quarter_code: period.quarterCode,
                  })}
                  className="inline-flex items-center gap-1 rounded border border-[#E4E9E6] bg-white px-2.5 py-1 text-[11px] font-medium text-[#122D33] hover:bg-[#F6F7F4]"
                >
                  <Download className="h-3 w-3 text-[#246B60]" />
                  CSV
                </a>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
