import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_export_pdf_report():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as ac:
        response = await ac.post("/editor/export-pdf", json={
            "text": "This is a test summary for the PDF report.\nIt should contain multiple lines."
        })
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "summary_report.pdf" in response.headers["content-disposition"]
    assert len(response.content) > 0
    assert response.content.startswith(b"%PDF")
