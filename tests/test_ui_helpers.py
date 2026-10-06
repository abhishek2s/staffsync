import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

from src.utils import ui_helpers


class TestUiHelpers(unittest.TestCase):
    def test_setup_page_configures_sidebar_without_refresh(self):
        with (
            patch.object(ui_helpers.st, "set_page_config") as set_page_config,
            patch.object(ui_helpers.st, "sidebar", nullcontext()),
            patch.object(ui_helpers.st, "markdown"),
            patch.object(ui_helpers.st, "caption"),
            patch.object(ui_helpers.st, "divider"),
            patch.object(ui_helpers.st, "write"),
            patch.object(ui_helpers.st, "button", return_value=False) as button,
        ):
            ui_helpers.setup_page("People")

        set_page_config.assert_called_once_with(page_title="StaffSync | People", layout="wide")
        button.assert_called_once_with("Refresh Data", type="primary", width="stretch")

    def test_setup_page_refreshes_and_displays_result_when_clicked(self):
        with (
            patch.object(ui_helpers.st, "set_page_config"),
            patch.object(ui_helpers.st, "sidebar", nullcontext()),
            patch.object(ui_helpers.st, "markdown"),
            patch.object(ui_helpers.st, "caption"),
            patch.object(ui_helpers.st, "divider"),
            patch.object(ui_helpers.st, "write"),
            patch.object(ui_helpers.st, "button", return_value=True),
            patch.object(ui_helpers.st, "spinner", return_value=nullcontext()),
            patch.object(ui_helpers, "AnalyticsManager") as analytics,
            patch.object(ui_helpers, "show_result") as show_result,
        ):
            analytics.return_value.refresh_warehouse.return_value = (True, "done")
            ui_helpers.setup_page("People")

        analytics.return_value.refresh_warehouse.assert_called_once_with()
        show_result.assert_called_once_with(True, "done")

    def test_show_result_success_clears_cache_and_failure_displays_error(self):
        with (
            patch.object(ui_helpers.st, "toast") as toast,
            patch.object(ui_helpers.st.cache_data, "clear") as clear,
        ):
            ui_helpers.show_result(True, "refreshed")
        toast.assert_called_once_with("refreshed", icon="✅")
        clear.assert_called_once_with()

        with patch.object(ui_helpers.st, "error") as error:
            ui_helpers.show_result(False, "refresh failed")
        error.assert_called_once_with("refresh failed", icon="🚨")

    def test_cached_analytics_dispatches_method_and_loads_departments(self):
        manager = Mock()
        manager.get_kpis.return_value = {"count": 1}
        with patch.object(ui_helpers, "AnalyticsManager", return_value=manager):
            self.assertEqual(ui_helpers._cached_analytics.__wrapped__("get_kpis"), {"count": 1})
        manager.get_kpis.assert_called_once_with()

        employee_manager = Mock()
        employee_manager.get_departments.return_value = ["Engineering"]
        with patch.object(ui_helpers, "EmployeeManager", return_value=employee_manager):
            self.assertEqual(ui_helpers.load_departments.__wrapped__(), ["Engineering"])
        employee_manager.get_departments.assert_called_once_with()

    def test_get_data_returns_value_or_displays_error_and_returns_none(self):
        with patch.object(ui_helpers, "_cached_analytics", return_value={"ok": True}) as cached:
            self.assertEqual(ui_helpers.get_data("get_kpis", 3), {"ok": True})
        cached.assert_called_once_with("get_kpis", 3)

        with (
            patch.object(ui_helpers, "_cached_analytics", side_effect=RuntimeError("offline")),
            patch.object(ui_helpers.st, "error") as error,
        ):
            self.assertIsNone(ui_helpers.get_data("get_kpis"))
        error.assert_called_once_with("Could not load data from the warehouse: offline")


if __name__ == "__main__":
    unittest.main()
