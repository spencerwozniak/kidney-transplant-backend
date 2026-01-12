# AI Assistant Integration Summary

## What Was Created

This integration adds an AI assistant capability to the kidney transplant backend that uses patient data to provide personalized responses about their transplant journey.

## Files Created

### 1. **Design Document** (`AI_ASSISTANT_DESIGN.md`)

- Comprehensive design overview
- Data sources and context assembly strategy
- Prompt construction approach
- Safety and compliance considerations
- Future enhancement roadmap

### 2. **Core Service** (`app/services/ai_assistant.py`)

- `build_patient_context()`: Aggregates all patient data into structured context
- `format_context_for_prompt()`: Formats context for LLM prompts
- `build_system_prompt()`: Creates system prompt with role and constraints
- `build_user_prompt()`: Combines user query with patient context
- `call_llm()`: Interfaces with LLM providers (OpenAI implemented)
- `get_ai_response()`: Main entry point for getting AI responses

### 3. **Configuration** (`app/core/ai_config.py`)

- `get_openai_api_key()`: Retrieves API key from environment
- `get_openai_client()`: Creates configured OpenAI client
- `get_default_model()`: Gets default model name
- `is_ai_enabled()`: Checks if AI is configured

### 4. **API Endpoints** (`app/api/ai_assistant.py`)

- `POST /api/v1/ai-assistant/query`: Query the AI assistant
- `GET /api/v1/ai-assistant/status`: Check AI configuration status
- `GET /api/v1/ai-assistant/context`: Get patient context (debug)

### 5. **Documentation** (`AI_ASSISTANT_QUICKSTART.md`)

- Setup instructions
- API usage examples
- Troubleshooting guide

### 6. **Updated Files**

- `app/api/__init__.py`: Added AI assistant router
- `requirements.txt`: Added `openai>=1.0.0` dependency

## How It Works

### Data Flow

1. **Patient Query** → User asks a question via API
2. **Data Aggregation** → System collects:
   - Patient demographics and medical info
   - Current pathway stage (identification, referral, evaluation, selection, etc.)
   - Checklist progress (completed/incomplete items)
   - Contraindications (absolute/relative)
   - Referral status and provider information
   - Recent activity (last completed items, questionnaire dates)
3. **Prompt Construction** → Data is formatted into:
   - System prompt (defines AI role and constraints)
   - User prompt (patient query + formatted context)
4. **LLM Call** → Prompt sent to OpenAI API
5. **Response** → AI-generated personalized response returned

### Example Context Structure

```json
{
  "pathway_stage": "evaluation",
  "status_summary": {
    "has_absolute_contraindications": false,
    "has_relative_contraindications": true,
    "relative_contraindications": [{ "question": "Do you currently smoke?" }]
  },
  "checklist_progress": {
    "total_items": 12,
    "completed_count": 5,
    "completion_percentage": 41.7,
    "incomplete_items": [
      { "title": "Cardiac Evaluation", "description": "...", "order": 6 }
    ]
  },
  "referral_information": {
    "has_referral": true,
    "referral_status": "in_progress"
  }
}
```

## Key Features

### ✅ Personalized Responses

- Uses actual patient data to tailor responses
- Understands current pathway stage
- References specific checklist items and progress

### ✅ Context-Aware

- Knows where patient is in journey
- Understands what's completed vs. incomplete
- Aware of contraindications and referral status

### ✅ Safety-First

- Explicitly instructed NOT to provide medical advice
- Always refers to healthcare providers for medical questions
- Clear disclaimers in system prompt

### ✅ Flexible Architecture

- Easy to switch LLM providers (OpenAI, Anthropic, etc.)
- Configurable models and parameters
- Extensible for future enhancements

## Usage Example

```python
# Query the AI assistant
POST /api/v1/ai-assistant/query
{
  "query": "Where am I in my transplant journey?"
}

# Response
{
  "response": "You're currently in the EVALUATION stage...",
  "context_summary": {
    "pathway_stage": "evaluation",
    "checklist_completion": 41.7,
    "has_referral": true
  }
}
```

## Setup Requirements

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Set API key**: `export OPENAI_API_KEY="your-key"`
3. **Start server**: `python run.py`
4. **Test**: `GET /api/v1/ai-assistant/status`

## Data Sources Used

The AI assistant has access to:

- ✅ **Patient** model: Demographics, medical flags (has_ckd_esrd, has_referral)
- ✅ **PatientStatus** model: Pathway stage, contraindications
- ✅ **TransplantChecklist** model: Items, completion status, progress
- ✅ **QuestionnaireSubmission** model: Answers, submission history
- ✅ **FinancialProfile** model: Financial assessment data
- ✅ **PatientReferralState** model: Referral status, provider info, location

## Next Steps for Enhancement

1. **Conversation History**: Store chat history for multi-turn conversations
2. **Multiple Providers**: Add support for Anthropic Claude, local models
3. **Document Q&A**: Allow questions about uploaded documents
4. **Proactive Suggestions**: AI-generated reminders and recommendations
5. **Response Validation**: Validate responses for safety/compliance
6. **Rate Limiting**: Add rate limiting to prevent abuse
7. **Caching**: Cache common queries to reduce API costs

## Architecture Decisions

### Why OpenAI First?

- Well-documented and reliable
- Good performance for this use case
- Easy to integrate
- Can switch providers later via abstraction

### Why Separate Service Layer?

- Clean separation of concerns
- Easy to test and mock
- Can swap LLM providers without changing API
- Reusable across different endpoints

### Why Context Aggregation?

- Single source of truth for patient state
- Consistent data formatting
- Easy to debug and inspect
- Can be used for other features (notifications, reports)

## Testing the Integration

1. **Check Status**:

   ```bash
   curl http://localhost:8000/api/v1/ai-assistant/status
   ```

2. **View Context**:

   ```bash
   curl http://localhost:8000/api/v1/ai-assistant/context
   ```

3. **Ask Question**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/ai-assistant/query \
     -H "Content-Type: application/json" \
     -d '{"query": "What do I need to do next?"}'
   ```

## Cost Considerations

- **Model**: GPT-3.5-turbo (cost-effective) or GPT-4 (higher quality)
- **Token Usage**: ~500-1000 tokens per query (varies by context size)
- **Pricing**: Check OpenAI pricing page for current rates
- **Optimization**: Can reduce context size or cache responses to save costs

## Security & Privacy

⚠️ **Important**:

- Patient data is sent to OpenAI API
- Ensure compliance with HIPAA/privacy regulations
- Consider data residency requirements
- Never log full prompts with PII
- Use environment variables for API keys (never commit)

## Support

For detailed information, see:

- `AI_ASSISTANT_DESIGN.md` - Architecture and design decisions
- `AI_ASSISTANT_QUICKSTART.md` - Setup and usage guide
- API documentation at `/docs` endpoint when server is running
