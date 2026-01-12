# AI Assistant Integration Design

## Overview

This document outlines the design for integrating an AI assistant into the kidney transplant backend. The assistant will use patient data stored in the system to provide personalized, context-aware responses about the patient's transplant journey.

## Goals

1. **Personalized Responses**: Use patient data (status, checklist, questionnaire, referral state) to tailor responses
2. **Context Awareness**: Understand where the patient is in their transplant journey (pathway stage)
3. **Actionable Guidance**: Provide specific next steps based on patient's current state
4. **Safe & Compliant**: Ensure responses are medically appropriate and don't provide direct medical advice

## Data Sources Available

The AI assistant will have access to the following patient data:

### 1. Patient (`Patient` model)
- Demographics: name, date_of_birth, sex, height, weight
- Contact: email, phone
- Medical: has_ckd_esrd, last_gfr, has_referral

### 2. Patient Status (`PatientStatus` model)
- **Pathway Stage**: Current stage in transplant journey
  - `identification`: Early awareness, no questionnaire or CKD/ESRD not confirmed
  - `referral`: Need referral to transplant center
  - `evaluation`: Undergoing pre-transplant evaluation (checklist < 80% complete)
  - `selection`: Evaluation mostly complete (checklist ≥ 80% complete), ready for waitlisting
  - `transplantation`: (Future) On waitlist or scheduled for transplant
  - `post-transplant`: (Future) Post-transplant care
- **Contraindications**: Absolute and relative contraindications from questionnaire
- **Timestamps**: When status was last updated

### 3. Transplant Checklist (`TransplantChecklist` model)
- **Items**: List of required evaluations/tests
  - Each item has: title, description, is_complete, notes, completed_at, order, documents
- **Progress**: Completion percentage (used to determine pathway stage)
- **Timestamps**: Created and updated dates

### 4. Questionnaire Submissions (`QuestionnaireSubmission` model)
- **Answers**: Key-value pairs of question_id → answer ('yes'/'no')
- **History**: All submissions retained (latest answer wins per question)
- **Timestamps**: When each questionnaire was submitted

### 5. Financial Profile (`FinancialProfile` model)
- **Answers**: Financial assessment responses
- **Timestamps**: Submitted and updated dates

### 6. Referral State (`PatientReferralState` model)
- **Location**: Zip, state, optionally lat/lng
- **Referral Status**: not_started, in_progress, completed
- **Provider Info**: Nephrologist, dialysis center details
- **Preferred Centers**: List of selected transplant center IDs

## Prompt Construction Strategy

### System Prompt (Base Instructions)

The system prompt will establish the AI's role and constraints:

```
You are a helpful assistant for patients navigating the kidney transplant journey. 
Your role is to:
- Provide clear, empathetic guidance about where they are in the process
- Explain what steps come next based on their current status
- Answer questions about their transplant journey using their personal data
- Help them understand their checklist progress and what's needed

IMPORTANT CONSTRAINTS:
- You are NOT providing medical advice or diagnoses
- Always refer patients to their healthcare providers for medical questions
- Use the patient's actual data to personalize responses
- Be encouraging and supportive while being realistic
- If you don't have information, say so rather than guessing
```

### Context Assembly

For each query, we'll assemble a context object containing:

1. **Patient Summary**: Key demographics and medical info (anonymized if needed)
2. **Current Pathway Stage**: Where they are in the journey
3. **Status Summary**: Contraindications (if any), referral status
4. **Checklist Progress**: Completed items, remaining items, completion percentage
5. **Recent Activity**: Latest questionnaire submission, checklist updates
6. **Referral Information**: Referral status, provider details, preferred centers

### Query Types

The assistant should handle different types of queries:

1. **Status Queries**: "Where am I in my transplant journey?"
2. **Progress Queries**: "What do I need to do next?"
3. **Checklist Queries**: "What items are still incomplete?"
4. **Contraindication Queries**: "What are my contraindications?"
5. **Referral Queries**: "How do I get a referral?"
6. **General Questions**: "What is a kidney transplant evaluation?"

## Implementation Architecture

### Components

1. **`app/services/ai_assistant.py`**: Core service for prompt construction and LLM interaction
2. **`app/api/ai_assistant.py`**: API endpoint for chat/query interface
3. **`app/core/ai_config.py`**: Configuration for AI provider (API keys, model selection)

### Data Aggregation Service

A service function will aggregate all relevant patient data into a structured context:

```python
def build_patient_context(patient_id: str) -> Dict[str, Any]:
    """
    Aggregates all patient data into a structured context for AI prompts
    """
    # Fetch all data sources
    # Structure into context object
    # Return formatted context
```

### Prompt Templates

Different prompt templates for different query types:

- **General Query Template**: User question + patient context
- **Status Query Template**: Focused on pathway stage and progress
- **Next Steps Template**: Actionable items based on current state

## LLM Provider Options

### Option 1: OpenAI (GPT-4, GPT-3.5-turbo)
- Pros: Well-documented, reliable, good performance
- Cons: Requires API key, costs per token

### Option 2: Anthropic (Claude)
- Pros: Strong safety features, good for medical contexts
- Cons: Requires API key, costs per token

### Option 3: Local Models (via Ollama, etc.)
- Pros: No API costs, data stays local
- Cons: May require more setup, potentially lower quality

### Recommendation

Start with OpenAI GPT-4 or GPT-3.5-turbo for MVP, with abstraction layer to easily switch providers later.

## Safety & Compliance Considerations

1. **Medical Disclaimer**: Always include disclaimer that AI is not providing medical advice
2. **Data Privacy**: Ensure patient data is handled securely (don't log full prompts with PII)
3. **Response Validation**: Consider validating responses don't contain dangerous medical claims
4. **Rate Limiting**: Implement rate limiting on AI endpoint
5. **Error Handling**: Graceful fallbacks if AI service is unavailable

## Example Use Cases

### Use Case 1: Patient asks "Where am I in my journey?"

**Context Provided:**
- Pathway stage: "evaluation"
- Checklist: 5/12 items complete (42%)
- Has referral: true
- Last activity: Completed "Lab Work" 3 days ago

**Expected Response:**
"You're currently in the **evaluation stage** of your transplant journey. You have a referral to a transplant center and are working through your pre-transplant evaluation checklist. You've completed 5 out of 12 required items (42% complete). Your most recent activity was completing your lab work 3 days ago. Next, you'll want to focus on [next incomplete item]..."

### Use Case 2: Patient asks "What do I need to do next?"

**Context Provided:**
- Pathway stage: "referral"
- Has referral: false
- Referral state: not_started
- Has nephrologist: true (from referral state)

**Expected Response:**
"You're currently in the **referral stage**. To move forward, you need to obtain a referral to a transplant center. Since you have a nephrologist, the next step is to contact their office and request a referral. Here's a suggested script: [script from referral pathway]..."

### Use Case 3: Patient asks about contraindications

**Context Provided:**
- Has absolute contraindications: false
- Has relative contraindications: true
- Relative contraindications: ["Active smoking", "BMI > 40"]

**Expected Response:**
"You have some relative contraindications that your transplant team will evaluate: [list]. These are factors that may need to be addressed but don't necessarily prevent you from receiving a transplant. Your transplant team will work with you to address these during your evaluation..."

## Future Enhancements

1. **Conversation History**: Store chat history for context across sessions
2. **Multi-turn Conversations**: Support follow-up questions
3. **Document Q&A**: Allow questions about uploaded documents
4. **Proactive Notifications**: AI-generated reminders about incomplete items
5. **Educational Content**: Provide educational resources based on pathway stage
6. **Sentiment Analysis**: Detect patient concerns or confusion

## Implementation Phases

### Phase 1: MVP (Current)
- Basic prompt construction from patient data
- Single query endpoint
- OpenAI integration
- Simple context aggregation

### Phase 2: Enhanced Context
- Conversation history
- Multi-turn support
- Better prompt templates

### Phase 3: Advanced Features
- Document analysis
- Proactive suggestions
- Multi-provider support

