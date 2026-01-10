"""
Checklist initialization service

Creates default pre-transplant checklist for new patients
"""
from datetime import datetime
from app.models.schemas import TransplantChecklist, ChecklistItem


def create_default_checklist(patient_id: str) -> TransplantChecklist:
    """
    Create default pre-transplant checklist for a patient
    
    Args:
        patient_id: Patient ID to associate checklist with
    
    Returns:
        TransplantChecklist with default items, starting at first item
    """
    default_items = [
        ChecklistItem(
            id='physical_exam',
            title='Complete Physical Examination',
            description='Comprehensive medical evaluation by transplant team',
            is_complete=False,
            order=1,
        ),
        ChecklistItem(
            id='lab_work',
            title='Laboratory Work & Viral Serology',
            description='Hepatitis profile, HIV, CMV, tissue typing, viral panel (repeated annually while waitlisted)',
            is_complete=False,
            order=2,
        ),
        ChecklistItem(
            id='cardiac_eval',
            title='Cardiac Evaluation',
            description='12-lead ECG for all candidates, stress testing especially for diabetics and those over 50',
            is_complete=False,
            order=3,
        ),
        ChecklistItem(
            id='cancer_screening',
            title='Cancer Screening',
            description='Colonoscopy for age over 50, PSA for men over 45, age-appropriate screenings',
            is_complete=False,
            order=4,
        ),
        ChecklistItem(
            id='pulmonary_tests',
            title='Pulmonary Function Tests',
            description='Lung capacity and respiratory evaluation',
            is_complete=False,
            order=5,
        ),
        ChecklistItem(
            id='psychosocial_eval',
            title='Psychosocial Evaluation',
            description='Assessment by social worker and transplant coordinator covering adherence potential, social support, financial clearance',
            is_complete=False,
            order=6,
        ),
    ]
    
    checklist = TransplantChecklist(
        patient_id=patient_id,
        items=default_items,
    )
    
    return checklist

