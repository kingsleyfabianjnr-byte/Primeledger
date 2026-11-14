"""watsonx connection test endpoint."""
from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/watsonx", tags=["watsonx"])


@router.get("/test")
async def test_watsonx(current_user: User = Depends(get_current_user)):
    """
    Test the live watsonx connection.
    Sends a minimal prompt to IBM Granite and returns the result.
    Visible at /docs — requires a valid login token.
    """
    from app.services.ai_pipeline import _get_watsonx_client, GRANITE_MODEL, GEN_PARAMS

    client = _get_watsonx_client()

    if client is None:
        return {
            "status": "mock",
            "message": "watsonx credentials not configured — running in mock mode",
            "model": None,
            "response": None,
        }

    try:
        from ibm_watsonx_ai.foundation_models import ModelInference
        model = ModelInference(
            model_id=GRANITE_MODEL,
            api_client=client,
            params={**GEN_PARAMS, "max_new_tokens": 30, "min_new_tokens": 5},
        )
        prompt = "In one sentence, what is bank reconciliation?"
        response = model.generate_text(prompt=prompt).strip()
        return {
            "status": "connected",
            "message": "Successfully connected to IBM watsonx",
            "model": GRANITE_MODEL,
            "response": response,
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "model": GRANITE_MODEL,
            "response": None,
        }
