"""
Image Detection and Text Extraction using OpenAI Vision API

Processes images and scanned PDFs to extract text or generate descriptions
using OpenAI's vision capabilities.
"""
import base64
from pathlib import Path


def encode_image_to_base64(image_path: str) -> str:
    """
    Encode an image file to base64 string
    
    Args:
        image_path: Path to the image file
    
    Returns:
        Base64 encoded string of the image
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def process_image_with_openai(image_path: str, extract_text: bool = True) -> str:
    """
    Process an image using OpenAI Vision API to extract text or generate description
    
    Args:
        image_path: Path to the image file
        extract_text: If True, focus on text extraction. If False, generate general description
    
    Returns:
        Extracted text or description
    """
    try:
        from app.services.ai.config import get_openai_client
        
        client = get_openai_client()
        
        # Encode image to base64
        base64_image = encode_image_to_base64(image_path)
        
        # Determine the prompt based on whether we want text extraction or description
        if extract_text:
            prompt = """Extract all text from this image. Include all visible text exactly as it appears, maintaining structure and formatting where possible. If the image contains no text, respond with "No text found in image"."""
        else:
            prompt = """Provide a clear, factual description of what is shown in this image. Describe the content objectively without interpretation or medical analysis. Focus on visible elements, layout, and structure."""
        
        # Use OpenAI Vision API
        # Try custom API structure first (as shown in example), then fallback to standard API
        try:
            # Try custom API structure with base64 image
            # Note: If file_id is required, we may need to upload file first
            try:
                response = client.responses.create(
                    model="gpt-5.1",
                    input=[{
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "image": base64_image,
                                "format": "base64"
                            },
                        ],
                    }],
                )
                return response.output_text.strip()
            except (AttributeError, TypeError, Exception) as e:
                # If custom API doesn't work, try uploading file first to get file_id
                # Upload image file to OpenAI
                with open(image_path, "rb") as image_file:
                    uploaded_file = client.files.create(
                        file=image_file,
                        purpose="vision"
                    )
                    file_id = uploaded_file.id
                
                # Use file_id in custom API
                response = client.responses.create(
                    model="gpt-5.1",
                    input=[{
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {
                                "type": "input_image",
                                "file_id": file_id,
                            },
                        ],
                    }],
                )
                result = response.output_text.strip()
                
                # Clean up uploaded file
                try:
                    client.files.delete(file_id)
                except:
                    pass
                
                return result
        except Exception:
            # Fallback to standard OpenAI Vision API format
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content.strip()
            
    except ImportError:
        return "Image processing unavailable (OpenAI client not configured)"
    except Exception as e:
        return f"Failed to process image: {str(e)}"


def process_scanned_pdf_with_openai(pdf_path: str) -> str:
    """
    Process a scanned PDF by converting pages to images and using OpenAI Vision API
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        Extracted text from all pages combined
    """
    try:
        from pdf2image import convert_from_path
        
        # Convert PDF pages to images
        images = convert_from_path(pdf_path)
        
        if not images:
            return "Failed to convert PDF to images"
        
        # Process each page
        all_text = []
        for i, img in enumerate(images):
            # Save image temporarily to process it
            temp_image_path = Path(pdf_path).parent / f"temp_page_{i}.png"
            try:
                img.save(temp_image_path, "PNG")
                
                # Process with OpenAI
                page_text = process_image_with_openai(str(temp_image_path), extract_text=True)
                if page_text and page_text != "No text found in image":
                    all_text.append(f"--- Page {i + 1} ---\n{page_text}")
            finally:
                # Clean up temporary file
                if temp_image_path.exists():
                    temp_image_path.unlink()
        
        if all_text:
            return "\n\n".join(all_text)
        else:
            return "No text found in scanned PDF"
            
    except ImportError:
        return "PDF processing unavailable (pdf2image not installed)"
    except Exception as e:
        return f"Failed to process scanned PDF: {str(e)}"


def has_meaningful_text(text_result: str) -> bool:
    """
    Determine if the extracted text result contains meaningful text content
    
    Args:
        text_result: The text extraction result from OpenAI
    
    Returns:
        True if meaningful text was found, False otherwise
    """
    if not text_result:
        return False
    
    # Check for explicit "no text" indicators
    no_text_indicators = [
        "No text found in image",
        "No text",
        "does not contain text",
        "no visible text",
        "no text content"
    ]
    
    text_lower = text_result.lower().strip()
    
    # If response explicitly says no text, return False
    for indicator in no_text_indicators:
        if indicator.lower() in text_lower:
            return False
    
    # Check if the result is meaningful (has substantial content)
    # Remove common prefixes/suffixes and check length
    cleaned_text = text_lower
    if cleaned_text.startswith("extracted text:"):
        cleaned_text = cleaned_text[15:].strip()
    if cleaned_text.startswith("text:"):
        cleaned_text = cleaned_text[5:].strip()
    
    # If after cleaning, we have less than 10 characters, it's probably not meaningful
    if len(cleaned_text) < 10:
        return False
    
    # If it's mostly whitespace or special characters, not meaningful
    alphanumeric_chars = sum(1 for c in cleaned_text if c.isalnum())
    if alphanumeric_chars < 5:
        return False
    
    return True


def process_image_file(image_path: str) -> str:
    """
    Process an image file - extract text if available, otherwise provide description
    
    The function determines if an image contains text by:
    1. Attempting text extraction with OpenAI Vision API
    2. Analyzing the response to check if meaningful text was found
    3. If no meaningful text, generating a general description instead
    
    Args:
        image_path: Path to the image file
    
    Returns:
        Extracted text or image description
    """
    try:
        # First, try to extract text
        text_result = process_image_with_openai(image_path, extract_text=True)
        
        # Check if meaningful text was actually found
        if has_meaningful_text(text_result):
            # Return the extracted text
            return text_result
        else:
            # No meaningful text found - provide a general description
            description = process_image_with_openai(image_path, extract_text=False)
            return f"Image Description: {description}"
            
    except Exception as e:
        return f"Failed to process image: {str(e)}"

