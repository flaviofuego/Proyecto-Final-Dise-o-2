 
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

app = FastAPI(title="Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "dev-example.auth0.com")
AUTH0_API_AUDIENCE = os.getenv("AUTH0_API_AUDIENCE", "https://api.example.com")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    message: str

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "auth"}

@app.post("/dev-token", response_model=TokenResponse)
async def get_dev_token():
    """Token de desarrollo para pruebas"""
    return TokenResponse(
        access_token="dev-token-123456789",
        token_type="bearer",
        message="Token de desarrollo - configurar Auth0 para producción"
    )

@app.get("/verify")
async def verify_token():
    """Verificación simplificada para desarrollo"""
    return {
        "valid": True, 
        "user": {
            "sub": "dev-user",
            "name": "Usuario de Desarrollo"
        }
    }

@app.get("/config")
async def get_auth_config():
    """Retorna configuración de Auth0"""
    return {
        "domain": AUTH0_DOMAIN,
        "audience": AUTH0_API_AUDIENCE,
        "mode": "development" if "dev-example" in AUTH0_DOMAIN else "production"
    }
 