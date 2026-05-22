import json

def format_netdata_chart(chart_name: str, title: str, units: str, family: str, dimensions: list) -> dict:
    """Format for custom Python.d plugin for Netdata"""
    return {
        "name": chart_name,
        "title": title,
        "units": units,
        "family": family,
        "dimensions": dimensions
    }
