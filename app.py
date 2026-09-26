import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk

from optimizer import (
    SiteInput,
    optimize_site,
    generate_candidates
)


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="EV Charging Optimizer",
    page_icon="⚡",
    layout="wide"
)


st.title(
    "⚡ Оптимизация размещения зарядных станций"
)

st.caption(
    "Демонстрационный прототип пространственно-"
    "экономической оптимизации зарядной инфраструктуры"
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header(
    "Параметры модели"
)


current_demand = st.sidebar.number_input(
    "Текущий спрос, ед./сутки",
    min_value=1.0,
    value=100.0
)


annual_growth = st.sidebar.number_input(
    "Рост спроса, % в год",
    min_value=0.0,
    max_value=100.0,
    value=20.0
)


fast_share = st.sidebar.number_input(
    "Доля быстрой зарядки, %",
    min_value=0.0,
    max_value=100.0,
    value=60.0
)


station_capacity = st.sidebar.number_input(
    "Ёмкость станции, ед./сутки",
    min_value=1.0,
    value=100.0
)


station_power = st.sidebar.number_input(
    "Мощность станции, кВт",
    min_value=1.0,
    value=150.0
)


grid_power = st.sidebar.number_input(
    "Доступная мощность сети, кВт",
    min_value=0.0,
    value=1000.0
)


simultaneity = st.sidebar.number_input(
    "Коэффициент одновременности",
    min_value=0.1,
    max_value=1.0,
    value=0.7,
    step=0.05
)


station_cost = st.sidebar.number_input(
    "Стоимость станции, ₽",
    min_value=0.0,
    value=5_000_000.0,
    step=100_000.0
)


grid_upgrade_cost = st.sidebar.number_input(
    "Модернизация сети / 100 кВт, ₽",
    min_value=0.0,
    value=1_000_000.0,
    step=100_000.0
)


st.sidebar.divider()


st.sidebar.header(
    "Экономика"
)


annual_revenue = st.sidebar.number_input(
    "Доход на станцию / год, ₽",
    min_value=0.0,
    value=3_000_000.0,
    step=100_000.0
)


annual_opex = st.sidebar.number_input(
    "OPEX на станцию / год, ₽",
    min_value=0.0,
    value=1_000_000.0,
    step=100_000.0
)


number_of_candidates = st.sidebar.slider(
    "Количество кандидатов",
    min_value=5,
    max_value=20,
    value=10
)


# ============================================================
# HEATMAP DATA
# ============================================================

demand_centers = [

    {
        "lat": 55.7558,
        "lon": 37.6176,
        "intensity": 1.00,
        "radius": 0.015
    },

    {
        "lat": 55.7415,
        "lon": 37.6260,
        "intensity": 0.75,
        "radius": 0.012
    },

    {
        "lat": 55.7690,
        "lon": 37.5950,
        "intensity": 1.25,
        "radius": 0.018
    }
]

# ============================================================
# DEMO GRID / SUBSTATIONS
# ============================================================

substations = [
    {
        "name": "ПС-01",
        "lat": 55.7558,
        "lon": 37.6176,
        "capacity_kw": 1200,
    },
    {
        "name": "ПС-02",
        "lat": 55.7415,
        "lon": 37.6260,
        "capacity_kw": 500,
    },
    {
        "name": "ПС-03",
        "lat": 55.7690,
        "lon": 37.5950,
        "capacity_kw": 800,
    },
    {
        "name": "ПС-04",
        "lat": 55.7800,
        "lon": 37.6500,
        "capacity_kw": 600,
    },
    {
        "name": "ПС-05",
        "lat": 55.7200,
        "lon": 37.5900,
        "capacity_kw": 1000,
    },
]

lat_values = np.linspace(
    55.69,
    55.82,
    70
)


lon_values = np.linspace(
    37.52,
    37.72,
    90
)


heatmap_points = []


for lat in lat_values:

    for lon in lon_values:

        demand = 0.0

        for center in demand_centers:

            distance = (
                (lat - center["lat"]) ** 2
                +
                (lon - center["lon"]) ** 2
            )

            influence = np.exp(
                -distance /
                (
                    center["radius"] ** 2
                )
            )

            demand += (
                influence *
                center["intensity"]
            )

        heatmap_points.append({

            "lat": lat,

            "lon": lon,

            "demand": demand

        })


heatmap_df = pd.DataFrame(
    heatmap_points
)

def find_nearest_substation(
    lat,
    lon,
    substations
):

    nearest = None
    min_distance = float("inf")

    for substation in substations:

        distance = (
            (lat - substation["lat"]) ** 2
            +
            (lon - substation["lon"]) ** 2
        ) ** 0.5

        if distance < min_distance:

            min_distance = distance
            nearest = substation

    return nearest, min_distance

# ============================================================
# AUTOMATIC CANDIDATES
# ============================================================

candidate_points = generate_candidates(

    heatmap_df,

    n_candidates=
        number_of_candidates,

    min_distance=0.008
)


max_demand = max(
    point["demand"]
    for point in candidate_points
)


sites_data = []

for i, point in enumerate(candidate_points):

    demand_multiplier = (
        point["demand"] / max_demand
    )

    accessibility = (
        60 +
        40 * demand_multiplier
    )

    nearest_substation, distance = (
        find_nearest_substation(
            point["lat"],
            point["lon"],
            substations
        )
    )

    sites_data.append({

        "name":
            f"Кандидат {i + 1}",

        "lat":
            point["lat"],

        "lon":
            point["lon"],

        "demand_multiplier":
            demand_multiplier,

        "accessibility":
            accessibility,

        "substation":
            nearest_substation["name"],

        "grid_capacity":
            nearest_substation["capacity_kw"],

        "substation_distance":
            distance
    })


# ============================================================
# OPTIMIZATION
# ============================================================

results = []


for site_data in sites_data:

    site_demand = (
        current_demand *
        site_data["demand_multiplier"]
    )


    site = SiteInput(

        name=
            site_data["name"],

        current_demand=
            site_demand,

        annual_growth=
            annual_growth,

        fast_share=
            fast_share,

        station_capacity=
            station_capacity,

        station_power_kw=
            station_power,

        station_cost=
            station_cost,

        grid_power_kw=
            site_data["grid_capacity"],

        simultaneity=
            simultaneity,

        grid_upgrade_cost_per_100kw=
            grid_upgrade_cost,

        annual_revenue_per_station=
            annual_revenue,

        annual_opex_per_station=
            annual_opex,

        accessibility_score=
            site_data["accessibility"]
    )


    result = optimize_site(
        site
    )


    results.append(
        result
    )


# ============================================================
# KPI
# ============================================================

st.header(
    "Результат оптимизации"
)


col1, col2, col3, col4 = st.columns(4)


col1.metric(
    "Кандидатов",
    len(results)
)


col2.metric(
    "BUILD",
    sum(
        r.verdict == "BUILD"
        for r in results
    )
)


col3.metric(
    "Средний Score",
    f"{sum(r.total_score for r in results) / len(results):.1f}"
)


valid_paybacks = [
    r.payback_years
    for r in results
    if r.payback_years != float("inf")
]


if valid_paybacks:

    average_payback = (
        sum(valid_paybacks) /
        len(valid_paybacks)
    )

else:

    average_payback = 0


col4.metric(
    "Средний Payback",
    f"{average_payback:.1f} лет"
)


# ============================================================
# HEATMAP + CANDIDATES
# ============================================================

st.header(
    "🔥 Тепловая карта транспортного спроса"
)


candidate_map_data = []


for site_data, result in zip(
    sites_data,
    results
):

    candidate_map_data.append({

        "lat":
            site_data["lat"],

        "lon":
            site_data["lon"],

        "name":
            result.name,

        "score":
            round(
                result.total_score,
                1
            ),

        "verdict":
            result.verdict,

        "grid_capacity":
            site_data["grid_capacity"],

        "substation":
            site_data["substation"]
    })


candidate_df = pd.DataFrame(
    candidate_map_data
)


# Heatmap
heatmap_layer = pdk.Layer(

    "HeatmapLayer",

    data=heatmap_df,

    get_position=
        "[lon, lat]",

    get_weight=
        "demand",

    radius_pixels=45,

    intensity=1.5,

    threshold=0.03
)


# Candidate points
candidate_layer = pdk.Layer(

    "ScatterplotLayer",

    data=candidate_df,

    get_position=
        "[lon, lat]",

    get_radius=450,

    get_fill_color=
        "[255, 255, 255, 255]",

    get_line_color=
        "[0, 0, 0, 255]",

    line_width_min_pixels=2,

    pickable=True
)

substation_df = pd.DataFrame(
    substations
)

substation_layer = pdk.Layer(

    "ScatterplotLayer",

    data=substation_df,

    get_position="[lon, lat]",

    get_radius=300,

    get_fill_color=
        "[50, 150, 255, 220]",

    get_line_color=
        "[255, 255, 255, 255]",

    line_width_min_pixels=2,

    pickable=True
)

view_state = pdk.ViewState(

    latitude=55.7558,

    longitude=37.6176,

    zoom=10.5,

    pitch=0
)


deck = pdk.Deck(

    layers=[
        heatmap_layer,
        candidate_layer,
        substation_layer
    ],

    initial_view_state=
        view_state,

    tooltip={

        "html": """
        <b>{name}</b><br/>
        Score: {score}<br/>
        Статус: {verdict}
        """
    }
)


st.pydeck_chart(
    deck,
    use_container_width=True
)


st.caption(
    "🔥 Тепловой слой показывает модельный "
    "уровень спроса. Белые точки — автоматически "
    "найденные кандидатные площадки."
)


# ============================================================
# TABLE
# ============================================================

st.header(
    "Кандидатные площадки"
)


table = []

for site_data, result in zip(
    sites_data,
    results
):

    year_1 = result.years[1]
    year_2 = result.years[2]
    year_3 = result.years[3]

    table.append({

        "Площадка":
            result.name,

        "Подстанция":
            site_data["substation"],

        "Сеть":
            f"{site_data['grid_capacity']:.0f} кВт",

        "Score":
            round(
                result.total_score,
                1
            ),

        "Сейчас":
            f"{result.years[0].utilization:.1f}%",

        "+1 год":
            f"{year_1.utilization:.1f}%",

        "+2 года":
            f"{year_2.utilization:.1f}%",

        "+3 года":
            f"{year_3.utilization:.1f}%",

        "Станций сейчас":
            result.years[0].stations,

        "Станций +3 года":
            year_3.stations,

        "CAPEX":
            f"{result.capex / 1_000_000:.1f} млн ₽",

        "Сеть":
            (
            f"{result.grid_upgrade_cost / 1_000_000:.1f} млн ₽"
            ),

        "Всего инвестиций":
            (
            f"{result.total_investment / 1_000_000:.1f} млн ₽"
            ),

        "Payback":
            (
                "—"
                if result.payback_years ==
                    float("inf")
                else
                    f"{result.payback_years:.1f} лет"
            ),

        "Вердикт":
            result.verdict
    })


df = pd.DataFrame(
    table
)


st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# DETAILS
# ============================================================

st.header(
    "Детализация площадок"
)


for result in results:

    with st.expander(

        f"{result.name} — "
        f"{result.verdict} — "
        f"Score {result.total_score:.1f}"

    ):

        col1, col2, col3, col4 = st.columns(4)


        col1.metric(
            "Score",
            f"{result.total_score:.1f}/100"
        )


        col2.metric(
            "CAPEX",
            f"{result.capex / 1_000_000:.1f} млн ₽"
        )


        col3.metric(
            "Payback",
            (
                "—"
                if result.payback_years ==
                    float("inf")
                else
                    f"{result.payback_years:.1f} лет"
            )
        )


        col4.metric(
            "OPEX / год",
            f"{result.annual_opex / 1_000_000:.1f} млн ₽"
        )

        st.subheader("Инвестиции")

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Станции",
            f"{result.capex / 1_000_000:.1f} млн ₽"
        )  

        col2.metric(
            "Сеть",
            f"{result.grid_upgrade_cost / 1_000_000:.1f} млн ₽"
        )

        col3.metric(
            "Всего",
            f"{result.total_investment / 1_000_000:.1f} млн ₽"
        )

        st.subheader(
            "Прогноз на 3 года"
        )


        forecast_df = pd.DataFrame([

            {

                "Год":
                    f"+{year.year}",

                "Спрос":
                    round(
                        year.demand,
                        1
                    ),

                "Станций":
                    year.stations,

                "Загрузка":
                    f"{year.utilization:.1f}%",

                "Эффективная мощность":
                    f"{year.effective_power_kw:.0f} кВт",

                "Резерв сети":
                    f"{year.grid_reserve_kw:.0f} кВт"
            }

            for year in result.years

        ])


        st.dataframe(

            forecast_df,

            use_container_width=True,

            hide_index=True
        )


        st.subheader(
            "Состав Score"
        )


        score_df = pd.DataFrame([

            {
                "Критерий":
                    "Спрос",

                "Вес":
                    "40%",

                "Оценка":
                    round(
                        result.demand_score,
                        1
                    )
            },

            {
                "Критерий":
                    "Сеть",

                "Вес":
                    "25%",

                "Оценка":
                    round(
                        result.grid_score,
                        1
                    )
            },

            {
                "Критерий":
                    "Экономика",

                "Вес":
                    "20%",

                "Оценка":
                    round(
                        result.economics_score,
                        1
                    )
            },

            {
                "Критерий":
                    "Доступность",

                "Вес":
                    "15%",

                "Оценка":
                    round(
                        result.accessibility_score,
                        1
                    )
            }

        ])


        st.dataframe(

            score_df,

            use_container_width=True,

            hide_index=True
        )


        if result.verdict == "BUILD":

            st.success(
                "🟢 BUILD — "
                "площадка проходит условия модели."
            )

        elif result.verdict == "GRID UPGRADE":

            st.warning(
                "🟡 GRID UPGRADE — "
                "перед строительством требуется "
                "модернизация сети."
            )

        else:

            st.error(
                "🔴 DON'T BUILD — "
                "площадка не проходит условия модели."
            )


# ============================================================
# DISCLAIMER
# ============================================================

st.divider()

st.caption(
    "Демонстрационный прототип. "
    "Тепловая карта и параметры площадок "
    "используют модельные данные. "
    "CAPEX, OPEX, Payback, веса Score и пороги "
    "BUILD являются проектными допущениями, "
    "а не официальной методикой РСЗС."
)