import pandas as pd
import os

folder = "public_release_csv"

with pd.ExcelWriter("datasage.xlsx") as writer:
    for file in os.listdir(folder):
        if file.endswith(".csv"):
            df = pd.read_csv(os.path.join(folder, file))

            sheet_name = file.replace(".csv", "")[:31]

            df.to_excel(
                writer,
                sheet_name=sheet_name,
                index=False
            )

print("Excel file created!")