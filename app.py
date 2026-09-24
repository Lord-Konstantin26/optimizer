"""
Интерактивный интерфейс Charge Optimizer.
"""

import streamlit as st

from config import (
    DEFAULT_CURRENT_DEMAND,
    DEFAULT_EV_GROWTH,
    DEFAULT_FAST_CHARGING_SHARE,
    DEFAULT_STATION_POWER,
    DEFAULT_GRID_POWER,
    DEFAULT_SIMULTANEITY,
    DEFAULT_STATION_COST,
    DEFAULT_GRID_UPGRADE_COST_PER_100KW,
    DEFAULT_STATION_CAPACITY,
    DEFAULT_SCENARIO_GROWTH,
    MAX_STATIONS_TO_CHECK,
)

from optimizer import (
    InputData,
    optimize,
    find_minimum_feasible,
    calculate_growth_scenario,
)

# --------------------------------------------------
# Настройки страницы
# --------------------------------------------------

st.set_page_config(
    page_title="Charge Optimizer",
    page_icon="⚡",
    layout="wide",
)

# --------------------------------------------------
# Заголовок
# --------------------------------------------------

st.title("⚡ Charge Optimizer")

st.markdown(
    """
    ### Оптимизация зарядной инфраструктуры

    Модель рассчитывает необходимое количество зарядных станций
    с учётом прогнозируемого спроса и ограничений электросети.
    """
)

# --------------------------------------------------
# Боковая панель
# --------------------------------------------------

st.sidebar.header("Исходные данные")

current_demand = st.sidebar.number_input(
    "Текущий спрос",
    min_value=1.0,
    value=float(DEFAULT_CURRENT_DEMAND),
    step=100.0,
)

ev_growth = st.sidebar.number_input(
    "Рост EV, %",
    min_value=0.0,
    max_value=500.0,
    value=float(DEFAULT_EV_GROWTH),
    step=5.0,
)

fast_share = st.sidebar.number_input(
    "Доля быстрого заряда, %",
    min_value=0.0,
    max_value=100.0,
    value=float(DEFAULT_FAST_CHARGING_SHARE),
    step=5.0,
)

st.sidebar.divider()

st.sidebar.subheader("Энергосистема")

station_power = st.sidebar.number_input(
    "Мощность одной станции, кВт",
    min_value=1.0,
    value=float(DEFAULT_STATION_POWER),
    step=10.0,
)

grid_power = st.sidebar.number_input(
    "Доступная мощность сети, кВт",
    min_value=1.0,
    value=float(DEFAULT_GRID_POWER),
    step=100.0,
)

simultaneity = st.sidebar.slider(
    "Коэффициент одновременности",
    min_value=0.1,
    max_value=1.0,
    value=float(DEFAULT_SIMULTANEITY),
    step=0.05,
)

st.sidebar.divider()

st.sidebar.subheader("Экономика")

station_cost = st.sidebar.number_input(
    "Стоимость одной станции, ₽",
    min_value=0.0,
    value=float(DEFAULT_STATION_COST),
    step=500_000.0,
)

grid_upgrade_cost = st.sidebar.number_input(
    "Усиление сети: стоимость 100 кВт, ₽",
    min_value=0.0,
    value=float(DEFAULT_GRID_UPGRADE_COST_PER_100KW),
    step=500_000.0,
)

station_capacity = st.sidebar.number_input(
    "Пропускная способность станции",
    min_value=1.0,
    value=float(DEFAULT_STATION_CAPACITY),
    step=10.0,
)

st.sidebar.divider()

scenario_growth = st.sidebar.number_input(
    "Дополнительный рост для сценария, %",
    min_value=0.0,
    max_value=500.0,
    value=float(DEFAULT_SCENARIO_GROWTH),
    step=5.0,
)

# --------------------------------------------------
# Формируем данные
# --------------------------------------------------

data = InputData(
    current_demand=current_demand,

    ev_growth_percent=ev_growth,

    fast_charging_share_percent=fast_share,

    station_power_kw=station_power,

    available_grid_power_kw=grid_power,

    simultaneity_factor=simultaneity,

    station_cost_rub=station_cost,

    grid_upgrade_cost_per_100kw_rub=(
        grid_upgrade_cost
    ),

    station_capacity=station_capacity,
)

# --------------------------------------------------
# Кнопка расчёта
# --------------------------------------------------

calculate_button = st.button(
    "🚀 Рассчитать",
    type="primary",
    use_container_width=True,
)

# --------------------------------------------------
# Расчёт
# --------------------------------------------------

if calculate_button:

    results = optimize(
        data,
        max_stations=MAX_STATIONS_TO_CHECK,
)

    optimal = find_minimum_feasible(results)

    # ----------------------------------------------
    # Верхние показатели
    # ----------------------------------------------

    future_demand = (
        current_demand
        * (1 + ev_growth / 100)
    )

    fast_demand = (
        future_demand
        * fast_share
        / 100
    )

    st.subheader("Основной результат")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Прогноз спроса",
        f"{future_demand:,.0f}",
    )

    col2.metric(
        "Спрос на быстрый заряд",
        f"{fast_demand:,.0f}",
    )

    if optimal:

        col3.metric(
            "Необходимое количество станций",
            optimal.stations,
        )

        col4.metric(
            "Общая стоимость",
            f"{optimal.total_cost_rub / 1_000_000:.1f} млн ₽",
        )

    else:

        col3.metric(
            "Необходимое количество станций",
            "Нет решения",
        )

        col4.metric(
            "Общая стоимость",
            "—",
        )

    # ----------------------------------------------
    # Подробный результат
    # ----------------------------------------------

    if optimal:

        st.divider()

        st.subheader("Проверка выбранного варианта")

        c1, c2 = st.columns(2)

        with c1:

            st.write("### ⚡ Электросеть")

            st.write(
                f"Установленная мощность: "
                f"**{optimal.installed_power_kw:,.0f} кВт**"
            )

            st.write(
                f"Расчётная мощность с учётом "
                f"одновременности: "
                f"**{optimal.effective_power_kw:,.0f} кВт**"
            )

            st.write(
                f"Доступная мощность: "
                f"**{optimal.available_grid_power_kw:,.0f} кВт**"
            )

            if optimal.grid_ok:

                st.success(
                    f"Мощности достаточно. "
                    f"Запас: {optimal.power_reserve_kw:,.0f} кВт."
                )

            else:

                st.error(
                    f"Недостаток мощности: "
                    f"{optimal.power_deficit_kw:,.0f} кВт."
                )

        with c2:

            st.write("### 📊 Спрос")

            st.write(
                f"Пропускная способность: "
                f"**{optimal.station_capacity_total:,.0f}**"
            )

            st.write(
                f"Прогнозируемый спрос: "
                f"**{optimal.fast_demand:,.0f}**"
            )

            st.write(
                f"Расчётная загрузка: "
                f"**{optimal.utilization_percent:.1f}%**"
            )

            if optimal.demand_ok:

                st.success(
                    "Спрос полностью покрывается."
                )

            else:

                st.error(
                    "Пропускной способности недостаточно."
                )

        # ------------------------------------------
        # Экономика
        # ------------------------------------------

        st.divider()

        st.subheader("💰 Экономика")

        e1, e2, e3 = st.columns(3)

        e1.metric(
            "Станции",
            f"{optimal.station_cost_rub / 1_000_000:.1f} млн ₽",
        )

        e2.metric(
            "Усиление сети",
            f"{optimal.grid_upgrade_cost_rub / 1_000_000:.1f} млн ₽",
        )

        e3.metric(
            "Итого",
            f"{optimal.total_cost_rub / 1_000_000:.1f} млн ₽",
        )

        # ------------------------------------------
        # Статус
        # ------------------------------------------

        st.divider()

        if optimal.feasible:

            st.success(
                f"✓ Найден допустимый вариант: "
                f"{optimal.stations} станций."
            )

        else:

            st.warning(
                "Не найден вариант, который одновременно "
                "покрывает спрос и укладывается в ограничения сети."
            )
# ------------------------------------------
        # Таблица всех вариантов
        # ------------------------------------------

        st.divider()

        st.subheader(
            "🔎 Проверенные варианты"
        )

        table_data = []

        for result in results:

            table_data.append(
                {
                    "Станции": result.stations,

                    "Загрузка, %": round(
                        result.utilization_percent,
                        1,
                    ),

                    "Мощность, кВт": round(
                        result.effective_power_kw,
                        1,
                    ),

                    "Запас сети, кВт": round(
                        result.power_reserve_kw,
                        1,
                    ),

                    "Дефицит, кВт": round(
                        result.power_deficit_kw,
                        1,
                    ),

                    "Стоимость, млн ₽": round(
                        result.total_cost_rub / 1_000_000,
                        2,
                    ),

                    "Спрос": (
                        "✓"
                        if result.demand_ok
                        else "✗"
                    ),

                    "Сеть": (
                        "✓"
                        if result.grid_ok
                        else "✗"
                    ),

                    "Допустим": (
                        "✓"
                        if result.feasible
                        else "✗"
                    ),
                }
            )

        st.dataframe(
            table_data,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.error(
            "В заданном диапазоне невозможно найти "
            "вариант, который удовлетворяет ограничениям."
        )

    # --------------------------------------------------
    # Сценарный анализ
    # --------------------------------------------------

    st.divider()

    st.subheader(
        "📈 Сценарный анализ"
    )

    st.write(
        f"Что произойдёт, если рынок вырастет "
        f"ещё на **{scenario_growth:.0f}%**?"
    )

    scenario_data, scenario_result = (
        calculate_growth_scenario(
            data,
            scenario_growth,
        )
    )

    if scenario_result:

        s1, s2, s3, s4 = st.columns(4)

        s1.metric(
            "Рост EV",
            f"{scenario_data.ev_growth_percent:.0f}%",
        )

        s2.metric(
            "Станции",
            scenario_result.stations,
        )

        s3.metric(
            "Загрузка",
            f"{scenario_result.utilization_percent:.1f}%",
        )

        s4.metric(
            "Стоимость",
            f"{scenario_result.total_cost_rub / 1_000_000:.1f} млн ₽",
        )

        if scenario_result.feasible:

            st.success(
                "✓ Инфраструктура сохраняет работоспособность "
                "при заданном сценарии роста."
            )

        else:

            st.warning(
                "⚠ При данном сценарии требуется "
                "изменение инфраструктуры."
            )

    else:

        st.error(
            "При заданном сценарии не удалось "
            "найти допустимое решение."
        )

else:

    # --------------------------------------------------
    # Экран до первого расчёта
    # --------------------------------------------------

    st.info(
        "Измените параметры слева и нажмите "
        "«Рассчитать»."
    )

    st.markdown(
        """
        ### Что умеет модель

        1. Прогнозирует будущий спрос.
        2. Определяет спрос на быстрый заряд.
        3. Перебирает разные варианты количества станций.
        4. Проверяет ограничения электросети.
        5. Рассчитывает стоимость.
        6. Находит допустимый вариант.
        7. Позволяет проверить дополнительный сценарий роста.
        """
    )