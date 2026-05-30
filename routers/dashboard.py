from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

router = APIRouter()

@router.get('/dashboard')
async def dashboard(request: Request):
    return RedirectResponse(url='/sales/dashboard')
