import pandas as pd

with open('description-with-classification-from-db.csv') as f:
    test_data = pd.read_csv(f,

                            dtype=str
                            )


# save to file with line numbers
test_data.to_csv('description-with-classification-from-db-ln.csv'
                 )
