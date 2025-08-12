 
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, Literal
from datetime import date, datetime
import asyncpg
import os
import json
from contextlib import asynccontextmanager

# Pool de conexiones global
db_pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    DATABASE_URL = os.getenv("DATABASE_URL")
    print(f"Conectando a la base de datos: {DATABASE_URL}")
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        print("Pool de conexiones creado exitosamente")
    except Exception as e:
        print(f"Error al crear pool: {e}")
    yield
    if db_pool:
        await db_pool.close()

app = FastAPI(title="Personas Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos Pydantic
class PersonaBase(BaseModel):
    tipo_documento: Literal["Tarjeta de identidad", "Cédula"]
    numero_documento: str = Field(..., max_length=10)
    primer_nombre: str = Field(..., max_length=30)
    segundo_nombre: Optional[str] = Field(None, max_length=30)
    apellidos: str = Field(..., max_length=60)
    fecha_nacimiento: date
    genero: Literal["Masculino", "Femenino", "No binario", "Prefiero no reportar"]
    correo_electronico: EmailStr
    celular: str = Field(..., pattern="^[0-9]{10}$")
    
    @validator('numero_documento')
    def validar_numero_documento(cls, v):
        if not v.isdigit():
            raise ValueError('El número de documento debe contener solo dígitos')
        return v
    
    @validator('primer_nombre', 'segundo_nombre', 'apellidos')
    def validar_nombres(cls, v):
        if v and any(char.isdigit() for char in v):
            raise ValueError('Los nombres no pueden contener números')
        return v

class PersonaResponse(PersonaBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }

# Función auxiliar para logs
async def registrar_log(tipo: str, documento: str, detalles: dict):
    if db_pool:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO logs (tipo_operacion, numero_documento, detalles) 
                   VALUES ($1, $2, $3::jsonb)""",
                tipo, documento, json.dumps(detalles)
            )

# Endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "personas"}

@app.post("/personas/", response_model=PersonaResponse)
async def crear_persona(persona: PersonaBase):
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    try:
        async with db_pool.acquire() as conn:
            # Verificar si ya existe
            existing = await conn.fetchval(
                "SELECT id FROM personas WHERE numero_documento = $1",
                persona.numero_documento
            )
            if existing:
                raise HTTPException(status_code=400, detail="El documento ya existe")
            
            # Insertar persona
            result = await conn.fetchrow(
                """INSERT INTO personas 
                   (tipo_documento, numero_documento, primer_nombre, segundo_nombre,
                    apellidos, fecha_nacimiento, genero, correo_electronico, celular)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                   RETURNING *""",
                persona.tipo_documento, persona.numero_documento, persona.primer_nombre,
                persona.segundo_nombre, persona.apellidos, persona.fecha_nacimiento,
                persona.genero, persona.correo_electronico, persona.celular
            )
            
            await registrar_log("CREATE", persona.numero_documento, {"accion": "Persona creada"})
            return PersonaResponse(**dict(result))
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/personas/{numero_documento}", response_model=PersonaResponse)
async def obtener_persona(numero_documento: str):
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            "SELECT * FROM personas WHERE numero_documento = $1",
            numero_documento
        )
        if not result:
            raise HTTPException(status_code=404, detail="Persona no encontrada")
        
        await registrar_log("READ", numero_documento, {"accion": "Consulta realizada"})
        return PersonaResponse(**dict(result))

@app.put("/personas/{numero_documento}", response_model=PersonaResponse)
async def actualizar_persona(numero_documento: str, persona: PersonaBase):
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    async with db_pool.acquire() as conn:
        result = await conn.fetchrow(
            """UPDATE personas 
               SET tipo_documento=$1, primer_nombre=$2, segundo_nombre=$3,
                   apellidos=$4, fecha_nacimiento=$5, genero=$6,
                   correo_electronico=$7, celular=$8, updated_at=CURRENT_TIMESTAMP
               WHERE numero_documento=$9
               RETURNING *""",
            persona.tipo_documento, persona.primer_nombre, persona.segundo_nombre,
            persona.apellidos, persona.fecha_nacimiento, persona.genero,
            persona.correo_electronico, persona.celular, numero_documento
        )
        if not result:
            raise HTTPException(status_code=404, detail="Persona no encontrada")
        
        await registrar_log("UPDATE", numero_documento, {"accion": "Persona actualizada"})
        return PersonaResponse(**dict(result))

@app.delete("/personas/{numero_documento}")
async def eliminar_persona(numero_documento: str):
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM personas WHERE numero_documento = $1",
            numero_documento
        )
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Persona no encontrada")
        
        await registrar_log("DELETE", numero_documento, {"accion": "Persona eliminada"})
        return {"message": "Persona eliminada exitosamente"}

@app.get("/personas/")
async def listar_personas():
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    async with db_pool.acquire() as conn:
        results = await conn.fetch("SELECT * FROM personas ORDER BY id DESC LIMIT 100")
        return [PersonaResponse(**dict(r)) for r in results]
 
