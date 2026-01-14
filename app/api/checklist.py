"""
Checklist management endpoints
"""
from fastapi import APIRouter, HTTPException, Body, UploadFile, File, Request
from fastapi.responses import FileResponse
import uuid
from datetime import datetime
from pathlib import Path
import shutil
import urllib.parse

from app.database.schemas import TransplantChecklist, PatientStatus
from app.database import storage as database
from app.services.checklist.initialization import create_default_checklist
from app.services.utils import convert_checklist_datetimes, convert_datetime_to_iso
from app.services.status.computation import recompute_pathway_stage
from app.api.utils import get_device_id
from app.services.ai.image_detection import process_image_file, process_scanned_pdf_with_openai

router = APIRouter()


def is_scanned_pdf(path: str, min_chars: int = 10) -> bool:
    """
    Determine if a PDF is scanned (image-based) or text-based
    
    Args:
        path: Path to the PDF file
        min_chars: Minimum number of characters to consider it text-based
    
    Returns:
        True if scanned PDF, False if text-based PDF
    """
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text and len(text.strip()) >= min_chars:
                    return False  # text-based PDF
        return True  # scanned PDF
    except Exception:
        # If pdfplumber fails or file is invalid, treat as scanned
        return True


def pdf_to_string(path: str) -> str:
    """
    Extract text from a text-based PDF
    
    Args:
        path: Path to the PDF file
    
    Returns:
        Extracted text as a string
    """
    try:
        import pdfplumber
        text = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
        return "\n".join(text)
    except Exception:
        return "Uploaded document does not contain text"




@router.get("/checklist", response_model=TransplantChecklist)
async def get_checklist(request: Request):
    """
    Get checklist for device's patient
    
    Uses cached checklist if available. If no checklist exists, creates default one for current patient.
    Optimized to avoid repeated patient file reads.
    """
    device_id = get_device_id(request)
    
    # Check cache first (fast path)
    checklist = database.get_checklist(device_id)
    if checklist:
        return checklist
    
    # Checklist doesn't exist - create default one
    # Get patient (uses cache, so no extra file read if patient was already loaded)
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="No patient found")
    
    # Create default checklist
    new_checklist = create_default_checklist(patient.get('id'))
    new_checklist.id = str(uuid.uuid4())
    
    # Prepare checklist data for storage
    checklist_data = convert_checklist_datetimes(new_checklist.model_dump())
    
    # Save checklist (this also updates the cache)
    database.save_checklist(checklist_data, device_id)
    
    return new_checklist


@router.post("/checklist", response_model=TransplantChecklist)
async def create_or_update_checklist(checklist: TransplantChecklist, request: Request):
    """
    Create or update checklist
    
    Generates UUID if needed, saves directly
    """
    device_id = get_device_id(request)
    # Verify patient exists
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Verify patient_id matches current patient
    if checklist.patient_id != patient.get('id'):
        raise HTTPException(status_code=400, detail="Patient ID does not match current patient")
    
    # Generate ID if not provided
    if not checklist.id:
        checklist.id = str(uuid.uuid4())
    
    # Prepare data for storage
    data = convert_checklist_datetimes(checklist.model_dump())
    
    # Save to database
    database.save_checklist(data, device_id)
    
    # Return the checklist with generated ID
    return checklist


@router.patch("/checklist/items/{item_id}", response_model=TransplantChecklist)
async def update_checklist_item(
    item_id: str,
    update_data: dict = Body(...),
    request: Request = ...,
):
    """
    Update a specific checklist item
    
    Updates is_complete, completed_at, and/or notes for a checklist item
    """
    device_id = get_device_id(request)
    # Verify patient exists
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get current checklist
    checklist_data = database.get_checklist(device_id)
    if not checklist_data:
        raise HTTPException(status_code=404, detail="No checklist found")
    
    # Find the item to update
    item_found = False
    for item in checklist_data.get('items', []):
        if item.get('id') == item_id:
            item_found = True
            # Update fields if provided
            if 'is_complete' in update_data:
                item['is_complete'] = update_data['is_complete']
                # If marking as incomplete, clear completed_at
                if update_data['is_complete'] is False:
                    item['completed_at'] = None
            if 'completed_at' in update_data:
                item['completed_at'] = update_data['completed_at']
            if 'notes' in update_data:
                item['notes'] = update_data['notes'] if update_data['notes'] else None
            if 'documents' in update_data:
                item['documents'] = update_data['documents']
            break
    
    if not item_found:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    
    # Update checklist updated_at timestamp
    checklist_data['updated_at'] = datetime.now().isoformat()
    
    # Save updated checklist
    database.save_checklist(checklist_data, device_id)
    
    # Recompute pathway stage if patient status exists
    status_data = database.get_patient_status(device_id)
    if status_data:
        status = PatientStatus(**status_data)
        status = recompute_pathway_stage(status, device_id)
        status_data_updated = convert_datetime_to_iso(status.model_dump(), ['updated_at'])
        database.save_patient_status(status_data_updated, device_id)
    
    # Return updated checklist
    return checklist_data


@router.post("/checklist/items/{item_id}/documents", response_model=TransplantChecklist)
async def upload_checklist_item_document(
    item_id: str,
    file: UploadFile = File(...),
    request: Request = ...,
):
    """
    Upload a document for a checklist item
    
    Accepts PDF or image files, saves to data/documents directory,
    and appends the file path to the checklist item's documents array
    """
    device_id = get_device_id(request)
    # Verify patient exists
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get current checklist
    checklist_data = database.get_checklist(device_id)
    if not checklist_data:
        raise HTTPException(status_code=404, detail="No checklist found")
    
    # Find the item
    item_found = False
    item = None
    for checklist_item in checklist_data.get('items', []):
        if checklist_item.get('id') == item_id:
            item_found = True
            item = checklist_item
            break
    
    if not item_found:
        raise HTTPException(status_code=404, detail="Checklist item not found")
    
    # Validate file type
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    file_extension = Path(file.filename).suffix.lower() if file.filename else ''
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: PDF, JPG, JPEG, PNG, GIF, BMP, WEBP"
        )
    
    # Create documents directory structure: data/documents/{patient_id}/{item_id}/
    patient_id = patient.get('id')
    documents_base = Path("data/documents")
    patient_dir = documents_base / patient_id
    item_dir = patient_dir / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename to avoid conflicts
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = item_dir / safe_filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Extract text from PDF or images using OpenAI Vision API
    text_file_path = file_path.with_name(file_path.name + '.txt')
    try:
        if file_extension == '.pdf':
            # Check if PDF is text-based or scanned
            if is_scanned_pdf(str(file_path)):
                # Scanned PDF - use OpenAI Vision API to extract text
                extracted_text = process_scanned_pdf_with_openai(str(file_path))
                with open(text_file_path, "w", encoding="utf-8") as text_file:
                    text_file.write(extracted_text)
            else:
                # Text-based PDF - extract text directly
                extracted_text = pdf_to_string(str(file_path))
                with open(text_file_path, "w", encoding="utf-8") as text_file:
                    text_file.write(extracted_text)
        else:
            # Image file - use OpenAI Vision API to extract text or generate description
            extracted_text = process_image_file(str(file_path))
            with open(text_file_path, "w", encoding="utf-8") as text_file:
                text_file.write(extracted_text)
    except Exception as e:
        # If text extraction fails, save error message or placeholder
        try:
            error_message = f"Failed to extract text: {str(e)}"
            with open(text_file_path, "w", encoding="utf-8") as text_file:
                text_file.write(error_message)
        except Exception:
            # If even error message fails, continue without text file
            pass
    
    # Create relative path for storage (relative to data/documents)
    relative_path = f"documents/{patient_id}/{item_id}/{safe_filename}"
    
    # Initialize documents array if it doesn't exist
    if 'documents' not in item:
        item['documents'] = []
    
    # Append the new document path
    item['documents'].append(relative_path)
    
    # Update checklist updated_at timestamp
    checklist_data['updated_at'] = datetime.now().isoformat()
    
    # Save updated checklist
    database.save_checklist(checklist_data, device_id)
    
    # Recompute pathway stage if patient status exists
    status_data = database.get_patient_status(device_id)
    if status_data:
        status = PatientStatus(**status_data)
        status = recompute_pathway_stage(status, device_id)
        status_data_updated = convert_datetime_to_iso(status.model_dump(), ['updated_at'])
        database.save_patient_status(status_data_updated, device_id)
    
    # Return updated checklist
    return checklist_data


@router.get("/documents/{file_path:path}")
async def get_document(file_path: str, request: Request):
    """
    Retrieve a document file
    
    Serves documents from the data/documents directory
    File path should be URL-encoded (e.g., documents/patient_id/item_id/filename.pdf)
    """
    device_id = get_device_id(request)
    # Verify patient exists
    patient = database.get_patient(device_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Decode the file path
    try:
        decoded_path = urllib.parse.unquote(file_path)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path encoding")
    
    # Construct full file path
    # File path format: documents/{patient_id}/{item_id}/{filename}
    full_path = Path("data") / decoded_path
    
    # Security check: ensure the path is within data/documents
    if not str(full_path.resolve()).startswith(str(Path("data/documents").resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Determine media type based on file extension
    file_extension = full_path.suffix.lower()
    media_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
    }
    media_type = media_types.get(file_extension, 'application/octet-stream')
    
    # Return the file
    return FileResponse(
        path=str(full_path),
        media_type=media_type,
        filename=full_path.name
    )

