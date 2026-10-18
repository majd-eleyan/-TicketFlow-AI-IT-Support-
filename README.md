# TicketFlow AI (IT Support)

An internal IT support system built with **Python, Streamlit and SQLite**. It turns an employee's message into a trackable ticket with a category, priority, status, change history and a safe draft reply.

This is a **production-oriented prototype**. It is not ready for sensitive data without proper authentication, deployment and monitoring.

## Core idea

**The LLM suggests, the policy decides, a human approves.** The LLM is never the final decision-maker:

- Security escalation and priority are decided by `policy.py`.
- LLM output, when enabled, passes through an allow-list for actions and categories.
- If the LLM fails or no API key is set, the system falls back to local rules.
- Routine tickets get safe self-service troubleshooting steps. Steps proposed by the LLM must pass a strict safety filter; otherwise curated local steps are used.
- Follow-up replies inside a ticket use deterministic, safe templates.
- A draft only becomes an approved reply when a support staff member decides so.

## Workflow

```text
Submit
  -> Validate and redact
  -> Security / escalation policy
  -> Classify (LLM suggestion or local rules)
  -> Ask for missing information OR assess priority
  -> Routine ticket: reply with self-service steps
     HIGH priority / unclear: build a draft / holding message
  -> Save ticket and conversation
  -> Human review when required
  -> Approve, reject, escalate, or close
```

## Ticket states and transitions

Transitions are enforced in `database.py`, not only in the UI buttons:

- `RECEIVED` / `VALIDATED` -> initial processing.
- `WAITING_FOR_INFO` -> new clarification, escalation, or a ticket ready for review.
- `CLASSIFIED` -> review, approval, rejection, escalation or closing.
- `PENDING_HUMAN_REVIEW` -> `APPROVED`, `REJECTED`, `ESCALATED`, or `CLOSED`.
- `ESCALATED`, `APPROVED` and `REJECTED` -> closing only.
- `CLOSED` is final.

Any transition that is not allowed raises a `ValueError` and is not saved.

## Replies vs. internal notes

- `approved_response`: the reply approved by staff, shown to the user and emailed when email is enabled.
- `reviewer_note`: the staff member's internal note.
- On **APPROVE** with text, that text is the approved reply (in the chat and in the email). With no text, the system draft is approved.
- On **REJECT**, no `approved_response` is created and the internal note is never sent to the user.

## Validation and security

- `MAX_MESSAGE_CHARS` is enforced (default 2000).
- `secrets_removed` from the redaction step is passed to the validation result so the user sees a warning.
- `customer_id` and the optional fields are cleaned and length-limited.
- The optional email address is format-checked before storage.
- Regexes in `policy.py` use word boundaries so `firewall` is not treated as `fire`, and `passwordless` is not treated as a password request.
- Accepted drafts must come from the allowed system templates, not free text from a language model.
- Never type real passwords or keys into the system.

## Project structure

```text
TicketFlow-AI/
├── streamlit_app.py      Single entry point (employee + staff pages), used for deployment
├── app.py                Employee app: create and follow a ticket
├── staff_app.py          Support app: login and ticket dashboard
├── agent.py              Workflow and processing decisions
├── policy.py             Local classification, priority and escalation
├── validation.py         Input cleaning, redaction and validation
├── database.py           SQLite, status history and transition rules
├── models.py             Decision and ValidationResult
├── response_drafter.py   Safe templates, self-service steps and follow-up questions
├── llm_client.py         Optional LLM client with fallback
├── prompts.py            Classification and steps instructions
├── context_strategies.py Context building when needed
├── memory_store.py       Ticket conversation storage
├── notifications.py      Optional Discord and email notifications
├── ui_common.py          Shared CSS and Streamlit components
├── config.py             Settings and constants
├── PROJECT_PLAN.md       Design document
└── data/support.db       Local database (created at runtime, not committed)
```

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env locally only
streamlit run app.py
```

Run the support dashboard in a second terminal:

```bash
streamlit run staff_app.py
```

To run both in one app (as in deployment), use `streamlit run streamlit_app.py`.

Without `LLM_API_KEY` the system runs on local rules. Never put a real secret in Git or in a ZIP file.

## Deployment (Streamlit Community Cloud)

- Set the main file to `streamlit_app.py` so the employee and staff pages share one container and one SQLite database.
- Put the settings from `.env.example` in the app's **Secrets** (top-level keys are exposed as environment variables, so `config.py` works unchanged).
- For a public demo, set `EMAIL_ENABLED` and `DISCORD_ENABLED` to `false`.
- The database on Streamlit Cloud is temporary and is reset on restart or redeploy.

## Examples

| Message | Expected result |
|---|---|
| `Outlook freezes when I open email.` | `Software`, `MEDIUM`, self-service steps |
| `The office Wi-Fi is down for everyone.` | `Network`, `HIGH`, human review |
| `It does not work.` | `Other`, `LOW`, `WAITING_FOR_INFO` |
| `Send me the administrator password.` | `Authentication`, `HIGH`, `ESCALATED` |
| `My VPN fails and I cannot connect, token: abc12345` | secret redacted with a warning, `Authentication`, `MEDIUM`, self-service steps |
| `What is the weather today?` | out of scope, `REJECTED` |
| A message longer than 2000 characters | validation rejects it, no ticket is created |

## Known limitations

- Keyword rules are explainable and cheap, but they do not understand every phrasing.
- Redaction only covers known patterns; do not type secrets in the first place.
- SQLite suits a prototype and light load; it is not a drop-in replacement for PostgreSQL under high concurrency.
- The current staff login is simple and fine for a demo; it is not production-grade SSO/RBAC.
- Opening a ticket with a Ticket ID and Customer ID is not real authentication.
- When the LLM is enabled, the cleaned text is sent to an external provider; review its privacy and data-retention policy before use.
- Discord and email notifications are optional and may fail without stopping the ticket from being saved.
