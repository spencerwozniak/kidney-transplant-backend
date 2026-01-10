# Kidney Transplant Navigation — Backend API

(PHP?)-based backend that powers a **patient-controlled transplant navigation system** by evaluating eligibility, detecting missed care events, and recording decisions in a transparent, auditable way.

> **Disclaimer**  
> This project is for educational and informational purposes only and does not provide medical advice.  
> It is intended to support patient understanding and navigation, not replace clinical judgment or professional care.

---

## What This Backend Does (MVP)

- Stores **kidney-specific patient data** (bounded scope)
- Evaluates transplant eligibility using **deterministic, explainable rules**
- Detects **missed dialysis sessions**
- Records all key events in an **append-only decision ledger**
- Exposes REST endpoints consumed by the mobile app
- Supports explainable, low-noise alerts

---

## Core Responsibilities

### Data Models
- Labs (e.g. eGFR)
- Dialysis sessions (scheduled vs attended)
- Eligibility questionnaire
- Uploaded documents (labs, reports)

### Eligibility Engine
- Rule-based (no black-box)
- Produces:
  - eligibility met / not met
  - explanation (human-readable)
  - timestamp when criteria were first met

### Decision Ledger
- Append-only (no updates or deletes)
- Records:
  - eligibility events
  - alerts
  - acknowledgments
  - overrides with explanations

### Alert Orchestration
- Alerts only on **omissions**, not predictions
- Gated by time windows and patient consent
- Designed explicitly to avoid alert fatigue

---

## Planned API Endpoints (MVP)

- `POST /upload`
- `POST /eligibility/evaluate`
- `GET /ledger`
- `GET /alerts`

---

## Tech Stack

- PHP (framework flexible: Laravel / Slim)
- REST + JSON
- (Postgres?)SQL database
- Simple, auditable business logic

---

## Design Philosophy

- Deterministic over probabilistic
- Explainable over clever
- Patient-owned data as canonical source
- Silence becomes visible, not patients blamed

---

## Status

Hackathon MVP — optimized for:
- Speed of development
- Clarity of logic
- Defensible demo narrative
- Future extensibility after validation
