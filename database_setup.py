import os
import pandas as pd
from sqlalchemy import create_engine

engine = create_engine("sqlite:///datasage.db")

csv_folder = "public_release_csv"

for file in os.listdir(csv_folder):
    if file.endswith(".csv"):
        path = os.path.join(csv_folder, file)

        table_name = file.replace(".csv", "")

        print(f"Loading {table_name}...")

        df = pd.read_csv(path)

        df.to_sql(
            table_name,
            engine,
            if_exists="replace",
            index=False
        )

        print(f"✓ Loaded {len(df)} rows")

print("\nDatabase created successfully!")