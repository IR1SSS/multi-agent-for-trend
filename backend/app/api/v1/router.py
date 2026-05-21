from fastapi import APIRouter

from app.api.v1.accounts import router as accounts_router
from app.api.v1.keywords import router as keywords_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.data import router as data_router
from app.api.v1.system import router as system_router
from app.api.v1.pipeline import router as pipeline_router
from app.api.v1.cleaned_data import router as cleaned_data_router
from app.api.v1.domains import router as domains_router

api_router = APIRouter()

api_router.include_router(accounts_router)
api_router.include_router(keywords_router)
api_router.include_router(tasks_router)
api_router.include_router(data_router)
api_router.include_router(system_router)
api_router.include_router(pipeline_router)
api_router.include_router(cleaned_data_router)
api_router.include_router(domains_router)
