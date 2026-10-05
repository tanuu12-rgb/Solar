"""GIS connection route planning, electrical losses, and infrastructure cost module.

Enforces PROJECT_SPEC Module 7 & Phase 4:
- Computes straight-line haversine distance (labelled 'straight-line lower bound').
- Computes route length with terrain factor (or least-cost path with networkx if obstacle layer provided).
- Computes voltage level selection (11 kV vs 33 kV).
- Computes 3-phase I2R peak loss (kW) and annual loss (MWh, % of generation) using hourly dispatch.
- Computes transmission line infrastructure cost (line length x capex/km + bay cost).
- Generates standard GeoJSON for map display.
"""

from typing import Dict, Any, List, Optional, Tuple
import math
import json
import numpy as np
import pandas as pd
import networkx as nx
from pydantic import BaseModel, Field

from core.config_loader import ConfigLoader, default_config_loader
from core.feasibility.rules_engine import select_transmission_voltage


class RouteResult(BaseModel):
    """Structured result model for GIS connection route analysis."""
    method: str
    straight_line_km: float
    route_km: float
    voltage_kv: float
    conductor_resistance_ohm_per_km: float
    conductor_reactance_ohm_per_km: float
    peak_current_a: float
    peak_loss_kw: float
    annual_loss_mwh: float
    loss_pct: float
    line_capex_per_km_inr: float
    line_capex_total_inr: float
    substation_bay_cost_inr: float
    total_infrastructure_cost_inr: float
    geojson: Dict[str, Any]
    coordinates_path: List[List[float]] = Field(default_factory=list)


def calculate_haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Calculate the great-circle distance between two points on the Earth (km).

    Formula:
    d = 2 * R * arcsin(sqrt(sin^2(dlat/2) + cos(lat1)*cos(lat2)*sin^2(dlon/2)))
    where R = 6371.0 km (Earth mean radius).
    """
    R = 6371.0  # Earth radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance_km = R * c
    return round(distance_km, 3)


def _point_in_polygon(x: float, y: float, poly: List[List[float]]) -> bool:
    """Ray casting algorithm for 2D point-in-polygon test."""
    n = len(poly)
    inside = False
    p1x, p1y = poly[0]
    for i in range(n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def _extract_polygon_rings(geojson_obj: Dict[str, Any]) -> List[List[List[float]]]:
    """Extract list of polygon coordinate rings from a GeoJSON object."""
    polygons: List[List[List[float]]] = []
    features = geojson_obj.get("features", []) if geojson_obj.get("type") == "FeatureCollection" else [geojson_obj]

    for feat in features:
        geom = feat.get("geometry", feat)
        geom_type = geom.get("type", "")
        coords = geom.get("coordinates", [])

        if geom_type == "Polygon":
            if coords and len(coords) > 0:
                polygons.append(coords[0])  # Exterior ring
        elif geom_type == "MultiPolygon":
            for poly in coords:
                if poly and len(poly) > 0:
                    polygons.append(poly[0])
    return polygons


def compute_least_cost_route(
    plant_lat: float,
    plant_lon: float,
    substation_lat: float,
    substation_lon: float,
    obstacle_geojson: Dict[str, Any],
    grid_cell_size_deg: float = 0.005,
    obstacle_cost_multiplier: float = 100.0,
) -> Tuple[List[List[float]], float]:
    """Compute shortest path over 2D grid avoiding obstacle polygons using networkx."""
    min_lat = min(plant_lat, substation_lat) - 0.02
    max_lat = max(plant_lat, substation_lat) + 0.02
    min_lon = min(plant_lon, substation_lon) - 0.02
    max_lon = max(plant_lon, substation_lon) + 0.02

    lat_steps = int(math.ceil((max_lat - min_lat) / grid_cell_size_deg)) + 1
    lon_steps = int(math.ceil((max_lon - min_lon) / grid_cell_size_deg)) + 1

    lats = [min_lat + i * grid_cell_size_deg for i in range(lat_steps)]
    lons = [min_lon + j * grid_cell_size_deg for j in range(lon_steps)]

    poly_rings = _extract_polygon_rings(obstacle_geojson)

    G = nx.Graph()

    def get_node_id(i: int, j: int) -> Tuple[int, int]:
        return (i, j)

    for i in range(lat_steps):
        for j in range(lon_steps):
            lat_val = lats[i]
            lon_val = lons[j]
            # Check if point is inside any obstacle polygon (lon, lat)
            is_obstacle = any(_point_in_polygon(lon_val, lat_val, ring) for ring in poly_rings)
            penalty = obstacle_cost_multiplier if is_obstacle else 1.0
            G.add_node((i, j), lat=lat_val, lon=lon_val, penalty=penalty)

    for i in range(lat_steps):
        for j in range(lon_steps):
            u = (i, j)
            u_pen = G.nodes[u]["penalty"]
            # 4-connectivity or 8-connectivity
            for di, dj in [(0, 1), (1, 0), (1, 1), (1, -1)]:
                ni, nj = i + di, j + dj
                if 0 <= ni < lat_steps and 0 <= nj < lon_steps:
                    v = (ni, nj)
                    v_pen = G.nodes[v]["penalty"]
                    d_km = calculate_haversine_distance_km(
                        G.nodes[u]["lat"], G.nodes[u]["lon"],
                        G.nodes[v]["lat"], G.nodes[v]["lon"],
                    )
                    weight = d_km * ((u_pen + v_pen) / 2.0)
                    G.add_edge(u, v, weight=weight, dist_km=d_km)

    # Find closest start node and end node
    def find_closest_node(target_lat: float, target_lon: float) -> Tuple[int, int]:
        best_node = (0, 0)
        min_d = float("inf")
        for i in range(lat_steps):
            for j in range(lon_steps):
                d = (lats[i] - target_lat) ** 2 + (lons[j] - target_lon) ** 2
                if d < min_d:
                    min_d = d
                    best_node = (i, j)
        return best_node

    start_node = find_closest_node(plant_lat, plant_lon)
    end_node = find_closest_node(substation_lat, substation_lon)

    try:
        path = nx.shortest_path(G, source=start_node, target=end_node, weight="weight")
        path_coords: List[List[float]] = [[plant_lon, plant_lat]]
        actual_distance_km = 0.0
        prev_lat, prev_lon = plant_lat, plant_lon

        for node in path:
            node_lat = G.nodes[node]["lat"]
            node_lon = G.nodes[node]["lon"]
            actual_distance_km += calculate_haversine_distance_km(prev_lat, prev_lon, node_lat, node_lon)
            path_coords.append([round(node_lon, 6), round(node_lat, 6)])
            prev_lat, prev_lon = node_lat, node_lon

        actual_distance_km += calculate_haversine_distance_km(prev_lat, prev_lon, substation_lat, substation_lon)
        path_coords.append([substation_lon, substation_lat])

        return path_coords, round(actual_distance_km, 3)
    except Exception:
        # Fallback to direct path
        straight = calculate_haversine_distance_km(plant_lat, plant_lon, substation_lat, substation_lon)
        return [[plant_lon, plant_lat], [substation_lon, substation_lat]], straight


def calculate_connection_route(
    plant_lat: float,
    plant_lon: float,
    substation_lat: float,
    substation_lon: float,
    plant_mw: float = 2.5,
    obstacle_geojson: Optional[Dict[str, Any]] = None,
    hourly_solar_generation_kwh: Optional[pd.Series] = None,
    loader: ConfigLoader = default_config_loader,
) -> RouteResult:
    """Compute complete GIS route, voltage selection, electrical losses, and infrastructure cost."""
    straight_line_km = calculate_haversine_distance_km(plant_lat, plant_lon, substation_lat, substation_lon)

    # Transmission Voltage Selection (11 kV vs 33 kV)
    voltage_kv = select_transmission_voltage(plant_mw, straight_line_km)

    # Conductor parameters from config
    if voltage_kv == 11.0:
        r_per_km = float(loader.get_assumption_value("line_resistance_per_km_11kv_ohm"))
        x_per_km = float(loader.get_assumption_value("line_reactance_per_km_11kv_ohm"))
        line_capex_per_km = float(loader.get_assumption_value("line_capex_per_km_11kv"))
    else:
        r_per_km = float(loader.get_assumption_value("line_resistance_per_km_33kv_ohm"))
        x_per_km = float(loader.get_assumption_value("line_reactance_per_km_33kv_ohm"))
        line_capex_per_km = float(loader.get_assumption_value("line_capex_per_km_33kv"))

    substation_bay_cost = float(loader.get_assumption_value("substation_bay_cost"))

    # Compute route path and distance
    if obstacle_geojson is not None and len(_extract_polygon_rings(obstacle_geojson)) > 0:
        cell_size = float(loader.get_assumption_value("gis_grid_cell_size_deg"))
        penalty = float(loader.get_assumption_value("gis_obstacle_cost_multiplier"))
        coords_path, route_km = compute_least_cost_route(
            plant_lat=plant_lat,
            plant_lon=plant_lon,
            substation_lat=substation_lat,
            substation_lon=substation_lon,
            obstacle_geojson=obstacle_geojson,
            grid_cell_size_deg=cell_size,
            obstacle_cost_multiplier=penalty,
        )
        # Ensure obstacle route is never shorter than straight-line
        route_km = max(route_km, straight_line_km)
        method_str = "Least-Cost Grid Routing with GeoJSON Obstacle Layer (networkx)"
    else:
        route_factor = float(loader.get_assumption_value("gis_route_factor"))
        route_km = round(straight_line_km * route_factor, 3)
        coords_path = [
            [round(plant_lon, 6), round(plant_lat, 6)],
            [round(substation_lon, 6), round(substation_lat, 6)],
        ]
        method_str = f"Straight-Line Distance with Terrain Factor ({route_factor:.2f}×)"

    # Total conductor resistance
    total_r_ohm = r_per_km * route_km
    pf = 0.95

    # Peak Loss Calculation:
    # I = P_peak / (sqrt(3) * V_LL * pf)
    peak_power_kw = plant_mw * 1000.0
    v_volts = voltage_kv * 1000.0
    peak_current_a = peak_power_kw / (math.sqrt(3.0) * (v_volts / 1000.0) * pf)
    # Peak loss = 3 * I^2 * R / 1000 kW
    peak_loss_kw = round(3.0 * (peak_current_a ** 2) * total_r_ohm / 1000.0, 2)

    # Annual Energy Loss Estimation:
    if hourly_solar_generation_kwh is not None:
        sol_kw = hourly_solar_generation_kwh.to_numpy()
        currents_a = sol_kw / (math.sqrt(3.0) * (v_volts / 1000.0) * pf)
        hourly_loss_kw = 3.0 * (currents_a ** 2) * total_r_ohm / 1000.0
        annual_loss_kwh = float(np.sum(hourly_loss_kw))
        annual_solar_gen_kwh = float(np.sum(sol_kw))
        annual_loss_mwh = round(annual_loss_kwh / 1000.0, 2)
        loss_pct = round((annual_loss_kwh / max(1.0, annual_solar_gen_kwh)) * 100.0, 2)
    else:
        # Benchmark loss factor approximation (peak loss * 8760 * loss_factor)
        # For solar, loss load factor ~ 0.15 - 0.20
        annual_loss_mwh = round(peak_loss_kw * 1500.0 / 1000.0, 2)
        annual_gen_mwh = plant_mw * 1600.0
        loss_pct = round((annual_loss_mwh / annual_gen_mwh) * 100.0, 2)

    # Infrastructure Capital Cost
    line_capex_total = route_km * line_capex_per_km
    total_infra_cost = line_capex_total + substation_bay_cost

    # Construct GeoJSON FeatureCollection
    geojson_features = [
        {
            "type": "Feature",
            "properties": {
                "name": "Connection Route",
                "voltage_kv": voltage_kv,
                "length_km": route_km,
                "method": method_str,
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords_path,
            },
        },
        {
            "type": "Feature",
            "properties": {
                "name": "Candidate Solar Plant",
                "capacity_mw": plant_mw,
                "role": "Generation Source",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(plant_lon, 6), round(plant_lat, 6)],
            },
        },
        {
            "type": "Feature",
            "properties": {
                "name": "33/11 kV Substation",
                "role": "Grid Interconnection Substation",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(substation_lon, 6), round(substation_lat, 6)],
            },
        },
    ]

    geojson_collection = {
        "type": "FeatureCollection",
        "features": geojson_features,
    }

    return RouteResult(
        method=method_str,
        straight_line_km=straight_line_km,
        route_km=route_km,
        voltage_kv=voltage_kv,
        conductor_resistance_ohm_per_km=r_per_km,
        conductor_reactance_ohm_per_km=x_per_km,
        peak_current_a=round(peak_current_a, 2),
        peak_loss_kw=peak_loss_kw,
        annual_loss_mwh=annual_loss_mwh,
        loss_pct=loss_pct,
        line_capex_per_km_inr=line_capex_per_km,
        line_capex_total_inr=round(line_capex_total, 2),
        substation_bay_cost_inr=round(substation_bay_cost, 2),
        total_infrastructure_cost_inr=round(total_infra_cost, 2),
        geojson=geojson_collection,
        coordinates_path=coords_path,
    )
