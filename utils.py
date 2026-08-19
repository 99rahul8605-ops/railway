import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

CLASS_ORDER = ["1A", "2A", "3A", "3E", "CC", "EC", "SL", "2S"]

def parse_availability(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert raw API availability into a normalized dict:
    {
        "status": "AVAILABLE" | "RAC" | "WL" | "REGRET",
        "count": int | None
    }
    """
    # API specifics may vary; assume fields: "availability", "status", "count"
    status = raw.get("status", "").upper()
    count = raw.get("count")
    if status in ("AVAILABLE", "CONFIRMED"):
        return {"status": "AVAILABLE", "count": count}
    if status == "RAC":
        return {"status": "RAC", "count": count}
    if status.startswith("WL"):
        # count may be waitlist number
        return {"status": "WL", "count": count}
    return {"status": "REGRET", "count": None}

def rank_availability(av: Dict[str, Any]) -> Tuple[int, int]:
    """
    Return a sortable key: lower is better.
    Priority: AVAILABLE (0), RAC (1), WL (2), REGRET (3)
    Within AVAILABLE, higher count first => negative count.
    """
    order = {"AVAILABLE": 0, "RAC": 1, "WL": 2, "REGRET": 3}
    prio = order.get(av["status"], 3)
    if prio == 0 and av["count"] is not None:
        return (prio, -av["count"])
    return (prio, 0)

def format_class_result(class_code: str, av: Dict[str, Any]) -> str:
    status = av["status"]
    count = av["count"]
    if status == "AVAILABLE":
        return f"{class_code}: AVAILABLE {count}"
    if status == "RAC":
        return f"{class_code}: RAC {count}"
    if status == "WL":
        return f"{class_code}: WL {count}"
    return f"{class_code}: NOT AVAILABLE"

def format_station_result(station_name: str, station_code: str, class_results: Dict[str, Any]) -> str:
    lines = [f"{station_name} → {station_code}"]
    for cls in CLASS_ORDER:
        if cls in class_results:
            lines.append(f"  {format_class_result(cls, class_results[cls])}")
    return "\n".join(lines)

def find_best_option(results: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """
    results: list of dicts with keys:
        boarding_code, boarding_name, dest_code, dest_name, classes (dict)
    Returns the best boarding station dict or None.
    """
    best = None
    best_key = None
    for r in results:
        # compute overall rank: best class rank
        class_ranks = [rank_availability(av) for av in r["classes"].values()]
        if not class_ranks:
            continue
        overall = min(class_ranks)
        if best_key is None or overall < best_key:
            best_key = overall
            best = r
    return best