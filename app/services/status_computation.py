"""
Patient status computation service

Computes patient transplant status from questionnaire answers
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.models.schemas import PatientStatus, Contraindication
from app.core import database


def load_questions() -> List[Dict[str, Any]]:
    """
    Load questions from JSON file
    
    Returns list of question dictionaries with id, category, question, description
    """
    questions_path = Path("data/questions.json")
    questions_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(questions_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Failed to load questions: {e}")


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
    
    # Stage 1: Identification & Awareness - Patient exists but no questionnaire
    if not has_questionnaire:
        return 'identification'
    
    # Get patient referral status
    has_referral = None
    if patient:
        has_referral = patient.get('has_referral')
    
    # Stage 2: Referral - Patient does not have a referral yet
    # If has_referral is False, they're in referral stage (need to get referred)
    if has_referral is False:
        return 'referral'
    
    # Stage 2: Referral - Questionnaire completed but no checklist yet
    if has_questionnaire and not checklist:
        return 'referral'
    
    # Stage 3: Evaluation - Checklist exists and has incomplete items
    # Only reach evaluation if they have a referral (has_referral is True or None/not set)
    if checklist:
        items = checklist.get('items', [])
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

