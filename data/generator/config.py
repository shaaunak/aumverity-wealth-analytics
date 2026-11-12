from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    num_advisors: int
    num_households: int
    num_clients: int
    num_accounts: int
    target_events: int
    baseline_date: date = date(2026, 9, 30)
    history_months: int = 24
    daily_window_days: int = 90


PROFILES: dict[str, ProfileConfig] = {
    "demo": ProfileConfig(
        name="demo",
        num_advisors=40,
        num_households=1800,
        num_clients=3000,
        num_accounts=5000,
        target_events=60000,
    ),
    "large": ProfileConfig(
        name="large",
        num_advisors=200,
        num_households=12000,
        num_clients=20000,
        num_accounts=35000,
        target_events=350000,
    ),
}

SEGMENTS = [
    ("ALWM", "Advisor-Led Wealth Management", "Full-service advisory relationships"),
    ("SDI", "Self-Directed Investing", "Client-directed brokerage and retirement accounts"),
    ("WPW", "Workplace Wealth", "Employer-sponsored and executive wealth plans"),
]

ACCOUNT_TYPES = [
    "Fee-based advisory",
    "Brokerage",
    "Retirement",
    "Cash management",
]

ASSET_CLASSES = [
    ("EQ", "Equities", False),
    ("FI", "Fixed income", False),
    ("ETF", "ETFs", False),
    ("MF", "Mutual funds", False),
    ("CASH", "Cash", True),
    ("ALT", "Other investment assets", False),
]

# Synthetic instrument definitions (clearly synthetic tickers & names)
SYNTHETIC_SECURITIES = [
    ("SYN-EQ-USLC", "Verity Synthetic US Large Cap Equity", "EQ", False, 145.00, 0.11, 0.16),
    ("SYN-EQ-TECH", "Verity Synthetic Innovation & Tech Equity", "EQ", False, 210.00, 0.22, 0.24),
    ("SYN-EQ-INTL", "Verity Synthetic Global Developed Equity", "EQ", False, 88.00, 0.08, 0.15),
    ("SYN-FI-CORE", "Verity Synthetic Core Aggregate Bond", "FI", False, 98.50, 0.04, 0.05),
    ("SYN-FI-MUNI", "Verity Synthetic Tax-Exempt Municipal Bond", "FI", False, 102.00, 0.035, 0.04),
    ("SYN-ETF-SPX", "Verity Synthetic Broad Market ETF", "ETF", False, 420.00, 0.12, 0.15),
    ("SYN-ETF-AI", "Verity Synthetic Growth Leaders ETF", "ETF", False, 175.00, 0.26, 0.22),
    ("SYN-MF-BAL", "Verity Synthetic Balanced Allocation Fund", "MF", False, 54.00, 0.075, 0.10),
    ("SYN-MF-INC", "Verity Synthetic Income & Dividend Fund", "MF", False, 41.00, 0.06, 0.08),
    ("SYN-ALT-RE", "Verity Synthetic Real Assets & Infra", "ALT", False, 65.00, 0.07, 0.12),
    ("SYN-CASH-MM", "Verity Synthetic Treasury Money Market", "CASH", True, 1.00, 0.045, 0.002),
]

REGIONS = ["Northeast", "Mid-Atlantic", "Southeast", "Midwest", "West", "Southwest"]
CLIENT_TIERS = ["Mass Affluent", "High Net Worth", "Ultra High Net Worth"]
RISK_PROFILES = ["Conservative", "Moderate", "Balanced Growth", "Aggressive Growth"]
