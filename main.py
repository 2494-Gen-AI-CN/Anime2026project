import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

data = pd.read_csv('profiles.csv')
df = pd.DataFrame(data)

# Extracts the birth year from the "birthday" column
df['birth_year'] = df['birthday'].str.extract(r'(\d{4})')[0]
df['birth_year'] = pd.to_numeric(df['birth_year']).astype('Int64')

gender_counts = df["gender"].value_counts()
birthday_counts = df['birth_year'].value_counts().sort_index()

fig, ax = plt.subplots(figsize=(12, 6))

ax.bar(birthday_counts.index.astype(int), birthday_counts.values, color="red")
ax.set_title("Favourite Animes Listed By Birth Year")
ax.set_xlabel("Birth Years")
ax.set_ylabel("Amount of Users")

plt.tight_layout()
plt.show()
plt.close(fig)