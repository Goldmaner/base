"""
Migration: add alt_lote_id to public.termos_alteracoes
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE public.termos_alteracoes ADD COLUMN IF NOT EXISTS alt_lote_id integer DEFAULT NULL")
    conn.commit()
    print("OK: alt_lote_id adicionada")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='termos_alteracoes' AND column_name='alt_lote_id'")
    row = cur.fetchone()
    print("Confirmado:", row)
except Exception as e:
    conn.rollback()
    print("ERRO:", e)
finally:
    cur.close()
    conn.close()
