"""
Data synthesizer for the Employee Analytics Data Warehouse project.

What it does
    1. Reads the IBM HR Analytics CSV (1,470 rows) from a LOCAL file (--source).
    2. Scales it to 100,000+ employees (originals are kept unchanged, the
       extra rows are jittered copies with new Faker names and hire dates).
    3. Engineers SCD Type 2 history: for ~5% of employees it invents past
       department changes, promotions and salary hikes.
    4. Generates projects, assignments and yearly performance reviews that
       are consistent with each other (dates, allocations).
    5. Validates the result, then writes five CSV files that map 1:1 to the
       staging tables.

How the SCD2 history is stored
    stg_employee          = the CURRENT version of every employee.
                            `effective_from` is the date the current version began.
    stg_employee_history  = PREVIOUS (closed) versions, each with valid_from / valid_to.
    So an employee with one past change has 1 history row + 1 snapshot row.

Usage
    python data_synthesizer.py --source data/raw/WA_Fn-UseC_-HR-Employee-Attrition.csv
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

REFERENCE_DATE = pd.Timestamp("2025-12-31")  # "today" inside the synthetic world
REVIEW_YEARS = (2023, 2024, 2025)
PROJECT_START_MIN = pd.Timestamp("2016-01-01")
PROJECT_START_MAX = pd.Timestamp("2023-06-30")  # before the first review (Dec 2023)
DROP_COLUMNS = ["employee_count", "employee_number", "over18", "standard_hours"]
REQUIRED_COLUMNS = [
    "age", "attrition", "department", "job_role", "job_level", "monthly_income",
    "years_at_company", "performance_rating", "gender", "job_satisfaction",
    "work_life_balance", "environment_satisfaction",
]


def to_snake(name: str) -> str:
    """BusinessTravel -> business_travel"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class DataSynthesizer:
    def __init__(
        self,
        source_csv: str,
        out_dir: str = "data/synthetic",
        target_rows: int = 100_000,
        history_share: float = 0.05,
        n_projects: int = 1000,
        seed: int = 42,
    ) -> None:
        self.source_csv = Path(source_csv)
        self.out_dir = Path(out_dir)
        self.target_rows = target_rows
        self.history_share = history_share
        self.n_projects = n_projects
        self.rng = np.random.default_rng(seed)
        Faker.seed(seed)
        self.fake = Faker("en_IN")

        self.base: pd.DataFrame | None = None
        self.employees: pd.DataFrame | None = None
        self.history: pd.DataFrame | None = None
        self.projects: pd.DataFrame | None = None
        self.assignments: pd.DataFrame | None = None
        self.reviews: pd.DataFrame | None = None
        self._dept_roles: dict[str, list[str]] = {}

    # ------------------------------------------------------------------ load
    def load_base(self) -> None:
        try:
            df = pd.read_csv(self.source_csv)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Could not find {self.source_csv}. Download the IBM HR Analytics "
                "dataset from Kaggle, save it under data/raw/ and pass its path with --source."
            ) from exc
        df.columns = [to_snake(c) for c in df.columns]
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Source CSV is missing expected columns: {missing}")
        df = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns])
        self.base = df
        self._dept_roles = {
            dept: sorted(group["job_role"].unique())
            for dept, group in df.groupby("department")
        }

    # ------------------------------------------------------------- employees
    def build_employees(self) -> None:
        base = self.base
        n_base, n = len(base), self.target_rows
        if n < n_base:
            raise ValueError("target_rows must be at least the size of the base data")

        extra = base.iloc[self.rng.integers(0, n_base, size=n - n_base)].copy()
        k = len(extra)
        extra["age"] = (extra["age"] + self.rng.integers(-3, 4, k)).clip(18, 60)

        # Keep HR numbers realistic after the age change (work years cannot
        # exceed age - 18, tenure cannot exceed work years, and so on).
        def cap(col: str, limit) -> None:
            if col in extra.columns:
                extra[col] = np.minimum(extra[col], limit)

        cap("total_working_years", np.maximum(extra["age"] - 18, 0))
        if "total_working_years" in extra.columns:
            cap("years_at_company", extra["total_working_years"])
        for col in ("years_in_current_role", "years_with_curr_manager",
                    "years_since_last_promotion"):
            cap(col, extra["years_at_company"])

        for col in ("monthly_income", "hourly_rate", "daily_rate", "monthly_rate"):
            if col in extra:
                factor = self.rng.uniform(0.9, 1.1, k)
                extra[col] = (extra[col] * factor).round().astype(int)
        if "distance_from_home" in extra:
            extra["distance_from_home"] = (
                extra["distance_from_home"] + self.rng.integers(-2, 3, k)
            ).clip(1, 29)

        emp = pd.concat([base, extra], ignore_index=True)
        n_total = len(emp)
        emp.insert(0, "employee_id", np.arange(1, n_total + 1))

        # Names: build small gender-aware pools with Faker, then sample (fast).
        male = np.array([self.fake.first_name_male() for _ in range(2000)])
        female = np.array([self.fake.first_name_female() for _ in range(2000)])
        last = np.array([self.fake.last_name() for _ in range(2000)])
        is_male = (emp["gender"] == "Male").to_numpy()
        emp["first_name"] = np.where(
            is_male, self.rng.choice(male, n_total), self.rng.choice(female, n_total)
        )
        emp["last_name"] = self.rng.choice(last, n_total)

        def clean(s: pd.Series) -> pd.Series:
            return s.str.lower().str.replace(r"[^a-z]", "", regex=True)

        emp["email"] = (
            clean(emp["first_name"]) + "." + clean(emp["last_name"]) + "."
            + emp["employee_id"].astype(str) + "@company.com"
        )

        days = (emp["years_at_company"] * 365 + self.rng.integers(0, 330, n_total)).to_numpy()
        emp["hire_date"] = REFERENCE_DATE - pd.to_timedelta(days, unit="D")
        emp["effective_from"] = emp["hire_date"]

        lead = ["employee_id", "first_name", "last_name", "email", "hire_date", "effective_from"]
        self.employees = emp[lead + [c for c in emp.columns if c not in lead]]

    # --------------------------------------------------------------- history
    def _undo_change(self, cur: dict, departments: list[str]) -> tuple[dict, str]:
        """Given the attributes AFTER a change, invent the attributes BEFORE it."""
        kind = str(self.rng.choice(
            ["DEPARTMENT_CHANGE", "PROMOTION", "SALARY_HIKE"], p=[0.35, 0.25, 0.40]
        ))
        if kind == "PROMOTION" and cur["job_level"] <= 1:
            kind = "SALARY_HIKE"  # cannot be promoted from below level 1
        prev = dict(cur)
        if kind == "DEPARTMENT_CHANGE":
            options = [d for d in departments if d != cur["department"]]
            prev["department"] = str(self.rng.choice(options))
            prev["job_role"] = str(self.rng.choice(self._dept_roles[prev["department"]]))
        elif kind == "PROMOTION":
            prev["job_level"] = cur["job_level"] - 1
            prev["monthly_income"] = int(round(cur["monthly_income"] / self.rng.uniform(1.15, 1.30)))
        else:
            prev["monthly_income"] = int(round(cur["monthly_income"] / self.rng.uniform(1.05, 1.12)))
        return prev, kind

    def build_history(self) -> None:
        emp = self.employees
        departments = sorted(self._dept_roles)
        eligible = emp.loc[emp["years_at_company"] >= 2, "employee_id"].to_numpy()
        n_sel = min(int(len(emp) * self.history_share), len(eligible))
        chosen = set(self.rng.choice(eligible, n_sel, replace=False).tolist())
        subset = emp[emp["employee_id"].isin(chosen)]

        rows: list[dict] = []
        last_change: dict[int, pd.Timestamp] = {}
        one_day = pd.Timedelta(days=1)

        for r in subset.itertuples(index=False):
            hire = r.hire_date
            tenure = (REFERENCE_DATE - hire).days
            if self.rng.random() < 0.25:  # two changes
                d1 = int(self.rng.integers(180, tenure // 2))
                d2 = int(self.rng.integers(tenure // 2 + 30, tenure - 60))
                offsets = [d1, d2]
            else:
                offsets = [int(self.rng.integers(180, tenure - 60))]
            dates = [hire + pd.Timedelta(days=o) for o in offsets]

            cur = {
                "department": r.department,
                "job_role": r.job_role,
                "job_level": int(r.job_level),
                "monthly_income": int(r.monthly_income),
            }
            last_change[r.employee_id] = dates[-1]

            # walk backwards from the current version, peeling off one change at a time
            for i in range(len(dates) - 1, -1, -1):
                prev, reason = self._undo_change(cur, departments)
                rows.append({
                    "employee_id": r.employee_id,
                    **prev,
                    "valid_from": dates[i - 1] if i > 0 else hire,
                    "valid_to": dates[i] - one_day,
                    "change_reason": reason,
                })
                cur = prev

        self.history = pd.DataFrame(rows).sort_values(["employee_id", "valid_from"]).reset_index(drop=True)
        self.history.insert(0, "history_id", np.arange(1, len(self.history) + 1))

        mask = self.employees["employee_id"].isin(last_change)
        self.employees.loc[mask, "effective_from"] = (
            self.employees.loc[mask, "employee_id"].map(last_change)
        )

    # -------------------------------------------------------------- projects
    def build_projects(self) -> None:
        """
        ~75% of projects are Active (end date after the reference date); the rest
        are Completed (ended before it). All projects start before the first
        review date, so any employee's review can safely point at an Active project.
        """
        n = self.n_projects
        departments = sorted(self._dept_roles)
        span = (PROJECT_START_MAX - PROJECT_START_MIN).days
        start = PROJECT_START_MIN + pd.to_timedelta(self.rng.integers(0, span, n), unit="D")

        is_active = self.rng.random(n) < 0.75
        active_end = REFERENCE_DATE + pd.to_timedelta(self.rng.integers(30, 800, n), unit="D")
        done_end = start + pd.to_timedelta(self.rng.integers(365, 1500, n), unit="D")
        done_end = np.minimum(done_end.values, (REFERENCE_DATE - pd.Timedelta(days=1)).to_datetime64())
        end = np.where(is_active, active_end.values, done_end)

        self.projects = pd.DataFrame({
            "project_id": np.arange(1, n + 1),
            "project_name": [f"PRJ-{i:04d} {self.fake.bs().title()}" for i in range(1, n + 1)],
            "department": self.rng.choice(departments, n),
            "start_date": start,
            "planned_end_date": pd.to_datetime(end),
            "status": np.where(is_active, "Active", "Completed"),
            "budget": self.rng.integers(50_000, 5_000_000, n),
        })

    def build_assignments(self) -> None:
        """
        Every employee gets one main assignment on an ACTIVE project of their
        department. About a third also get a second assignment, allocated so the
        total never exceeds 100%. A second assignment is only kept if the employee
        was hired before that project ended.
        """
        emp, proj = self.employees, self.projects
        start_map = proj.set_index("project_id")["start_date"]
        end_map = proj.set_index("project_id")["planned_end_date"]
        parts = []
        for dept, group in emp.groupby("department"):
            dept_proj = proj[proj["department"] == dept]
            active_pool = dept_proj.loc[dept_proj["status"] == "Active", "project_id"].to_numpy()
            all_pool = dept_proj["project_id"].to_numpy()
            if len(active_pool) == 0:
                raise ValueError(f"No Active projects generated for department {dept}")
            ids = group["employee_id"].to_numpy()
            hires = group["hire_date"].to_numpy()

            first = self.rng.choice(active_pool, len(ids))
            first_alloc = self.rng.choice([50, 75, 100], len(ids), p=[0.4, 0.3, 0.3])
            parts.append(pd.DataFrame({
                "employee_id": ids, "project_id": first,
                "allocation_pct": first_alloc, "hire_date": hires,
            }))

            second = self.rng.choice(all_pool, len(ids))
            second_end = end_map.reindex(second).to_numpy()
            keep = (
                (self.rng.random(len(ids)) < 0.5)
                & (first_alloc < 100)
                & (second != first)
                & (hires <= second_end)
            )
            parts.append(pd.DataFrame({
                "employee_id": ids[keep], "project_id": second[keep],
                "allocation_pct": 100 - first_alloc[keep], "hire_date": hires[keep],
            }))

        a = pd.concat(parts, ignore_index=True).sort_values("employee_id", kind="stable")
        proj_start = a["project_id"].map(start_map)
        a["assigned_date"] = a["hire_date"].where(a["hire_date"] > proj_start, proj_start)
        a["role_on_project"] = self.rng.choice(
            ["Developer", "Analyst", "Lead", "Tester", "Coordinator"], len(a)
        )
        a = a.drop(columns="hire_date").reset_index(drop=True)
        a.insert(0, "assignment_id", np.arange(1, len(a) + 1))
        self.assignments = a[[
            "assignment_id", "employee_id", "project_id",
            "assigned_date", "role_on_project", "allocation_pct",
        ]]

    # --------------------------------------------------------------- reviews
    def build_reviews(self) -> None:
        emp = self.employees
        # main (first) assignment = an Active project the employee has been on since hire
        first_project = (
            self.assignments.drop_duplicates("employee_id").set_index("employee_id")["project_id"]
        )
        # ratings drift upward year over year so the dashboard has a trend to show
        shifts = {2023: [0.20, 0.60, 0.20], 2024: [0.15, 0.60, 0.25], 2025: [0.10, 0.55, 0.35]}
        frames = []
        for year in REVIEW_YEARS:
            review_date = pd.Timestamp(year=year, month=12, day=15)
            eligible = emp[emp["hire_date"] <= review_date - pd.Timedelta(days=90)]
            n = len(eligible)
            delta = self.rng.choice([-1, 0, 1], size=n, p=shifts[year])
            rating = np.clip(eligible["performance_rating"].to_numpy() + delta, 1, 5)
            score = np.clip(rating * 20 + self.rng.normal(0, 6, n), 0, 100).round(1)

            def satisfaction(col: str) -> np.ndarray:
                return np.clip(eligible[col].to_numpy() + self.rng.integers(-1, 2, n), 1, 4)

            frames.append(pd.DataFrame({
                "employee_id": eligible["employee_id"].to_numpy(),
                "project_id": eligible["employee_id"].map(first_project).to_numpy(),
                "review_date": review_date,
                "performance_rating": rating,
                "review_score": score,
                "job_satisfaction": satisfaction("job_satisfaction"),
                "work_life_balance": satisfaction("work_life_balance"),
                "environment_satisfaction": satisfaction("environment_satisfaction"),
            }))
        reviews = pd.concat(frames, ignore_index=True)
        reviews.insert(0, "review_id", np.arange(1, len(reviews) + 1))
        self.reviews = reviews

    # ------------------------------------------------------------ validation
    def validate(self) -> None:
        emp, hist = self.employees, self.history
        proj, asg, rev = self.projects, self.assignments, self.reviews

        def fail(msg: str) -> None:
            raise ValueError(f"Validation failed: {msg}")

        # employees
        if not emp["employee_id"].is_unique:
            fail("employee_id is not unique")
        if not emp["email"].is_unique:
            fail("email is not unique")
        if emp.isna().any().any():
            fail("employees contain missing values")
        if "total_working_years" in emp.columns:
            if (emp["total_working_years"] > emp["age"] - 18).any():
                fail("an employee's total_working_years exceeds age - 18")
            if (emp["years_at_company"] > emp["total_working_years"]).any():
                fail("an employee's years_at_company exceeds total_working_years")
        if (emp["hire_date"] > REFERENCE_DATE).any():
            fail("a hire_date is in the future")

        # SCD2 history
        if (hist["valid_from"] > hist["valid_to"]).any():
            fail("a history row has valid_from after valid_to")
        last_to = hist.groupby("employee_id")["valid_to"].max()
        current_from = emp.set_index("employee_id").loc[last_to.index, "effective_from"]
        if not (last_to < current_from).all():
            fail("a history version overlaps the current version")
        if (hist["valid_from"] < hist["employee_id"].map(emp.set_index("employee_id")["hire_date"])).any():
            fail("a history version starts before the hire date")

        # projects, assignments, reviews must agree with each other
        pj = proj.set_index("project_id")
        if (proj["start_date"] >= proj["planned_end_date"]).any():
            fail("a project ends before it starts")
        a_end = asg["project_id"].map(pj["planned_end_date"])
        if (asg["assigned_date"] > a_end).any():
            fail("an assignment starts after its project ended")
        a_hire = asg["employee_id"].map(emp.set_index("employee_id")["hire_date"])
        if (asg["assigned_date"] < a_hire).any():
            fail("an assignment starts before the employee was hired")
        if (asg.groupby("employee_id")["allocation_pct"].sum() > 100).any():
            fail("an employee is allocated more than 100%")
        if (emp["employee_id"].isin(asg["employee_id"]) == False).any():  # noqa: E712
            fail("an employee has no assignment")
        r_start = rev["project_id"].map(pj["start_date"])
        r_end = rev["project_id"].map(pj["planned_end_date"])
        if ((rev["review_date"] < r_start) | (rev["review_date"] > r_end)).any():
            fail("a review is dated outside its project's lifetime")
        if not rev["performance_rating"].between(1, 5).all():
            fail("performance_rating outside 1-5")
        for col in ("job_satisfaction", "work_life_balance", "environment_satisfaction"):
            if not rev[col].between(1, 4).all():
                fail(f"{col} outside 1-4")
        if rev.isna().any().any():
            fail("reviews contain missing values")

    # ----------------------------------------------------------------- output
    def write_csvs(self) -> dict[str, tuple[int, int]]:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        tables = {
            "stg_employee": self.employees,
            "stg_employee_history": self.history,
            "stg_project": self.projects,
            "stg_assignment": self.assignments,
            "stg_review": self.reviews,
        }
        for name, df in tables.items():
            df.to_csv(self.out_dir / f"{name}.csv", index=False, date_format="%Y-%m-%d")
        return {name: df.shape for name, df in tables.items()}

    def run(self) -> dict[str, tuple[int, int]]:
        t0 = time.time()
        steps = [
            ("Loading base data", self.load_base),
            ("Scaling employees", self.build_employees),
            ("Engineering SCD2 history", self.build_history),
            ("Building projects", self.build_projects),
            ("Building assignments", self.build_assignments),
            ("Building reviews", self.build_reviews),
            ("Validating", self.validate),
        ]
        for label, step in steps:
            print(f"{label}...", flush=True)
            step()
        shapes = self.write_csvs()
        print(f"\nValidation passed. Done in {time.time() - t0:.1f}s. Files written to {self.out_dir}:")
        for name, (rows, cols) in shapes.items():
            print(f"  {name:<22}{rows:>10,} rows  x {cols} columns")
        return shapes


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthesize the employee data warehouse dataset")
    parser.add_argument("--source", required=True, help="path to the IBM HR Analytics CSV")
    parser.add_argument("--out", default="data/synthetic", help="output folder")
    parser.add_argument("--rows", type=int, default=100_000, help="number of employees")
    parser.add_argument("--history-share", type=float, default=0.05, help="share of employees with SCD2 history")
    parser.add_argument("--projects", type=int, default=1000, help="number of projects")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    DataSynthesizer(
        args.source, args.out, args.rows, args.history_share, args.projects, args.seed
    ).run()


if __name__ == "__main__":
    main()