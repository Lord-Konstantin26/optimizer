from dataclasses import dataclass
from math import ceil


@dataclass
class SiteInput:
    name: str
    current_demand: float
    annual_growth: float
    fast_share: float
    station_capacity: float
    station_power_kw: float
    station_cost: float
    grid_power_kw: float
    simultaneity: float
    grid_upgrade_cost_per_100kw: float
    annual_revenue_per_station: float
    annual_opex_per_station: float
    accessibility_score: float = 80.0


@dataclass
class YearResult:
    year: int
    demand: float
    stations: int
    utilization: float
    installed_power_kw: float
    effective_power_kw: float
    grid_reserve_kw: float


@dataclass
class SiteResult:
    name: str
    years: list
    capex: float
    total_capex: float
    total_investment: float
    annual_opex: float
    annual_revenue: float
    annual_cash_flow: float
    payback_years: float
    grid_upgrade_required: bool
    grid_upgrade_cost: float
    grid_deficit_kw: float
    grid_upgrade_year: int | None
    demand_score: float
    grid_score: float
    economics_score: float
    accessibility_score: float
    total_score: float
    verdict: str


def calculate_demand(current_demand, annual_growth, year=0):
    return current_demand * ((1 + annual_growth / 100) ** year)


def calculate_fast_demand(total_demand, fast_share):
    return total_demand * fast_share / 100


def calculate_stations(fast_demand, station_capacity):
    return max(1, ceil(fast_demand / station_capacity))


def calculate_year(site: SiteInput, year: int) -> YearResult:
    demand = calculate_demand(site.current_demand, site.annual_growth, year)
    fast_demand = calculate_fast_demand(demand, site.fast_share)
    stations = calculate_stations(fast_demand, site.station_capacity)

    installed_power = stations * site.station_power_kw
    effective_power = installed_power * site.simultaneity
    reserve = site.grid_power_kw - effective_power

    utilization = min(
        150.0,
        fast_demand / max(stations * site.station_capacity, 1) * 100,
    )

    return YearResult(
        year=year,
        demand=demand,
        stations=stations,
        utilization=utilization,
        installed_power_kw=installed_power,
        effective_power_kw=effective_power,
        grid_reserve_kw=reserve,
    )


def calculate_grid_upgrade(site: SiteInput, years):
    # We check the whole planning horizon. The first year with a deficit
    # determines when reinforcement becomes necessary.
    worst_deficit = 0.0
    upgrade_year = None

    for year_result in years:
        deficit = max(
            0.0,
            year_result.effective_power_kw - site.grid_power_kw,
        )
        if deficit > worst_deficit:
            worst_deficit = deficit
            upgrade_year = year_result.year

    blocks = ceil(worst_deficit / 100) if worst_deficit > 0 else 0
    cost = blocks * site.grid_upgrade_cost_per_100kw

    return worst_deficit, cost, upgrade_year


def calculate_economics(site: SiteInput, year_result: YearResult, grid_upgrade_cost=0):
    stations = year_result.stations
    capex = stations * site.station_cost
    total_investment = capex + grid_upgrade_cost

    annual_revenue = stations * site.annual_revenue_per_station
    annual_opex = stations * site.annual_opex_per_station
    annual_cash_flow = annual_revenue - annual_opex

    payback = (
        total_investment / annual_cash_flow
        if annual_cash_flow > 0
        else float("inf")
    )

    return (
        capex,
        total_investment,
        annual_revenue,
        annual_opex,
        annual_cash_flow,
        payback,
    )


def calculate_scores(site: SiteInput, year0: YearResult, payback: float):
    # Project assumptions, not an official RSZS methodology.
    # Demand score rewards meaningful demand without making every
    # candidate automatically "good".
    demand_score = max(
        0.0,
        min(100.0, site.current_demand / 180.0 * 100.0),
    )

    reserve_ratio = site.grid_power_kw / max(year0.effective_power_kw, 1)

    if reserve_ratio >= 1.50:
        grid_score = 100.0
    elif reserve_ratio >= 1.0:
        grid_score = 55.0 + (reserve_ratio - 1.0) / 0.50 * 45.0
    else:
        grid_score = max(0.0, reserve_ratio * 55.0)

    economics_score = (
        max(0.0, min(100.0, 100.0 - payback * 15.0))
        if payback != float("inf")
        else 0.0
    )

    accessibility_score = max(0.0, min(100.0, site.accessibility_score))

    total_score = (
        demand_score * 0.40
        + grid_score * 0.25
        + economics_score * 0.20
        + accessibility_score * 0.15
    )

    return (
        demand_score,
        grid_score,
        economics_score,
        accessibility_score,
        total_score,
    )


def calculate_verdict(total_score, payback, year3_utilization, grid_upgrade_required):
    if grid_upgrade_required:
        return "GRID UPGRADE"

    if total_score >= 70 and payback <= 6 and year3_utilization <= 90:
        return "BUILD"

    return "DON'T BUILD"


def optimize_site(site: SiteInput, horizon=3):
    years = [calculate_year(site, y) for y in range(horizon + 1)]

    (
        grid_deficit,
        grid_upgrade_cost,
        grid_upgrade_year,
    ) = calculate_grid_upgrade(site, years)

    (
        capex,
        total_investment,
        annual_revenue,
        annual_opex,
        annual_cash_flow,
        payback,
    ) = calculate_economics(
        site,
        years[0],
        grid_upgrade_cost,
    )

    (
        demand_score,
        grid_score,
        economics_score,
        accessibility_score,
        total_score,
    ) = calculate_scores(
        site,
        years[0],
        payback,
    )

    grid_upgrade_required = grid_upgrade_cost > 0

    verdict = calculate_verdict(
        total_score,
        payback,
        years[-1].utilization,
        grid_upgrade_required,
    )

    return SiteResult(
        name=site.name,
        years=years,
        capex=capex,
        total_capex=capex,
        total_investment=total_investment,
        annual_opex=annual_opex,
        annual_revenue=annual_revenue,
        annual_cash_flow=annual_cash_flow,
        payback_years=payback,
        grid_upgrade_required=grid_upgrade_required,
        grid_upgrade_cost=grid_upgrade_cost,
        grid_deficit_kw=grid_deficit,
        grid_upgrade_year=grid_upgrade_year,
        demand_score=demand_score,
        grid_score=grid_score,
        economics_score=economics_score,
        accessibility_score=accessibility_score,
        total_score=total_score,
        verdict=verdict,
    )


def generate_candidates(heatmap_df, n_candidates=12, min_distance=0.012):
    """
    Select candidates from several demand bands rather than taking only
    the hottest cells. This makes the optimization problem spatially
    meaningful: low, medium and high demand locations are all considered.
    """
    if heatmap_df is None or len(heatmap_df) == 0:
        return []

    df = heatmap_df.copy()
    df["band"] = pd_qcut_safe(df["intensity"].tolist(), 5)

    selected = []
    # Start with high-demand locations, then medium and low-demand ones.
    band_order = sorted(
        df["band"].dropna().unique().tolist(),
        key=lambda x: x[0] if hasattr(x, "__getitem__") else 0,
        reverse=True,
    )

    # Fall back to intensity ranking if bands cannot be constructed.
    if not band_order:
        ranked = df.sort_values("intensity", ascending=False)
        return _spatial_select(ranked, n_candidates, min_distance)

    # Round-robin across bands to avoid a cluster of identical candidates.
    per_band = {band: df[df["band"] == band].sort_values(
        "intensity", ascending=False
    ) for band in band_order}

    made_progress = True
    while len(selected) < n_candidates and made_progress:
        made_progress = False
        for band in band_order:
            frame = per_band[band]
            if frame.empty:
                continue

            for _, row in frame.iterrows():
                point = {"lat": float(row["lat"]), "lon": float(row["lon"])}
                if all(
                    ((point["lat"] - p["lat"]) ** 2
                     + (point["lon"] - p["lon"]) ** 2) ** 0.5
                    >= min_distance
                    for p in selected
                ):
                    selected.append(point)
                    made_progress = True
                    break

                # Prevent scanning forever once this band is exhausted.
            if len(selected) >= n_candidates:
                break

        # Remove used points from each band for the next round.
        if made_progress:
            used = {(round(p["lat"], 6), round(p["lon"], 6)) for p in selected}
            for band in band_order:
                frame = per_band[band]
                if not frame.empty:
                    per_band[band] = frame[
                        ~frame.apply(
                            lambda r: (
                                round(float(r["lat"]), 6),
                                round(float(r["lon"]), 6),
                            ) in used,
                            axis=1,
                        )
                    ]

    if len(selected) < n_candidates:
        ranked = df.sort_values("intensity", ascending=False)
        extra = _spatial_select(
            ranked,
            n_candidates,
            min_distance,
            existing=selected,
        )
        selected = extra[:n_candidates]

    return selected[:n_candidates]


def _spatial_select(ranked, n_candidates, min_distance, existing=None):
    selected = list(existing or [])

    for _, row in ranked.iterrows():
        point = {"lat": float(row["lat"]), "lon": float(row["lon"])}
        if all(
            ((point["lat"] - p["lat"]) ** 2
             + (point["lon"] - p["lon"]) ** 2) ** 0.5
            >= min_distance
            for p in selected
        ):
            selected.append(point)

        if len(selected) >= n_candidates:
            break

    return selected


def pd_qcut_safe(series, q):
    # Lightweight replacement for pandas.qcut so optimizer.py stays
    # independent of pandas.
    values = sorted(float(x) for x in series)
    if not values:
        return []

    n = len(values)
    cuts = []
    for i in range(1, q):
        idx = min(n - 1, int(n * i / q))
        cuts.append(values[idx])

    def label(x):
        x = float(x)
        band = 0
        for cut in cuts:
            if x >= cut:
                band += 1
        return (band, band)

    return [label(x) for x in series]
