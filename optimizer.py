from dataclasses import dataclass
from math import ceil


# ============================================================
# INPUT
# ============================================================

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


# ============================================================
# YEAR RESULT
# ============================================================

@dataclass
class YearResult:
    year: int
    demand: float
    stations: int
    utilization: float
    installed_power_kw: float
    effective_power_kw: float
    grid_reserve_kw: float


# ============================================================
# FINAL RESULT
# ============================================================

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

    demand_score: float
    grid_score: float
    economics_score: float
    accessibility_score: float

    total_score: float
    verdict: str


# ============================================================
# DEMAND
# ============================================================

def calculate_demand(
    current_demand,
    growth,
    years
):
    return current_demand * (
        (1 + growth / 100) ** years
    )


def calculate_fast_demand(
    total_demand,
    fast_share
):
    return total_demand * fast_share / 100


# ============================================================
# STATIONS
# ============================================================

def calculate_stations(
    demand,
    station_capacity
):
    return max(
        1,
        ceil(demand / station_capacity)
    )


# ============================================================
# YEAR CALCULATION
# ============================================================

def calculate_year(
    site: SiteInput,
    year: int
):

    total_demand = calculate_demand(
        site.current_demand,
        site.annual_growth,
        year
    )

    fast_demand = calculate_fast_demand(
        total_demand,
        site.fast_share
    )

    stations = calculate_stations(
        fast_demand,
        site.station_capacity
    )

    installed_power = (
        stations *
        site.station_power_kw
    )

    effective_power = (
        installed_power *
        site.simultaneity
    )

    grid_reserve = (
        site.grid_power_kw -
        effective_power
    )

    utilization = (
        fast_demand /
        (stations * site.station_capacity)
    ) * 100

    return YearResult(
        year=year,
        demand=fast_demand,
        stations=stations,
        utilization=utilization,
        installed_power_kw=installed_power,
        effective_power_kw=effective_power,
        grid_reserve_kw=grid_reserve
    )


# ============================================================
# GRID
# ============================================================

def calculate_grid_upgrade(
    site: SiteInput,
    year_result: YearResult
):

    deficit = max(
        0,
        year_result.effective_power_kw -
        site.grid_power_kw
    )

    if deficit <= 0:
        return False, 0

    blocks = ceil(
        deficit / 100
    )

    return (
        True,
        blocks *
        site.grid_upgrade_cost_per_100kw
    )


# ============================================================
# ECONOMICS
# ============================================================

def calculate_economics(
    site: SiteInput,
    year_result: YearResult,
    grid_upgrade_cost: float = 0
):

    stations = year_result.stations

    # Стоимость зарядных станций
    capex = (
        stations *
        site.station_cost
    )

    # Стоимость модернизации сети
    total_investment = (
        capex +
        grid_upgrade_cost
    )

    # Годовая выручка
    annual_revenue = (
        stations *
        site.annual_revenue_per_station
    )

    # Годовые расходы
    annual_opex = (
        stations *
        site.annual_opex_per_station
    )

    # Денежный поток
    annual_cash_flow = (
        annual_revenue -
        annual_opex
    )

    # Окупаемость
    if annual_cash_flow > 0:

        payback = (
            total_investment /
            annual_cash_flow
        )

    else:

        payback = float("inf")

    return (
        capex,
        total_investment,
        annual_revenue,
        annual_opex,
        annual_cash_flow,
        payback
    )


# ============================================================
# SCORE
# ============================================================

def calculate_scores(
    site: SiteInput,
    years,
    payback
):

    year_3 = years[3]

    # ----------------------------------------
    # Demand
    # ----------------------------------------

    demand_score = min(
        100,
        year_3.utilization /
        90 *
        100
    )

    # ----------------------------------------
    # Grid
    # ----------------------------------------

    if year_3.grid_reserve_kw >= 0:

        grid_score = 100

    else:

        grid_score = max(
            0,
            100 +
            (
                year_3.grid_reserve_kw /
                site.grid_power_kw *
                100
            )
        )

    # ----------------------------------------
    # Economics
    # ----------------------------------------

    if payback <= 3:

        economics_score = 100

    elif payback <= 5:

        economics_score = 85

    elif payback <= 6:

        economics_score = 70

    elif payback <= 8:

        economics_score = 50

    else:

        economics_score = 20

    # ----------------------------------------
    # Final score
    # ----------------------------------------

    total_score = (
        demand_score * 0.40 +
        grid_score * 0.25 +
        economics_score * 0.20 +
        site.accessibility_score * 0.15
    )

    return (
        demand_score,
        grid_score,
        economics_score,
        site.accessibility_score,
        total_score
    )


# ============================================================
# VERDICT
# ============================================================

def calculate_verdict(
    total_score,
    payback,
    year_3,
    grid_upgrade_required
):

    if grid_upgrade_required:

        return "GRID UPGRADE"

    if (
        total_score >= 70
        and payback <= 6
        and year_3.utilization <= 90
    ):

        return "BUILD"

    return "DON'T BUILD"


# ============================================================
# MAIN OPTIMIZER
# ============================================================

def optimize_site(
    site: SiteInput
):

    years = [
        calculate_year(
            site,
            year
        )
        for year in range(4)
    ]

    year_3 = years[3]

    (
        grid_upgrade_required,
        grid_upgrade_cost
    ) = calculate_grid_upgrade(
        site,
        year_3
    )

    (
        capex,
        total_investment,
        annual_revenue,
        annual_opex,
        annual_cash_flow,
        payback
    ) = calculate_economics(
        site,
        years[0],
        grid_upgrade_cost
    )

    (
        demand_score,
        grid_score,
        economics_score,
        accessibility_score,
        total_score
    ) = calculate_scores(
        site,
        years,
        payback
    )

    verdict = calculate_verdict(
        total_score,
        payback,
        year_3,
        grid_upgrade_required
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

        grid_upgrade_required=
            grid_upgrade_required,

        grid_upgrade_cost=
            grid_upgrade_cost,

        demand_score=demand_score,
        grid_score=grid_score,
        economics_score=economics_score,
        accessibility_score=
            accessibility_score,

        total_score=total_score,
        verdict=verdict
    )


# ============================================================
# AUTOMATIC CANDIDATE GENERATION
# ============================================================

def generate_candidates(
    heatmap_df,
    n_candidates=10,
    min_distance=0.008
):

    points = (
        heatmap_df
        .sort_values(
            "demand",
            ascending=False
        )
        .reset_index(drop=True)
    )

    selected = []

    for _, point in points.iterrows():

        lat = point["lat"]
        lon = point["lon"]

        too_close = False

        for candidate in selected:

            distance = (
                (
                    lat -
                    candidate["lat"]
                ) ** 2
                +
                (
                    lon -
                    candidate["lon"]
                ) ** 2
            ) ** 0.5

            if distance < min_distance:

                too_close = True
                break

        if too_close:
            continue

        selected.append({
            "lat": lat,
            "lon": lon,
            "demand": point["demand"]
        })

        if len(selected) >= n_candidates:

            break

    return selected