import json, sys
a, b = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
lost = {t: len(set(v) - set(b.get(t, []))) for t, v in a.items() if set(v) - set(b.get(t, []))}
missing_tables = [t for t in a if t not in b]
added_tables = [t for t in b if t not in a]
added_rows = {t: len(set(b[t]) - set(a[t])) for t in a if t in b and set(b[t]) - set(a[t])}
print("tables disparues :", missing_tables)
print("lignes perdues ou modifiées :", lost)
print("tables ajoutées :", len(added_tables), sorted(added_tables)[:20])
print("lignes ajoutées dans des tables existantes :", added_rows)
