import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { FilterProvider } from "@/context/FilterContext";
import { AdvisorDetail } from "@/pages/AdvisorDetail";
import { AdvisorExplorer } from "@/pages/AdvisorExplorer";
import { AssetBridgePage } from "@/pages/AssetBridgePage";
import { ClientAccountExplorer } from "@/pages/ClientAccountExplorer";
import { ExecutiveOverview } from "@/pages/ExecutiveOverview";
import { FlowAnalytics } from "@/pages/FlowAnalytics";
import { InvestigationWorkspace } from "@/pages/InvestigationWorkspace";
import { MetricDictionaryPage } from "@/pages/MetricDictionaryPage";
import { ReconciliationCenter } from "@/pages/ReconciliationCenter";
import { ReportsPage } from "@/pages/ReportsPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export function AppRoutes() {
  return (
    <FilterProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<ExecutiveOverview />} />
          <Route path="/bridge" element={<AssetBridgePage />} />
          <Route path="/advisors" element={<AdvisorExplorer />} />
          <Route path="/advisors/:advisorId" element={<AdvisorDetail />} />
          <Route path="/clients" element={<ClientAccountExplorer />} />
          <Route path="/clients/:clientId" element={<ClientAccountExplorer />} />
          <Route path="/flows" element={<FlowAnalytics />} />
          <Route path="/reconciliation" element={<ReconciliationCenter />} />
          <Route path="/investigations" element={<InvestigationWorkspace />} />
          <Route path="/lineage" element={<MetricDictionaryPage />} />
          <Route path="/exports" element={<ReportsPage />} />
        </Route>
      </Routes>
    </FilterProvider>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
