export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.toString() || "http://localhost:8000";

export interface HealthStatus {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  calculation_version: string;
  reporting_currency: string;
  data_classification: string;
  timestamp_utc: string;
}

export interface ReadinessStatus {
  status: string;
  database: string;
  detail?: string | null;
  timestamp_utc: string;
}

export interface OverviewData {
  period: { start_date: string; end_date: string };
  query_version: string;
  data_classification: string;
  currency: string;
  opening_assets_usd: string;
  closing_assets_usd: string;
  total_asset_growth_usd: string;
  total_asset_growth_pct: string | null;
  external_net_flows_usd: string;
  firm_style_nna_usd: string;
  gross_inflows_usd: string;
  gross_outflows_usd: string;
  market_driven_movement_usd: string;
  fees_and_commissions_usd: string;
  unexplained_residual_usd: string;
  fee_based_assets_usd: string;
  reporting_completeness_pct: string | null;
  narrative: string;
}

export interface ExplainableKpiData {
  metric_id: string;
  metric_name: string;
  value: string | null;
  unit: string;
  currency: string;
  period: { start_date: string; end_date: string };
  formula: string;
  definition: string;
  components: { name: string; value: string }[];
  top_drivers: {
    entity_id: string | null;
    label: string;
    value: string;
    share_pct: string | null;
    explanation: string;
  }[];
  narrative: string;
  reconciliation: {
    status: string;
    unexplained_residual_usd: string;
    open_issues_count: number;
  };
  lineage: {
    sql_model: string;
    sql_template: string;
    source_tables: string[];
    inclusion_policy: string;
    exclusion_policy: string;
  };
  query_version: string;
}

export interface AssetBridgeStep {
  step_key: string;
  label: string;
  amount_usd: string;
  step_type: string;
}

export interface AssetBridgeData {
  steps: AssetBridgeStep[];
  reconciliation_status: string;
  unexplained_residual_usd: string;
}

export interface SegmentData {
  segment_id: string;
  segment_code: string;
  segment_name: string;
  opening_assets_usd: string;
  closing_assets_usd: string;
  total_growth_usd: string;
  firm_style_nna_usd: string;
  external_net_flows_usd: string;
  market_movement_usd: string;
  nna_growth_rate_pct: string | null;
  segment_aum_share_pct: string | null;
}

export interface AdvisorRow {
  advisor_id: string;
  advisor_code: string;
  advisor_name: string;
  segment_name: string;
  opening_assets_usd: string;
  closing_assets_usd: string;
  aum_growth_usd: string;
  gross_inflows_usd: string;
  gross_outflows_usd: string;
  external_net_flows_usd: string;
  firm_style_nna_usd: string;
  market_movement_usd: string;
  nna_rank: number;
  outflow_rank: number;
}

export interface FlowSeriesRow {
  period_code: string;
  start_date: string;
  end_date: string;
  opening_assets_usd: string;
  closing_assets_usd: string;
  gross_inflows_usd: string;
  gross_outflows_usd: string;
  external_net_flows_usd: string;
  firm_style_nna_usd: string;
  market_driven_movement_usd: string;
  fees_and_commissions_usd: string;
}

export interface ReconciliationIssue {
  issue_id: string;
  issue_code: string;
  issue_type: string;
  severity: string;
  affected_period: string;
  affected_scope: string;
  expected_amount_usd: string;
  reported_amount_usd: string;
  difference_usd: string;
  likely_reason: string;
  detection_rule?: string;
  status: string;
  source_records?: Record<string, unknown>[];
  audit_history?: Record<string, unknown>[];
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`API error (${res.status}) on ${path}`);
  }
  return res.json();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`API error (${res.status}) on ${path}`);
  }
  return res.json();
}

export const fetchHealth = () => getJson<HealthStatus>("/api/v1/health");
export const fetchReadiness = () => getJson<ReadinessStatus>("/api/v1/ready");

export function fetchOverview(params: {
  startDate: string;
  endDate: string;
  segmentId?: string;
}) {
  const q = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
  });
  if (params.segmentId) q.set("segment_id", params.segmentId);
  return getJson<OverviewData>(`/api/v1/overview?${q.toString()}`);
}

export function fetchAssetBridge(params: {
  startDate: string;
  endDate: string;
  segmentId?: string;
}) {
  const q = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
  });
  if (params.segmentId) q.set("segment_id", params.segmentId);
  return getJson<AssetBridgeData>(`/api/v1/asset-bridge?${q.toString()}`);
}

export function fetchExplainableMetric(params: {
  metricId: string;
  startDate: string;
  endDate: string;
  segmentId?: string;
}) {
  const q = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
  });
  if (params.segmentId) q.set("segment_id", params.segmentId);
  return getJson<ExplainableKpiData>(`/api/v1/metrics/${params.metricId}?${q.toString()}`);
}

export function fetchSegments(quarterCode = "2026-Q3") {
  return getJson<SegmentData[]>(`/api/v1/segments?quarter_code=${encodeURIComponent(quarterCode)}`);
}

export function fetchFlows(params: {
  startDate: string;
  endDate: string;
  segmentId?: string;
}) {
  const q = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
  });
  if (params.segmentId) q.set("segment_id", params.segmentId);
  return getJson<FlowSeriesRow[]>(`/api/v1/flows?${q.toString()}`);
}

export function fetchAdvisors(params: {
  quarterCode?: string;
  segmentId?: string;
  search?: string;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  page?: number;
  pageSize?: number;
}) {
  const q = new URLSearchParams({
    quarter_code: params.quarterCode || "2026-Q3",
    page: String(params.page || 1),
    page_size: String(params.pageSize || 40),
    sort_by: params.sortBy || "firm_style_nna_usd",
    sort_dir: params.sortDir || "desc",
  });
  if (params.segmentId) q.set("segment_id", params.segmentId);
  if (params.search) q.set("search", params.search);
  return getJson<{ items: AdvisorRow[]; pagination: { total_items: number } }>(
    `/api/v1/advisors?${q.toString()}`,
  );
}

export const fetchReconciliation = () => getJson<ReconciliationIssue[]>("/api/v1/reconciliation");

export interface EvidenceRow {
  event_id: string;
  external_ref: string;
  account_number: string;
  effective_date: string;
  posted_date: string;
  event_type: string;
  flow_classification: string;
  gross_amount: string;
  fee_amount: string;
  net_amount: string;
}

export function fetchMetricEvidence(params: {
  metricId: string;
  startDate: string;
  endDate: string;
  segmentId?: string;
  page?: number;
  pageSize?: number;
}) {
  const q = new URLSearchParams({
    start_date: params.startDate,
    end_date: params.endDate,
    page: String(params.page || 1),
    page_size: String(params.pageSize || 20),
  });
  if (params.segmentId) q.set("segment_id", params.segmentId);
  return getJson<{
    items: EvidenceRow[];
    pagination: { page: number; page_size: number; total_items: number; total_pages: number };
  }>(`/api/v1/metrics/${params.metricId}/evidence?${q.toString()}`);
}

export interface AdvisorSummaryData {
  performance: AdvisorRow & {
    fees_and_commissions_usd: string;
    internal_transfers_usd: string;
    unexplained_residual_usd: string;
  };
  account_distribution: { account_type: string; account_count: number; total_aum_usd: string }[];
  top_clients: {
    client_id: string;
    client_code: string;
    full_name: string;
    client_tier: string;
    total_aum_usd: string;
    q3_outflows_usd: string;
  }[];
}

export function fetchAdvisorSummary(advisorId: string, quarterCode = "2026-Q3") {
  return getJson<AdvisorSummaryData>(
    `/api/v1/advisors/${advisorId}/summary?quarter_code=${encodeURIComponent(quarterCode)}`,
  );
}

export function fetchAdvisorFlows(advisorId: string) {
  return getJson<
    {
      period_code: string;
      start_date: string;
      end_date: string;
      external_inflows_usd: string;
      external_outflows_usd: string;
      external_net_flows_usd: string;
      firm_style_nna_usd: string;
      internal_transfer_net_usd: string;
    }[]
  >(`/api/v1/advisors/${advisorId}/flows`);
}

export interface ClientListItem {
  client_id: string;
  client_code: string;
  full_name: string;
  client_tier: string;
  risk_profile: string;
  account_count: number;
  total_aum_usd: string;
}

export function fetchClients(params: { search?: string; page?: number; pageSize?: number }) {
  const q = new URLSearchParams({
    page: String(params.page || 1),
    page_size: String(params.pageSize || 25),
  });
  if (params.search) q.set("search", params.search);
  return getJson<{
    items: ClientListItem[];
    pagination: { page: number; page_size: number; total_items: number; total_pages: number };
  }>(`/api/v1/clients?${q.toString()}`);
}

export interface ClientDetailData {
  client_id: string;
  client_code: string;
  full_name: string;
  client_tier: string;
  risk_profile: string;
  onboarding_date: string;
  status: string;
  accounts: {
    account_id: string;
    account_number: string;
    account_type: string;
    status: string;
    latest_aum_usd: string | null;
  }[];
}

export const fetchClientDetail = (clientId: string) =>
  getJson<ClientDetailData>(`/api/v1/clients/${clientId}`);

export interface AccountDetailData {
  account: {
    account_id: string;
    account_number: string;
    account_type: string;
    opened_date: string;
    status: string;
    client_id: string;
    client_code: string;
    client_name: string;
    advisor_id: string;
    advisor_code: string;
    advisor_name: string;
    segment_name: string;
  };
  valuations: {
    as_of_date: string;
    cash_value_usd: string;
    securities_value_usd: string;
    total_aum_usd: string;
  }[];
  positions: {
    ticker: string;
    security_name: string;
    asset_class_name: string;
    quantity: string;
    market_price_usd: string;
    market_value_usd: string;
  }[];
  assignments: {
    effective_from: string;
    effective_to: string | null;
    is_current: boolean;
    assignment_reason: string;
    advisor_code: string;
    advisor_name: string;
  }[];
}

export const fetchAccountDetails = (accountId: string) =>
  getJson<AccountDetailData>(`/api/v1/accounts/${accountId}/details`);

export const fetchAccountTransactions = (accountId: string, page = 1, pageSize = 25) =>
  getJson<{
    items: EvidenceRow[];
    pagination: { page: number; page_size: number; total_items: number; total_pages: number };
  }>(`/api/v1/accounts/${accountId}/transactions?page=${page}&page_size=${pageSize}`);

export interface InvestigationTemplateMeta {
  template_id: string;
  title: string;
  description: string;
}

export interface InvestigationResult {
  template_id: string;
  title: string;
  description: string;
  sql_template: string;
  query_version: string;
  rows: Record<string, string | number | boolean | null>[];
  narrative: string;
}

export const fetchInvestigationTemplates = () =>
  getJson<InvestigationTemplateMeta[]>("/api/v1/investigations/templates");

export const runInvestigation = (body: {
  template_id: string;
  quarter_code: string;
  advisor_code?: string;
  limit?: number;
}) => postJson<InvestigationResult>("/api/v1/investigations/run", body);

export const parseInvestigationIntent = (query: string) =>
  postJson<{
    supported: boolean;
    template_id: string | null;
    quarter_code: string;
    message: string;
  }>("/api/v1/investigations/parse-intent", { query });

export interface SavedInvestigation {
  investigation_id: string;
  name: string;
  template_id: string;
  quarter_code: string;
  calculation_version: string;
  created_at: string;
}

export const fetchSavedInvestigations = () =>
  getJson<SavedInvestigation[]>("/api/v1/investigations/saved");

export const saveInvestigation = (body: {
  name: string;
  template_id: string;
  quarter_code: string;
  filters?: Record<string, unknown>;
  selected_metric?: string;
}) => postJson<SavedInvestigation>("/api/v1/investigations/saved", body);

export const acknowledgeReconciliationIssue = (issueId: string, note?: string) =>
  postJson<ReconciliationIssue>(`/api/v1/reconciliation/${issueId}/acknowledge`, {
    note: note ?? "Acknowledged by analyst in Reconciliation Center (demo-only audit flag).",
  });

export interface PeriodCompareMetricRow {
  metric: string;
  current_usd: string;
  prior_usd: string;
  abs_change_usd: string;
  pct_change: number | null;
}

export interface PeriodCompareRankingRow {
  advisor_code: string;
  advisor_name: string;
  prior_rank: number;
  current_rank: number;
  rank_improvement: number;
  current_nna_usd: string;
  prior_nna_usd: string;
}

export interface PeriodCompareResponse {
  current_quarter: string;
  prior_quarter: string;
  methodology: string;
  metrics: PeriodCompareMetricRow[];
  ranking_changes: PeriodCompareRankingRow[];
}

export const fetchPeriodCompare = (
  currentQuarter = "2026-Q3",
  priorQuarter = "2026-Q2",
) => {
  const q = new URLSearchParams({
    current_quarter: currentQuarter,
    prior_quarter: priorQuarter,
  });
  return getJson<PeriodCompareResponse>(`/api/v1/period-compare?${q.toString()}`);
};

export interface MetricDictionaryItem {
  metric_id: string;
  display_name: string;
  category: string;
  formula_expression: string;
  inclusion_policy: string;
  exclusion_policy: string;
  owner: string;
  sql_view_name: string;
}

export const fetchMetricDictionary = () =>
  getJson<MetricDictionaryItem[]>("/api/v1/metric-dictionary");

export function getExcelExportUrl(params: {
  quarter_code?: string;
  segment_code?: string;
  advisor_code?: string;
} = {}): string {
  const q = new URLSearchParams();
  if (params.quarter_code) q.set("quarter_code", params.quarter_code);
  if (params.segment_code) q.set("segment_code", params.segment_code);
  if (params.advisor_code) q.set("advisor_code", params.advisor_code);
  const qs = q.toString();
  return `${API_BASE_URL}/api/v1/exports/excel${qs ? `?${qs}` : ""}`;
}

export function getTableauExportUrl(
  datasetName:
    | "advisor_performance"
    | "asset_movement"
    | "segment_performance"
    | "monthly_flows"
    | "reconciliation_exceptions",
  params: {
    quarter_code?: string;
    segment_code?: string;
  } = {},
): string {
  const q = new URLSearchParams();
  if (params.quarter_code) q.set("quarter_code", params.quarter_code);
  if (params.segment_code) q.set("segment_code", params.segment_code);
  const qs = q.toString();
  return `${API_BASE_URL}/api/v1/exports/tableau/${datasetName}.csv${qs ? `?${qs}` : ""}`;
}
