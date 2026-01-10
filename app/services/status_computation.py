"""
Patient status computation service

Computes patient transplant status from questionnaire answers
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.models.schemas import PatientStatus, Contraindication


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


def compute_patient_status(answers: Dict[str, str], patient_id: str) -> PatientStatus:
    """
    Compute patient status from questionnaire answers
    
    Args:
        answers: Dictionary mapping question_id to 'yes' or 'no'
        patient_id: Patient ID this status is associated with
    
    Returns:
        PatientStatus object with computed contraindications
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
    
    # Create status
    status = PatientStatus(
        patient_id=patient_id,
        has_absolute=len(absolute_contraindications) > 0,
        has_relative=len(relative_contraindications) > 0,
        absolute_contraindications=absolute_contraindications,
        relative_contraindications=relative_contraindications,
    )
    
    return status

