from dataclasses import dataclass
from math import ceil

import pandas as pd


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
    demand_score_override: float | None = None
    grid_score_override: float | None = None
    coverage_gap_score: float = 50.0


@dataclass
class YearResult:
    year: int
    demand: float
    stations: int
    utilization: float
    installed_power_kw: float
    effective_power_kw: float
    grid_reserve_kw: float
    grid_deficit_kw: float


@dataclass
class SiteResult:
    name: str
    years: list
    capex: float
    total_investment: float
    annual_opex: float
    annual_revenue: float
    annual_cash_flow: float
    payback_years: float
    grid_upgrade_required: bool
    grid_upgrade_cost: float
    grid_deficit_kw: float
    demand_score: float
    grid_score: float
    economics_score: float
    accessibility_score: float
    coverage_gap_score: float
    total_score: float
    verdict: str
    current_verdict: str
    planned_year: int | None
    yearly_decisions: list


def calculate_demand(current_demand, annual_growth, year=0):
    return current_demand * ((1 + annual_growth / 100.0) ** year)


def calculate_fast_demand(total_demand, fast_share):
    return total_demand * fast_share / 100.0


def calculate_stations(fast_demand, station_capacity):
    return max(1, ceil(fast_demand / max(station_capacity, 1e-9)))


def calculate_year(site: SiteInput, year: int) -> YearResult:
    demand = calculate_demand(site.current_demand, site.annual_growth, year)
    fast_demand = calculate_fast_demand(demand, site.fast_share)
    stations = calculate_stations(fast_demand, site.station_capacity)

    installed_power = stations * site.station_power_kw
    effective_power = installed_power * site.simultaneity
    reserve = site.grid_power_kw - effective_power
    deficit = max(0.0, -reserve)

    utilization = min(
        150.0,
        fast_demand / max(stations * site.station_capacity, 1) * 100.0,
    )

    return YearResult(
        year=year,
        demand=demand,
        stations=stations,
        utilization=utilization,
        installed_power_kw=installed_power,
        effective_power_kw=effective_power,
        grid_reserve_kw=reserve,
        grid_deficit_kw=deficit,
    )


def calculate_grid_upgrade(site: SiteInput, years):
    max_deficit = max((y.grid_deficit_kw for y in years), default=0.0)
    blocks = ceil(max_deficit / 100.0) if max_deficit > 0 else 0
    cost = blocks * site.grid_upgrade_cost_per_100kw
    return max_deficit, cost


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

    return capex, total_investment, annual_revenue, annual_opex, annual_cash_flow, payback


def calculate_scores(site: SiteInput, year0: YearResult, payback: float):
    # Unified, explainable score. Weights are project assumptions, not official RSZS methodology.
    demand_score = (
        max(0.0, min(100.0, site.demand_score_override))
        if site.demand_score_override is not None
        else max(0.0, min(100.0, 45.0 + site.fast_share * 0.35 + (year0.demand / max(site.current_demand, 1)) * 18.0))
    )

    if site.grid_score_override is not None:
        grid_score = max(0.0, min(100.0, site.grid_score_override))
    else:
        reserve_ratio = site.grid_power_kw / max(year0.effective_power_kw, 1.0)
        if reserve_ratio >= 1.30:
            grid_score = 100.0
        elif reserve_ratio >= 1.0:
            grid_score = 70.0 + (reserve_ratio - 1.0) / 0.30 * 30.0
        else:
            grid_score = max(0.0, reserve_ratio * 70.0)

    economics_score = (
        max(0.0, min(100.0, 100.0 - payback * 12.0))
        if payback != float("inf")
        else 0.0
    )
    accessibility_score = max(0.0, min(100.0, site.accessibility_score))
    coverage_gap_score = max(0.0, min(100.0, site.coverage_gap_score))

    total_score = (
        demand_score * 0.35
        + coverage_gap_score * 0.15
        + grid_score * 0.25
        + accessibility_score * 0.10
        + economics_score * 0.15
    )

    return demand_score, grid_score, economics_score, accessibility_score, coverage_gap_score, total_score


def _score_for_year(site: SiteInput, year_result: YearResult, base_demand: float, grid_upgrade_cost: float):
    """Recalculate decision score for a specific forecast year."""
    demand_score_base = (
        site.demand_score_override
        if site.demand_score_override is not None
        else 45.0 + site.fast_share * 0.35 + 18.0
    )
    demand_score = max(
        0.0,
        min(100.0, float(demand_score_base) * year_result.demand / max(base_demand, 1e-9)),
    )

    reserve_ratio = site.grid_power_kw / max(year_result.effective_power_kw, 1.0)
    if reserve_ratio >= 1.30:
        grid_score = 100.0
    elif reserve_ratio >= 1.0:
        grid_score = 70.0 + (reserve_ratio - 1.0) / 0.30 * 30.0
    else:
        grid_score = max(0.0, reserve_ratio * 70.0)

    stations = year_result.stations
    investment = stations * site.station_cost + grid_upgrade_cost
    cash_flow = stations * (site.annual_revenue_per_station - site.annual_opex_per_station)
    payback = investment / cash_flow if cash_flow > 0 else float("inf")
    economics_score = max(0.0, min(100.0, 100.0 - payback * 12.0)) if payback != float("inf") else 0.0
    accessibility_score = max(0.0, min(100.0, site.accessibility_score))
    coverage_gap_score = max(0.0, min(100.0, site.coverage_gap_score))

    total_score = (
        demand_score * 0.35
        + coverage_gap_score * 0.15
        + grid_score * 0.25
        + accessibility_score * 0.10
        + economics_score * 0.15
    )
    return {
        "year": year_result.year,
        "score": total_score,
        "demand_score": demand_score,
        "grid_score": grid_score,
        "economics_score": economics_score,
        "payback": payback,
        "utilization": year_result.utilization,
        "grid_deficit_kw": year_result.grid_deficit_kw,
        "grid_upgrade_cost": grid_upgrade_cost,
        "stations": year_result.stations,
    }


def _passes_non_grid(decision):
    return (
        decision["score"] >= 70
        and decision["payback"] <= 6
        and decision["utilization"] <= 90
    )


def optimize_site(site: SiteInput, horizon=3):
    years = [calculate_year(site, y) for y in range(horizon + 1)]

    yearly_decisions = []
    for year_result in years:
        deficit = year_result.grid_deficit_kw
        upgrade_blocks = ceil(deficit / 100.0) if deficit > 0 else 0
        upgrade_cost = upgrade_blocks * site.grid_upgrade_cost_per_100kw
        decision = _score_for_year(site, year_result, years[0].demand, upgrade_cost)
        decision["passes"] = _passes_non_grid(decision)
        if decision["passes"] and deficit <= 0:
            decision["status"] = "BUILD NOW" if year_result.year == 0 else f"PLAN — YEAR {year_result.year}"
        elif decision["passes"] and deficit > 0:
            decision["status"] = "GRID UPGRADE NOW" if year_result.year == 0 else f"GRID UPGRADE — YEAR {year_result.year}"
        else:
            decision["status"] = "NOT READY"
        yearly_decisions.append(decision)

    current_decision = yearly_decisions[0]
    future_ready = next((d for d in yearly_decisions if d["passes"]), None)
    if current_decision["passes"]:
        verdict = current_decision["status"]
    elif future_ready is not None:
        verdict = future_ready["status"]
    else:
        verdict = "DON'T BUILD"

    planned_year = future_ready["year"] if future_ready is not None and future_ready["year"] > 0 else None

    # Current-year financial figures are shown separately from future planning.
    current_upgrade_cost = current_decision["grid_upgrade_cost"]
    capex, total_investment, annual_revenue, annual_opex, annual_cash_flow, payback = calculate_economics(
        site, years[0], current_upgrade_cost
    )
    grid_upgrade_required = years[0].grid_deficit_kw > 0

    return SiteResult(
        name=site.name,
        years=years,
        capex=capex,
        total_investment=total_investment,
        annual_opex=annual_opex,
        annual_revenue=annual_revenue,
        annual_cash_flow=annual_cash_flow,
        payback_years=payback,
        grid_upgrade_required=grid_upgrade_required,
        grid_upgrade_cost=current_upgrade_cost,
        grid_deficit_kw=years[0].grid_deficit_kw,
        demand_score=current_decision["demand_score"],
        grid_score=current_decision["grid_score"],
        economics_score=current_decision["economics_score"],
        accessibility_score=max(0.0, min(100.0, site.accessibility_score)),
        coverage_gap_score=max(0.0, min(100.0, site.coverage_gap_score)),
        total_score=current_decision["score"],
        verdict=verdict,
        current_verdict=current_decision["status"],
        planned_year=planned_year,
        yearly_decisions=yearly_decisions,
    )


def generate_candidates(
    heatmap_df,
    n_candidates=12,
    min_distance=0.014,
    existing_stations=None,
    substations=None,
    fast_share=60.0,
    station_capacity=100.0,
    station_power_kw=150.0,
    simultaneity=0.6,
    station_cost=5_000_000.0,
    annual_revenue_per_station=3_000_000.0,
    annual_opex_per_station=1_000_000.0,
    grid_upgrade_cost_per_100kw=1_000_000.0,
):
    """Выбор площадок с пространственным балансом.

    Важное отличие V7:
    - сектора строятся по всей исследуемой территории, а не по уже отфильтрованным
      горячим ячейкам;
    - спрос остаётся главным фактором, но не может единолично забрать все точки;
    - близость к существующим станциям сильнее снижает привлекательность;
    - если строгий min_distance не позволяет набрать заданное число кандидатов,
      расстояние постепенно ослабляется;
    - вторая фаза добирает точки глобально, сохраняя пространственное разнообразие.

    Все веса и пороги — проектные допущения демонстрационного прототипа.
    """
    if heatmap_df is None or len(heatmap_df) == 0:
        return []

    import numpy as np

    work_all = heatmap_df.copy().reset_index(drop=True)

    # 1. Убираем только внешний край карты. Секторные границы при этом
    #    рассчитываются ПО ВСЕЙ внутренней территории, а не по горячим ячейкам.
    lat_min = float(work_all["lat"].min())
    lat_max = float(work_all["lat"].max())
    lon_min = float(work_all["lon"].min())
    lon_max = float(work_all["lon"].max())

    lat_margin = (lat_max - lat_min) * 0.07
    lon_margin = (lon_max - lon_min) * 0.07

    inner = work_all[
        (work_all["lat"] >= lat_min + lat_margin)
        & (work_all["lat"] <= lat_max - lat_margin)
        & (work_all["lon"] >= lon_min + lon_margin)
        & (work_all["lon"] <= lon_max - lon_margin)
    ].copy()

    if inner.empty:
        inner = work_all.copy()

    # 2. Не отбрасываем всё, кроме горячего центра.
    #    Небольшой ненулевой спрос остаётся в пуле кандидатов, чтобы сектора
    #    могли участвовать в пространственном покрытии.
    demand_floor = max(
        12.0,
        float(inner["demand_score_proxy"].quantile(0.08))
        if "demand_score_proxy" in inner.columns else 12.0,
    )
    work = inner[inner["demand_score_proxy"] >= demand_floor].copy()
    if work.empty:
        work = inner.copy()

    def min_distance_to_points(lat, lon, points):
        if not points:
            return float("inf")
        return min(
            ((lat - p["lat"]) ** 2 + (lon - p["lon"]) ** 2) ** 0.5
            for p in points
        )

    # 3. Пробел покрытия. Используем насыщение, чтобы отсутствие станции
    #    далеко от города не превращалось в бесконечный бонус.
    if existing_stations:
        work["charger_gap_deg"] = work.apply(
            lambda r: min_distance_to_points(
                float(r.lat), float(r.lon), existing_stations
            ),
            axis=1,
        )
        # 0.018° ~= порядка 2 км по широте. Дальше бонус почти насыщается.
        coverage_scale = 0.018
        work["coverage_gap_score"] = (
            1.0 - np.exp(-work["charger_gap_deg"] / coverage_scale)
        ) * 100.0
    else:
        work["charger_gap_deg"] = np.inf
        work["coverage_gap_score"] = 50.0

    # 4. Сетевая пригодность.
    if substations:
        grid_caps = []
        grid_distances = []
        for row in work.itertuples():
            nearest = min(
                substations,
                key=lambda s: (
                    (row.lat - s["lat"]) ** 2
                    + (row.lon - s["lon"]) ** 2
                ) ** 0.5,
            )
            dist = (
                (row.lat - nearest["lat"]) ** 2
                + (row.lon - nearest["lon"]) ** 2
            ) ** 0.5
            grid_caps.append(float(nearest["capacity_kw"]))
            grid_distances.append(dist)

        work["nearest_grid_capacity"] = grid_caps
        work["grid_distance_deg"] = grid_distances
    else:
        work["nearest_grid_capacity"] = 0.0
        work["grid_distance_deg"] = 0.0

    fast_share = max(0.0, min(100.0, float(fast_share)))
    station_capacity = max(float(station_capacity), 1e-9)
    station_power_kw = max(float(station_power_kw), 1e-9)
    simultaneity = max(0.0, min(1.0, float(simultaneity)))

    fast_demand_proxy = work["raw_demand"] * fast_share / 100.0
    work["stations_proxy"] = np.ceil(
        fast_demand_proxy / station_capacity
    ).clip(lower=1)
    work["required_power_proxy"] = (
        work["stations_proxy"] * station_power_kw * simultaneity
    )

    reserve_proxy = work["nearest_grid_capacity"] - work["required_power_proxy"]
    work["grid_score_proxy"] = (
        (reserve_proxy / work["nearest_grid_capacity"].replace(0, np.nan)) * 100.0
        + 50.0
    ).clip(0, 100).fillna(0)

    grid_upgrade_proxy = (
        np.ceil((-reserve_proxy).clip(lower=0) / 100.0)
        * grid_upgrade_cost_per_100kw
    )
    annual_cashflow_proxy = work["stations_proxy"] * max(
        0.0, annual_revenue_per_station - annual_opex_per_station
    )
    total_investment_proxy = (
        work["stations_proxy"] * station_cost + grid_upgrade_proxy
    )
    payback_proxy = total_investment_proxy / annual_cashflow_proxy.replace(0, np.nan)
    work["economics_score_proxy"] = (
        100.0 - payback_proxy * 12.0
    ).clip(0, 100).fillna(0)

    # 5. Итоговый pre-score.
    #    Спрос — главный фактор, но покрытие и сеть достаточно сильны,
    #    чтобы точка в уже насыщенном центре не выигрывала автоматически.
    work["candidate_score"] = (
        work["demand_score_proxy"] * 0.40
        + work["coverage_gap_score"] * 0.20
        + work["grid_score_proxy"] * 0.25
        + work["accessibility_score_proxy"] * 0.05
        + work["economics_score_proxy"] * 0.10
    )

    # 6. Сектора по ВСЕЙ внутренней карте.
    #    4 x 4 даёт достаточно пространства для 6–20 кандидатов.
    n_sector_rows = 4
    n_sector_cols = 4
    sector_lat_min = float(inner["lat"].min())
    sector_lat_max = float(inner["lat"].max())
    sector_lon_min = float(inner["lon"].min())
    sector_lon_max = float(inner["lon"].max())

    def sector_id(lat, lon):
        row = min(
            n_sector_rows - 1,
            max(
                0,
                int(
                    (lat - sector_lat_min)
                    / max(sector_lat_max - sector_lat_min, 1e-9)
                    * n_sector_rows
                ),
            ),
        )
        col = min(
            n_sector_cols - 1,
            max(
                0,
                int(
                    (lon - sector_lon_min)
                    / max(sector_lon_max - sector_lon_min, 1e-9)
                    * n_sector_cols
                ),
            ),
        )
        return row, col

    sector_ids = [sector_id(float(r.lat), float(r.lon)) for r in work.itertuples()]
    work["sector_row"] = [x[0] for x in sector_ids]
    work["sector_col"] = [x[1] for x in sector_ids]
    work["sector"] = [
        f"Сектор {r + 1}-{c + 1}"
        for r, c in sector_ids
    ]

    # Для первого прохода нужен умеренный спрос, но не только горячие зоны.
    sector_demand_threshold = max(
        18.0,
        float(work["demand_score_proxy"].quantile(0.20)),
    )
    eligible = work[
        work["demand_score_proxy"] >= sector_demand_threshold
    ].copy()

    candidates = []

    def add_row(row):
        candidates.append(
            {
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "intensity": float(row["intensity"]),
                "candidate_score": float(row["candidate_score"]),
                "coverage_gap_score": float(row["coverage_gap_score"]),
                "grid_score_proxy": float(row["grid_score_proxy"]),
                "accessibility_score_proxy": float(row["accessibility_score_proxy"]),
                "demand_score_proxy": float(row["demand_score_proxy"]),
                "economics_score_proxy": float(row["economics_score_proxy"]),
                "stations_proxy": int(row["stations_proxy"]),
                "required_power_proxy": float(row["required_power_proxy"]),
                "nearest_grid_capacity": float(row["nearest_grid_capacity"]),
                "charger_gap_deg": float(row["charger_gap_deg"]),
                "sector": str(row["sector"]),
            }
        )

    # 7. Адаптивное расстояние.
    #    Сначала строго, затем мягче. Поэтому модель не возвращает 4 точки
    #    только потому, что в горячей зоне слишком много близких ячеек.
    distance_levels = [
        float(min_distance),
        float(min_distance) * 0.82,
        float(min_distance) * 0.65,
        float(min_distance) * 0.50,
        float(min_distance) * 0.35,
    ]

    def acceptable(row, distance_limit):
        if not candidates:
            return True
        lat = float(row["lat"])
        lon = float(row["lon"])
        return min_distance_to_points(lat, lon, candidates) >= distance_limit

    # 8. Первый проход: максимум одна точка из сектора.
    #    Сначала используем самые сильные сектора, но не разрешаем одному
    #    сектору занять весь список.
    sector_best = []
    for sector, group in eligible.groupby("sector"):
        ranked = group.sort_values("candidate_score", ascending=False)
        chosen = ranked.iloc[0]
        sector_best.append(chosen)

    sector_best = sorted(
        sector_best,
        key=lambda r: float(r["candidate_score"]),
        reverse=True,
    )

    for distance_limit in distance_levels:
        for row in sector_best:
            if len(candidates) >= n_candidates:
                break
            if acceptable(row, distance_limit):
                add_row(row)
        if len(candidates) >= n_candidates:
            break

    # 9. Второй проход: глобальное добирание. Сохраняем разнообразие,
    #    но не запрещаем дополнительные точки в действительно сильной зоне.
    available = work.copy()

    for distance_limit in distance_levels:
        while len(candidates) < n_candidates and len(available) > 0:
            best_idx = None
            best_value = -float("inf")

            for idx, row in available.iterrows():
                if not acceptable(row, distance_limit):
                    continue

                lat = float(row["lat"])
                lon = float(row["lon"])

                if candidates:
                    d_selected = min_distance_to_points(lat, lon, candidates)
                    diversity = min(
                        1.0,
                        d_selected / max(distance_limit * 2.5, 1e-9),
                    )
                else:
                    diversity = 1.0

                # Небольшой бонус за новый сектор.
                sector = str(row["sector"])
                used_sectors = {c["sector"] for c in candidates}
                sector_bonus = 1.06 if sector not in used_sectors else 1.0

                value = (
                    float(row["candidate_score"])
                    * (0.82 + 0.18 * diversity)
                    * sector_bonus
                )

                if value > best_value:
                    best_value = value
                    best_idx = idx

            if best_idx is None:
                break

            add_row(available.loc[best_idx])
            available = available.drop(index=best_idx)

        if len(candidates) >= n_candidates:
            break

    return candidates
