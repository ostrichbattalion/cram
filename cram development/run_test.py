#!/usr/bin/env python3
"""
run_tests.py - Comprehensive Unit Test Suite and HTML Report Generator for Cram.
Validates SAQA calculations, phase tracking, day-state rules, and recommendation logic.
Guaranteed safe: uses memory-mocking to prevent touching production JSON files.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
import os

# Import core system components
from models import Module, Topic, Assignment, Assessment, Session, ConfidenceEvent
from scheduler import WeeklyPlanner, DailyRecommender


class TestSAQANotionalHours(unittest.TestCase):
    """Verifies compliance with the SAQA definition rules for derived hour budgets."""

    def test_derived_self_study_budget_deductions(self):
        """Confirm that self-study budget accounts for credits, contact time, and questions."""
        # 15 Credits = 150 Notional Hours. 3 assignment questions @ 2h each = 6h. 
        # 150 - 3 (contact) - 6 (assignment) = 141.0 Hours self-study budget
        module = Module(
            code="INF600",
            name="Test Module",
            nqf_level=6,
            credits=15,
            assignment=Assignment(total_q=3)
        )
        self.assertEqual(module.notional_hours, 150.0)
        self.assertEqual(module.assignment_notional_hours, 6.0)
        self.assertEqual(module.self_study_budget, 141.0)

    def test_phase_budget_allocations(self):
        """Verify that phase weight coefficients match exact study guide distributions."""
        module = Module(code="INF600", name="Test Module", nqf_level=6, credits=10, assignment=None)
        # 10 Credits = 100 Notional Hours - 3 contact = 97.0h self-study budget
        # Phase 1: 20% of 97 = 19.4
        # Phase 2: 25% of 97 = 24.25 -> rounded to 24.3
        self.assertEqual(module.phase_budget(1), 19.4)
        self.assertEqual(module.phase_budget(2), 24.3)


class TestBurnDownCalculations(unittest.TestCase):
    """Validates the math driving the remaining timeline daily metrics generation."""

    def test_burn_down_with_active_target_date(self):
        """Ensure daily hour burn-down calculates correctly based on assessment horizons."""
        module = Module(code="INF600", name="Test Module", nqf_level=6, credits=10)
        # self_study_budget = 100 - 3 = 97.0h.
        
        # Inject an upcoming CA assessment due exactly 10 days from now
        future_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        module.ca.due_date_str = future_date
        
        # 97.0 hours left / 10 days left = 9.7h per day
        self.assertEqual(module.recommended_daily_hours(), 9.7)

    def test_burn_down_exhausted_or_passed(self):
        """Ensure burn-down handles completed hours safely without plunging into negatives."""
        module = Module(code="INF600", name="Test Module", nqf_level=6, credits=10)
        t = Topic(number=1, name="Topic 1", arc="ca")
        t.log_session(hours=100.0) # completely exhaust budget
        module.topics.append(t)
        
        future_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        module.ca.due_date_str = future_date
        
        self.assertEqual(module.recommended_daily_hours(), 0.0)


class TestWeeklyPlannerAndDayStates(unittest.TestCase):
    """Tests study hour pool shifts across dynamic day states."""

    def test_rest_day_state_zeroes_budget(self):
        """Confirm that 'off' day state zeroes out recommended targets and drops recommendations."""
        planner = WeeklyPlanner()
        planner.set_day_state("off")
        self.assertEqual(planner.recommended_today(), 0.0)

    def test_light_day_state_caps_budget(self):
        """Confirm that 'light' day state strictly caps recommendations at 1.0 hour."""
        planner = WeeklyPlanner()
        planner.set_day_state("light")
        self.assertEqual(planner.recommended_today(), 1.0)

    def test_intensive_day_auto_detection(self):
        """Verify that logging long sessions automatically flips day state to 'intensive'."""
        planner = WeeklyPlanner()
        # Weekday default is 2.0. Logging 2.0 * 1.3 = 2.6h minimum triggers transition.
        planner.log_hours(3.5)
        self.assertEqual(planner.day_state(), "intensive")


class TestDailyRecommender(unittest.TestCase):
    """Validates the core engine ranking priority, urgency scores, and interleaving rules."""

    def test_soft_interleaving_cap(self):
        """Verify that the recommender selects a maximum of 2 modules (Primary and Revisit)."""
        # Set up 4 distinct active modules
        m1 = Module(code="M1", name="Stats", nqf_level=6, credits=10)
        m2 = Module(code="M2", name="Programming", nqf_level=6, credits=10)
        m3 = Module(code="M3", name="Machine Learning", nqf_level=6, credits=10)
        m4 = Module(code="M4", name="Info Systems", nqf_level=6, credits=10)
        
        for m in [m1, m2, m3, m4]:
            m.topics.append(Topic(number=1, name="Intro", arc="ca"))
            
        planner = WeeklyPlanner()
        planner.set_day_state("active") # Budget typically around 2-3 hours
        
        recommender = DailyRecommender([m1, m2, m3, m4], planner)
        recs = recommender.recommend()
        
        self.assertLessEqual(len(recs), 2)
        if len(recs) == 2:
            self.assertNotEqual(recs[0]["module"].name, recs[1]["module"].name)

    def test_phase_driven_topic_scoping(self):
        """Ensure topic selection prioritises content matching the module's active phase."""
        module = Module(code="M1", name="System Arc", nqf_level=6, credits=10, current_phase=4)
        t1 = Topic(number=1, name="CA Topic", arc="ca")
        t2 = Topic(number=2, name="Final Topic", arc="final")
        module.topics.extend([t1, t2])
        
        planner = WeeklyPlanner()
        recommender = DailyRecommender([module], planner)
        
        # In phase 4, best topic should target the final arc exclusively
        chosen_topic = recommender._best_topic(module)
        self.assertEqual(chosen_topic.arc, "final")


class TestPersistenceSanity(unittest.TestCase):
    """Guarantees that active application states change predictably via mutation commands."""

    @patch('database.load_active')
    @patch('database.save_active')
    def test_cmd_log_session_mirrors_to_planner(self, mock_save, mock_load):
        """Verify logging a session updates subject targets and shifts the daily tracker pool."""
        from commands import cmd_log
        
        # Configure a target test environment structure mock
        m = Module(code="DS1", name="Data Science", nqf_level=6, credits=10)
        t = Topic(number=1, name="Data Prep", arc="ca")
        m.topics.append(t)
        mock_load.return_value = [m]
        
        # Patch data loading/writing environments to protect production json assets
        with patch('commands.load_planner') as mock_p_load, \
             patch('commands.save_planner') as mock_p_save:
             
            planner = WeeklyPlanner()
            mock_p_load.return_value = planner
            
            # Execute targeted mutation command handler
            res = cmd_log(module_query="Data Science", topic_ref="1", hours=2.5, note="Testing automation")
            
            self.assertIn("✅", res)
            self.assertEqual(t.hours_studied, 2.5)
            mock_save.assert_called_once()
            mock_p_save.assert_called_once()


# ── Custom HTML Test Reporting Engine ───────────────────────────────────────

class HTMLTestResult(unittest.TestResult):
    """Custom collector to preserve outcomes for HTML injection formatting."""
    def __init__(self):
        super().__init__()
        self.results = []

    def addSuccess(self, test):
        self.results.append({
            "name": test._testMethodName,
            "doc": test._testMethodDoc or "No description provided.",
            "suite": test.__class__.__name__,
            "status": "PASS",
            "message": ""
        })

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.results.append({
            "name": test._testMethodName,
            "doc": test._testMethodDoc or "No description provided.",
            "suite": test.__class__.__name__,
            "status": "FAIL",
            "message": str(err[1])
        })

    def addError(self, test, err):
        super().addError(test, err)
        self.results.append({
            "name": test._testMethodName,
            "doc": test._testMethodDoc or "No description provided.",
            "suite": test.__class__.__name__,
            "status": "ERROR",
            "message": str(err[1])
        })


def generate_html_report(result, duration):
    """Compiles tracked framework testing statistics into a styled static standalone report."""
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors

    # Clean Obsidian-inspired layout elements
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Cram System Test Results</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #1e1e1e;
            color: #dcddde;
            margin: 0;
            padding: 40px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        header {{
            border-bottom: 1px solid #3e3e3e;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        h1 {{ margin: 0; color: #ffffff; font-size: 28px; }}
        .meta {{ color: #72767d; font-size: 14px; margin-top: 5px; }}
        .summary-cards {{
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
        }}
        .card {{
            flex: 1;
            background: #2f3136;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #36393f;
        }}
        .card .value {{ font-size: 32px; font-weight: bold; color: #fff; }}
        .card .label {{ font-size: 12px; text-transform: uppercase; color: #b9bbbe; margin-top: 5px; }}
        .card.pass {{ border-left: 5px solid #43b581; }}
        .card.fail {{ border-left: 5px solid #f04747; }}
        .suite-section {{
            background: #2f3136;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #36393f;
            overflow: hidden;
        }}
        .suite-header {{
            background: #202225;
            padding: 15px 20px;
            font-weight: bold;
            color: #ffffff;
            border-bottom: 1px solid #36393f;
        }}
        .test-row {{
            display: flex;
            align-items: center;
            padding: 15px 20px;
            border-bottom: 1px solid #36393f;
        }}
        .test-row:last-child {{ border-bottom: none; }}
        .test-info {{ flex: 1; }}
        .test-name {{ font-weight: 600; color: #f6f6f7; }}
        .test-doc {{ font-size: 13px; color: #b9bbbe; margin-top: 2px; }}
        .badge {{
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 0.5px;
        }}
        .badge.pass {{ background-color: rgba(67, 181, 129, 0.2); color: #43b581; }}
        .badge.fail {{ background-color: rgba(240, 71, 71, 0.2); color: #f04747; }}
        .badge.error {{ background-color: rgba(250, 166, 26, 0.2); color: #faa61a; }}
        .error-log {{
            background: #111214;
            color: #ff8383;
            padding: 12px;
            font-family: monospace;
            font-size: 12px;
            border-radius: 4px;
            margin-top: 10px;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Cram Execution Validation Engine</h1>
            <div class="meta">Executed on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Duration: {duration:.3f}s</div>
        </header>

        <div class="summary-cards">
            <div class="card pass">
                <div class="value">{passed}</div>
                <div class="label">Passed</div>
            </div>
            <div class="card {"fail" if failures > 0 else ""}">
                <div class="value">{failures}</div>
                <div class="label">Failures</div>
            </div>
            <div class="card {"fail" if errors > 0 else ""}">
                <div class="value">{errors}</div>
                <div class="label">Errors</div>
            </div>
            <div class="card">
                <div class="value">{total_tests}</div>
                <div class="label">Total Evaluated</div>
            </div>
        </div>

        {"".join(render_suite_html(suite_name, suite_tests) for suite_name, suite_tests in group_by_suite(result.results))}
    </div>
</body>
</html>
"""
    with open("test_report.html", "w") as f:
        f.write(html_template)


def group_by_suite(results):
    suites = {}
    for r in results:
        suites.setdefault(r["suite"], []).append(r)
    return suites.items()


def render_suite_html(suite_name, tests):
    rows = ""
    for t in tests:
        badge_class = t["status"].lower()
        error_block = f'<div class="error-log">{t["message"]}</div>' if t["message"] else ""
        rows += f"""
        <div class="test-row">
            <div class="test-info">
                <div class="test-name">{t["name"]}</div>
                <div class="test-doc">{t["doc"]}</div>
                {error_block}
            </div>
            <div>
                <span class="badge {badge_class}">{t["status"]}</span>
            </div>
        </div>"""
    
    return f"""
    <div class="suite-section">
        <div class="suite-header">{suite_name}</div>
        {rows}
    </div>"""


if __name__ == "__main__":
    import time
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    
    # Load all local components safely
    suite.addTests(loader.loadTestsFromTestCase(TestSAQANotionalHours))
    suite.addTests(loader.loadTestsFromTestCase(TestBurnDownCalculations))
    suite.addTests(loader.loadTestsFromTestCase(TestWeeklyPlannerAndDayStates))
    suite.addTests(loader.loadTestsFromTestCase(TestDailyRecommender))
    suite.addTests(loader.loadTestsFromTestCase(TestPersistenceSanity))

    runner_result = HTMLTestResult()
    
    start_time = time.time()
    suite.run(runner_result)
    end_time = time.time()
    
    generate_html_report(runner_result, end_time - start_time)
    print(f"🚀 Verification Complete! Total run count: {runner_result.testsRun}. Clean metrics written out to 'test_report.html'")