import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from config import APP_TITLE, DEFAULTS
from optimizer import SiteInput, generate_candidates, optimize_site

st.set_page_config(page_title=APP_TITLE, page_icon="⚡", layout="wide")

st.title("⚡ EV Charging Optimizer V9")
st.caption("Интерактивная пространственная оптимизация размещения зарядной инфраструктуры")

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
        10.0,
        100.0,
        DEFAULTS["fast_share"],
        5.0,
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
        0.10,
        1.00,
        DEFAULTS["simultaneity"],
        0.05,
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
        6,
        20,
        DEFAULTS["number_of_candidates"],
    )
    map_year = st.slider(
        "Год для теплокарты",
        0,
        3,
        0,
        help="Карта показывает пространственный спрос выбранного года. При изменении параметров она пересчитывается автоматически.",
    )
    map_mode = st.radio(
        "Режим карты",
        ["Абсолютный спрос", "Изменение к году 0", "Изменение к базовым параметрам"],
        index=0,
        help="Помогает визуально увидеть, как параметры меняют не только решения, но и сам пространственный спрос.",
    )

    st.info(
        "V9: отдельно показывает целесообразность строительства сейчас и год, когда площадка может стать готовой по прогнозу."
    )

# ============================================================
# DEMO SPATIAL MODEL
# ============================================================
MAP_BOUNDS = {
    "lat_min": 55.55,
    "lat_max": 55.90,
    "lon_min": 37.35,
    "lon_max": 37.85,
}

# Synthetic demand centers. These are demo assumptions, not real traffic data.
demand_centers = [
    {"lat": 55.885, "lon": 37.475, "intensity": 0.38, "radius": 0.025, "growth_sensitivity": 1.25, "fast_sensitivity": 1.10},
    {"lat": 55.855, "lon": 37.570, "intensity": 0.55, "radius": 0.022, "growth_sensitivity": 1.10, "fast_sensitivity": 1.15},
    {"lat": 55.820, "lon": 37.690, "intensity": 0.48, "radius": 0.024, "growth_sensitivity": 1.30, "fast_sensitivity": 1.05},
    {"lat": 55.790, "lon": 37.445, "intensity": 0.44, "radius": 0.025, "growth_sensitivity": 0.90, "fast_sensitivity": 0.85},
    {"lat": 55.7558, "lon": 37.6176, "intensity": 1.00, "radius": 0.022, "growth_sensitivity": 0.85, "fast_sensitivity": 1.30},
    {"lat": 55.742, "lon": 37.690, "intensity": 0.68, "radius": 0.020, "growth_sensitivity": 1.00, "fast_sensitivity": 1.20},
    {"lat": 55.715, "lon": 37.545, "intensity": 0.58, "radius": 0.024, "growth_sensitivity": 1.20, "fast_sensitivity": 0.95},
    {"lat": 55.690, "lon": 37.690, "intensity": 0.50, "radius": 0.026, "growth_sensitivity": 1.35, "fast_sensitivity": 0.90},
    {"lat": 55.650, "lon": 37.575, "intensity": 0.42, "radius": 0.025, "growth_sensitivity": 1.30, "fast_sensitivity": 0.80},
    {"lat": 55.625, "lon": 37.735, "intensity": 0.36, "radius": 0.024, "growth_sensitivity": 1.40, "fast_sensitivity": 0.80},
    {"lat": 55.835, "lon": 37.390, "intensity": 0.30, "radius": 0.025, "growth_sensitivity": 0.80, "fast_sensitivity": 0.75},
    {"lat": 55.585, "lon": 37.425, "intensity": 0.28, "radius": 0.025, "growth_sensitivity": 1.45, "fast_sensitivity": 0.70},
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

# Demo existing charging stations. They are used only to estimate the
# "coverage gap": places farther from an existing station receive a higher
# candidate score. These are synthetic points for the prototype.
existing_stations = [
    {"name": "ЗС-01", "lat": 55.755, "lon": 37.610},
    {"name": "ЗС-02", "lat": 55.748, "lon": 37.635},
    {"name": "ЗС-03", "lat": 55.770, "lon": 37.585},
    {"name": "ЗС-04", "lat": 55.805, "lon": 37.620},
    {"name": "ЗС-05", "lat": 55.720, "lon": 37.600},
    {"name": "ЗС-06", "lat": 55.690, "lon": 37.690},
    {"name": "ЗС-07", "lat": 55.650, "lon": 37.575},
    {"name": "ЗС-08", "lat": 55.835, "lon": 37.470},
    {"name": "ЗС-09", "lat": 55.790, "lon": 37.730},
    {"name": "ЗС-10", "lat": 55.700, "lon": 37.520},
]


def make_heatmap(demand_value, growth_value, fast_value, year_value):
    lats = np.linspace(MAP_BOUNDS["lat_min"], MAP_BOUNDS["lat_max"], 120)
    lons = np.linspace(MAP_BOUNDS["lon_min"], MAP_BOUNDS["lon_max"], 150)
    rows = []

    growth_base = growth_value / 100.0
    fast_base = fast_value / 100.0
    total_growth_factor = (1.0 + growth_base) ** year_value

    for lat in lats:
        for lon in lons:
            spatial = 0.006
            for center in demand_centers:
                d2 = (lat - center["lat"]) ** 2 + (lon - center["lon"]) ** 2
                decay = np.exp(-d2 / (2 * center["radius"] ** 2))

                # Spatially heterogeneous growth and fast-charge sensitivity.
                growth_factor = (1.0 + growth_base * center["growth_sensitivity"]) ** year_value
                fast_factor = 0.72 + 0.56 * fast_base * center["fast_sensitivity"]
                spatial += center["intensity"] * decay * growth_factor * fast_factor

            absolute_demand = demand_value * total_growth_factor * spatial
            rows.append({"lat": lat, "lon": lon, "raw_demand": absolute_demand, "intensity": spatial})

    df = pd.DataFrame(rows)

    # Fixed reference scale: changing demand now visibly changes absolute colors
    # instead of being hidden by automatic normalization.
    reference_max = 450.0
    df["map_intensity"] = (df["raw_demand"] / reference_max).clip(0, 1)

    # Accessibility proxy: a smooth demo factor based on the city-center distance.
    center_lat, center_lon = 55.7558, 37.6176
    center_dist = np.sqrt((df["lat"] - center_lat) ** 2 + (df["lon"] - center_lon) ** 2)
    df["accessibility"] = (1.0 - center_dist / 0.28).clip(0, 1)

    # Proxies used by the candidate-selection algorithm. They are deliberately
    # kept separate so the jury can see what drives a proposed site.
    df["demand_score_proxy"] = (df["map_intensity"] * 100.0).clip(0, 100)
    df["accessibility_score_proxy"] = (df["accessibility"] * 100.0).clip(0, 100)

    # The final candidate score is calculated inside generate_candidates(),
    # after coverage gap and grid suitability are known.
    df["candidate_score"] = df["demand_score_proxy"]
    return df


def find_nearest_substation(lat, lon):
    nearest = None
    min_distance = float("inf")
    for sub in substations:
        d = ((lat - sub["lat"]) ** 2 + (lon - sub["lon"]) ** 2) ** 0.5
        if d < min_distance:
            min_distance = d
            nearest = sub
    return nearest, min_distance


def nearest_heatmap_row(lat, lon, heatmap):
    d2 = (heatmap["lat"] - lat) ** 2 + (heatmap["lon"] - lon) ** 2
    idx = d2.idxmin()
    return heatmap.loc[idx]


def make_sites(heatmap_df):
    # Candidate geometry is selected only from the fixed baseline scenario.
    # Current map year and interactive parameters update site metrics below,
    # but must never move the candidate coordinates.
    candidate_base = make_heatmap(
        DEFAULTS["current_demand"],
        DEFAULTS["annual_growth"],
        DEFAULTS["fast_share"],
        0,
    )
    candidates = generate_candidates(
        candidate_base,
        n_candidates=number_of_candidates,
        min_distance=0.014,
        existing_stations=existing_stations,
        substations=substations,
        fast_share=DEFAULTS["fast_share"],
        station_capacity=DEFAULTS["station_capacity"],
        station_power_kw=DEFAULTS["station_power_kw"],
        simultaneity=DEFAULTS["simultaneity"],
        station_cost=DEFAULTS["station_cost"],
        annual_revenue_per_station=DEFAULTS["annual_revenue_per_station"],
        annual_opex_per_station=DEFAULTS["annual_opex_per_station"],
        grid_upgrade_cost_per_100kw=DEFAULTS["grid_upgrade_cost_per_100kw"],
    )

    sites = []
    for i, point in enumerate(candidates):
        nearest, distance = find_nearest_substation(point["lat"], point["lon"])
        hrow = nearest_heatmap_row(point["lat"], point["lon"], heatmap_df)

        # Accessibility is still a demo proxy, while the candidate-selection
        # score now separately accounts for demand, coverage gap and grid fit.
        accessibility = max(50.0, min(100.0, float(point.get("accessibility_score_proxy", 70.0))))
        intensity = float(hrow["map_intensity"])
        demand_multiplier = 0.50 + intensity * 1.70
        if intensity >= 0.75:
            demand_zone = "пиковый спрос"
        elif intensity >= 0.45:
            demand_zone = "высокий спрос"
        elif intensity >= 0.22:
            demand_zone = "средний спрос"
        else:
            demand_zone = "низкий спрос"

        sites.append(
            {
                "name": f"Кандидат {i + 1}",
                "lat": point["lat"],
                "lon": point["lon"],
                "demand_multiplier": demand_multiplier,
                "demand_intensity": intensity,
                "demand_zone": demand_zone,
                "accessibility": accessibility,
                "substation": nearest["name"],
                "grid_capacity": nearest["capacity_kw"],
                "substation_distance": distance,
                # Demand score follows the selected year's/current parameter map.
                "demand_score_proxy": float(hrow["demand_score_proxy"]),
                "coverage_gap_score": point.get("coverage_gap_score", 0.0),
                "grid_score_proxy": point.get("grid_score_proxy", 0.0),
                "economics_score_proxy": point.get("economics_score_proxy", 0.0),
                "stations_proxy": point.get("stations_proxy", 0),
                "required_power_proxy": point.get("required_power_proxy", 0.0),
                "candidate_score": point.get("candidate_score", 0.0),
                "charger_gap_deg": point.get("charger_gap_deg", 0.0),
                "sector": point.get("sector", "—"),
            }
        )

    return pd.DataFrame(sites)


heatmap_df = make_heatmap(current_demand, annual_growth, fast_share, map_year)
base_year0_heatmap = make_heatmap(current_demand, annual_growth, fast_share, 0)
default_reference_heatmap = make_heatmap(
    DEFAULTS["current_demand"],
    DEFAULTS["annual_growth"],
    DEFAULTS["fast_share"],
    map_year,
)

# Align baseline fields by coordinates.
heatmap_df["year0_demand"] = base_year0_heatmap["raw_demand"].values
heatmap_df["default_demand"] = default_reference_heatmap["raw_demand"].values
heatmap_df["change_year0"] = (
    heatmap_df["raw_demand"] / heatmap_df["year0_demand"].replace(0, np.nan) - 1.0
).fillna(0.0)
heatmap_df["change_default"] = (
    heatmap_df["raw_demand"] / heatmap_df["default_demand"].replace(0, np.nan) - 1.0
).fillna(0.0)
heatmap_df["change_intensity"] = (
    (heatmap_df["change_year0"] + 0.50) / 1.00
).clip(0, 1)
heatmap_df["change_default_intensity"] = (
    (heatmap_df["change_default"] + 0.50) / 1.00
).clip(0, 1)

sites_df = make_sites(heatmap_df)


# ============================================================
# MODEL
# ============================================================
def calculate_results(growth_override=None, fast_share_override=None):
    growth = annual_growth if growth_override is None else growth_override
    fast = fast_share if fast_share_override is None else fast_share_override

    # Rebuild the spatial field for scenario calculations too.
    scenario_heatmap = make_heatmap(current_demand, growth, fast, map_year)
    scenario_sites = make_sites(scenario_heatmap)

    results = []
    for _, site_data in scenario_sites.iterrows():
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
            demand_score_override=float(site_data["demand_score_proxy"]),
            grid_score_override=float(site_data["grid_score_proxy"]),
            coverage_gap_score=float(site_data["coverage_gap_score"]),
        )
        results.append(optimize_site(site, horizon=3))

    return results, scenario_sites


results, model_sites_df = calculate_results()

# Keep the displayed candidate data synchronized with the recalculated model.
sites_df = model_sites_df.copy()

build_count = sum(r.current_verdict == "BUILD NOW" for r in results)
upgrade_count = sum(r.current_verdict == "GRID UPGRADE NOW" for r in results)
plan_count = sum(r.planned_year is not None and r.current_verdict not in ("BUILD NOW", "GRID UPGRADE NOW") for r in results)
dont_build_count = sum(r.verdict == "DON'T BUILD" for r in results)
avg_score = np.mean([r.total_score for r in results]) if results else 0

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Кандидатов", len(results))
m2.metric("Строить сейчас", build_count)
m3.metric("Усилить сеть сейчас", upgrade_count)
m4.metric("План на годы 1–3", plan_count)
m5.metric("Не строить", dont_build_count)

# ============================================================
# MAP
# ============================================================
st.subheader("1. Динамическая карта спроса и кандидатов")
st.caption(
    f"Год карты: {map_year} · Режим: {map_mode}. Пространственный спрос пересчитывается по ячейкам; "
    "кандидаты выбираются по совокупному баллу: спрос + дефицит покрытия + пригодность сети + доступность. Это синтетический демонстрационный спрос, а не реальные GIS-данные."
)

candidate_map_df = sites_df.copy()
candidate_map_df["Решение"] = [r.verdict for r in results]
candidate_map_df["Текущее решение"] = [r.current_verdict for r in results]
candidate_map_df["Плановый год"] = [r.planned_year if r.planned_year is not None else "—" for r in results]
candidate_map_df["Score"] = [round(r.total_score, 1) for r in results]
# ASCII aliases are used in PyDeck tooltips for reliable field substitution.
candidate_map_df["verdict"] = candidate_map_df["Решение"]
candidate_map_df["score"] = candidate_map_df["Score"]
candidate_map_df["planned_year"] = [str(r.planned_year) if r.planned_year is not None else "—" for r in results]
candidate_map_df["grid_capacity_kw"] = candidate_map_df["grid_capacity"].astype(float)
candidate_map_df["coverage_gap"] = candidate_map_df["coverage_gap_score"].round(1)
candidate_map_df["grid_score"] = candidate_map_df["grid_score_proxy"].round(1)
candidate_map_df["economics_score"] = candidate_map_df["economics_score_proxy"].round(1)
candidate_map_df["radius"] = 520

# Verdict-specific colors: green = BUILD, orange = GRID UPGRADE, red = DON'T BUILD.
def verdict_color(v):
    if v == "BUILD NOW":
        return [70, 200, 110, 240]
    if "GRID UPGRADE" in v:
        return [245, 165, 50, 245]
    if v.startswith("PLAN"):
        return [65, 145, 235, 245]
    return [230, 70, 70, 245]

candidate_map_df["color"] = candidate_map_df["Решение"].apply(verdict_color)

if map_mode == "Абсолютный спрос":
    heat_weight = "map_intensity"
    heat_colors = [
        [30, 80, 180], [40, 150, 210], [70, 195, 120],
        [245, 220, 70], [245, 145, 45], [220, 45, 35],
    ]
elif map_mode == "Изменение к году 0":
    heat_weight = "change_intensity"
    heat_colors = [
        [30, 80, 180], [80, 150, 220], [170, 210, 120],
        [245, 220, 70], [245, 145, 45], [220, 45, 35],
    ]
else:
    heat_weight = "change_default_intensity"
    heat_colors = [
        [30, 80, 180], [80, 150, 220], [170, 210, 120],
        [245, 220, 70], [245, 145, 45], [220, 45, 35],
    ]

heat_layer = pdk.Layer(
    "HeatmapLayer",
    data=heatmap_df,
    get_position="[lon, lat]",
    get_weight=heat_weight,
    radius_pixels=34,
    intensity=1.15,
    threshold=0.02,
    color_range=heat_colors,
)

candidate_layer = pdk.Layer(
    "ScatterplotLayer",
    data=candidate_map_df,
    get_position="[lon, lat]",
    get_radius="radius",
    get_fill_color="color",
    get_line_color=[255, 255, 255, 255],
    line_width_min_pixels=2,
    radius_min_pixels=5,
    radius_max_pixels=13,
    pickable=True,
)

existing_df = pd.DataFrame(existing_stations)
existing_df["radius"] = 260
existing_df["color"] = [[255, 255, 255, 220]] * len(existing_df)
existing_df["popup_name"] = existing_df["name"].astype(str)
existing_df["verdict"] = "СУЩЕСТВУЮЩАЯ СТАНЦИЯ"
existing_df["score"] = ""
existing_df["substation"] = "—"
existing_df["grid_capacity_kw"] = ""
existing_df["coverage_gap"] = "—"
existing_df["grid_score"] = "—"
existing_df["economics_score"] = "—"
existing_layer = pdk.Layer(
    "ScatterplotLayer",
    data=existing_df,
    get_position="[lon, lat]",
    get_radius="radius",
    get_fill_color="color",
    get_line_color=[30, 30, 30, 255],
    line_width_min_pixels=1,
    radius_min_pixels=3,
    radius_max_pixels=7,
    pickable=True,
)

sub_df = pd.DataFrame(substations)
sub_df["radius"] = 390
sub_df["popup_name"] = sub_df["name"].astype(str)
sub_df["capacity_kw_value"] = sub_df["capacity_kw"].astype(float)
sub_df["verdict"] = "ПОДСТАНЦИЯ"
sub_df["score"] = ""
sub_df["substation"] = sub_df["name"].astype(str)
sub_df["grid_capacity_kw"] = sub_df["capacity_kw"].astype(float)
sub_df["coverage_gap"] = "—"
sub_df["grid_score"] = "—"
sub_df["economics_score"] = "—"
sub_layer = pdk.Layer(
    "ScatterplotLayer",
    data=sub_df,
    get_position="[lon, lat]",
    get_radius="radius",
    get_fill_color=[50, 130, 255, 230],
    get_line_color=[255, 255, 255, 255],
    line_width_min_pixels=1,
    radius_min_pixels=4,
    radius_max_pixels=10,
    pickable=True,
)

map_view = pdk.ViewState(latitude=55.735, longitude=37.60, zoom=8.65, pitch=0, bearing=0)

st.pydeck_chart(
    pdk.Deck(
        layers=[heat_layer, existing_layer, candidate_layer, sub_layer],
        initial_view_state=map_view,
        tooltip={
            "html": (
                "<b>{name}</b><br/>"
                "Решение: {verdict}<br/>"
                "Score (сейчас): {score}<br/>"
                "Плановый год: {planned_year}<br/>"
                "Подстанция: {substation}<br/>"
                "Мощность ПС: {grid_capacity_kw} кВт<br/>"
                "Пробел покрытия: {coverage_gap}<br/>"
                "Сеть: {grid_score}<br/>"
                "Экономика: {economics_score}"
            ),
            "style": {"backgroundColor": "#1f2937", "color": "white"},
        },
    ),
    use_container_width=True,
)

l1, l2, l3, l4, l5 = st.columns(5)
l1.markdown("🔵 **Низкий спрос**")
l2.markdown("🟢 **Средний спрос**")
l3.markdown("🟡 **Высокий спрос**")
l4.markdown("🔴 **Пиковый спрос**")
l5.markdown("🟢 СЕЙЧАС · 🔵 ПЛАН · 🟠 СЕТЬ · 🔴 НЕ СТРОИТЬ · 🔵 ПС")

# ============================================================
# LIVE EFFECTS
# ============================================================
st.subheader("2. Что изменилось после ввода параметров")
raw_peak = float(heatmap_df["raw_demand"].max())
mean_raw = float(heatmap_df["raw_demand"].mean())

x1, x2, x3, x4 = st.columns(4)
x1.metric("Пиковый пространственный спрос", f"{raw_peak:.1f} ед./день")
x2.metric("Средний спрос по карте", f"{mean_raw:.1f} ед./день")
x3.metric("Кандидатов пересчитано", len(sites_df))
x4.metric("Кандидатов с модернизацией", upgrade_count)

st.caption(
    "При изменении параметров Streamlit автоматически перезапускает расчёт: сначала меняется пространственный спрос, "
    "затем набор кандидатов, затем нагрузка на станции и сеть, экономика и итоговое решение."
)

# ============================================================
# TABLE
# ============================================================
st.subheader("3. Сравнение кандидатов")
table_rows = []
for _, site_data in sites_df.iterrows():
    result = next(r for r in results if r.name == site_data["name"])
    table_rows.append(
        {
            "Кандидат": result.name,
            "Сектор": site_data.get("sector", "—"),
            "Зона спроса": site_data["demand_zone"],
            "Спрос": round(site_data["demand_multiplier"], 2),
            "Подстанция": site_data["substation"],
            "Сеть, кВт": int(site_data["grid_capacity"]),
            "Score": round(result.total_score, 1),
            "Спрос, балл": round(float(site_data["demand_score_proxy"]), 1),
            "Пробел покрытия": round(float(site_data["coverage_gap_score"]), 1),
            "Сеть, балл": round(float(site_data["grid_score_proxy"]), 1),
            "Экономика, балл": round(float(site_data["economics_score_proxy"]), 1),
            "Станций, год 0": result.years[0].stations,
            "Станций, год 3": result.years[3].stations,
            "Util. год 1": f"{result.years[1].utilization:.1f}%",
            "Util. год 3": f"{result.years[3].utilization:.1f}%",
            "CAPEX": int(result.capex),
            "Усиление сети": int(result.grid_upgrade_cost),
            "Инвестиции": int(result.total_investment),
            "Окупаемость": None if np.isinf(result.payback_years) else round(result.payback_years, 2),
            "Сейчас": result.current_verdict,
            "План на год": result.planned_year if result.planned_year is not None else "—",
            "Итоговый статус": result.verdict,
        }
    )

table_df = pd.DataFrame(table_rows)
st.dataframe(table_df, use_container_width=True, hide_index=True)

# ============================================================
# DETAILS
# ============================================================
st.subheader("4. Объяснение решения")
st.caption("Один и тот же итоговый Score используется в таблице, на карте и в карточке. Взвешенный вклад показывает, сколько баллов каждый фактор добавляет к результату.")
selected_name = st.selectbox("Выберите кандидата для объяснения", [r.name for r in sorted(results, key=lambda x: x.total_score, reverse=True)], key="explain_candidate")
selected_result = next(r for r in results if r.name == selected_name)
selected_site = sites_df.loc[sites_df["name"] == selected_name].iloc[0]
contributions = pd.DataFrame([
    {"Фактор": "Спрос", "Оценка": selected_result.demand_score, "Вес, %": 35, "Вклад в Score": selected_result.demand_score * 0.35},
    {"Фактор": "Дефицит покрытия", "Оценка": selected_result.coverage_gap_score, "Вес, %": 15, "Вклад в Score": selected_result.coverage_gap_score * 0.15},
    {"Фактор": "Электросеть", "Оценка": selected_result.grid_score, "Вес, %": 25, "Вклад в Score": selected_result.grid_score * 0.25},
    {"Фактор": "Доступность", "Оценка": selected_result.accessibility_score, "Вес, %": 10, "Вклад в Score": selected_result.accessibility_score * 0.10},
    {"Фактор": "Экономика", "Оценка": selected_result.economics_score, "Вес, %": 15, "Вклад в Score": selected_result.economics_score * 0.15},
])
ex1, ex2, ex3 = st.columns(3)
ex1.metric("Итоговый Score", f"{selected_result.total_score:.1f}/100")
ex2.metric("Сейчас", selected_result.current_verdict)
ex3.metric("Плановый год", str(selected_result.planned_year) if selected_result.planned_year is not None else "—")
st.dataframe(contributions.round(1), use_container_width=True, hide_index=True)
st.bar_chart(contributions.set_index("Фактор")["Вклад в Score"], horizontal=True)

st.markdown("**Почему получено такое решение**")
reasons = []
if selected_result.current_verdict == "BUILD NOW":
    reasons.append("Условия модели выполняются уже в базовом году: площадку можно рассматривать для строительства сейчас.")
elif selected_result.current_verdict == "GRID UPGRADE NOW":
    reasons.append(f"По спросу и экономике площадка проходит пороги, но сейчас нужен резерв/усиление сети: дефицит {selected_result.grid_deficit_kw:.0f} кВт.")
elif selected_result.planned_year is not None:
    reasons.append(f"Сейчас строить рано. По заданному сценарию площадка впервые проходит проектные пороги в году {selected_result.planned_year}; это ориентир для планирования, не гарантия спроса.")
else:
    reasons.append("На горизонте прогноза 0–3 года площадка не проходит все проектные пороги.")
current = selected_result.yearly_decisions[0]
failed = []
if current["score"] < 70: failed.append(f"Score {current['score']:.1f} ниже 70")
if current["payback"] > 6: failed.append("окупаемость больше 6 лет")
if current["utilization"] > 90: failed.append(f"загрузка {current['utilization']:.1f}% выше 90%")
if current["grid_deficit_kw"] > 0: failed.append(f"дефицит сети {current['grid_deficit_kw']:.0f} кВт")
if failed:
    reasons.append("Что мешает строить сейчас: " + "; ".join(failed) + ".")
reasons.append(f"Ближайшая подстанция: {selected_site['substation']} ({selected_site['grid_capacity']:.0f} кВт); расстояние по координатам около {selected_site['substation_distance']:.3f}°.")
reasons.append(f"До ближайшей существующей зарядки: около {selected_site['charger_gap_deg']:.3f}° по координатам. Это демонстрационная оценка покрытия, не дорожное расстояние.")
for reason in reasons:
    st.write("• " + reason)

st.subheader("5. План строительства по годам")
st.caption("BUILD NOW означает, что условия проходят в базовом году. PLAN — YEAR N означает, что условия впервые выполняются в прогнозном году N; это плановый ориентир, а не рекомендация строить заранее.")
plan_rows = []
for r in results:
    plan_rows.append({"Кандидат": r.name, "Решение сейчас": r.current_verdict, "Первый год прохождения": r.planned_year if r.planned_year is not None else "—", "Статус плана": r.verdict, "Score сейчас": round(r.total_score, 1)})
st.dataframe(pd.DataFrame(plan_rows), use_container_width=True, hide_index=True)

st.subheader("6. Детальный анализ")
for result in sorted(results, key=lambda x: (x.planned_year is None, x.planned_year if x.planned_year is not None else 99, -x.total_score)):
    with st.expander(f"{result.name} — сейчас: {result.current_verdict} · план: {result.verdict} · score {result.total_score:.1f}"):
        site_row = sites_df.loc[sites_df["name"] == result.name].iloc[0]
        st.caption(
            f"Сектор {site_row.get('sector', '—')} · причина выбора: {site_row['demand_zone']} · спрос {site_row['demand_score_proxy']:.1f}/100 · "
            f"пробел покрытия {site_row['coverage_gap_score']:.1f}/100 · сеть {site_row['grid_score_proxy']:.1f}/100 · "
            f"экономика {result.economics_score:.1f}/100 · доступность {site_row['accessibility']:.1f}/100 · "
            f"до {site_row['substation']} ≈ {site_row['substation_distance']:.3f}°."
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Demand score", f"{result.demand_score:.1f}")
        c2.metric("Grid score", f"{result.grid_score:.1f}")
        c3.metric("Economics score", f"{result.economics_score:.1f}")
        c4.metric("Пробел покрытия", f"{result.coverage_gap_score:.1f}")

        forecast = pd.DataFrame([
            {
                "Год": y.year,
                "Спрос": round(y.demand, 1),
                "Станций": y.stations,
                "Utilization": f"{y.utilization:.1f}%",
                "Эфф. мощность, кВт": round(y.effective_power_kw, 1),
                "Дефицит, кВт": round(y.grid_deficit_kw, 1),
                "Score года": round(result.yearly_decisions[y.year]["score"], 1),
                "Окупаемость, лет": ("∞" if np.isinf(result.yearly_decisions[y.year]["payback"]) else round(result.yearly_decisions[y.year]["payback"], 2)),
                "Статус года": result.yearly_decisions[y.year]["status"],
            }
            for y in result.years
        ])
        st.dataframe(forecast, use_container_width=True, hide_index=True)

        a, b, c, d = st.columns(4)
        a.metric("CAPEX", f"{result.capex:,.0f} ₽")
        b.metric("Усиление сети", f"{result.grid_upgrade_cost:,.0f} ₽")
        c.metric("Всего инвестиций", f"{result.total_investment:,.0f} ₽")
        d.metric("Payback", "∞" if np.isinf(result.payback_years) else f"{result.payback_years:.2f} лет")

        if result.current_verdict == "BUILD NOW":
            st.success("Рекомендация модели: рассматривать строительство сейчас.")
        elif result.current_verdict == "GRID UPGRADE NOW":
            st.warning("Площадка может быть целесообразна сейчас, но сначала требуется решение по усилению сети.")
        elif result.planned_year is not None:
            st.info(f"Не строить немедленно: включить в план развития и повторно оценить в году {result.planned_year}.")
        else:
            st.error("На горизонте 0–3 года проектные пороги не выполнены.")

# ============================================================
# SCENARIOS
# ============================================================
st.subheader("7. Сценарный анализ")
scenarios = [
    ("Базовый", annual_growth, fast_share),
    ("Высокий рост", min(100, annual_growth + 15), fast_share),
    ("Высокая доля быстрой зарядки", annual_growth, min(100, fast_share + 20)),
    ("Стресс", min(100, annual_growth + 25), min(100, fast_share + 20)),
]

scenario_rows = []
for scenario_name, growth_s, fast_s in scenarios:
    scenario_results, scenario_sites = calculate_results(growth_override=growth_s, fast_share_override=fast_s)
    paybacks = [r.payback_years for r in scenario_results if not np.isinf(r.payback_years)]
    scenario_rows.append(
        {
            "Сценарий": scenario_name,
            "Рост спроса": f"{growth_s:.0f}%",
            "Fast charge": f"{fast_s:.0f}%",
            "Кандидатов": len(scenario_results),
            "Строить сейчас": sum(r.current_verdict == "BUILD NOW" for r in scenario_results),
            "Усилить сеть сейчас": sum(r.current_verdict == "GRID UPGRADE NOW" for r in scenario_results),
            "План на годы 1–3": sum(r.planned_year is not None and r.current_verdict not in ("BUILD NOW", "GRID UPGRADE NOW") for r in scenario_results),
            "Не строить": sum(r.verdict == "DON'T BUILD" for r in scenario_results),
            "Средний score": round(float(np.mean([r.total_score for r in scenario_results])), 1),
            "Средняя окупаемость": round(float(np.mean(paybacks)), 2) if paybacks else None,
        }
    )

scenario_df = pd.DataFrame(scenario_rows)
st.dataframe(scenario_df, use_container_width=True, hide_index=True)

# ============================================================
# EXPORT
# ============================================================
st.subheader("8. Экспорт")
csv_bytes = table_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "⬇ Скачать результаты CSV",
    data=csv_bytes,
    file_name="ev_optimizer_v9_results.csv",
    mime="text/csv",
)

st.caption(
    "V9 — демонстрационный прототип. Пространственный спрос, подстанции, веса score и пороги решений "
    "являются проектными допущениями; для промышленной модели нужны реальные транспортные и сетевые данные."
)
