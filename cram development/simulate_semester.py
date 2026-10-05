#!/usr/bin/env python3
"""
simulate_semester.py - Full 5-Module Production Stress Testing Engine for Cram.
Executes an all-inclusive, multi-iteration semester playback tracking your complete
academic curriculum block to comprehensively test algorithmic elasticity.
"""

import random
import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch

# Import exact framework structural units
from models import Module, Topic, Assignment, Assessment
from scheduler import WeeklyPlanner, DailyRecommender

# Complete 5-Module Production Dataset representation
RAW_MODULES_MOCK = {
    "active": [
        {
            "code": "600*", "name": "Statistics for Data Science", "nqf_level": 6, "credits": 15,
            "current_phase": 1, "ca_written": False, "ca": {"kind": "ca", "due_date": "2026-05-26"},
            "final": {"kind": "final", "due_date": "2026-06-18"}, "assignment": {"total_q": 3, "completed_q": 0, "due_date": "2026-05-28"},
            "topics": [
                {"number": 1, "name": "Types of Data and Steps of Data Science", "arc": "ca"},
                {"number": 2, "name": "Basic Mathematics", "arc": "ca"},
                {"number": 3, "name": "Probability Theory and Distributions", "arc": "ca"},
                {"number": 4, "name": "Basic Statistics", "arc": "final"},
                {"number": 5, "name": "Inferential Statistics", "arc": "final"},
                {"number": 6, "name": "Techniques for Communicating Data", "arc": "final"}
            ]
        },
        {
            "code": "622", "name": "Programming", "nqf_level": 6, "credits": 15,
            "current_phase": 1, "ca_written": False, "ca": {"kind": "ca", "due_date": "2026-05-13"},
            "final": {"kind": "final", "due_date": "2026-06-20"}, "assignment": {"total_q": 7, "completed_q": 0, "due_date": "2026-04-24"},
            "topics": [
                {"number": 1, "name": "Software Engineering Principles and C++ Classes", "arc": "ca"},
                {"number": 2, "name": "Standard Template Library (STL)", "arc": "ca"},
                {"number": 3, "name": "Linked Lists", "arc": "ca"},
                {"number": 4, "name": "Recursion", "arc": "ca"},
                {"number": 5, "name": "Stacks", "arc": "ca"},
                {"number": 6, "name": "Queues", "arc": "final"},
                {"number": 7, "name": "Searching and Hashing Algorithms", "arc": "final"},
                {"number": 8, "name": "Sorting Algorithms", "arc": "final"},
                {"number": 9, "name": "Binary Trees and B-Trees", "arc": "final"},
                {"number": 10, "name": "Graphs", "arc": "final"}
            ]
        },
        {
            "code": "600", "name": "Machine Learning", "nqf_level": 6, "credits": 10,
            "current_phase": 1, "ca_written": False, "ca": {"kind": "ca", "due_date": "2026-05-08"},
            "final": {"kind": "final", "due_date": "2026-06-15"}, "assignment": {"total_q": 6, "completed_q": 0, "due_date": "2026-05-28"},
            "topics": [
                {"number": 1, "name": "Introduction to Machine Learning", "arc": "ca"},
                {"number": 2, "name": "Data Preprocessing and Feature Engineering", "arc": "ca"},
                {"number": 3, "name": "Supervised Learning - Regression", "arc": "ca"},
                {"number": 4, "name": "Supervised Learning - Classification", "arc": "final"},
                {"number": 5, "name": "Unsupervised Learning - Clustering", "arc": "final"}
            ]
        },
        {
            "code": "622", "name": "Information Systems", "nqf_level": 6, "credits": 10,
            "current_phase": 1, "ca_written": False, "ca": {"kind": "ca", "due_date": "2026-05-04"},
            "final": {"kind": "final", "due_date": "2026-06-12"}, "assignment": {"total_q": 3, "completed_q": 0, "due_date": "2026-04-10"},
            "topics": [
                {"number": 1, "name": "Development Strategies", "arc": "ca"},
                {"number": 2, "name": "User Interface Design", "arc": "ca"},
                {"number": 3, "name": "Data Design", "arc": "ca"},
                {"number": 4, "name": "System Architecture", "arc": "final"},
                {"number": 5, "name": "Managing Systems Implementation", "arc": "final"},
                {"number": 6, "name": "Managing Systems Support and Security", "arc": "final"}
            ]
        },
        {
            "code": "600", "name": "Big Data and IoT", "nqf_level": 6, "credits": 10,
            "current_phase": 1, "ca_written": False, "ca": {"kind": "ca", "due_date": "2026-05-19"},
            "final": {"kind": "final", "due_date": "2026-06-19"}, "assignment": {"total_q": 4, "completed_q": 0, "due_date": "2026-04-24"},
            "topics": [
                {"number": 1, "name": "Big Data Analysis and Extraction Techniques", "arc": "ca"},
                {"number": 2, "name": "IoT Architectures and Applications", "arc": "ca"},
                {"number": 3, "name": "IoT Technologies and Standards", "arc": "ca"},
                {"number": 4, "name": "Big Data Storage and Security", "arc": "final"},
                {"number": 5, "name": "Strategy Development and Big Data Analytics", "arc": "final"}
            ]
        }
    ]
}

class FullSemesterSimulator:
    def __init__(self):
        self.start_date = datetime(2026, 2, 23)
        self.end_date = datetime(2026, 6, 20)
        self.iterations = {
            "Perfect Adherence (100%)": {"rate": 1.0, "color": "#43b581"},
            "Strategic Adherence (75%)": {"rate": 0.75, "color": "#faa61a"},
            "Low Adherence (45%)": {"rate": 0.45, "color": "#f04747"}
        }
        self.results = {}

    def run_single_track(self, profile_name, adherence_rate):
        random.seed(42)  # Maintain consistent randomization weights across different track configurations
        modules = [Module.from_dict(m) for m in RAW_MODULES_MOCK["active"]]
        planner = WeeklyPlanner()
        current_sim_date = self.start_date
        delta_day = timedelta(days=1)

        # Baseline randomized topic tracking limits
        topic_difficulty = {}
        for m in modules:
            for t in m.topics:
                topic_difficulty[f"{m.code}-{t.number}"] = {
                    1: random.uniform(3.0, 5.0),
                    2: random.uniform(5.0, 8.0),
                    3: random.uniform(8.0, 12.0)
                }

        while current_sim_date <= self.end_date:
            date_str = current_sim_date.strftime("%Y-%m-%d")

            # REPLACE WITH THIS NEW TIME-HORIZON BLOCK GEMINI recommendation 17/05/2026:
            for m in modules:
                ca_date = datetime.strptime(m.ca.due_date_str, "%Y-%m-%d") if m.ca.due_date_str else None
                final_date = datetime.strptime(m.final.due_date_str, "%Y-%m-%d") if m.final.due_date_str else None
                
                # Pre-CA milestone progression
                if not m.ca_written and ca_date:
                    days_to_ca = (ca_date - current_sim_date).days
                    if days_to_ca <= 0:
                        m.ca_written = True
                        m.current_phase = 4  # Move to new content post-CA immediately
                    elif days_to_ca <= 10:
                        m.current_phase = 3  # Phase 3: CA Review window
                    elif days_to_ca <= 45:
                        m.current_phase = 2  # Phase 2: Active Learning & Assignment window
                    else:
                        m.current_phase = 1  # Phase 1: First Exposure
                        
                # Post-CA milestone progression
                elif m.ca_written and final_date:
                    days_to_final = (final_date - current_sim_date).days
                    if days_to_final <= 14:
                        m.current_phase = 5  # Phase 5: Comprehensive Review window (2 weeks)
                    else:
                        m.current_phase = 4  # Phase 4: First pass of post-CA content
                
                # Progress assignment completion based on adherence rate
                if m.assignment and not m.assignment.is_complete and random.random() < adherence_rate:
                    m.assignment.complete_questions(1)

            # Framework Context Patching via Standard Library Wrappers
            with patch('models.datetime', wraps=datetime) as mock_models_dt, \
                 patch('scheduler.datetime', wraps=datetime) as mock_sched_dt:
                
                mock_models_dt.now.return_value = current_sim_date
                mock_sched_dt.now.return_value = current_sim_date

                recommender = DailyRecommender(modules, planner)
                recommendations = recommender.recommend()

                if recommendations:
                    for rec in recommendations:
                        if random.random() <= adherence_rate:
                            hours_spent = rec["hours"]
                        else:
                            hours_spent = rec["hours"] * random.choice([0.0, 0.25, 0.5])

                        if hours_spent > 0:
                            target_mod = next(m for m in modules if m.name == rec["module"].name)
                            target_topic = next(t for t in target_mod.topics if t.number == rec["topic"].number)
                            
                            target_topic.log_session(hours_spent)
                            planner.log_hours(hours_spent, date_str=date_str)

                            curr_conf = target_topic.confidence
                            if curr_conf < 4:
                                diff_key = f"{target_mod.code}-{target_topic.number}"
                                if target_topic.hours_studied >= topic_difficulty[diff_key][curr_conf]:
                                    target_topic.set_confidence(curr_conf + 1)

            current_sim_date += delta_day

        profile_summary = []
        for m in modules:
            profile_summary.append({
                "module_name": m.name,
                "total_budget": m.self_study_budget,
                "hours_spent": sum(t.hours_studied for t in m.topics),
                "avg_confidence": m.average_confidence(),
                "topics": [
                    {"number": t.number, "name": t.name, "hours": t.hours_studied, "confidence": t.confidence}
                    for t in m.topics
                ]
            })
        return profile_summary

    def execute_all_iterations(self):
        for name, config in self.iterations.items():
            self.results[name] = self.run_single_track(name, config["rate"])
        self.generate_comparison_html()

    def generate_comparison_html(self):
        matrix_rows = ""
        for name, modules in self.results.items():
            color = self.iterations[name]["color"]
            for m in modules:
                pct_met = (m["hours_spent"] / m["total_budget"]) * 100 if m["total_budget"] > 0 else 0
                matrix_rows += f"""
                <tr>
                    <td style="border-left: 5px solid {color}; font-weight: bold;">{name}</td>
                    <td>{m['module_name']}</td>
                    <td>{m['hours_spent']:.1f} / {m['total_budget']} hrs</td>
                    <td>
                        <div style="background:#111214; border-radius:4px; width:100px; height:8px; overflow:hidden; display:inline-block; margin-right:8px;">
                            <div style="background:{color}; width:{min(pct_met, 100):.0f}%; height:100%;"></div>
                        </div>
                        {pct_met:.1f}%
                    </td>
                    <td><strong style="color: #fff;">{m['avg_confidence']:.1f} / 4.0</strong></td>
                </tr>"""

        topic_breakdown_html = ""
        for name, modules in self.results.items():
            color = self.iterations[name]["color"]
            topic_breakdown_html += f"""
            <div class="iteration-block">
                <h3 style="color:{color}; border-bottom: 1px solid #3e3e3e; padding-bottom: 5px; margin-top:30px;">{name}</h3>
            """
            for m in modules:
                topic_breakdown_html += f"<h4>{m['module_name']}</h4>"
                topic_breakdown_html += "<table><thead><tr><th>Topic</th><th style='width: 200px;'>Time Expended</th><th>Final Confidence</th></tr></thead><tbody>"
                for t in m["topics"]:
                    conf_stars = "●" * t["confidence"] + "○" * (4 - t["confidence"])
                    topic_breakdown_html += f"""
                    <tr>
                        <td>T{t['number']} - {t['name']}</td>
                        <td><strong>{t['hours']:.1f} hrs</strong></td>
                        <td style="font-family: monospace; letter-spacing:2px; color:{color};">{conf_stars} (Lvl {t['confidence']})</td>
                    </tr>"""
                topic_breakdown_html += "</tbody></table>"
            topic_breakdown_html += "</div>"

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Cram Comprehensive 5-Module Adherence Optimization Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background-color: #1e1e1e; color: #dcddde; padding: 40px; margin: 0; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{ border-bottom: 1px solid #3e3e3e; padding-bottom: 20px; margin-bottom: 30px; }}
        h1 {{ margin: 0; color: #ffffff; }}
        h2 {{ color: #ffffff; margin-top: 40px; }}
        h4 {{ color: #7289da; margin-bottom: 5px; margin-top:20px; }}
        table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; background: #2f3136; border-radius: 6px; overflow: hidden; }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #36393f; font-size: 14px; }}
        th {{ background-color: #202225; color: #fff; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
        tr:last-child td {{ border-bottom: none; }}
        .summary-box {{ background: #2f3136; padding: 20px; border-radius: 8px; border-left: 5px solid #7289da; margin-bottom: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Cram Production Curriculum Sensitivity Matrix</h1>
            <div style="color: #72767d; margin-top: 5px;">Analysis of Model Elasticity across all 5 Academic Roster Modules</div>
        </header>

        <div class="summary-box">
            <h3>Full-Scale Workload Evaluation</h3>
            <p style="margin: 5px 0 0 0; font-size: 14px; line-height: 1.5; color: #b9bbbe;">
                This matrix monitors scheduling behavior when managing 5 concurrent subjects under the SAQA framework. 
                By incorporating all modules, you can observe how the scheduling pool handles overlapping deadlines. 
                When adherence slips, the system dynamically prioritizes low-confidence topics to prevent exam-week bottlenecks.
            </p>
        </div>

        <h2>Comparative Summary Matrix</h2>
        <table>
            <thead>
                <tr>
                    <th>Simulation Run Track</th>
                    <th>Module Profile Name</th>
                    <th>Time Budget Consumption</th>
                    <th>% Budget Met</th>
                    <th>Average Final Confidence</th>
                </tr>
            </thead>
            <tbody>
                {matrix_rows}
            </tbody>
        </table>

        <h2>Granular Topic Time Distributions</h2>
        {topic_breakdown_html}
    </div>
</body>
</html>
"""
        with open("semester_simulation_report.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("📊 5-Module multi-track simulation complete. Report generated safely at 'semester_simulation_report.html'.")

if __name__ == "__main__":
    simulator = FullSemesterSimulator()
    simulator.execute_all_iterations()