import unittest

from app.schemas.detection_schema import AlertResponse, FaceIdentityResponse, FaceLogResponse, TokenResponse
from app.schemas.dashboard_schema import (
    AnalyticsMetricItem,
    AnalyticsSummaryResponse,
    AnalyticsTrendPoint,
    DashboardActivityItem,
    DashboardMetricSummary,
    DashboardOperationPoint,
    DashboardSummaryResponse,
)


class ApiContractModelTests(unittest.TestCase):
    def test_token_response_fields_unchanged(self):
        self.assertEqual(set(TokenResponse.model_fields.keys()), {"access_token", "token_type", "name"})

    def test_face_identity_response_fields_unchanged(self):
        expected = {"id", "name", "category", "registered_by", "has_image", "is_active", "created_at", "updated_at"}
        self.assertEqual(set(FaceIdentityResponse.model_fields.keys()), expected)

    def test_alert_response_fields_unchanged(self):
        expected = {
            "id",
            "alert_type",
            "camera_id",
            "person_id",
            "person_name",
            "severity",
            "threat_level",
            "category",
            "description",
            "status",
            "resolved_by",
            "notes",
            "suspect_image_url",
            "evidence_image_url",
            "timestamp",
        }
        self.assertEqual(set(AlertResponse.model_fields.keys()), expected)

    def test_face_log_response_fields_unchanged(self):
        expected = {"id", "face_id", "camera_id", "confidence", "timestamp"}
        self.assertEqual(set(FaceLogResponse.model_fields.keys()), expected)

    def test_dashboard_metric_summary_fields_unchanged(self):
        expected = {"active_alerts", "online_cameras", "resolved_cases", "face_data_records"}
        self.assertEqual(set(DashboardMetricSummary.model_fields.keys()), expected)

    def test_dashboard_operation_point_fields_unchanged(self):
        expected = {"label", "value"}
        self.assertEqual(set(DashboardOperationPoint.model_fields.keys()), expected)

    def test_dashboard_activity_item_fields_unchanged(self):
        expected = {"id", "message", "timestamp"}
        self.assertEqual(set(DashboardActivityItem.model_fields.keys()), expected)

    def test_dashboard_summary_response_fields_unchanged(self):
        expected = {"metrics", "operations", "recent_activity"}
        self.assertEqual(set(DashboardSummaryResponse.model_fields.keys()), expected)

    def test_analytics_metric_item_fields_unchanged(self):
        expected = {"label", "value"}
        self.assertEqual(set(AnalyticsMetricItem.model_fields.keys()), expected)

    def test_analytics_trend_point_fields_unchanged(self):
        expected = {"label", "value"}
        self.assertEqual(set(AnalyticsTrendPoint.model_fields.keys()), expected)

    def test_analytics_summary_response_fields_unchanged(self):
        expected = {"metrics", "trend"}
        self.assertEqual(set(AnalyticsSummaryResponse.model_fields.keys()), expected)


if __name__ == "__main__":
    unittest.main()
