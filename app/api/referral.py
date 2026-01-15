"""
Transplant Access Navigator endpoints

Handles transplant center discovery and referral orchestration
"""
from fastapi import APIRouter, HTTPException, Request
from typing import List, Dict, Any, Optional
import json
import math
from pathlib import Path
import httpx

from app.database import storage as database
from app.database.schemas import PatientReferralState, PatientStatus
from app.api.utils import get_device_id
from app.services.status.computation import recompute_pathway_stage
from app.services.utils import convert_datetime_to_iso

router = APIRouter()

# Cache for transplant centers (loaded once, reused across requests)
_transplant_centers_cache: Optional[List[Dict[str, Any]]] = None


async def zip_to_coordinates(zip_code: str) -> Optional[Dict[str, Any]]:
    """
    Convert zip code to latitude and longitude coordinates using zippopotam.us API
    
    Uses the free zippopotam.us API to get coordinates for any US zip code.
    API documentation: https://zippopotam.us/
    
    Args:
        zip_code: 5-digit US zip code
    
    Returns:
        Dict with 'lat', 'lng', and 'state' keys, or None if not found/error
    """
    if not zip_code or len(zip_code) != 5 or not zip_code.isdigit():
        return None
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"https://api.zippopotam.us/us/{zip_code}")
            
            if response.status_code == 200:
                data = response.json()
                places = data.get('places', [])
                if places and len(places) > 0:
                    place = places[0]  # Use first place if multiple
                    return {
                        'lat': float(place.get('latitude')),
                        'lng': float(place.get('longitude')),
                        'state': place.get('state abbreviation'),
                        'city': place.get('place name')
                    }
            elif response.status_code == 404:
                # Zip code not found
                return None
            else:
                # Other error
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Zippopotam API returned status {response.status_code} for zip {zip_code}")
                return None
    except httpx.TimeoutException:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Timeout calling zippopotam API for zip {zip_code}")
        return None
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error calling zippopotam API for zip {zip_code}: {str(e)}")
        return None


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
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_miles: Optional[int] = None,
    limit: Optional[int] = None,
    request: Request = ...,
):
    """
    Find nearby transplant centers sorted by distance
    
    Converts zip code to coordinates and calculates distance to all centers.
    Returns all centers sorted by closest distance first.
    
    Query Parameters:
    - zip_code (optional): 5-digit US zip code. Will be converted to lat/lng for distance calculation.
    - lat/lng (optional): Latitude/longitude for distance calculation. Takes precedence over zip_code.
    - radius_miles (optional): Maximum distance in miles (default: no limit)
    - limit (optional): Maximum number of results (default: no limit)
    
    Examples:
    - GET /api/v1/centers/nearby?zip_code=29601
    - GET /api/v1/centers/nearby?lat=32.8801&lng=-117.234&radius_miles=50
    - GET /api/v1/centers/nearby?zip_code=29601&limit=10
    """
    centers = load_transplant_centers()
    
    # Clean and validate zip_code if provided
    if zip_code:
        zip_code = zip_code.strip()
        # Extract first 5 digits if longer (e.g., "29601-1234" -> "29601")
        if len(zip_code) > 5:
            zip_code = zip_code[:5]
    
    # Get coordinates - prioritize explicit lat/lng, otherwise convert from zip_code
    patient_lat = lat
    patient_lng = lng
    
    if not patient_lat or not patient_lng:
        if zip_code:
            coords = await zip_to_coordinates(zip_code)
            if coords:
                patient_lat = coords['lat']
                patient_lng = coords['lng']
    
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Finding centers for zip_code={zip_code}, lat={patient_lat}, lng={patient_lng}, centers_count={len(centers)}")
    
    # Collect all centers with distance calculations
    results = []
    
    for center in centers:
        center_lat = center['location']['lat']
        center_lng = center['location']['lng']
        
        # Calculate distance if we have patient coordinates
        distance_miles = None
        if patient_lat and patient_lng:
            distance_miles = round(haversine_distance(patient_lat, patient_lng, center_lat, center_lng), 1)
            
            # Filter by radius if specified
            if radius_miles is not None and distance_miles > radius_miles:
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
            "insurance_compatible": True,  # Always true since we removed insurance filtering
        })
    
    # Sort by distance (closest first), centers without distance go to the end
    results.sort(key=lambda x: x['distance_miles'] if x['distance_miles'] is not None else float('inf'))
    
    # Apply limit if specified
    if limit is not None and limit > 0:
        results = results[:limit]
    
    logger.info(f"Returning {len(results)} centers")
    
    return results


@router.get("/referral-state")
async def get_referral_state(request: Request):
    """
    Get patient referral state
    
    Returns location with zip, city, and state fields.
    City and state should be provided by frontend.
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
    
    state['location'] = location
    return state


@router.post("/referral-state")
async def update_referral_state(state: Dict[str, Any], request: Request):
    """
    Update patient referral state
    
    Accepts location with zip, city, and state fields.
    Frontend should provide city/state directly.
    """
    device_id = get_device_id(request)
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Ensure patient_id matches
    state['patient_id'] = patient['id']
    
    # Ensure location has city and state fields
    location = state.get('location', {})
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

