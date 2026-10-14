# StaffSync

StaffSync is a data engineering and analytics project for employee performance, project workload, and workforce trends. The system generates synthetic HR and project data, loads it into a MySQL-based medallion warehouse, and presents business insights through a Streamlit dashboard.

## Overview

The project follows a Bronze, Silver, and Gold architecture:

- Bronze: raw and staged data ingestion
- Silver: normalized 3NF OLTP model
- Gold: dimensional OLAP layer for reporting and dashboards

This makes the pipeline suitable for operational analytics, historical tracking, and executive reporting.

## Key Features

- Synthetic employee, project, assignment, and review data generation
- Medallion architecture for analytics workflows
- SCD Type 2 style historical employee changes
- MySQL-backed data storage and stored procedure execution
- Streamlit dashboard for KPI monitoring and workforce insights

## Tech Stack

- Python
- Pandas and NumPy
- SQLAlchemy
- MySQL
- Streamlit
- Faker and dotenv

## Project Structure

```text
staffsync/
├── app/
│   ├── main.py
│   └── pages/
├── config/
│   └── settings.py
├── data/
│   ├── raw/
│   └── synthetic/
├── docs/
├── logs/
├── sql/
├── src/
│   ├── dal/
│   ├── models/
│   ├── utils/
│   ├── db_manager.py
│   ├── loader.py
│   └── synthesizer.py
├── tests/
├── .env.example
├── run_pipeline.py
├── requirements.txt
└── README.md
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure your MySQL connection and project paths in your environment file.
4. Ensure the input data file exists in the raw data location.

## Running the Pipeline

Use the pipeline entry point to generate synthetic data and load it into the warehouse layers:

```bash
python run_pipeline.py
```

This executes the full workflow:

1. Generate synthetic datasets
2. Load data into the Bronze schema
3. Run the Silver transformation procedure
4. Run the Gold reporting load procedure

## Launching the Dashboard

Start the Streamlit app from the app directory:

```bash
streamlit run app/main.py
```

The app limits native numerical-library threads to reduce memory pressure
when Streamlit loads multiple pages and Pandas/NumPy initializes.

## Dashboard authentication and roles

The dashboard requires a login. Users are stored in the Silver database
schema. Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes; plaintext
passwords are never written to the database or source code.

Admin users can use Home, Data Entry, Analytics, and Directory. Viewer users
can use Home, Analytics, and Directory in read-only mode; Data Entry and the
warehouse refresh action are blocked.

Users can create an account from the sign-in page using the work email on
their employee record. The app assigns Admin to Human Resources employees and
Viewer to Sales and Research & Development employees, based on the current
department each time they sign in. Accounts cannot be created for emails that
are not present in the Silver employee tables.

Run the Silver schema script once. Admin or Viewer accounts can also be
provisioned manually:

```bash
python scripts/create_user.py alice Admin
python scripts/create_user.py analyst Viewer
```

The command prompts for each password without displaying or storing it.
Database credentials should be kept in `.env` locally or in your deployment
secret manager; never commit them to Git. This is a basic session-based login
intended for local/internal use; production deployments should place
authentication behind an identity provider.

## Environment Variables

The project reads configuration from `.env` files in the root and config directories. Typical values include MySQL host, port, credentials, and schema names.

Signup checks that the supplied email matches an employee record, but does not
verify control of that email address. Keep the app on a trusted internal
network or use a verified identity provider before exposing it publicly.

## Notes

The application is designed for local analytics and warehouse-style experimentation. It can be extended with additional business rules, data quality checks, and deployment automation for production workloads.
