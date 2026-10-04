from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from src.utils.logger import setup_logger

logger = setup_logger("DataSynthesizer")

REFERENCE_DATE = pd.Timestamp("2025-12-31")
REVIEW_YEARS = (2023, 2024, 2025)
PROJECT_START_MIN = pd.Timestamp("2016-01-01")
PROJECT_START_MAX = pd.Timestamp("2023-06-30")
DROP_COLUMNS = ["employee_count", "employee_number", "over18", "standard_hours"]
REQUIRED_COLUMNS = [
    "age", "attrition", "department", "job_role", "job_level", "monthly_income",
    "years_at_company", "performance_rating", "gender", "job_satisfaction",
    "work_life_balance", "environment_satisfaction",
]


def to_snake(name: str) -> str:
    """Convert a PascalCase column name into snake_case."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class DataSynthesizer:
    """Generate synthetic workforce, review, and project datasets."""

    def __init__(
        self,
        source_csv: str | None = None,
        out_dir: str | None = None,
        target_rows: int = 100_000,
        history_share: float = 0.05,
        n_projects: int = 1000,
        seed: int = 42,
    ) -> None:
        self.source_csv = Path(source_csv or os.getenv("RAW_DATA_PATH", "data/raw/WA_Fn-UseC_-HR-Employee-Attrition.csv"))
        self.out_dir = Path(out_dir or os.getenv("DATA_DIR", "data/synthetic"))
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

    def load_base(self) -> None:
        if not self.source_csv.exists():
            logger.error(f"Source file missing at {self.source_csv}")
            raise FileNotFoundError(f"Download IBM HR dataset to {self.source_csv}")
        logger.info(f"Loading raw baseline dataset from {self.source_csv}...")
        df = pd.read_csv(self.source_csv)
        df.columns = [to_snake(c) for c in df.columns]
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Source CSV missing required columns: {missing}")
        df = df.drop(columns=[c for c in DROP_COLUMNS if c in df.columns])
        self.base = df
        self._dept_roles = {
            dept: sorted(group["job_role"].unique())
            for dept, group in df.groupby("department")
        }

    def build_employees(self) -> None:
        base = self.base
        n_base, n = len(base), self.target_rows
        logger.info(f"Scaling employee dataset from {n_base:,} to {n:,} rows...")
        extra = base.iloc[self.rng.integers(0, n_base, size=n - n_base)].copy()
        k = len(extra)
        extra["age"] = (extra["age"] + self.rng.integers(-3, 4, k)).clip(18, 60)

        def cap(col: str, limit) -> None:
            if col in extra.columns:
                extra[col] = np.minimum(extra[col], limit)

        cap("total_working_years", np.maximum(extra["age"] - 18, 0))
        if "total_working_years" in extra.columns:
            cap("years_at_company", extra["total_working_years"])
        for col in ("years_in_current_role", "years_with_curr_manager", "years_since_last_promotion"):
            cap(col, extra["years_at_company"])

        for col in ("monthly_income", "hourly_rate", "daily_rate", "monthly_rate"):
            if col in extra:
                factor = self.rng.uniform(0.9, 1.1, k)
                extra[col] = (extra[col] * factor).round().astype(int)

        emp = pd.concat([base, extra], ignore_index=True)
        n_total = len(emp)
        emp.insert(0, "employee_id", np.arange(1, n_total + 1))

        males = np.array([self.fake.first_name_male() for _ in range(2000)])
        females = np.array([self.fake.first_name_female() for _ in range(2000)])
        lasts = np.array([self.fake.last_name() for _ in range(2000)])
        is_male = (emp["gender"] == "Male").to_numpy()
        emp["first_name"] = np.where(is_male, self.rng.choice(males, n_total), self.rng.choice(females, n_total))
        emp["last_name"] = self.rng.choice(lasts, n_total)

        def clean(s: pd.Series) -> pd.Series:
            return s.str.lower().str.replace(r"[^a-z]", "", regex=True)

        emp["email"] = clean(emp["first_name"]) + "." + clean(emp["last_name"]) + "." + emp["employee_id"].astype(str) + "@company.com"
        days = (emp["years_at_company"] * 365 + self.rng.integers(0, 330, n_total)).to_numpy()
        emp["hire_date"] = REFERENCE_DATE - pd.to_timedelta(days, unit="D")
        emp["effective_from"] = emp["hire_date"]

        lead = ["employee_id", "first_name", "last_name", "email", "hire_date", "effective_from"]
        self.employees = emp[lead + [c for c in emp.columns if c not in lead]]

    def _undo_change(self, cur: dict, departments: list[str]) -> tuple[dict, str]:
        kind = str(self.rng.choice(["DEPARTMENT_CHANGE", "PROMOTION", "SALARY_HIKE"], p=[0.35, 0.25, 0.40]))
        if kind == "PROMOTION" and cur["job_level"] <= 1:
            kind = "SALARY_HIKE"
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
        logger.info("Engineering synthetic historical changes (SCD Type 2 snapshot records)...")
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
            offsets = [int(self.rng.integers(180, tenure - 60))]
            dates = [hire + pd.Timedelta(days=o) for o in offsets]

            cur = {
                "department": r.department,
                "job_role": r.job_role,
                "job_level": int(r.job_level),
                "monthly_income": int(r.monthly_income),
            }
            last_change[r.employee_id] = dates[-1]

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
        self.employees.loc[mask, "effective_from"] = self.employees.loc[mask, "employee_id"].map(last_change)

    def build_projects(self) -> None:
        logger.info("Generating project master records...")
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
        logger.info("Generating project assignment records...")
        emp, proj = self.employees, self.projects
        start_map = proj.set_index("project_id")["start_date"]
        parts = []
        for dept, group in emp.groupby("department"):
            dept_proj = proj[proj["department"] == dept]
            active_pool = dept_proj.loc[dept_proj["status"] == "Active", "project_id"].to_numpy()
            ids = group["employee_id"].to_numpy()
            hires = group["hire_date"].to_numpy()
            first = self.rng.choice(active_pool, len(ids))
            first_alloc = self.rng.choice([50, 75, 100], len(ids), p=[0.4, 0.3, 0.3])
            parts.append(pd.DataFrame({
                "employee_id": ids, "project_id": first,
                "allocation_pct": first_alloc, "hire_date": hires,
            }))

        a = pd.concat(parts, ignore_index=True).sort_values("employee_id", kind="stable")
        proj_start = a["project_id"].map(start_map)
        a["assigned_date"] = a["hire_date"].where(a["hire_date"] > proj_start, proj_start)
        a["role_on_project"] = self.rng.choice(["Developer", "Analyst", "Lead", "Tester", "Coordinator"], len(a))
        a = a.drop(columns="hire_date").reset_index(drop=True)
        a.insert(0, "assignment_id", np.arange(1, len(a) + 1))
        self.assignments = a[["assignment_id", "employee_id", "project_id", "assigned_date", "role_on_project", "allocation_pct"]]

    def build_reviews(self) -> None:
        logger.info("Generating yearly performance review records...")
        emp = self.employees
        first_project = self.assignments.drop_duplicates("employee_id").set_index("employee_id")["project_id"]
        shifts = {2023: [0.20, 0.60, 0.20], 2024: [0.15, 0.60, 0.25], 2025: [0.10, 0.55, 0.35]}
        frames = []
        for year in REVIEW_YEARS:
            review_date = pd.Timestamp(year=year, month=12, day=15)
            eligible = emp[emp["hire_date"] <= review_date - pd.Timedelta(days=90)]
            n = len(eligible)
            delta = self.rng.choice([-1, 0, 1], size=n, p=shifts[year])
            rating = np.clip(eligible["performance_rating"].to_numpy() + delta, 1, 5)
            score = np.clip(rating * 20 + self.rng.normal(0, 6, n), 0, 100).round(1)

            frames.append(pd.DataFrame({
                "employee_id": eligible["employee_id"].to_numpy(),
                "project_id": eligible["employee_id"].map(first_project).to_numpy(),
                "review_date": review_date,
                "performance_rating": rating,
                "review_score": score,
                "job_satisfaction": np.clip(eligible["job_satisfaction"].to_numpy() + self.rng.integers(-1, 2, n), 1, 4),
                "work_life_balance": np.clip(eligible["work_life_balance"].to_numpy() + self.rng.integers(-1, 2, n), 1, 4),
                "environment_satisfaction": np.clip(eligible["environment_satisfaction"].to_numpy() + self.rng.integers(-1, 2, n), 1, 4),
            }))
        reviews = pd.concat(frames, ignore_index=True)
        reviews.insert(0, "review_id", np.arange(1, len(reviews) + 1))
        self.reviews = reviews

    def _inject_noise(self) -> None:
        """Injects ~1% controlled imperfections (duplicates, NULLs, casing issues) into staging."""
        logger.info("Injecting controlled staging noise (duplicates, NULLs, formatting variations)...")
        
        # 1. Inject NULLs into optional employee field (education_field)
        null_mask = self.rng.random(len(self.employees)) < 0.01
        self.employees.loc[null_mask, "education_field"] = None

        # 2. Inject casing variations into department names
        dept_mask = self.rng.random(len(self.employees)) < 0.02
        self.employees.loc[dept_mask, "department"] = self.employees.loc[dept_mask, "department"].str.lower()

        # 3. Inject ~1% duplicate employee rows to simulate duplicate landing payloads
        dup_count = int(len(self.employees) * 0.01)
        duplicates = self.employees.iloc[self.rng.integers(0, len(self.employees), size=dup_count)].copy()
        self.employees = pd.concat([self.employees, duplicates], ignore_index=True)

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
            out_file = self.out_dir / f"{name}.csv"
            df.to_csv(out_file, index=False, date_format="%Y-%m-%d")
            logger.info(f"Exported CSV: {out_file} ({len(df):,} rows)")
        return {name: df.shape for name, df in tables.items()}

    def run(self) -> dict[str, tuple[int, int]]:
        self.load_base()
        self.build_employees()
        self.build_history()
        self.build_projects()
        self.build_assignments()
        self.build_reviews()
        self._inject_noise()
        return self.write_csvs()