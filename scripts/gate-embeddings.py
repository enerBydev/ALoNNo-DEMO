#!/usr/bin/env python3
# Gate del §8 del brief: elegir el modelo de embeddings MIDIENDO, no por preferencia.
#
#   uv run --with openai python scripts/gate-embeddings.py
#
# Mide recall@1 cross-lingua sobre pares DE<->EN construidos con las frases REALES de Helder
# (§9-A): cada frase alemana debe recuperar su equivalente inglesa entre todas las demas.
# Imprime ademas el margen medio —cuanto le saca el par correcto al mejor impostor—, que es
# lo que dice si el resultado aguanta o va justo.
#
# Resultado del 9 de septiembre de 2026:
#
#   nemotron-3-embed-1b     2048 dim · 8/8 · +0.340   <- ELEGIDO
#   text-embedding-3-small  1536 dim · 8/8 · +0.319
#   nemotron-3-embed-1b     SIN input_type: 7/8 · +0.091
#
# Empatan en recall, asi que NO decide la calidad: decide el CUPO. La unica via a
# text-embedding-3-small desde aqui es el AI Gateway de Vercel, y su free tier corta con
# `429 rate-limited` a la segunda tanda; sembrar son ~420 items. NIM hizo 60 vectores en
# 4.8 s sin un fallo. Vercel queda como respaldo declarado, no como via principal.
#
# El precio de elegir NIM: 2048 dim no caben en un indice HNSW con el tipo `vector` (tope
# 2000), asi que el indice va sobre `halfvec` y la consulta tiene que llevar el mismo cast.
# Y la tercera linea es una trampa cara: `nemotron-3-embed-1b` es un modelo ASIMETRICO y sin
# `input_type` (query al consultar, passage al sembrar) su calidad se desploma.
#
# Las credenciales se leen de GCP Secret Manager, nunca de argv.
import json, math, subprocess, sys
from openai import OpenAI

def clave(nombre):
    c = subprocess.run(["gcloud","secrets","versions","access","latest","--secret",nombre,
                        "--project","enerby-workstation"], capture_output=True, text=True, check=True).stdout.strip()
    try:
        d = json.loads(c); return next(iter(d.values())) if isinstance(d, dict) else c
    except Exception: return c

PARES = [
  ("Ich habe noch ein Ticket für Burna Boy in Düsseldorf am Samstag. Mein Freund kann nicht mehr und ich möchte nicht alleine gehen.",
   "I have a spare ticket for Burna Boy in Dusseldorf on Saturday. My friend cannot come and I do not want to go alone."),
  ("Ich möchte am Wochenende auf ein Techno-Festival in Berlin, aber keiner von meinen Freunden hat Lust.",
   "I want to go to a techno festival in Berlin this weekend, but none of my friends feel like it."),
  ("Ich habe für Freitagabend einen Tisch in Frankfurt reserviert, aber meine Begleitung ist ausgefallen.",
   "I booked a table in Frankfurt for Friday evening, but the person coming with me cancelled."),
  ("Ich habe eine Reise nach Barcelona gebucht und möchte ungern alleine fahren.",
   "I booked a trip to Barcelona and would rather not travel alone."),
  ("Meine Freunde interessieren sich nicht für Afrobeats. Ich suche jemanden in Köln, der gerne auf solche Konzerte geht.",
   "My friends are not into afrobeats. I am looking for someone in Cologne who enjoys those concerts."),
  ("Ich habe ein Extra-Ticket für Bayern gegen Dortmund in München morgen.",
   "I have an extra ticket for Bayern against Dortmund in Munich tomorrow."),
  ("Ich plane ein Wander-Wochenende in der Nähe von München, aber mein Freund hat abgesagt.",
   "I planned a hiking weekend near Munich, but my friend cancelled."),
  ("Ich bin dieses Wochenende in Berlin und möchte spontan etwas unternehmen.",
   "I am in Berlin this weekend and would like to do something spontaneous."),
]
cos=lambda a,b: sum(x*y for x,y in zip(a,b))/(math.sqrt(sum(x*x for x in a))*math.sqrt(sum(y*y for y in b)))

def evaluar(nombre, base, secreto, modelo, extra_q=None, extra_p=None):
    c = OpenAI(base_url=base, api_key=clave(secreto))
    de = [p[0] for p in PARES]; en = [p[1] for p in PARES]
    ve = c.embeddings.create(model=modelo, input=de, **({"extra_body":extra_q} if extra_q else {})).data
    vp = c.embeddings.create(model=modelo, input=en, **({"extra_body":extra_p} if extra_p else {})).data
    ve=[x.embedding for x in ve]; vp=[x.embedding for x in vp]
    aciertos=0; margenes=[]
    for i in range(len(PARES)):
        sims=[cos(ve[i], vp[j]) for j in range(len(PARES))]
        mejor=max(range(len(sims)), key=lambda j: sims[j])
        correcto = sims[i]
        otros = sorted((s for j,s in enumerate(sims) if j!=i), reverse=True)[0]
        margenes.append(correcto-otros)
        aciertos += (mejor==i)
    print(f"  {nombre:<46} dim {len(ve[0]):>5} · recall@1 {aciertos}/{len(PARES)} · margen medio {sum(margenes)/len(margenes):+.3f}")

print("=== gate cross-lingua DE->EN, 8 pares de las frases de Helder ===")
evaluar("text-embedding-3-small (Vercel)", "https://ai-gateway.vercel.sh/v1", "vercel-ai-gateway", "openai/text-embedding-3-small")
evaluar("nemotron-3-embed-1b (NIM, con input_type)", "https://integrate.api.nvidia.com/v1", "nvidia-nim",
        "nvidia/nemotron-3-embed-1b", {"input_type":"query","truncate":"END"}, {"input_type":"passage","truncate":"END"})
evaluar("nemotron-3-embed-1b (NIM, SIN input_type)", "https://integrate.api.nvidia.com/v1", "nvidia-nim",
        "nvidia/nemotron-3-embed-1b")
