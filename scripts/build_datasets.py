from pathlib import Path
import csv, datetime as dt
base = Path(__file__).resolve().parents[1]
out = base / 'datasets' / f'opportunity-snapshot-{dt.date.today().isoformat()}.csv'
rows = [
    ['category', 'opportunity', 'why_it_matters'],
    ['homelab', 'Used mini PC with extra RAM', 'Affordable lab starter with low power draw'],
    ['budget pc', 'Used GPU under market comps', 'Potential flip margin if condition is good'],
    ['privacy', 'Security key bundle', 'Useful starter item for privacy-conscious users']
]
with out.open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(rows)
print(out)
