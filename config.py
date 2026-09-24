"""
Настройки проекта.

Здесь находятся значения по умолчанию.
Если нужно изменить стартовые значения интерфейса,
удобнее всего делать это здесь.
"""

# -----------------------------
# Значения по умолчанию
# -----------------------------

DEFAULT_CURRENT_DEMAND = 1000
DEFAULT_EV_GROWTH = 30
DEFAULT_FAST_CHARGING_SHARE = 40

DEFAULT_STATION_POWER = 150
DEFAULT_GRID_POWER = 1000
DEFAULT_SIMULTANEITY = 0.70

DEFAULT_STATION_COST = 4_000_000
DEFAULT_GRID_UPGRADE_COST_PER_100KW = 2_000_000

# Сколько условных единиц спроса
# способна обслужить одна станция.
DEFAULT_STATION_CAPACITY = 100

# Дополнительный сценарий роста
DEFAULT_SCENARIO_GROWTH = 50

# Максимальное количество станций,
# которое алгоритм будет проверять.
MAX_STATIONS_TO_CHECK = 50