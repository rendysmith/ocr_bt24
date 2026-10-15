"""Database connection utilities for MSSQL via pyodbc.

Reads connection parameters from config.ini (legacy) or environment variables.
"""

import os
import configparser
import pyodbc


def _get_config() -> configparser.ConfigParser:
    """Load and return the configparser instance (lazy-loaded)."""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")
    if os.path.exists(config_path):
        config.read(config_path)
    return config


def odbc_params() -> str:
    """Build an ODBC connection string from config.ini or env vars.

    Returns:
        A fully-formed ODBC connection string.
    """
    drivers = [x for x in pyodbc.drivers()]
    driver = "{" + f"{drivers[0]}" + "}" if drivers else "{ODBC Driver 17 for SQL Server}"

    config = _get_config()

    try:
        server = config.get("mssql", "server")
        database = config.get("mssql", "database")
        username = config.get("mssql", "username")
        password = config.get("mssql", "password")
    except (configparser.NoSectionError, configparser.NoOptionError):
        server = os.environ.get("mssql_server", "")
        database = os.environ.get("mssql_database", "")
        username = os.environ.get("mssql_username", "")
        password = os.environ.get("mssql_password", "")

    return (
        f"DRIVER={driver};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password}"
    )


def py_odbc():
    """Create and return a pyodbc connection using configured parameters."""
    return pyodbc.connect(odbc_params())
