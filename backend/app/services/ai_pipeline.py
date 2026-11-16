"""
AI pipeline service — IBM watsonx Granite via ibm-watsonx-ai SDK.

Falls back to deterministic mock responses when watsonx credentials are not
configured, so the app always works in dev/test without a live connection.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


# ── watsonx client (lazy, singleton) ─────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_watsonx_client():
    """Return a configured WatsonxAI client, or None if not configured."""
    from app.core.config import settings
    if not settings.WATSONX_API_KEY or not settings.WATSONX_PROJECT_ID:
        logger.warning("watsonx credentials not set — using mock AI responses")
        return None
    try:
        from ibm_watsonx_ai import APIClient, Credentials
        credentials = Credentials(
            url=settings.WATSONX_URL,
            api_key=settings.WATSONX_API_KEY,
        )
        client = APIClient(credentials)
        client.set.default_project(settings.WATSONX_PROJECT_ID)
        logger.info("watsonx client initialised (project %s)", settings.WATSONX_PROJECT_ID)
        return client
    except Exception as exc:
        logger.error("Failed to init watsonx client: %s", exc)
        return None


# ── Granite model ID ──────────────────────────────────────────────────────────

GRANITE_MODEL = "ibm/granite-13b-instruct-v2"

# Generation parameters — conservative for finance explanations
GEN_PARAMS = {
    "max_new_tokens": 220,
    "min_new_tokens": 30,
    "temperature": 0.2,          # low temperature = consistent, factual output
    "top_p": 0.85,
    "repetition_penalty": 1.1,
    "stop_sequences": ["\n\n", "###"],
}


# ── Prompt builders ───────────────────────────────────────────────────────────

def _explanation_prompt(
    exception_type: str,
    bank_date: str,
    description: str,
    amount: Decimal,
    ledger_amount: Optional[Decimal] = None,
) -> str:
    """Build a structured prompt for Granite to explain a reconciliation exception."""
    type_context = {
        "timing":               "The transaction appears in the bank statement but not in the general ledger for this period.",
        "duplicate":            "This transaction may be a duplicate of another entry already in the ledger.",
        "missing_entry":        "No matching entry was found in the general ledger.",
        "amount_mismatch":      f"The bank shows ${amount:,.2f} but the ledger shows ${ledger_amount or 0:,.2f}.",
        "fx":                   "This transaction involves a foreign-currency amount with a potential translation difference.",
        "undocumented_expense": f"A ${amount:,.2f} charge was recorded without a reference number, receipt, or supporting documentation.",
        "stale_item":           "This item has been outstanding for an extended period (possibly crossing fiscal years) and was never properly reconciled.",
        "contract_variance":    f"The payment of ${amount:,.2f} does not match the contracted scheduled amount. The variance must be investigated before closing.",
    }.get(exception_type, "An unclassified discrepancy was found.")

    return f"""### Bank Reconciliation Exception Analysis

You are a senior accountant reviewing a bank reconciliation exception. Write a clear, concise explanation (2-3 sentences) for the finance team. Be factual and professional.

Exception type: {exception_type.replace("_", " ").title()}
Bank date: {bank_date}
Bank description: {description}
Bank amount: ${amount:,.2f}
Context: {type_context}

Explanation:"""


def _journal_prompt(
    exception_type: str,
    amount: Decimal,
    description: str,
) -> str:
    """Build a prompt for Granite to suggest a correcting journal entry."""
    return f"""### Journal Entry Suggestion

You are a senior accountant. Suggest the correct double-entry journal to resolve this bank reconciliation exception. Format exactly as shown.

Exception type: {exception_type.replace("_", " ").title()}
Description: {description}
Amount: ${amount:,.2f}

Provide ONLY the journal entry in this exact format:
Dr [account code] [account name] ......... [amount]
Cr [account code] [account name] ... [amount]

Journal entry:"""


# ── Fallback mock responses (used when watsonx is unavailable) ────────────────

_MOCK_EXPLANATIONS = {
    "timing": (
        "The bank charged this fee on {bank_date}. It was not recorded in the ledger. "
        "Same amount and description as the previous three months — this appears to be a "
        "recurring charge that crossed a period boundary."
    ),
    "duplicate": (
        "This transaction matches a ledger entry with the same payee and amount. "
        "The bank may have processed it twice or the entry was double-posted. "
        "Confirm with the bank before approving."
    ),
    "missing_entry": (
        "No matching entry found in the general ledger for '{desc}'. "
        "The description does not match any vendor in the chart of accounts. "
        "A new journal entry is suggested below."
    ),
    "amount_mismatch": (
        "The bank records ${bank_amt} but the ledger shows ${ledger_amt} for a transaction "
        "with the same reference. The variance may indicate a currency rounding difference "
        "or a split transaction."
    ),
    "fx": (
        "This foreign-currency transaction settled at a different rate than the month-end "
        "rate used in the ledger, creating a translation difference. "
        "The difference should be recorded in the FX gain/loss account."
    ),
    "undocumented_expense": (
        "A ${bank_amt} charge labelled '{desc}' was posted without a reference number or "
        "supporting receipt. Finance policy requires documentation for all expenses above $25. "
        "Obtain a receipt or vendor invoice before this entry can be approved."
    ),
    "stale_item": (
        "This item originated in fiscal year {fiscal_year} and has remained unreconciled "
        "for over 90 days. Prior-period adjustments of this nature require controller approval "
        "and may need to be posted to a suspense account pending resolution."
    ),
    "contract_variance": (
        "The payment of ${bank_amt} does not match the contracted monthly amount of ${ledger_amt}. "
        "The variance of ${diff} must be explained — either an approved change order, a partial "
        "payment, or a billing error from the counterparty. Contract balance has been flagged."
    ),
}

_MOCK_JOURNALS = {
    "timing":               ("Dr 6200 Bank Fees", "Cr 1010 Operating Cash"),
    "duplicate":            ("Dr 2100 Accounts Payable", "Cr 1010 Operating Cash"),
    "missing_entry":        ("Dr 6500 Miscellaneous Expense", "Cr 1010 Operating Cash"),
    "amount_mismatch":      ("Dr 6200 Bank Fees", "Cr 1010 Operating Cash"),
    "fx":                   ("Dr 7100 FX Loss / Gain", "Cr 1010 Operating Cash"),
    "undocumented_expense": ("Dr 6500 Miscellaneous Expense", "Cr 1010 Operating Cash"),
    "stale_item":           ("Dr 1990 Suspense Account", "Cr 2900 Prior Period Adjustment"),
    "contract_variance":    ("Dr 2100 Accounts Payable", "Cr 1010 Operating Cash"),
}

_MOCK_CONFIDENCE = {
    "timing":               Decimal("0.94"),
    "duplicate":            Decimal("0.87"),
    "missing_entry":        Decimal("0.79"),
    "amount_mismatch":      Decimal("0.91"),
    "fx":                   Decimal("0.88"),
    "undocumented_expense": Decimal("0.96"),
    "stale_item":           Decimal("0.85"),
    "contract_variance":    Decimal("0.93"),
}


def _mock_explanation(
    exception_type: str,
    bank_date: str,
    description: str,
    amount: Decimal,
    ledger_amount: Optional[Decimal],
    fiscal_year: Optional[int] = None,
) -> str:
    template = _MOCK_EXPLANATIONS.get(exception_type, _MOCK_EXPLANATIONS["missing_entry"])
    diff = abs(amount - (ledger_amount or amount))
    # Derive fiscal year from bank_date if not provided
    if not fiscal_year:
        try:
            fiscal_year = int(bank_date[:4])
        except (ValueError, TypeError):
            fiscal_year = datetime.now(timezone.utc).year
    return template.format(
        bank_date=bank_date,
        desc=description[:40],
        bank_amt=f"{amount:,.2f}",
        ledger_amt=f"{ledger_amount or 0:,.2f}",
        diff=f"{diff:,.2f}",
        fiscal_year=fiscal_year,
    )


def _mock_journal(exception_type: str, amount: Decimal) -> tuple[str, str]:
    debit_label, credit_label = _MOCK_JOURNALS.get(
        exception_type, _MOCK_JOURNALS["missing_entry"]
    )
    return (
        f"{debit_label} ......... {amount:,.2f}",
        f"{credit_label} ... {amount:,.2f}",
    )


# ── Public interface ──────────────────────────────────────────────────────────

def generate_ai_explanation(
    exception_type: str,
    bank_date: str,
    description: str,
    amount: Decimal,
    ledger_amount: Optional[Decimal] = None,
    reference: Optional[str] = None,
) -> dict:
    """
    Generate an AI explanation for a reconciliation exception.
    Uses real IBM Granite via watsonx if credentials are present, otherwise mock.
    Returns {"explanation": str, "confidence": Decimal}
    """
    confidence = _MOCK_CONFIDENCE.get(exception_type, Decimal("0.80"))
    client = _get_watsonx_client()

    if client is not None:
        try:
            from ibm_watsonx_ai.foundation_models import ModelInference
            model = ModelInference(
                model_id=GRANITE_MODEL,
                api_client=client,
                params=GEN_PARAMS,
            )
            prompt = _explanation_prompt(
                exception_type, bank_date, description, amount, ledger_amount
            )
            response = model.generate_text(prompt=prompt)
            explanation = response.strip()
            if explanation:
                logger.info("watsonx explanation generated for %s exception", exception_type)
                return {"explanation": explanation, "confidence": confidence}
        except Exception as exc:
            logger.error("watsonx generate_text failed: %s — falling back to mock", exc)

    # Fallback
    return {
        "explanation": _mock_explanation(
            exception_type, bank_date, description, amount, ledger_amount
        ),
        "confidence": confidence,
    }


def suggest_journal_entry(
    exception_type: str,
    amount: Decimal,
    description: str,
) -> dict:
    """
    Suggest a correcting journal entry.
    Uses real IBM Granite via watsonx if credentials are present, otherwise mock.
    Returns {"suggested_debit": str, "suggested_credit": str, "suggested_amount": Decimal}
    """
    client = _get_watsonx_client()

    if client is not None:
        try:
            from ibm_watsonx_ai.foundation_models import ModelInference
            model = ModelInference(
                model_id=GRANITE_MODEL,
                api_client=client,
                params={**GEN_PARAMS, "max_new_tokens": 80},
            )
            prompt = _journal_prompt(exception_type, amount, description)
            response = model.generate_text(prompt=prompt).strip()
            lines = [l.strip() for l in response.splitlines() if l.strip()]
            # Expect at least two lines: Dr ... and Cr ...
            if len(lines) >= 2:
                debit_line = lines[0]
                credit_line = lines[1]
                logger.info("watsonx journal entry generated for %s", exception_type)
                return {
                    "suggested_debit": debit_line,
                    "suggested_credit": credit_line,
                    "suggested_amount": amount,
                }
        except Exception as exc:
            logger.error("watsonx journal generation failed: %s — falling back to mock", exc)

    # Fallback
    debit, credit = _mock_journal(exception_type, amount)
    return {
        "suggested_debit": debit,
        "suggested_credit": credit,
        "suggested_amount": amount,
    }


# ── Hash chain for audit trail ────────────────────────────────────────────────

def compute_entry_hash(
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    user_id: Optional[int],
    details: Optional[dict],
    created_at: datetime,
    previous_hash: Optional[str],
) -> str:
    """SHA-256 hash of the audit log entry — tamper-evident chain."""
    payload = json.dumps(
        {
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "user_id": user_id,
            "details": details,
            "created_at": created_at.isoformat(),
            "previous_hash": previous_hash,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
