 
-- Crear base de datos si no existe
-- La base ya se crea con docker-compose, pero agregamos configuración

-- Tabla de personas
CREATE TABLE IF NOT EXISTS personas (
    id SERIAL PRIMARY KEY,
    tipo_documento VARCHAR(20) NOT NULL,
    numero_documento VARCHAR(10) UNIQUE NOT NULL,
    primer_nombre VARCHAR(30) NOT NULL,
    segundo_nombre VARCHAR(30),
    apellidos VARCHAR(60) NOT NULL,
    fecha_nacimiento DATE NOT NULL,
    genero VARCHAR(20) NOT NULL,
    correo_electronico VARCHAR(100) NOT NULL,
    celular VARCHAR(10) NOT NULL,
    foto BYTEA,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de logs
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    tipo_operacion VARCHAR(20) NOT NULL,
    numero_documento VARCHAR(10),
    usuario VARCHAR(100),
    detalles JSONB,
    fecha_transaccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para búsquedas
CREATE INDEX IF NOT EXISTS idx_personas_documento ON personas(numero_documento);
CREATE INDEX IF NOT EXISTS idx_logs_documento ON logs(numero_documento);
CREATE INDEX IF NOT EXISTS idx_logs_fecha ON logs(fecha_transaccion);
CREATE INDEX IF NOT EXISTS idx_logs_tipo ON logs(tipo_operacion);

-- Insertar datos de prueba
INSERT INTO personas (tipo_documento, numero_documento, primer_nombre, segundo_nombre, apellidos, fecha_nacimiento, genero, correo_electronico, celular)
VALUES 
    ('Cédula', '1234567890', 'Juan', 'Carlos', 'Pérez González', '1990-05-15', 'Masculino', 'juan.perez@email.com', '3001234567'),
    ('Tarjeta de identidad', '9876543210', 'María', 'Isabel', 'López Martínez', '2005-08-22', 'Femenino', 'maria.lopez@email.com', '3109876543'),
    ('Cédula', '1111111111', 'Pedro', NULL, 'Ramírez', '2000-01-10', 'Masculino', 'pedro.ramirez@email.com', '3201111111')
ON CONFLICT DO NOTHING;
 