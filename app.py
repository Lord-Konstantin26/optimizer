import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from config import APP_TITLE, DEFAULTS
from optimizer import SiteInput, generate_candidates, optimize_site


st.set_page_config(page_title=APP_TITLE, page_icon="⚡", layout="wide")

st.title("⚡ EV Charging Optimizer")
st.caption("V3 · 2D-пространственная оптимизация размещения зарядной инфраструктуры")


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("Параметры модели")

    current_demand = st.number_input(
        "Базовый спрос, ед./день",
        min_value=1.0,
        value=DEFAULTS["current_demand"],
        step=10.0,
    )

    annual_growth = st.number_input(
        "Годовой рост спроса, %",
        min_value=0.0,
        max_value=100.0,
        value=DEFAULTS["annual_growth"],
        step=5.0,
    )

    fast_share = st.slider(
        "Доля быстрой зарядки, %",
        10.0, 100.0, DEFAULTS["fast_share"], 5.0
    )

    station_capacity = st.number_input(
        "Пропускная способность станции, ед./день",
        min_value=1.0,
        value=DEFAULTS["station_capacity"],
        step=10.0,
    )

    station_power_kw = st.number_input(
        "Мощность станции, кВт",
        min_value=10.0,
        value=DEFAULTS["station_power_kw"],
        step=10.0,
    )

    simultaneity = st.slider(
        "Коэффициент одновременности",
        0.10, 1.00, DEFAULTS["simultaneity"], 0.05
    )

    st.divider()
    st.subheader("Экономика")

    station_cost = st.number_input(
        "Стоимость станции, ₽",
        min_value=100_000.0,
        value=DEFAULTS["station_cost"],
        step=500_000.0,
    )

    grid_upgrade_cost = st.number_input(
        "Усиление сети на 100 кВт, ₽",
        min_value=0.0,
        value=DEFAULTS["grid_upgrade_cost_per_100kw"],
        step=100_000.0,
    )

    annual_revenue = st.number_input(
        "Выручка станции / год, ₽",
        min_value=0.0,
        value=DEFAULTS["annual_revenue_per_station"],
        step=250_000.0,
    )

    annual_opex = st.number_input(
        "OPEX станции / год, ₽",
        min_value=0.0,
        value=DEFAULTS["annual_opex_per_station"],
        step=100_000.0,
    )

    st.divider()

    number_of_candidates = st.slider(
        "Количество кандидатов",
        6, 20, DEFAULTS["number_of_candidates"]
    )

    st.caption(
        "Спрос, подстанции и экономика являются демонстрационными данными."
    )


# ============================================================
# SPATIAL DATA
# ============================================================
MAP_BOUNDS = {
    "lat_min": 55.55,
    "lat_max": 55.90,
    "lon_min": 37.35,
    "lon_max": 37.85,
}

demand_centers = [
    {"lat": 55.885, "lon": 37.475, "intensity": 0.38, "radius": 0.025},
    {"lat": 55.855, "lon": 37.570, "intensity": 0.55, "radius": 0.022},
    {"lat": 55.820, "lon": 37.690, "intensity": 0.48, "radius": 0.024},
    {"lat": 55.790, "lon": 37.445, "intensity": 0.44, "radius": 0.025},
    {"lat": 55.7558, "lon": 37.6176, "intensity": 1.00, "radius": 0.022},
    {"lat": 55.742, "lon": 37.690, "intensity": 0.68, "radius": 0.020},
    {"lat": 55.715, "lon": 37.545, "intensity": 0.58, "radius": 0.024},
    {"lat": 55.690, "lon": 37.690, "intensity": 0.50, "radius": 0.026},
    {"lat": 55.650, "lon": 37.575, "intensity": 0.42, "radius": 0.025},
    {"lat": 55.625, "lon": 37.735, "intensity": 0.36, "radius": 0.024},
    {"lat": 55.835, "lon": 37.390, "intensity": 0.30, "radius": 0.025},
    {"lat": 55.585, "lon": 37.425, "intensity": 0.28, "radius": 0.025},
]

substations = [
    {"name": "ПС-Север", "lat": 55.875, "lon": 37.500, "capacity_kw": 300},
    {"name": "ПС-Север-2", "lat": 55.830, "lon": 37.625, "capacity_kw": 1200},
    {"name": "ПС-Центр", "lat": 55.7558, "lon": 37.6176, "capacity_kw": 250},
    {"name": "ПС-Восток", "lat": 55.790, "lon": 37.730, "capacity_kw": 600},
    {"name": "ПС-СЗ", "lat": 55.790, "lon": 37.440, "capacity_kw": 750},
    {"name": "ПС-ЮЗ", "lat": 55.700, "lon": 37.520, "capacity_kw": 300},
    {"name": "ПС-Юг", "lat": 55.650, "lon": 37.650, "capacity_kw": 1000},
    {"name": "ПС-ЮВ", "lat": 55.690, "lon": 37.760, "capacity_kw": 350},
    {"name": "ПС-Запад", "lat": 55.830, "lon": 37.390, "capacity_kw": 700},
]


def make_heatmap():
    lats = np.linspace(MAP_BOUNDS["lat_min"], MAP_BOUNDS["lat_max"], 115)
    lons = np.linspace(MAP_BOUNDS["lon_min"], MAP_BOUNDS["lon_max"], 145)

    rows = []

    for lat in lats:
        for lon in lons:
            intensity = 0.015

            for center in demand_centers:
                d2 = (lat - center["lat"]) ** 2 + (lon - center["lon"]) ** 2
                intensity += center["intensity"] * np.exp(
                    -d2 / (2 * center["radius"] ** 2)
                )

            rows.append({
                "lat": lat,
                "lon": lon,
                "intensity": intensity,
            })

    df = pd.DataFrame(rows)

    low = df["intensity"].quantile(0.02)
    high = df["intensity"].quantile(0.98)

    df["intensity"] = (
        (df["intensity"] - low) / max(high - low, 1e-9)
    ).clip(0, 1)

    return df


def find_nearest_substation(lat, lon, subs):
    nearest = None
    min_distance = float("inf")

    for sub in subs:
        distance = ((lat - sub["lat"]) ** 2 + (lon - sub["lon"]) ** 2) ** 0.5

        if distance < min_distance:
            min_distance = distance
            nearest = sub

    return nearest, min_distance


def nearest_heatmap_intensity(lat, lon, heatmap):
    distance_sq = (
        (heatmap["lat"] - lat) ** 2
        + (heatmap["lon"] - lon) ** 2
    )
    idx = distance_sq.idxmin()
    return float(heatmap.loc[idx, "intensity"])


def make_sites():
    heatmap_df = make_heatmap()

    candidate_points = generate_candidates(
        heatmap_df,
        n_candidates=number_of_candidates,
        min_distance=0.012,
    )

    sites = []

    for i, point in enumerate(candidate_points):
        nearest, distance = find_nearest_substation(
            point["lat"], point["lon"], substations
        )

        intensity = nearest_heatmap_intensity(
            point["lat"],
            point["lon"],
            heatmap_df,
        )

        demand_multiplier = 0.45 + intensity * 1.55

        accessibility = max(
            55.0,
            min(100.0, 100.0 - distance * 1800),
        )

        sites.append({
            "name": f"Кандидат {i + 1}",
            "lat": point["lat"],
            "lon": point["lon"],
            "demand_multiplier": demand_multiplier,
            "demand_intensity": intensity,
            "accessibility": accessibility,
            "substation": nearest["name"],
            "grid_capacity": nearest["capacity_kw"],
            "substation_distance": distance,
        })

    return heatmap_df, pd.DataFrame(sites)


heatmap_df, sites_df = make_sites()


# ============================================================
# MODEL
# ============================================================
def calculate_results(growth_override=None, fast_share_override=None):
    growth = annual_growth if growth_override is None else growth_override
    fast = fast_share if fast_share_override is None else fast_share_override

    results = []

    for _, site_data in sites_df.iterrows():
        adjusted_demand = current_demand * site_data["demand_multiplier"]

        site = SiteInput(
            name=site_data["name"],
            current_demand=adjusted_demand,
            annual_growth=growth,
            fast_share=fast,
            station_capacity=station_capacity,
            station_power_kw=station_power_kw,
            station_cost=station_cost,
            grid_power_kw=site_data["grid_capacity"],
            simultaneity=simultaneity,
            grid_upgrade_cost_per_100kw=grid_upgrade_cost,
            annual_revenue_per_station=annual_revenue,
            annual_opex_per_station=annual_opex,
            accessibility_score=site_data["accessibility"],
        )

        results.append(optimize_site(site, horizon=3))

    return results


results = calculate_results()


# ============================================================
# HEADER
# ============================================================
build_count = sum(r.verdict == "BUILD" for r in results)
upgrade_count = sum(r.verdict == "GRID UPGRADE" for r in results)
dont_build_count = sum(r.verdict == "DON'T BUILD" for r in results)
avg_score = np.mean([r.total_score for r in results]) if results else 0

m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("Кандидатов", len(results))
m2.metric("BUILD", build_count)
m3.metric("GRID UPGRADE", upgrade_count)
m4.metric("DON'T BUILD", dont_build_count)
m5.metric("Средний score", f"{avg_score:.1f}")


# ============================================================
# MAP
# ============================================================
st.subheader("1. Карта спроса и кандидатов")
st.caption(
    "2D-режим. Синий/зелёный — низкий и средний спрос; "
    "жёлтый/оранжевый/красный — высокий."
)

candidate_map_df = sites_df.copy()

candidate_layer = pdk.Layer(
    "ScatterplotLayer",
    data=candidate_map_df,
    get_position="[lon, lat]",
    get_radius=420,
    radius_min_pixels=4,
    radius_max_pixels=18,
    get_fill_color=[255, 255, 255, 245],
    get_line_color=[15, 15, 15, 255],
    line_width_min_pixels=2,
    pickable=True,
)

heat_layer = pdk.Layer(
    "HeatmapLayer",
    data=heatmap_df,
    get_position="[lon, lat]",
    get_weight="intensity",
    radius_pixels=30,
    intensity=1.0,
    threshold=0.035,
    color_range=[
        [30, 80, 180],
        [40, 150, 190],
        [70, 190, 120],
        [240, 220, 70],
        [245, 145, 45],
        [220, 45, 35],
    ],
)

sub_df = pd.DataFrame(substations)

sub_layer = pdk.Layer(
    "ScatterplotLayer",
    data=sub_df,
    get_position="[lon, lat]",
    get_radius=280,
    radius_min_pixels=3,
    radius_max_pixels=12,
    get_fill_color=[30, 120, 255, 235],
    get_line_color=[255, 255, 255, 255],
    line_width_min_pixels=1,
    pickable=True,
)

map_view = pdk.ViewState(
    latitude=55.735,
    longitude=37.60,
    zoom=9.3,
    pitch=0,
    bearing=0,
)

st.pydeck_chart(
    pdk.Deck(
        layers=[heat_layer, candidate_layer, sub_layer],
        initial_view_state=map_view,
        tooltip={
            "html": "<b>{name}</b><br/>Мощность ПС: {capacity_kw} кВт",
            "style": {
                "backgroundColor": "#1f2937",
                "color": "white",
            },
        },
    ),
    use_container_width=True,
)

l1, l2, l3, l4 = st.columns(4)
l1.markdown("🔵 **Низкий спрос**")
l2.markdown("🟢 **Средний спрос**")
l3.markdown("🟠 **Высокий спрос**")
l4.markdown("🔴 **Пиковый спрос**")


# ============================================================
# CANDIDATE COMPARISON
# ============================================================
st.subheader("2. Сравнение кандидатов")

table_rows = []

for _, site_data in sites_df.iterrows():
    result = next(r for r in results if r.name == site_data["name"])

    table_rows.append({
        "Кандидат": result.name,
        "Спрос ×": round(site_data["demand_multiplier"], 2),
        "Подстанция": site_data["substation"],
        "Сеть, кВт": int(site_data["grid_capacity"]),
        "Score": round(result.total_score, 1),
        "Станций, год 0": result.years[0].stations,
        "Станций, год 3": result.years[3].stations,
        "Util. год 1": f"{result.years[1].utilization:.1f}%",
        "Util. год 3": f"{result.years[3].utilization:.1f}%",
        "CAPEX": result.capex,
        "Усиление сети": result.grid_upgrade_cost,
        "Инвестиции": result.total_investment,
        "Окупаемость": (
            None
            if np.isinf(result.payback_years)
            else round(result.payback_years, 2)
        ),
        "Решение": result.verdict,
    })

table_df = pd.DataFrame(table_rows)

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# DETAILS
# ============================================================
st.subheader("3. Детальный анализ")

for result in sorted(results, key=lambda x: x.total_score, reverse=True):
    with st.expander(
        f"{result.name} — {result.verdict} — score {result.total_score:.1f}"
    ):
        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Demand score", f"{result.demand_score:.1f}")
        c2.metric("Grid score", f"{result.grid_score:.1f}")
        c3.metric("Economics score", f"{result.economics_score:.1f}")
        c4.metric("Accessibility", f"{result.accessibility_score:.1f}")

        forecast = pd.DataFrame([
            {
                "Год": year.year,
                "Спрос": round(year.demand, 1),
                "Станций": year.stations,
                "Utilization": f"{year.utilization:.1f}%",
                "Эфф. мощность, кВт": round(year.effective_power_kw, 1),
                "Резерв сети, кВт": round(year.grid_reserve_kw, 1),
            }
            for year in result.years
        ])

        st.dataframe(
            forecast,
            use_container_width=True,
            hide_index=True,
        )

        a, b, c, d = st.columns(4)

        a.metric("CAPEX", f"{result.capex:,.0f} ₽")
        b.metric("Усиление сети", f"{result.grid_upgrade_cost:,.0f} ₽")
        c.metric("Всего инвестиций", f"{result.total_investment:,.0f} ₽")
        d.metric(
            "Payback",
            "∞"
            if np.isinf(result.payback_years)
            else f"{result.payback_years:.2f} лет",
        )

        if result.grid_upgrade_required:
            st.warning(
                f"В горизонте 0–3 лет выявлен дефицит "
                f"{result.grid_deficit_kw:.0f} кВт. "
                f"Усиление требуется к году {result.grid_upgrade_year}."
            )
        else:
            st.success("Дефицит мощности в горизонте 0–3 лет не выявлен.")


# ============================================================
# SCENARIOS
# ============================================================
st.subheader("4. Сценарный анализ")

scenarios = [
    ("Базовый", annual_growth, fast_share),
    ("Высокий рост", annual_growth + 15, fast_share),
    ("Высокая доля быстрой зарядки", annual_growth, min(100, fast_share + 20)),
    ("Стресс", annual_growth + 25, min(100, fast_share + 20)),
]

scenario_rows = []

for scenario_name, growth_s, fast_s in scenarios:
    scenario_results = calculate_results(
        growth_override=growth_s,
        fast_share_override=fast_s,
    )

    paybacks = [
        r.payback_years
        for r in scenario_results
        if not np.isinf(r.payback_years)
    ]

    scenario_rows.append({
        "Сценарий": scenario_name,
        "Рост спроса": f"{growth_s:.0f}%",
        "Fast charge": f"{fast_s:.0f}%",
        "Макс. score": round(
            max(r.total_score for r in scenario_results), 1
        ),
        "Средняя окупаемость": (
            round(float(np.mean(paybacks)), 2)
            if paybacks else None
        ),
        "GRID UPGRADE": sum(
            r.verdict == "GRID UPGRADE"
            for r in scenario_results
        ),
        "DON'T BUILD": sum(
            r.verdict == "DON'T BUILD"
            for r in scenario_results
        ),
    })

scenario_df = pd.DataFrame(scenario_rows)

st.dataframe(
    scenario_df,
    use_container_width=True,
    hide_index=True,
)


# ============================================================
# EXPORT
# ============================================================
st.subheader("5. Экспорт")

csv_bytes = table_df.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    "⬇ Скачать результаты CSV",
    data=csv_bytes,
    file_name="ev_optimizer_v3_results.csv",
    mime="text/csv",
)

st.caption(
    "V3 — демонстрационный прототип. Параметры, веса score и пороги "
    "решений являются проектными допущениями."
)
