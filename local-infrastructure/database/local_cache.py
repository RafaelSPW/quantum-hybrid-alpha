import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "compliance_cache.db")


def init_db():
    """Crea las tablas si no existen."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compliance_reports (
            documento        TEXT PRIMARY KEY,
            nombre           TEXT NOT NULL,
            resultado_json   TEXT NOT NULL,
            fecha_consulta   TEXT NOT NULL,
            status           TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_queries (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            activo           TEXT NOT NULL,
            resultado_json   TEXT NOT NULL,
            fecha_consulta   TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def guardar_reporte_compliance(documento: str, nombre: str, resultado: dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO compliance_reports
        (documento, nombre, resultado_json, fecha_consulta, status)
        VALUES (?, ?, ?, ?, ?)
    """, (
        documento,
        nombre,
        json.dumps(resultado, ensure_ascii=False),
        datetime.utcnow().isoformat(),
        resultado.get("status_evaluacion", "DESCONOCIDO"),
    ))
    conn.commit()
    conn.close()


def buscar_reporte_compliance(documento: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT resultado_json FROM compliance_reports WHERE documento = ?",
        (documento,),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return None


if __name__ == "__main__":
    init_db()
    print(f"[DB] Base de datos inicializada en: {DB_PATH}")
