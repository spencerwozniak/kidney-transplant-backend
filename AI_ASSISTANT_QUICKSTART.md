# AI Assistant Quick Start Guide

## Overview

The AI Assistant integration allows patients to ask questions about their transplant journey and receive personalized responses based on their stored data.

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install the `openai` package along with other dependencies.

### 2. Configure API Key

Set your OpenAI API key as an environment variable:

**Linux/Mac:**
```bash
export OPENAI_API_KEY="your-api-key-here"
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

**Windows (Command Prompt):**
```cmd
set OPENAI_API_KEY=your-api-key-here
```

**For Development (Optional):**
Create a `.env` file in the project root (not tracked in git):
```
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-3.5-turbo  # Optional: specify model
```

### 3. Start the Server

```bash
python run.py
```

## API Endpoints

### Query the AI Assistant

**POST** `/api/v1/ai-assistant/query`

Send a patient question and get a personalized response.

**Request Body:**
```json
{
  "query": "Where am I in my transplant journey?",
  "provider": "openai",  // Optional, defaults to "openai"
  "model": "gpt-3.5-turbo"  // Optional, defaults to "gpt-3.5-turbo"
}
```

**Response:**
```json
{
  "response": "You're currently in the EVALUATION stage of your transplant journey...",
  "context_summary": {
    "pathway_stage": "evaluation",
    "checklist_completion": 42.5,
    "has_referral": true
  }
}
```

**Example Queries:**
- "Where am I in my transplant journey?"
- "What do I need to do next?"
- "What items are still incomplete on my checklist?"
- "What are my contraindications?"
- "How do I get a referral?"
- "What is a kidney transplant evaluation?"

### Check AI Status

**GET** `/api/v1/ai-assistant/status`

Check if AI assistant is configured and enabled.

**Response:**
```json
{
  "enabled": true,
  "provider": "openai",
  "message": "AI assistant is configured and ready"
}
```

### Get Patient Context (Debug)

**GET** `/api/v1/ai-assistant/context`

Get the patient context that would be used for AI prompts. Useful for debugging.

**Response:**
```json
{
  "patient_id": "uuid-here",
  "context": {
    "patient_summary": {...},
    "pathway_stage": "evaluation",
    "status_summary": {...},
    "checklist_progress": {...},
    "recent_activity": {...},
    "referral_information": {...}
  }
}
```

## How It Works

1. **Data Aggregation**: The system collects all relevant patient data:
   - Patient demographics and medical info
   - Current pathway stage
   - Checklist progress
   - Contraindications
   - Referral status
   - Recent activity

2. **Prompt Construction**: The data is formatted into a structured context and combined with:
   - System prompt defining the AI's role and constraints
   - User's question
   - Patient context

3. **LLM Call**: The prompt is sent to OpenAI (or other provider) which generates a personalized response

4. **Response**: The AI's response is returned to the patient

## Example Usage

### Using curl

```bash
# Check if AI is enabled
curl http://localhost:8000/api/v1/ai-assistant/status

# Ask a question
curl -X POST http://localhost:8000/api/v1/ai-assistant/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What do I need to do next?"
  }'
```

### Using Python

```python
import requests

# Query the AI assistant
response = requests.post(
    "http://localhost:8000/api/v1/ai-assistant/query",
    json={
        "query": "Where am I in my transplant journey?"
    }
)

data = response.json()
print(data["response"])
```

## Data Privacy & Safety

- **No Medical Advice**: The AI is explicitly instructed NOT to provide medical advice
- **Data Usage**: Patient data is sent to OpenAI API - ensure you comply with HIPAA/privacy regulations
- **API Key Security**: Never commit API keys to version control
- **Error Handling**: The system gracefully handles API failures

## Cost Considerations

- OpenAI charges per token (input + output)
- GPT-3.5-turbo is more cost-effective than GPT-4
- Typical query: ~500-1000 tokens per request
- Monitor usage in OpenAI dashboard

## Troubleshooting

### "AI assistant is not configured"

- Ensure `OPENAI_API_KEY` environment variable is set
- Restart the server after setting the variable
- Check `/api/v1/ai-assistant/status` endpoint

### "OpenAI API error"

- Verify API key is valid
- Check OpenAI account has credits/quota
- Ensure internet connection is available
- Check OpenAI status page for outages

### Import errors

- Run `pip install -r requirements.txt` to install dependencies
- Ensure you're using Python 3.9+

## Next Steps

See `AI_ASSISTANT_DESIGN.md` for:
- Detailed architecture
- Future enhancements
- Customization options
- Multi-provider support

