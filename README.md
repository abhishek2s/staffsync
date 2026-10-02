# staffsync

1. create virtual environment

2. install requirements.txt

```pip install -r requirements.txt```

3. freeze the requirements

```pip freeze > requirements.txt```


4. create a .env file with these fields

```DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=yourdbpassword
DB_SCHEMA=staging
```

5. run synthesizer.py

```python python/synthesizer.py --source data/raw/WA_Fn-UseC_-HR-Employee-Attrition.csv ```

6. run load_staging.py

```python python/load_staging.py```