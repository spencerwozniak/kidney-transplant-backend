"""
Transplant Access Navigator endpoints

Handles transplant center discovery and referral orchestration
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import json
import math
from pathlib import Path

from app.database import storage as database
from app.database.schemas import PatientReferralState

router = APIRouter()


def load_transplant_centers() -> List[Dict[str, Any]]:
    """Load transplant centers from JSON file"""
    centers_path = Path("data/transplant_centers.json")
    centers_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(centers_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
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
    insurance_type: Optional[str] = None
):
    """
    Find nearby transplant centers
    
    Filters by location, state acceptance, and insurance compatibility
    """
    centers = load_transplant_centers()
    patient = database.get_patient()
    
    # Get patient location
    patient_state = state
    patient_lat = lat
    patient_lng = lng
    
    if not patient_state and patient:
        # Try to get from patient referral state
        referral_state = database.get_patient_referral_state()
        if referral_state:
            patient_state = referral_state.get('location', {}).get('state')
            patient_lat = referral_state.get('location', {}).get('lat')
            patient_lng = referral_state.get('location', {}).get('lng')
    
    if not patient_state:
        raise HTTPException(status_code=400, detail="State or location required")
    
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
        
        # Check insurance compatibility
        insurance_compatible = True
        if insurance_type:
            if insurance_type == 'medicare':
                insurance_compatible = center.get('insurance_notes', {}).get('medicare', False)
            elif insurance_type == 'medicaid':
                medicaid_states = center.get('insurance_notes', {}).get('medicaid_states', [])
                insurance_compatible = patient_state in medicaid_states
        
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
    
    # Sort by distance if available
    results.sort(key=lambda x: x['distance_miles'] if x['distance_miles'] is not None else float('inf'))
    
    return results


@router.get("/referral-state")
async def get_referral_state():
    """Get patient referral state"""
    state = database.get_patient_referral_state()
    if not state:
        # Create default state from patient data
        patient = database.get_patient()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Initialize with patient's has_referral status
        default_state = {
            "patient_id": patient['id'],
            "location": {
                "zip": None,
                "state": None
            },
            "has_referral": patient.get('has_referral', False),
            "referral_source": None,
            "last_nephrologist": None,
            "dialysis_center": None,
            "preferred_centers": [],
            "referral_status": "not_started"
        }
        database.save_patient_referral_state(default_state)
        return default_state
    
    return state


@router.post("/referral-state")
async def update_referral_state(state: Dict[str, Any]):
    """Update patient referral state"""
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Ensure patient_id matches
    state['patient_id'] = patient['id']
    
    # Save state
    database.save_patient_referral_state(state)
    
    # Update patient's has_referral if provided
    if 'has_referral' in state:
        patient['has_referral'] = state['has_referral']
        database.save_patient(patient)
    
    return state


@router.get("/referral-pathway")
async def get_referral_pathway():
    """
    Determine referral pathway based on patient state
    
    Returns pathway type and guidance
    """
    patient = database.get_patient()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    referral_state = database.get_patient_referral_state()
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

