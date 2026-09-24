"""
Основной алгоритм оптимизации зарядной инфраструктуры.
"""

import math
from dataclasses import dataclass
from typing import List

@dataclass
class InputData:
    """
    Входные параметры модели.
    """

    current_demand: float
    ev_growth_percent: float
    fast_charging_share_percent: float

    station_power_kw: float
    available_grid_power_kw: float
    simultaneity_factor: float

    station_cost_rub: float
    grid_upgrade_cost_per_100kw_rub: float

    station_capacity: float

@dataclass
class ScenarioResult:
    """
    Результат расчёта одного сценария.
    """

    stations: int

    current_demand: float
    future_demand: float
    fast_demand: float

    station_capacity_total: float

    installed_power_kw: float
    effective_power_kw: float

    available_grid_power_kw: float
    power_deficit_kw: float
    power_reserve_kw: float

    station_cost_rub: float
    grid_upgrade_cost_rub: float
    total_cost_rub: float

    utilization_percent: float

    demand_ok: bool
    grid_ok: bool
    feasible: bool

def calculate_future_demand(
    current_demand: float,
    growth_percent: float
) -> float:
    """
    Прогнозирует будущий спрос.

    Например:
    1000 + 30% = 1300
    """

    return current_demand * (1 + growth_percent / 100)

def calculate_fast_demand(
    future_demand: float,
    fast_charging_share_percent: float
) -> float:
    """
    Определяет спрос, который должен покрываться
    быстрой зарядной инфраструктурой.
    """

    return future_demand * fast_charging_share_percent / 100

def calculate_required_stations(
    fast_demand: float,
    station_capacity: float
) -> int:
    """
    Рассчитывает минимальное количество станций,
    необходимое для покрытия спроса.
    """

    if station_capacity <= 0:
        raise ValueError("Производительность станции должна быть больше 0.")

    return max(1, math.ceil(fast_demand / station_capacity))

def calculate_scenario(
    data: InputData,
    stations: int
) -> ScenarioResult:
    """
    Рассчитывает один вариант количества станций.
    """

    if stations <= 0:
        raise ValueError("Количество станций должно быть больше 0.")

    future_demand = calculate_future_demand(
        data.current_demand,
        data.ev_growth_percent
    )

    fast_demand = calculate_fast_demand(
        future_demand,
        data.fast_charging_share_percent
    )

    station_capacity_total = stations * data.station_capacity

    # Реальная установленная мощность
    installed_power_kw = stations * data.station_power_kw

    # Учитываем одновременность работы станций
    effective_power_kw = (
        installed_power_kw * data.simultaneity_factor
    )

    # Проверяем, хватает ли мощности сети
    power_deficit_kw = max(
        0,
        effective_power_kw - data.available_grid_power_kw
    )

    power_reserve_kw = max(
        0,
        data.available_grid_power_kw - effective_power_kw
    )

    # Стоимость самих станций
    station_cost_rub = (
        stations * data.station_cost_rub
    )

    # Если мощности не хватает,
    # считаем стоимость усиления сети.
    grid_upgrade_cost_rub = (
        math.ceil(power_deficit_kw / 100)
        * data.grid_upgrade_cost_per_100kw_rub
        if power_deficit_kw > 0
        else 0
    )

    total_cost_rub = (
        station_cost_rub
        + grid_upgrade_cost_rub
    )

    # Загрузка станций.
    #
    # Если мощность станций позволяет покрыть спрос,
    # загрузка определяется отношением спроса
    # к общей пропускной способности.
    if station_capacity_total > 0:
        utilization_percent = min(
            100,
            fast_demand / station_capacity_total * 100
        )
    else:
        utilization_percent = 100

    demand_ok = (
        station_capacity_total >= fast_demand
    )

    grid_ok = (
        effective_power_kw <= data.available_grid_power_kw
    )

    feasible = demand_ok and grid_ok

    return ScenarioResult(
        stations=stations,

        current_demand=data.current_demand,
        future_demand=future_demand,
        fast_demand=fast_demand,

        station_capacity_total=station_capacity_total,

        installed_power_kw=installed_power_kw,
        effective_power_kw=effective_power_kw,

        available_grid_power_kw=data.available_grid_power_kw,
        power_deficit_kw=power_deficit_kw,
        power_reserve_kw=power_reserve_kw,

        station_cost_rub=station_cost_rub,
        grid_upgrade_cost_rub=grid_upgrade_cost_rub,
        total_cost_rub=total_cost_rub,

        utilization_percent=utilization_percent,

        demand_ok=demand_ok,
        grid_ok=grid_ok,
        feasible=feasible,
    )

def optimize(
    data: InputData,
    max_stations: int = 50
) -> List[ScenarioResult]:
    """
    Перебирает разные варианты количества станций.

    Например:
    1 станция
    2 станции
    3 станции
    ...
    50 станций

    Для каждого варианта выполняется полный расчёт.
    """

    results = []

    for stations in range(1, max_stations + 1):

        result = calculate_scenario(
            data,
            stations
        )

        results.append(result)

    return results

def find_minimum_feasible(
    results: List[ScenarioResult]
):
    """
    Возвращает первый вариант,
    который одновременно:

    1. покрывает спрос;
    2. не превышает доступную мощность сети.
    """

    for result in results:

        if result.feasible:
            return result

    return None

def calculate_growth_scenario(
    data: InputData,
    additional_growth_percent: float
):
    """
    Создаёт дополнительный сценарий развития.

    Например:
    основной рост = 30%
    дополнительный сценарий = +50%

    Тогда рост становится 80%.
    """

    scenario_data = InputData(
        current_demand=data.current_demand,

        ev_growth_percent=(
            data.ev_growth_percent
            + additional_growth_percent
        ),

        fast_charging_share_percent=(
            data.fast_charging_share_percent
        ),

        station_power_kw=data.station_power_kw,

        available_grid_power_kw=(
            data.available_grid_power_kw
        ),

        simultaneity_factor=(
            data.simultaneity_factor
        ),

        station_cost_rub=(
            data.station_cost_rub
        ),

        grid_upgrade_cost_per_100kw_rub=(
            data.grid_upgrade_cost_per_100kw_rub
        ),

        station_capacity=(
            data.station_capacity
        ),
    )

    results = optimize(scenario_data)

    return (
        scenario_data,
        find_minimum_feasible(results)
    )