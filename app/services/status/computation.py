"""
Patient status computation service

Computes patient transplant status from questionnaire answers
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from app.database.schemas import PatientStatus, Contraindication
from app.database import storage as database


def load_questions() -> List[Dict[str, Any]]:
    """
    Load questions from JSON file
    
    Returns list of question dictionaries with id, category, question, description
    If file doesn't exist or is invalid, returns empty list (demo-safe fallback)
    """
    questions_path = Path("data/questions.json")
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(questions_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"WARNING: Failed to load questions.json: {e}. Returning empty list (demo-safe fallback).")
        return []


def determine_pathway_stage(
    has_questionnaire: bool, 
    checklist: Optional[Dict[str, Any]] = None,
    patient: Optional[Dict[str, Any]] = None
) -> str:
    """
    Determine the current pathway stage based on patient data
    
    Args:
        has_questionnaire: Whether patient has completed questionnaire
        checklist: Optional checklist data dictionary
        patient: Optional patient data dictionary (to check has_ckd_esrd and has_referral)
    
    Returns:
        Pathway stage string: 'identification', 'referral', 'evaluation', 'selection', 'transplantation', 'post-transplant'
    """
    # Stage 1: Identification & Awareness - Patient does not have CKD/ESRD
    # If patient doesn't have CKD or ESRD, they're still in identification/awareness stage
    if patient:
        has_ckd_esrd = patient.get('has_ckd_esrd')
        if has_ckd_esrd is False:
            return 'identification'
    
    # Get patient referral status
    has_referral = None
    if patient:
        has_referral = patient.get('has_referral')
    
    # Stage 3: Evaluation - Patient has referral but no questionnaire yet
    # If has_referral is True and no questionnaire, they're in evaluation stage
    # (they have a referral, so they can start the evaluation process)
    if not has_questionnaire and has_referral is True:
        return 'evaluation'
    
    # Stage 1: Identification & Awareness - Patient exists but no questionnaire and no referral
    if not has_questionnaire:
        return 'identification'
    
    # Stage 2: Referral - Patient does not have a referral yet
    # Only advance past referral stage if has_referral is explicitly True
    # If has_referral is False or None, they're in referral stage (need to get referred)
    if has_referral is not True:
        return 'referral'
    
    # Stage 2: Referral - Questionnaire completed but no checklist yet
    if has_questionnaire and not checklist:
        return 'referral'
    
    # Stage 3: Evaluation - Checklist exists and has incomplete items
    # Only reach evaluation if they have a referral (has_referral is explicitly True)
    if checklist:
        items = checklist.get('items', [])
        items = items or []  # Guard against None
        if not items:
            return 'referral'
        
        completed_items = sum(1 for item in items if item.get('is_complete', False))
        total_items = len(items)
        completion_percentage = completed_items / total_items if total_items > 0 else 0
        
        # If less than 80% complete, still in evaluation
        if completion_percentage < 0.8:
            return 'evaluation'
        
        # Stage 4: Selection & Waitlisting - Most checklist items complete
        # (In a real system, this would be determined by actual waitlist status)
        if completion_percentage >= 0.8:
            return 'selection'
    
    # Default to referral if we have questionnaire
    return 'referral'


def compute_patient_status(answers: Dict[str, str], patient_id: str) -> PatientStatus:
    """
    Compute patient status from questionnaire answers
    
    Args:
        answers: Dictionary mapping question_id to 'yes' or 'no'
        patient_id: Patient ID this status is associated with
    
    Returns:
        PatientStatus object with computed contraindications and pathway stage
    """
    questions = load_questions()
    
    # Find absolute contraindications (category='absolute' and answer='yes')
    absolute_contraindications = []
    for question in questions:
        if question.get('category') == 'absolute' and answers.get(question['id']) == 'yes':
            absolute_contraindications.append(
                Contraindication(
                    id=question['id'],
                    question=question['question']
                )
            )
    
    # Find relative contraindications (category='relative' and answer='yes')
    relative_contraindications = []
    for question in questions:
        if question.get('category') == 'relative' and answers.get(question['id']) == 'yes':
            relative_contraindications.append(
                Contraindication(
                    id=question['id'],
                    question=question['question']
                )
            )
    
    # Determine pathway stage
    # Questionnaire exists (we're computing status from it), so has_questionnaire = True
    checklist = database.get_checklist()
    patient = database.get_patient()
    pathway_stage = determine_pathway_stage(has_questionnaire=True, checklist=checklist, patient=patient)
    
    # Create status
    status = PatientStatus(
        patient_id=patient_id,
        has_absolute=len(absolute_contraindications) > 0,
        has_relative=len(relative_contraindications) > 0,
        absolute_contraindications=absolute_contraindications,
        relative_contraindications=relative_contraindications,
        pathway_stage=pathway_stage,
    )
    
    return status

def compute_patient_status_from_all_questionnaires(patient_id: str) -> PatientStatus:
    """
    Compute patient status by rolling up all questionnaires for a patient
    
    If no questionnaires exist, returns an initial status based on patient data.
    
    Args:
        patient_id: Patient ID to compute status for
    
    Returns:
        PatientStatus object with computed contraindications across all questionnaires
        - Deduplicates contraindications by question_id
        - has_absolute = True if any absolute contraindication found across all questionnaires
        - has_relative = True if any relative contraindication found across all questionnaires
        - If no questionnaires exist, returns initial status with no contraindications
    """
    # Get all questionnaires for this patient
    questionnaires = database.get_all_questionnaires_for_patient(patient_id)
    
    if not questionnaires:
        # No questionnaires - return initial status based on patient data
        return create_initial_status(patient_id)
    
    questions = load_questions()
    
    # Sort questionnaires by submitted_at descending (most recent first)
    # Questionnaires without submitted_at are treated as oldest (sorted last)
    def get_sort_key(q: Dict[str, Any]) -> str:
        submitted_at = q.get('submitted_at')
        if submitted_at is None:
            return '0000-00-00T00:00:00'  # Oldest if missing
        if isinstance(submitted_at, str):
            return submitted_at
        # If it's a datetime object, convert to ISO string
        if hasattr(submitted_at, 'isoformat'):
            return submitted_at.isoformat()
        return str(submitted_at)
    
    questionnaires_sorted = sorted(questionnaires, key=get_sort_key, reverse=True)
    
    # Build latest_answers dict: process questionnaires from newest to oldest
    # Latest answer wins (overwrites earlier answers)
    latest_answers = {}  # question_id -> answer
    for questionnaire in questionnaires_sorted:
        answers = questionnaire.get('answers', {})
        for question_id, answer in answers.items():
            # Only set if not already set (newest wins)
            if question_id not in latest_answers:
                latest_answers[question_id] = answer
    
    # Collect contraindications from latest answers only
    absolute_contraindications_dict = {}  # question_id -> Contraindication
    relative_contraindications_dict = {}  # question_id -> Contraindication
    
    # Only process contraindications if questions list is not empty
    if questions:
        # Build a map of question_id -> question dict for quick lookup
        question_map = {q['id']: q for q in questions}
        
        # Process latest answers (only 'yes' answers create contraindications)
        for question_id, answer in latest_answers.items():
            if answer == 'yes':
                question_info = question_map.get(question_id)
                if question_info:
                    category = question_info.get('category')
                    
                    if category == 'absolute':
                        absolute_contraindications_dict[question_id] = Contraindication(
                            id=question_id,
                            question=question_info['question']
                        )
                    elif category == 'relative':
                        relative_contraindications_dict[question_id] = Contraindication(
                            id=question_id,
                            question=question_info['question']
                        )
    
    # Convert dictionaries to lists
    absolute_contraindications = list(absolute_contraindications_dict.values())
    relative_contraindications = list(relative_contraindications_dict.values())
    
    # Determine pathway stage
    # Questionnaires exist, so has_questionnaire = True
    checklist = database.get_checklist()
    patient = database.get_patient()
    pathway_stage = determine_pathway_stage(has_questionnaire=True, checklist=checklist, patient=patient)
    
    # Create status
    status = PatientStatus(
        patient_id=patient_id,
        has_absolute=len(absolute_contraindications) > 0,
        has_relative=len(relative_contraindications) > 0,
        absolute_contraindications=absolute_contraindications,
        relative_contraindications=relative_contraindications,
        pathway_stage=pathway_stage,
    )
    
    return status


def create_initial_status(patient_id: str) -> PatientStatus:
    """
    Create initial patient status when no questionnaire exists yet
    
    This is used after patient onboarding to set an initial pathway stage
    based on patient data (e.g., has_referral status)
    
    Args:
        patient_id: Patient ID this status is associated with
    
    Returns:
        PatientStatus object with initial pathway stage (no contraindications yet)
    """
    # Get patient data to determine initial stage
    patient = database.get_patient()
    checklist = database.get_checklist()
    
    # Determine pathway stage (no questionnaire yet)
    pathway_stage = determine_pathway_stage(has_questionnaire=False, checklist=checklist, patient=patient)
    
    # Create initial status with no contraindications
    status = PatientStatus(
        patient_id=patient_id,
        has_absolute=False,
        has_relative=False,
        absolute_contraindications=[],
        relative_contraindications=[],
        pathway_stage=pathway_stage,
    )
    
    return status


def recompute_pathway_stage(status: PatientStatus) -> PatientStatus:
    """
    Recompute pathway stage for an existing status
    
    This is useful when checklist changes and we need to update the pathway stage
    
    Args:
        status: Existing PatientStatus object
    
    Returns:
        PatientStatus with updated pathway_stage
    """
    # Check if questionnaire exists (status exists means questionnaire was completed)
    has_questionnaire = True  # If status exists, questionnaire was completed
    
    # Get current checklist and patient data
    checklist = database.get_checklist()
    patient = database.get_patient()
    
    # Determine pathway stage
    pathway_stage = determine_pathway_stage(has_questionnaire=has_questionnaire, checklist=checklist, patient=patient)
    
    # Update status with new pathway stage
    status.pathway_stage = pathway_stage
    
    return status

