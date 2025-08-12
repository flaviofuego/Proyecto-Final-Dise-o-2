 
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import date, datetime
import asyncpg
import os
import json

app = FastAPI(title="Consultas Service")

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
    return {"status": "healthy", "service": "consultas"}

@app.get("/consultar")
async def consultar_personas(
    numero_documento: Optional[str] = Query(None),
    tipo_documento: Optional[str] = Query(None),
    nombre: Optional[str] = Query(None)
):
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    query = "SELECT * FROM personas WHERE 1=1"
    params = []
    param_count = 0
    
    if numero_documento:
        param_count += 1
        query += f" AND numero_documento = ${param_count}"
        params.append(numero_documento)
    
    if tipo_documento:
        param_count += 1
        query += f" AND tipo_documento = ${param_count}"
        params.append(tipo_documento)
    
    if nombre:
        param_count += 1
        query += f" AND (primer_nombre ILIKE ${param_count} OR apellidos ILIKE ${param_count})"
        params.append(f"%{nombre}%")
    
    async with db_pool.acquire() as conn:
        results = await conn.fetch(query, *params)
        
        # Registrar consulta en log
        await conn.execute(
            """INSERT INTO logs (tipo_operacion, detalles) 
               VALUES ($1, $2::jsonb)""",
            "CONSULTA",
            json.dumps({"filtros": {"documento": numero_documento, "tipo": tipo_documento, "nombre": nombre}})
        )
        
        return [dict(r) for r in results]

@app.get("/estadisticas")
async def obtener_estadisticas():
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    async with db_pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM personas")
        por_genero = await conn.fetch(
            "SELECT genero, COUNT(*) as cantidad FROM personas GROUP BY genero"
        )
        edad_promedio = await conn.fetchval("""
            SELECT AVG(EXTRACT(YEAR FROM age(fecha_nacimiento))) 
            FROM personas
        """)
        
        return {
            "total_personas": total,
            "distribucion_genero": [dict(r) for r in por_genero],
            "edad_promedio": float(edad_promedio) if edad_promedio else 0
        }
 