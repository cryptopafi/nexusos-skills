# Correlation Analysis for Portfolio Construction (Python)

[FINANCE] Correlation Analysis for Portfolio Construction (Python) — Procedura Standard de Operare
Scope: Calculul și interpretarea matricei de corelație între active financiare pentru construcția unui portofoliu diversificat care minimizează riscul prin selectarea activelor cu corelație scăzută.
Steps:
- Colectarea returnurilor pentru 5-10 active diversificate
- Calculul matricei de corelație cu pd.DataFrame.corr()
- Vizualizarea heat map cu seaborn
- Identificarea perechilor cu corelație ridicată (>0.8)
- Identificarea perechilor cu corelație scăzută/negativă (<0.3) pentru diversificare
- Calculul impactului corelației portofoliului
- Construirea portofoliului diversificat minimizând corelația