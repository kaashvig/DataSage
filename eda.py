import pandas as pd
import os

for file in os.listdir("public_release_csv"):
    if file.endswith(".csv"):
        df = pd.read_csv(f"public_release_csv/{file}")
        print("\n")
        print(file)
        print(df.columns.tolist())