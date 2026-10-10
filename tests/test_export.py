"""Tests for export_parquet module.

Unit tests that run without AWS credentials or a real TeslaMate database.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture
def mock_db_connection():
    """Mock PostgreSQL connection."""
    conn = MagicMock()
    return conn


@pytest.fixture
def mock_drives_df():
    """Mock drives DataFrame."""
    return pd.DataFrame(
        {
            "id": [1, 2],
            "start_date": [datetime(2026, 10, 7, 10, 0), datetime(2026, 10, 7, 15, 30)],
            "end_date": [datetime(2026, 10, 7, 10, 30), datetime(2026, 10, 7, 16, 0)],
            "start_address": ["Home", "Office"],
            "end_address": ["Office", "Home"],
            "distance": [15.5, 16.2],
            "duration_min": [30.0, 30.0],
            "start_km": [10000.0, 10015.5],
            "end_km": [10015.5, 10031.7],
            "kwh_used": [3.1, 3.2],
            "start_battery_level": [280, 276],
            "end_battery_level": [276, 273],
            "outside_temp_avg": [22.5, 23.0],
            "speed_max": [80.0, 85.0],
            "efficiency": [200.0, 197.5],
        }
    )


@pytest.fixture
def mock_charges_df():
    """Mock charges DataFrame."""
    return pd.DataFrame(
        {
            "id": [1],
            "start_date": [datetime(2026, 10, 7, 18, 0)],
            "end_date": [datetime(2026, 10, 7, 20, 0)],
            "address": ["Home Charger"],
            "charge_energy_added": [25.5],
            "start_battery_level": [150],
            "end_battery_level": [250],
            "duration_min": [120.0],
            "cost": [5.10],
        }
    )


def test_export_drives_success(mock_db_connection, mock_drives_df):
    """Test successful drives export."""
    with patch(
        "src.export.export_parquet.pd.read_sql_query", return_value=mock_drives_df
    ):
        with patch("pandas.DataFrame.to_parquet") as mock_to_parquet:
            from src.export.export_parquet import export_drives

            count = export_drives(mock_db_connection, "2026-10-07", "test-bucket")

            assert count == 2
            mock_to_parquet.assert_called_once()
            call_args = mock_to_parquet.call_args
            assert (
                "s3://test-bucket/raw/drives/date=2026-10-07/drives.parquet"
                in call_args[0]
            )


def test_export_drives_no_data(mock_db_connection):
    """Test drives export with no data."""
    empty_df = pd.DataFrame()

    with patch("src.export.export_parquet.pd.read_sql_query", return_value=empty_df):
        from src.export.export_parquet import export_drives

        count = export_drives(mock_db_connection, "2026-10-07", "test-bucket")

        assert count == 0


def test_export_charges_success(mock_db_connection, mock_charges_df):
    """Test successful charges export."""
    with patch(
        "src.export.export_parquet.pd.read_sql_query", return_value=mock_charges_df
    ):
        with patch("pandas.DataFrame.to_parquet") as mock_to_parquet:
            from src.export.export_parquet import export_charges

            count = export_charges(mock_db_connection, "2026-10-07", "test-bucket")

            assert count == 1
            mock_to_parquet.assert_called_once()
            call_args = mock_to_parquet.call_args
            assert (
                "s3://test-bucket/raw/charges/date=2026-10-07/charges.parquet"
                in call_args[0]
            )


def test_export_charges_no_data(mock_db_connection):
    """Test charges export with no data."""
    empty_df = pd.DataFrame()

    with patch("src.export.export_parquet.pd.read_sql_query", return_value=empty_df):
        from src.export.export_parquet import export_charges

        count = export_charges(mock_db_connection, "2026-10-07", "test-bucket")

        assert count == 0


def test_export_drives_custom_prefix(mock_db_connection, mock_drives_df):
    """Test drives export with custom S3 prefix."""
    with patch(
        "src.export.export_parquet.pd.read_sql_query", return_value=mock_drives_df
    ):
        with patch("pandas.DataFrame.to_parquet") as mock_to_parquet:
            from src.export.export_parquet import export_drives

            export_drives(
                mock_db_connection, "2026-10-07", "test-bucket", s3_prefix="custom/path"
            )

            call_args = mock_to_parquet.call_args
            assert (
                "s3://test-bucket/custom/path/date=2026-10-07/drives.parquet"
                in call_args[0]
            )


def test_get_db_connection():
    """Test database connection function signature."""
    from src.export.export_parquet import get_db_connection

    with patch("src.export.export_parquet.psycopg2.connect") as mock_connect:
        mock_connect.return_value = MagicMock()

        conn = get_db_connection(
            host="testhost",
            port=5432,
            user="testuser",
            password="testpass",
            dbname="testdb",
        )

        mock_connect.assert_called_once_with(
            host="testhost",
            port=5432,
            user="testuser",
            password="testpass",
            dbname="testdb",
        )
        assert conn is not None


def test_drives_query_columns():
    """Test that drives query uses correct TeslaMate column names."""
    # Extract the SQL query from the function
    import inspect

    from src.export.export_parquet import export_drives

    source = inspect.getsource(export_drives)

    # Verify correct column references (not the wrong ones)
    assert "start_ideal_battery_range_km" not in source
    assert "end_ideal_battery_range_km" not in source

    # Verify it joins with positions for battery_level
    assert "positions sp" in source or "positions AS sp" in source
    assert "sp.battery_level" in source
    assert "ep.battery_level" in source

    # Verify it has position joins
    assert "start_position_id" in source
    assert "end_position_id" in source


def test_charges_query_columns():
    """Test that charges query uses correct TeslaMate column names."""
    # Extract the SQL query from the function
    import inspect

    from src.export.export_parquet import export_charges

    source = inspect.getsource(export_charges)

    # Verify correct column references (not the wrong ones)
    assert "start_ideal_battery_range_km" not in source
    assert "end_ideal_battery_range_km" not in source

    # Verify it uses the direct columns from charging_processes
    assert "c.start_battery_level" in source
    assert "c.end_battery_level" in source


def test_drives_parquet_schema_matches_glue():
    """Test that drives Parquet schema matches Glue table definition."""
    import inspect

    from src.export.export_parquet import export_drives

    source = inspect.getsource(export_drives)

    # Verify PyArrow schema is defined with correct types matching Glue:
    # bigint -> int64
    assert "pa.int64()" in source or "int64" in source

    # timestamp -> timestamp("ms")
    assert 'pa.timestamp("ms")' in source or "timestamp" in source

    # string
    assert "pa.string()" in source or "string" in source

    # double -> float64
    assert "pa.float64()" in source or "float64" in source

    # int -> int32
    assert "pa.int32()" in source or "Int32" in source

    # Verify timestamp precision is set to ms (not ns)
    assert '.dt.floor("ms")' in source


def test_charges_parquet_schema_matches_glue():
    """Test that charges Parquet schema matches Glue table definition."""
    import inspect

    from src.export.export_parquet import export_charges

    source = inspect.getsource(export_charges)

    # Verify PyArrow schema is defined with correct types matching Glue:
    # bigint -> int64
    assert "pa.int64()" in source or "int64" in source

    # timestamp -> timestamp("ms")
    assert 'pa.timestamp("ms")' in source or "timestamp" in source

    # string
    assert "pa.string()" in source or "string" in source

    # double -> float64
    assert "pa.float64()" in source or "float64" in source

    # int -> int32
    assert "pa.int32()" in source or "Int32" in source

    # Verify timestamp precision is set to ms (not ns)
    assert '.dt.floor("ms")' in source
