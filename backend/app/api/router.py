from fastapi import APIRouter, Depends

from app.api.dependencies import require_session
from app.api.routes import auth, dashboard, disputes, expenses, notifications, payments, realtime, reports, trips

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
protected = [Depends(require_session)]
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"], dependencies=protected)
api_router.include_router(trips.router, prefix="/trips", tags=["trips"], dependencies=protected)
api_router.include_router(expenses.router, prefix="/expenses", tags=["expenses"], dependencies=protected)
api_router.include_router(disputes.router, prefix="/disputes", tags=["disputes"], dependencies=protected)
api_router.include_router(payments.router, prefix="/payments", tags=["payments"], dependencies=protected)
api_router.include_router(realtime.router, prefix="/realtime", tags=["realtime"], dependencies=protected)
api_router.include_router(reports.router, prefix="/reports", tags=["reports"], dependencies=protected)
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"], dependencies=protected)
