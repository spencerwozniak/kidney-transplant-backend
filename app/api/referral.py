"""
Transplant Access Navigator endpoints

Handles transplant center discovery and referral orchestration
"""
from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any, Optional
import json
import math
from pathlib import Path

from app.database import storage as database
from app.database.schemas import PatientReferralState, PatientStatus
from app.api.utils import get_device_id
from app.services.status.computation import recompute_pathway_stage
from app.services.utils import convert_datetime_to_iso

router = APIRouter()

# Cache for transplant centers (loaded once, reused across requests)
_transplant_centers_cache: Optional[List[Dict[str, Any]]] = None


def derive_state_from_zip(zip_code: str) -> Optional[str]:
    """
    Derive state from zip code using USPS zip code ranges
    
    This is a simplified lookup based on USPS zip code ranges.
    For production, use a proper zip code database or geocoding API.
    
    Args:
        zip_code: 5-digit US zip code
    
    Returns:
        State abbreviation (e.g., "CA", "NY") or None if not found
    """
    if not zip_code or len(zip_code) != 5 or not zip_code.isdigit():
        return None
    
    zip_num = int(zip_code)
    
    # USPS zip code ranges by state (simplified - covers major ranges)
    # Source: USPS zip code ranges
    if 90000 <= zip_num <= 96199:
        return "CA"  # California
    elif 10000 <= zip_num <= 14999:
        return "NY"  # New York
    elif 75000 <= zip_num <= 79999:
        return "TX"  # Texas
    elif 32000 <= zip_num <= 34999:
        return "FL"  # Florida
    elif 60000 <= zip_num <= 62999:
        return "IL"  # Illinois
    elif 80000 <= zip_num <= 81999:
        return "CO"  # Colorado
    elif 20000 <= zip_num <= 23999:
        return "VA"  # Virginia / DC area
    elif 30000 <= zip_num <= 31999:
        return "GA"  # Georgia
    elif 70000 <= zip_num <= 71999:
        return "LA"  # Louisiana
    elif 28000 <= zip_num <= 28999:
        return "NC"  # North Carolina
    elif 29000 <= zip_num <= 29999:
        return "SC"  # South Carolina (29601 is here)
    elif 40000 <= zip_num <= 42999:
        return "KY"  # Kentucky
    elif 43000 <= zip_num <= 45999:
        return "OH"  # Ohio
    elif 46000 <= zip_num <= 47999:
        return "IN"  # Indiana
    elif 48000 <= zip_num <= 49999:
        return "MI"  # Michigan
    elif 50000 <= zip_num <= 52999:
        return "IA"  # Iowa
    elif 53000 <= zip_num <= 54999:
        return "WI"  # Wisconsin
    elif 55000 <= zip_num <= 56999:
        return "MN"  # Minnesota
    elif 57000 <= zip_num <= 57999:
        return "SD"  # South Dakota
    elif 58000 <= zip_num <= 58999:
        return "ND"  # North Dakota
    elif 59000 <= zip_num <= 59999:
        return "MT"  # Montana
    elif 97000 <= zip_num <= 97999:
        return "OR"  # Oregon
    elif 98000 <= zip_num <= 99999:
        return "WA"  # Washington
    elif 1000 <= zip_num <= 2799:
        return "MA"  # Massachusetts
    elif 3000 <= zip_num <= 3899:
        return "NH"  # New Hampshire
    elif 4000 <= zip_num <= 4999:
        return "ME"  # Maine
    elif 5000 <= zip_num <= 5999:
        return "VT"  # Vermont
    elif 6000 <= zip_num <= 6999:
        return "CT"  # Connecticut
    elif 7000 <= zip_num <= 8999:
        return "NJ"  # New Jersey (includes 08000-08999)
    elif 15000 <= zip_num <= 19999:
        return "PA"  # Pennsylvania
    elif 20000 <= zip_num <= 23999:
        return "DC"  # District of Columbia / VA
    elif 24000 <= zip_num <= 26999:
        return "VA"  # Virginia
    elif 27000 <= zip_num <= 27999:
        return "NC"  # North Carolina
    elif 35000 <= zip_num <= 36999:
        return "AL"  # Alabama
    elif 37000 <= zip_num <= 38999:
        return "TN"  # Tennessee
    elif 39000 <= zip_num <= 39999:
        return "MS"  # Mississippi
    elif 70000 <= zip_num <= 71999:
        return "LA"  # Louisiana
    elif 72000 <= zip_num <= 72999:
        return "AR"  # Arkansas
    elif 73000 <= zip_num <= 74999:
        return "OK"  # Oklahoma
    elif 80000 <= zip_num <= 81999:
        return "CO"  # Colorado
    elif 82000 <= zip_num <= 83999:
        return "WY"  # Wyoming
    elif 84000 <= zip_num <= 84999:
        return "UT"  # Utah
    elif 85000 <= zip_num <= 86999:
        return "AZ"  # Arizona
    elif 87000 <= zip_num <= 88999:
        return "NM"  # New Mexico
    elif 89000 <= zip_num <= 89999:
        return "NV"  # Nevada
    elif 90000 <= zip_num <= 96199:
        return "CA"  # California
    elif 96700 <= zip_num <= 96999:
        return "HI"  # Hawaii
    elif 99500 <= zip_num <= 99999:
        return "AK"  # Alaska
    
    return None


def derive_city_state_from_zip(zip_code: str) -> Dict[str, Optional[str]]:
    """
    Derive city and state from zip code
    
    For demo purposes, this is a simple lookup. In production, you would use:
    - A zip code database (USPS, GeoNames, etc.)
    - A geocoding API (Google Maps, Mapbox, etc.)
    
    Currently returns state from zip code lookup, but city is None.
    Frontend can provide city directly to avoid this limitation.
    
    Args:
        zip_code: 5-digit US zip code
    
    Returns:
        Dict with 'city' and 'state' keys (state may be derived, city is None)
    """
    state = derive_state_from_zip(zip_code)
    return {
        "city": None,
        "state": state
    }


def load_transplant_centers() -> List[Dict[str, Any]]:
    """
    Load transplant centers from JSON file
    
    Uses in-memory cache to avoid repeated file reads.
    Cache persists for the lifetime of the server process.
    """
    global _transplant_centers_cache
    
    # Return cached data if available
    if _transplant_centers_cache is not None:
        return _transplant_centers_cache
    
    # Load from file
    centers_path = Path("data/transplant_centers.json")
    centers_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(centers_path, 'r') as f:
            _transplant_centers_cache = json.load(f)
            return _transplant_centers_cache
    except (FileNotFoundError, json.JSONDecodeError):
        _transplant_centers_cache = []
        return []


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points using Haversine formula
    Returns distance in miles
    """
    R = 3959  # Earth radius in miles
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


@router.get("/centers/nearby")
async def find_nearby_centers(
    zip_code: Optional[str] = None,
    state: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    insurance_type: Optional[str] = None,
    radius_miles: Optional[int] = None,
    limit: Optional[int] = None,
    request: Request = ...,
):
    """
    Find nearby transplant centers
    
    Filters by location, state acceptance, and insurance compatibility.
    
    Query Parameters:
    - zip_code (optional): 5-digit US zip code. If provided, state will be derived if not specified.
    - state (optional): US state abbreviation (e.g., "CA", "NY"). Required if zip_code not provided.
    - lat/lng (optional): Latitude/longitude for distance calculation
    - insurance_type (optional): Filter by insurance type ("medicare", "medicaid")
    - radius_miles (optional): Maximum distance in miles (default: no limit)
    - limit (optional): Maximum number of results (default: no limit)
    
    Examples:
    - GET /api/v1/centers/nearby?zip_code=29601
    - GET /api/v1/centers/nearby?state=SC
    - GET /api/v1/centers/nearby?zip_code=29601&insurance_type=medicare&limit=10
    """
    device_id = get_device_id(request)
    centers = load_transplant_centers()
    patient = database.get_patient(device_id) if device_id else None
    
    # Get patient location
    patient_state = state
    patient_lat = lat
    patient_lng = lng
    
    # If zip_code is provided but state is not, derive state from zip
    if zip_code and not patient_state:
        patient_state = derive_state_from_zip(zip_code)
    
    # Try to get from patient referral state if still not available
    if not patient_state and patient and device_id:
        referral_state = database.get_patient_referral_state(device_id)
        if referral_state:
            location = referral_state.get('location', {})
            patient_state = location.get('state')
            if not patient_lat:
                patient_lat = location.get('lat')
            if not patient_lng:
                patient_lng = location.get('lng')
    
    # If still no state, return empty list instead of 400 (graceful degradation)
    if not patient_state:
        return []
    
    results = []
    
    for center in centers:
        center_state = center['location']['state']
        
        # Filter by state acceptance
        if patient_state not in center.get('accepts_referrals_from', []):
            continue
        
        # Calculate distance if we have coordinates
        distance_miles = None
        if patient_lat and patient_lng:
            center_lat = center['location']['lat']
            center_lng = center['location']['lng']
            distance_miles = round(haversine_distance(patient_lat, patient_lng, center_lat, center_lng), 1)
            
            # Filter by radius if specified
            if radius_miles is not None and distance_miles is not None:
                if distance_miles > radius_miles:
                    continue
        
        # Check insurance compatibility
        insurance_compatible = True
        if insurance_type:
            if insurance_type == 'medicare':
                insurance_compatible = center.get('insurance_notes', {}).get('medicare', False)
            elif insurance_type == 'medicaid':
                medicaid_states = center.get('insurance_notes', {}).get('medicaid_states', [])
                insurance_compatible = patient_state in medicaid_states
        
        # Skip if insurance filter doesn't match
        if insurance_type and not insurance_compatible:
            continue
        
        results.append({
            "center_id": center['center_id'],
            "name": center['name'],
            "location": center['location'],
            "distance_miles": distance_miles,
            "referral_required": center['referral_requirements']['required'],
            "self_referral_allowed": center['referral_requirements']['self_referral_allowed'],
            "who_can_refer": center['referral_requirements']['who_can_refer'],
            "contact": center['contact'],
            "insurance_compatible": insurance_compatible,
        })
    
    # Sort by distance if available (closest first)
    results.sort(key=lambda x: x['distance_miles'] if x['distance_miles'] is not None else float('inf'))
    
    # Apply limit if specified
    if limit is not None and limit > 0:
        results = results[:limit]
    
    return results


@router.get("/referral-state")
async def get_referral_state(request: Request):
    """
    Get patient referral state
    
    Returns location with zip, city, and state fields.
    City and state are included if provided by frontend or derived from zip.
    """
    device_id = get_device_id(request)
    state = database.get_patient_referral_state(device_id)
    if not state:
        # Create default state from patient data
        patient = database.get_patient(device_id)
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Initialize with patient's has_referral status
        default_state = {
            "patient_id": patient['id'],
            "location": {
                "zip": None,
                "city": None,
                "state": None
            },
            "has_referral": patient.get('has_referral', False),
            "referral_source": None,
            "last_nephrologist": None,
            "dialysis_center": None,
            "preferred_centers": [],
            "referral_status": "not_started"
        }
        database.save_patient_referral_state(default_state, device_id)
        return default_state
    
    # Ensure location has city and state fields (for backward compatibility)
    location = state.get('location', {})
    if 'city' not in location:
        location['city'] = None
    if 'state' not in location:
        location['state'] = None
    
    # If zip is provided but city/state are missing, try to derive them
    zip_code = location.get('zip')
    if zip_code and not location.get('city') and not location.get('state'):
        derived = derive_city_state_from_zip(zip_code)
        if derived.get('city'):
            location['city'] = derived['city']
        if derived.get('state'):
            location['state'] = derived['state']
    
    state['location'] = location
    return state


@router.post("/referral-state")
async def update_referral_state(state: Dict[str, Any], request: Request):
    """
    Update patient referral state
    
    Accepts location with zip, city, and state fields.
    If zip is provided but city/state are missing, attempts to derive them.
    Frontend can provide city/state directly to ensure accuracy.
    """
    device_id = get_device_id(request)
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Ensure patient_id matches
    state['patient_id'] = patient['id']
    
    # Ensure location has city and state fields
    location = state.get('location', {})
    zip_code = location.get('zip')
    
    # If zip is provided but city/state are missing, try to derive them
    if zip_code and not location.get('city') and not location.get('state'):
        derived = derive_city_state_from_zip(zip_code)
        if derived.get('city') and not location.get('city'):
            location['city'] = derived['city']
        if derived.get('state') and not location.get('state'):
            location['state'] = derived['state']
    
    # Ensure location dict has all expected fields
    if 'city' not in location:
        location['city'] = None
    if 'state' not in location:
        location['state'] = None
    
    state['location'] = location
    
    # Save state
    database.save_patient_referral_state(state, device_id)
    
    # Update patient's has_referral if provided
    if 'has_referral' in state:
        patient['has_referral'] = state['has_referral']
        database.save_patient(patient, device_id)
        
        # Recompute pathway stage since has_referral affects pathway progression
        status_data = database.get_patient_status(device_id)
        if status_data:
            status = PatientStatus(**status_data)
            status = recompute_pathway_stage(status, device_id)
            status_data_updated = convert_datetime_to_iso(status.model_dump(), ['updated_at'])
            database.save_patient_status(status_data_updated, device_id)
    
    return state


@router.get("/referral-pathway")
async def get_referral_pathway(request: Request):
    """
    Determine referral pathway based on patient state
    
    Returns pathway type and guidance
    """
    device_id = get_device_id(request)
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    referral_state = database.get_patient_referral_state(device_id)
    if not referral_state:
        referral_state = {
            "last_nephrologist": None,
            "dialysis_center": None,
            "has_referral": patient.get('has_referral', False)
        }
    
    # Safely check for nephrologist and dialysis center
    # Handle case where values might be None
    last_nephrologist = referral_state.get('last_nephrologist')
    dialysis_center = referral_state.get('dialysis_center')
    
    has_nephrologist = (
        last_nephrologist is not None 
        and isinstance(last_nephrologist, dict) 
        and last_nephrologist.get('name') is not None
    )
    has_dialysis_center = (
        dialysis_center is not None 
        and isinstance(dialysis_center, dict) 
        and dialysis_center.get('name') is not None
    )
    
    if has_nephrologist:
        pathway = "nephrologist_referral"
        guidance = {
            "title": "You have a nephrologist who can refer you",
            "steps": [
                "Contact your nephrologist's office",
                "Request a referral to your preferred transplant center",
                "Ask them to send your recent medical records"
            ],
            "script": "I'm pursuing a kidney transplant evaluation at [Center Name]. Could you please send a referral and my recent records?",
            "what_to_send": [
                "Referral form (from transplant center)",
                "Last nephrology note",
                "Recent lab work",
                "Dialysis summary (if applicable)"
            ]
        }
    elif has_dialysis_center:
        pathway = "dialysis_center_referral"
        guidance = {
            "title": "Your dialysis center can help with referral",
            "steps": [
                "Speak with your dialysis center social worker or care coordinator",
                "Request assistance with transplant center referral",
                "They can initiate the referral process"
            ],
            "script": "I'd like to pursue a kidney transplant evaluation. Can you help me get a referral to [Center Name]?",
            "what_to_send": [
                "Dialysis treatment records",
                "Recent lab work",
                "Medical history summary"
            ]
        }
    else:
        pathway = "no_provider"
        guidance = {
            "title": "You'll need to establish care first",
            "paths": [
                {
                    "name": "Find a nephrologist",
                    "description": "A nephrologist can evaluate your kidney function and refer you to a transplant center",
                    "action": "Find nearby nephrologists or kidney care clinics"
                },
                {
                    "name": "Contact transplant center directly",
                    "description": "Some centers can guide you on next steps, though they may still require a referral",
                    "action": "Call the transplant center's referral line"
                },
                {
                    "name": "Find a community health center",
                    "description": "Federally Qualified Health Centers can help establish care and provide referrals",
                    "action": "Search for community health centers in your area"
                }
            ]
        }
    
    return {
        "pathway": pathway,
        "guidance": guidance
    }

