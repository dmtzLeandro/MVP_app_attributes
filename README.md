# main working branch is render-demo



# # Tiendanube Attributes App (MVP)

Aplicación externa para Tiendanube que permite gestionar atributos de catálogo que no existen de forma nativa en la plataforma.

----------------------------------------------------------------------------------------------------------------------------------------

## Objetivo

Esta app agrega una capa de datos propia sobre Tiendanube para administrar atributos personalizados por producto, manteniendo:

- independencia del modelo de Tiendanube
- escalabilidad multitienda
- alto rendimiento sin consultas constantes al storefront

## Atributos actuales (MVP)

- `ancho_cm`
- `composicion`

------------------------------------------------------------------------------------------------------------------------------------------

## Arquitectura
Tiendanube (OAuth + API)
>
Backend (FastAPI)
>
PostgreSQL (Render)
<
Frontend (React + Vite)
>
Storefront Script (JS embebido en tienda)


-------------------------------------------------------

## Concepto clave

La app es **multitienda real**, basada en la combinación:


store_id + product_id


Los atributos se almacenan como:


store_id + product_id + attribute_key


Esto garantiza aislamiento total entre tiendas.

--------------------------------------------------------

##  Funcionalidades principales

## Autenticación
- OAuth con Tiendanube
- JWT para panel admin

##  Productos
- importación desde Tiendanube
- almacenamiento local en DB

##  Atributos
- lectura por producto
- edición individual
- edición batch (optimizada)
- import/export CSV

##  Panel admin
- listado paginado
- edición inline
- edición masiva
- filtros (faltantes, búsqueda)

## Storefront
- endpoint público de atributos
- script JS que inyecta atributos en la tienda

## Imágenes
- generación de thumbnails optimizados
- cache local en servidor
- URLs firmadas (seguridad + performance)

-------------------------------------------------

## Stack tecnológico

## Backend
- FastAPI
- SQLAlchemy 2.0
- PostgreSQL
- Alembic
- JWT
- httpx

## Frontend
- React
- Vite
- TypeScript

## Infraestructura
- Render (backend + frontend)
- PostgreSQL (Render)

-----------------------------------------------------

## Estructura del proyecto


backend/
|-- app/
│ |-- admin_api/
│ |-- core/
│ |-- db/
│ |-- services/
│ |_ _ main.py
|-- alembic/
|__ requirements.txt

frontend/
|-- src/
│ |-- api/
│ |-- pages/
│ |__ App.tsx
|__ package.json


----------------------------------------------------



## Flujo de instalación (OAuth)

1. Usuario instala la app en Tiendanube
2. Redirección a `/auth/install`
3. Autorización en Tiendanube
4. Callback → `/auth/callback`
5. Se guarda:
   - `store_id`
   - `access_token`
6. Se importan productos automáticamente

---

## CSV

Formato esperado:


product_id, ancho_cm, composicion


Reglas:
- UTF-8
- valores vacíos → eliminan atributo
- productos inexistentes → ignorados

---

## Storefront Script

El storefront consume:


POST /admin/storefront/attributes/batch


Y renderiza atributos en la grilla de productos.

>  Actualmente el `store_id` se define en el script (MVP).  
> En futuras versiones será dinámico.

-------------------------------------------------------------

## Seguridad

- JWT para panel admin
- tokens de tienda cifrados
- URLs firmadas para thumbnails
- rate limiting
- idempotency en operaciones batch

----------------------------------------------------------------

##  Performance

- batch operations (lectura y escritura)
- cache en endpoints públicos
- thumbnails optimizados en WebP
- minimización de requests al storefront

----------------------------------------------------------------

## Estado del proyecto

### Funcional ###
- OAuth completo
- importación de productos
- panel admin operativo
- edición batch estabilizada
- CSV import/export
- endpoint storefront

### En evolución
- login multitienda real
- mejoras en thumbnails
- optimización de performance

-----------------------------------------------------------------

## Roadmap

- autenticación por tienda (panel_users)
- eliminación de hardcode de store_id en frontend/script
- sincronización automática de catálogo
- mejoras de cache y performance
- soporte para nuevos atributos dinámicos

-----------------------------------------------------------------



## Desarrollo local

### Backend

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # o .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar migraciones
alembic upgrade head

# Levantar servidor
uvicorn app.main:app --reload
Base de datos (PostgreSQL)

Docker:
docker compose up -d

Frontend
npm install
npm run dev

# Variables de entorno

Backend
DB_URL=
TN_CLIENT_ID=
TN_CLIENT_SECRET=
TN_OAUTH_BASE=
TN_API_BASE=
JWT_SECRET=

Frontend
VITE_API_BASE=
VITE_STORE_ID=

