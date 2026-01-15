"""
Patient personal details normalization and feature extraction
"""
from typing import Dict, Any, Tuple, Optional
from datetime import date, datetime


LBS_PER_KG = 2.20462


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _kg_to_lbs(kg: Optional[float]) -> Optional[float]:
    if kg is None:
        return None
    return round(kg * LBS_PER_KG, 2)


def _lbs_to_kg(lbs: Optional[float]) -> Optional[float]:
    if lbs is None:
        return None
    return round(lbs / LBS_PER_KG, 2)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def canonicalize_patient_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize request payload to canonical keys only.

    Canonical keys:
    - date_of_birth
    - sex
    - height_cm
    - weight_kg
    """
    data = dict(payload or {})

    # Aliases -> canonical (only when provided)
    canonical = {
        **{k: v for k, v in data.items() if k not in {
            "dob",
            "sex_assigned_at_birth",
            "height",
            "height_cm",
            "weight",
            "weight_lbs",
            "weight_kg",
        }}
    }

    if "date_of_birth" in data or "dob" in data:
        canonical["date_of_birth"] = data.get("date_of_birth") or data.get("dob")

    if "sex" in data or "sex_assigned_at_birth" in data:
        canonical["sex"] = data.get("sex") or data.get("sex_assigned_at_birth")

    if "height_cm" in data or "height" in data:
        height_cm = data.get("height_cm")
        if height_cm is None:
            height_cm = data.get("height")
        canonical["height_cm"] = _to_float(height_cm)

    if "weight_kg" in data or "weight" in data or "weight_lbs" in data:
        weight_kg = data.get("weight_kg")
        if weight_kg is None:
            weight_kg = data.get("weight")  # legacy kg
        weight_kg = _to_float(weight_kg)

        weight_lbs = _to_float(data.get("weight_lbs"))
        if weight_kg is None and weight_lbs is not None:
            weight_kg = _lbs_to_kg(weight_lbs)

        canonical["weight_kg"] = weight_kg

    return canonical


def add_aliases_for_response(patient: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add deprecated alias fields to response for backward compatibility.
    """
    data = dict(patient or {})
    dob = data.get("date_of_birth")
    sex = data.get("sex")
    height_cm = _to_float(data.get("height_cm"))
    weight_kg = _to_float(data.get("weight_kg"))

    data["dob"] = dob
    data["sex_assigned_at_birth"] = sex
    data["height"] = height_cm
    data["weight"] = weight_kg
    data["weight_lbs"] = _kg_to_lbs(weight_kg)

    return data


def extract_personal_details(patient: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Dict[str, str]]]:
    """
    Extract personal details from canonical storage and report provenance.
    """
    data = dict(patient or {})
    sources: Dict[str, Dict[str, str]] = {}

    dob = data.get("date_of_birth")
    if dob:
        sources["dob"] = {"from": "patient.date_of_birth", "transform": "none"}

    sex = data.get("sex")
    if sex:
        sources["sex_assigned_at_birth"] = {"from": "patient.sex", "transform": "none"}

    height_cm = _to_float(data.get("height_cm"))
    if height_cm is not None:
        sources["height_cm"] = {"from": "patient.height_cm", "transform": "none"}

    weight_kg = _to_float(data.get("weight_kg"))
    if weight_kg is not None:
        sources["weight_kg"] = {"from": "patient.weight_kg", "transform": "none"}
        sources["weight_lbs"] = {"from": "patient.weight_kg", "transform": "kg_to_lbs"}

    age_years = None
    dob_date = _parse_date(dob)
    if dob_date:
        today = date.today()
        age_years = today.year - dob_date.year - (
            (today.month, today.day) < (dob_date.month, dob_date.day)
        )
        sources["age_years"] = {"from": "patient.date_of_birth", "transform": "dob_to_age"}

    bmi = None
    if height_cm and weight_kg:
        height_m = height_cm / 100.0
        if height_m > 0:
            bmi = round(weight_kg / (height_m ** 2), 1)
            sources["bmi"] = {
                "from": "patient.height_cm,patient.weight_kg",
                "transform": "bmi",
            }

    return {
        "dob": dob,
        "sex_assigned_at_birth": sex,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "weight_lbs": _kg_to_lbs(weight_kg),
        "age_years": age_years,
        "bmi": bmi,
    }, sources
