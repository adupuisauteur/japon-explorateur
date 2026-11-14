"""Empreinte de chaque ligne de chaque table (indépendante du code). Usage : snapshot.py NOM_BASE SORTIE.json"""
import json, sys
import psycopg
db, out = sys.argv[1], sys.argv[2]
with psycopg.connect(host="localhost", user="postgres", dbname=db) as c:
    tables = [r[0] for r in c.execute("select tablename from pg_tables where schemaname='public' order by 1")]
    snap = {}
    for t in tables:
        rows = c.execute(f'select md5(x::text) from "{t}" x').fetchall()
        snap[t] = sorted(r[0] for r in rows)
json.dump(snap, open(out, "w"))
print(f"{len(snap)} tables, {sum(len(v) for v in snap.values())} lignes")
