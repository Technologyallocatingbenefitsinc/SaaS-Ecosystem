import httpx
import os
from app.config import settings

async def log_token_usage(user_id, plan_type, prompt_tokens, response_tokens):
    """
    Sends token counts to n8n to prevent budget overruns.
    Prices for Gemini 1.5 Flash:
    $0.075 per 1M input tokens | $0.30 per 1M output tokens (current rates)
    """
    n8n_logger_url = settings.N8N_TOKEN_LOGGER_URL
    if not n8n_logger_url or "your-n8n-instance" in n8n_logger_url:
        print(f"Usage Log (Local Only): User {user_id} used {prompt_tokens + response_tokens} tokens.")
        return

    # Calculate estimated cost in USD
    estimated_cost = (prompt_tokens * 0.000000075) + (response_tokens * 0.0000003)
    
    payload = {
        "user_id": user_id,
        "plan": plan_type,
        "tokens_in": prompt_tokens,
        "tokens_out": response_tokens,
        "cost_usd": estimated_cost,
        "secret": settings.AUTH_SECRET_TOKEN
    }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(n8n_logger_url, json=payload)
        except Exception as e:
            print(f"Failed to log token usage to n8n: {e}")
