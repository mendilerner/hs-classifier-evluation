import pandas as pd
df = pd.read_csv('classification-results.csv', index_col=0)
okay = df['predicted_code'].notna()
okay_df = df[okay]
missing = okay_df[okay_df['mas_knia_mismatch'].isna()]
print(missing[['predicted_code', 'actual_code', 'description']].to_string())
