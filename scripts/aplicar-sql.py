#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aplicar-sql — manda un fichero .sql a Postgres por la API de gestion de Supabase.

    python3 scripts/aplicar-sql.py db/schema.sql db/funciones.sql

Existia el hueco raro de que `db/schema.sql` y `db/funciones.sql` estaban versionados y NINGUN
script los aplicaba: se pegaban a mano en el editor SQL. Eso hace que «el esquema del repo» y «el
esquema de la base» sean dos cosas distintas sin que nadie lo note, que es exactamente el fallo
que `just hechos` existe para impedir en la documentacion.

Los dos ficheros son idempotentes a proposito (`create ... if not exists`, `alter ... add column
if not exists`, `create or replace function`), asi que correr esto dos veces no hace da~no.

El WAF de Cloudflare delante de `api.supabase.com` responde 403 `error code: 1010` al user-agent
por defecto de urllib — la misma trampa que costo una tanda de embeddings el 10-sep-2026.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

PROYECTO = "qbrgwphcpflbwhfqhffc"
API_SQL = f"https://api.supabase.com/v1/projects/{PROYECTO}/database/query"
AGENTE = "alonno-demo-sembrador/1.0"


def token():
    t = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if t:
        return t
    crudo = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest", "--secret", "devenv-supabase",
         "--project", "enerby-workstation"],
        capture_output=True, text=True, check=True).stdout.strip()
    return json.loads(crudo)["SUPABASE_ACCESS_TOKEN"]


def ejecutar(sql, tk):
    pet = urllib.request.Request(
        API_SQL,
        data=json.dumps({"query": sql}).encode(),
        headers={"Authorization": f"Bearer {tk}", "Content-Type": "application/json",
                 "User-Agent": AGENTE},
        method="POST")
    with urllib.request.urlopen(pet, timeout=180) as r:
        return json.loads(r.read())


def main():
    rutas = sys.argv[1:] or ["db/schema.sql", "db/funciones.sql"]
    tk = token()
    for ruta in rutas:
        with open(ruta, encoding="utf-8") as f:
            sql = f.read()
        try:
            ejecutar(sql, tk)
        except urllib.error.HTTPError as e:
            print(f"✗ {ruta}\n{e.read().decode()[:1200]}", file=sys.stderr)
            return 1
        print(f"✓ {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
