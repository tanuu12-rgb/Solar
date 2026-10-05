"""Unit tests for GIS connection route module, electrical losses, and infrastructure cost."""

import numpy as np
import pandas as pd
import pytest

from core.gis.route import (
    calculate_haversine_distance_km,
    calculate_connection_route,
)


def test_haversine_known_coordinates() -> None:
    """Verify haversine formula against known analytical distance.

    Coordinates:
    Latur Town Hall: 18.4000 N, 76.5800 E
    Bhatangali Substation area: 18.3500 N, 76.5500 E
    Hand calculation / Great circle: ~6.39 km
    """
    lat1, lon1 = 18.4000, 76.5800
    lat2, lon2 = 18.3500, 76.5500

    d_km = calculate_haversine_distance_km(lat1, lon1, lat2, lon2)
    assert np.isclose(d_km, 6.39, atol=0.1)


def test_losses_increase_with_distance() -> None:
    """Verify that electrical losses (peak kW and annual MWh) increase with route distance at given voltage."""
    # Near plant: ~1.2 km (11 kV)
    res_near = calculate_connection_route(
        plant_lat=18.380,
        plant_lon=76.540,
        substation_lat=18.390,
        substation_lon=76.545,
        plant_mw=2.5,
    )

    # Medium plant: ~4.0 km (11 kV)
    res_medium = calculate_connection_route(
        plant_lat=18.380,
        plant_lon=76.540,
        substation_lat=18.415,
        substation_lon=76.545,
        plant_mw=2.5,
    )

    assert res_near.voltage_kv == res_medium.voltage_kv == 11.0
    assert res_medium.route_km > res_near.route_km
    assert res_medium.peak_loss_kw > res_near.peak_loss_kw
    assert res_medium.annual_loss_mwh > res_near.annual_loss_mwh


def test_cost_scales_linearly_with_length() -> None:
    """Verify that transmission line infrastructure capex scales linearly with route distance."""
    res_short = calculate_connection_route(
        plant_lat=18.380,
        plant_lon=76.540,
        substation_lat=18.390,
        substation_lon=76.540,
        plant_mw=2.0,
    )

    res_long = calculate_connection_route(
        plant_lat=18.380,
        plant_lon=76.540,
        substation_lat=18.410,
        substation_lon=76.540,
        plant_mw=2.0,
    )

    # Unit line cost (INR/km) is constant
    assert res_short.line_capex_per_km_inr == res_long.line_capex_per_km_inr
    expected_ratio = res_long.route_km / res_short.route_km
    actual_ratio = res_long.line_capex_total_inr / res_short.line_capex_total_inr
    assert np.isclose(actual_ratio, expected_ratio, atol=1e-3)


def test_obstacle_path_never_shorter_than_straight_line() -> None:
    """Verify that route avoiding obstacle polygons is never shorter than straight-line distance."""
    plant_lat, plant_lon = 18.380, 76.540
    substation_lat, substation_lon = 18.400, 76.540

    # Obstacle polygon placed directly in the path between plant and substation
    obstacle_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Forest Reserve Obstacle"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [76.535, 18.388],
                            [76.545, 18.388],
                            [76.545, 18.392],
                            [76.535, 18.392],
                            [76.535, 18.388],
                        ]
                    ],
                },
            }
        ],
    }

    res = calculate_connection_route(
        plant_lat=plant_lat,
        plant_lon=plant_lon,
        substation_lat=substation_lat,
        substation_lon=substation_lon,
        plant_mw=2.5,
        obstacle_geojson=obstacle_geojson,
    )

    assert res.route_km >= res.straight_line_km
    assert len(res.coordinates_path) >= 2
    assert "Obstacle Layer" in res.method
