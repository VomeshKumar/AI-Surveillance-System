from datetime import datetime

from pydantic import BaseModel


class DashboardMetricSummary(BaseModel):
    active_alerts: int
    online_cameras: int
    resolved_cases: int
    face_data_records: int


class DashboardOperationPoint(BaseModel):
    label: str
    value: int


class DashboardActivityItem(BaseModel):
    id: str
    message: str
    timestamp: datetime


class DashboardSummaryResponse(BaseModel):
    metrics: DashboardMetricSummary
    operations: list[DashboardOperationPoint]
    recent_activity: list[DashboardActivityItem]


class AnalyticsMetricItem(BaseModel):
    label: str
    value: str


class AnalyticsTrendPoint(BaseModel):
    label: str
    value: int


class AnalyticsSummaryResponse(BaseModel):
    metrics: list[AnalyticsMetricItem]
    trend: list[AnalyticsTrendPoint]


class ReportMetricSummary(BaseModel):
    available_reports: int
    ready_to_download: int
    pending_generation: int


class ReportItem(BaseModel):
    id: str
    name: str
    type: str
    status: str
    description: str
    generated_at: str


class ReportsSummaryResponse(BaseModel):
    metrics: ReportMetricSummary
    reports: list[ReportItem]
