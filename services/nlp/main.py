 
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncpg
import os
import json
from typing import List, Dict
from datetime import datetime

app = FastAPI(title="NLP Service - RAG")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

db_pool = None

# Importar Gemini solo si hay API key
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        gemini_available = True
    except Exception as e:
        print(f"Error configurando Gemini: {e}")
        gemini_available = False
else:
    print("GEMINI_API_KEY no configurada - usando respuestas simuladas")
    gemini_available = False

@app.on_event("startup")
async def startup():
    global db_pool
    print(f"Conectando a: {DATABASE_URL}")
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

class ConsultaNLP(BaseModel):
    pregunta: str

class RespuestaNLP(BaseModel):
    pregunta: str
    respuesta: str
    contexto: List[Dict]

async def obtener_contexto_personas():
    """Obtiene todos los datos de personas para contexto"""
    if not db_pool:
        return []
    
    async with db_pool.acquire() as conn:
        personas = await conn.fetch("""
            SELECT tipo_documento, numero_documento, primer_nombre, 
                   segundo_nombre, apellidos, fecha_nacimiento, 
                   genero, correo_electronico, celular
            FROM personas
        """)
        return [dict(p) for p in personas]

def procesar_sin_gemini(pregunta: str, contexto: List[Dict]) -> str:
    """Procesamiento básico sin Gemini para pruebas"""
    pregunta_lower = pregunta.lower()
    
    if not contexto:
        return "No hay datos de personas registradas en el sistema."
    
    # Buscar el más joven
    if "joven" in pregunta_lower or "menor" in pregunta_lower:
        persona_mas_joven = None
        fecha_mas_reciente = None
        
        for persona in contexto:
            fecha_nac = persona.get('fecha_nacimiento')
            if fecha_nac:
                if isinstance(fecha_nac, str):
                    fecha_nac = datetime.fromisoformat(fecha_nac).date()
                
                if fecha_mas_reciente is None or fecha_nac > fecha_mas_reciente:
                    fecha_mas_reciente = fecha_nac
                    persona_mas_joven = persona
        
        if persona_mas_joven:
            nombre = f"{persona_mas_joven['primer_nombre']} {persona_mas_joven['apellidos']}"
            return f"El empleado más joven registrado es {nombre}, nacido el {fecha_mas_reciente}"
    
    # Contar personas
    if "cuantos" in pregunta_lower or "total" in pregunta_lower:
        return f"Hay {len(contexto)} personas registradas en el sistema."
    
    # Listar nombres
    if "quienes" in pregunta_lower or "lista" in pregunta_lower:
        nombres = [f"{p['primer_nombre']} {p['apellidos']}" for p in contexto[:5]]
        return f"Algunas personas registradas son: {', '.join(nombres)}"
    
    return f"Hay {len(contexto)} personas en la base de datos. Puedes preguntar por el más joven, cuántas personas hay, etc."

async def procesar_pregunta_rag(pregunta: str, contexto: List[Dict]) -> str:
    """Procesa la pregunta usando RAG con Gemini o fallback"""
    
    if not gemini_available:
        return procesar_sin_gemini(pregunta, contexto)
    
    contexto_str = json.dumps(contexto, default=str, ensure_ascii=False)
    
    prompt = f"""
    Eres un asistente que responde preguntas sobre una base de datos de personas.
    
    CONTEXTO DE LA BASE DE DATOS:
    {contexto_str}
    
    PREGUNTA DEL USUARIO:
    {pregunta}
    
    INSTRUCCIONES:
    1. Responde basándote ÚNICAMENTE en los datos proporcionados
    2. Si la pregunta es sobre el empleado más joven, calcula basándote en fecha_nacimiento
    3. Si no puedes responder con los datos disponibles, indícalo claramente
    4. Sé conciso y directo en tu respuesta
    
    RESPUESTA:
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error con Gemini: {e}")
        return procesar_sin_gemini(pregunta, contexto)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "service": "nlp",
        "gemini_available": gemini_available
    }

@app.post("/consulta-nlp", response_model=RespuestaNLP)
async def consulta_lenguaje_natural(consulta: ConsultaNLP):
    try:
        # Obtener contexto de la base de datos
        contexto = await obtener_contexto_personas()
        
        if not contexto:
            respuesta = "No hay datos de personas en la base de datos."
        else:
            # Procesar con RAG
            respuesta = await procesar_pregunta_rag(consulta.pregunta, contexto)
        
        # Registrar en log
        if db_pool:
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO logs (tipo_operacion, detalles) 
                       VALUES ($1, $2::jsonb)""",
                    "CONSULTA_NLP",
                    json.dumps({"pregunta": consulta.pregunta, "respuesta": respuesta})
                )
        
        return RespuestaNLP(
            pregunta=consulta.pregunta,
            respuesta=respuesta,
            contexto=contexto[:3] if contexto else []
        )
        
    except Exception as e:
        print(f"Error en consulta NLP: {e}")
        raise HTTPException(status_code=500, detail=str(e))
 