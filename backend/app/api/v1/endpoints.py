# backend/app/api/v1/endpoints.py

from fastapi import APIRouter

from .ui import router as ui_router
from .data_read import router as data_read_router
from .data_write import router as data_write_router
from .actions import router as actions_router
from .onchange import router as onchange_router

router = APIRouter()
router.include_router(ui_router)
router.include_router(data_read_router)
router.include_router(data_write_router)
router.include_router(actions_router)
router.include_router(onchange_router)