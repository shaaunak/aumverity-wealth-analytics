import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppRoutes } from "@/App";

describe("AUMVERITY Phase 04 Institutional UI", () => {
  it("renders AUMVERITY wordmark, synthetic badge, navigation items, and Executive Overview", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <AppRoutes />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText("AUMVERITY")).toBeInTheDocument();
    expect(screen.getByText("SYNTHETIC DATA")).toBeInTheDocument();
    expect(screen.getByText("Executive Overview")).toBeInTheDocument();
    expect(screen.getByText("Understand the movements behind your client assets.")).toBeInTheDocument();
    expect(screen.getByText("Asset Bridge")).toBeInTheDocument();
    expect(screen.getByText("Advisor Explorer")).toBeInTheDocument();
    expect(screen.getByText("Reconciliation")).toBeInTheDocument();
    expect(screen.getByText("Metric Dictionary")).toBeInTheDocument();
  });

  it("renders date-range selector, segment selector, and global search in top bar", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <AppRoutes />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByLabelText("Reporting Period")).toBeInTheDocument();
    expect(screen.getByLabelText("Business Segment")).toBeInTheDocument();
    expect(screen.getByLabelText("Global advisor search")).toBeInTheDocument();
    expect(screen.getByLabelText("Refresh analytical data")).toBeInTheDocument();
  });
});
