 
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime, date
import asyncpg
import os

app = FastAPI(title="Logs Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")
db_pool = None

@app.on_event("startup")
async def startup():
    global db_pool
    print(f"Conectando a: {DATABASE_URL}")
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "logs"}

@app.get("/logs")
async def consultar_logs(
    tipo_operacion: Optional[str] = Query(None),
    numero_documento: Optional[str] = Query(None),
    fecha_inicio: Optional[date] = Query(None),
    fecha_fin: Optional[date] = Query(None)
):
    if not db_pool:
        return []
    
    query = "SELECT * FROM logs WHERE 1=1"
    params = []
    param_count = 0
    
    if tipo_operacion:
        param_count += 1
        query += f" AND tipo_operacion = ${param_count}"
        params.append(tipo_operacion)
    
    if numero_documento:
        param_count += 1
        query += f" AND numero_documento = ${param_count}"
        params.append(numero_documento)
    
    if fecha_inicio:
        param_count += 1
        query += f" AND fecha_transaccion >= ${param_count}"
        params.append(fecha_inicio)
    
    if fecha_fin:
        param_count += 1
        query += f" AND fecha_transaccion <= ${param_count}"
        params.append(fecha_fin)
    
    query += " ORDER BY fecha_transaccion DESC LIMIT 100"
    
    async with db_pool.acquire() as conn:
        results = await conn.fetch(query, *params)
        return [dict(r) for r in results]

@app.get("/logs/resumen")
async def resumen_logs():
    if not db_pool:
        return {"total_operaciones": 0, "operaciones_24h": 0, "distribucion_tipos": []}
    
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM logs")
        por_tipo = await conn.fetch(
            "SELECT tipo_operacion, COUNT(*) as cantidad FROM logs GROUP BY tipo_operacion"
        )
        ultimas_24h = await conn.fetchval(
            "SELECT COUNT(*) FROM logs WHERE fecha_transaccion > NOW() - INTERVAL '24 hours'"
        )
        
        return {
            "total_operaciones": total or 0,
            "operaciones_24h": ultimas_24h or 0,
            "distribucion_tipos": [dict(r) for r in por_tipo]
        }
 