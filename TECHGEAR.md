# TechGear: API Django y tienda web

`techgear_api` y `techgear_web` son proyectos Django independientes. La API usa Django REST Framework y MongoDB Atlas mediante PyMongo; la web consulta la API desde el servidor y conserva el token en una colección de sesiones de Atlas, no en una cookie del navegador. Cerro Tusa conserva sus variables `MONGODB_URI` y `MONGODB_DATABASE`; localmente TechGear usa `TECHGEAR_MONGODB_URI` y la base Atlas `techgear`, separada de Cerro Tusa. El usuario de Atlas necesita permiso de lectura/escritura para `techgear`.

## Desarrollo local en Windows

Instala dependencias en el entorno virtual existente y configura `.env`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```dotenv
DJANGO_SECRET_KEY=un-secreto-aleatorio-largo-para-Django
DJANGO_WEB_SECRET_KEY=otro-secreto-aleatorio-largo-para-Django
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
TECHGEAR_MONGODB_URI=mongodb+srv://...
TECHGEAR_MONGODB_DATABASE=techgear_store
TECHGEAR_DNS_NAMESERVERS=1.1.1.1,8.8.8.8
TECHGEAR_JWT_SECRET=un-secreto-JWT-de-al-menos-32-caracteres
TECHGEAR_ADMIN_EMAIL=admin@example.com
TECHGEAR_ADMIN_PASSWORD=una-contraseña-larga-de-12-caracteres-o-más
TECHGEAR_API_URL=http://127.0.0.1:8001
```

`TECHGEAR_DNS_NAMESERVERS` es opcional; úsalo solo si el DNS de tu red no resuelve Atlas SRV. El cambio aplica únicamente al proceso TechGear, no al DNS global del equipo. Genera secretos nuevos localmente y guárdalos solo en `.env`; por ejemplo: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. En Render se generan las claves de Django y JWT automáticamente.

No escribas las contraseñas reales de Atlas en archivos versionados. En Atlas crea una base de datos/usuario separado para TechGear, concede los permisos mínimos y autoriza solo las direcciones de salida necesarias.

Abre dos terminales desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe .\techgear_api\manage.py runserver 8001
```

```powershell
.\.venv\Scripts\python.exe .\techgear_web\manage.py runserver 8000
```

Web: <http://127.0.0.1:8000/>. API: <http://127.0.0.1:8001/api/>. La web muestra el estado de conexión en `/health/`; la API lo comprueba en `/api/health/`.

Para desarrollo local, `TECHGEAR_API_URL` debe apuntar a `http://127.0.0.1:8001`. En producción Render usa `https://techgear-api.onrender.com`.

Para crear el primer administrador local, mantén esas variables configuradas y ejecuta:

```powershell
.\.venv\Scripts\python.exe .\techgear_api\manage.py create_techgear_admin
```

Inicia sesión con esa cuenta en `/cuenta/`; aparecerá `/gestion/` para administrar categorías, productos e inventario, y actualizar el estado de los pedidos. El catálogo empieza vacío.

## Despliegue en Render

Actualmente solo está desplegada la API; la tienda web aún requiere desplegarse como servicio independiente.

`render.yaml` declara servicios independientes `techgear-api` y `techgear-web` en la región Ohio, alineada con las salidas de Render que tienen autorización en Atlas; el build de la web también recopila y sirve el CSS con WhiteNoise. Configura `TECHGEAR_MONGODB_URI` como secreto en ambos servicios y `TECHGEAR_ADMIN_EMAIL` / `TECHGEAR_ADMIN_PASSWORD` para el administrador inicial de la API. Tras el primer despliegue, ejecuta desde la consola del servicio API:

```text
python techgear_api/manage.py create_techgear_admin
```

El comando es seguro de repetir y no cambia una cuenta existente. La allowlist de Atlas ya contiene rangos de salida de Render para Ohio; no abras el clúster globalmente. La URL pública de la API configurada en `TECHGEAR_API_URL` de la web debe coincidir con el dominio del servicio API.

## API disponible

| Método | Ruta | Acceso |
|---|---|---|
| GET | `/api/health/` | Público |
| POST | `/api/auth/register/`, `/api/auth/login/` | Público; JWT Bearer |
| GET, POST | `/api/categories/` | Lectura pública; creación admin |
| PATCH | `/api/categories/<id>/` | Admin |
| GET, POST | `/api/products/` | Lectura pública; creación admin |
| GET, PATCH, DELETE | `/api/products/<id>/` | Lectura pública; cambios admin |
| GET, POST, DELETE | `/api/cart/` | Usuario autenticado |
| GET, POST | `/api/orders/` | Usuario autenticado |
| GET | `/api/admin/orders/` | Admin |
| PATCH | `/api/admin/orders/<id>/` | Admin |

El primer registro crea siempre un usuario cliente. Crear el administrador requiere el comando dedicado; nunca se acepta elevar el rol mediante registro. Contraseñas se guardan con el hasher de Django y la API usa tokens JWT de ocho horas. Atlas no es compatible con el ORM/admin relacional estándar de Django; los datos de TechGear se gestionan desde `/gestion/`, no desde `/admin/`.

El checkout descuenta inventario y revierte los descuentos si no alcanza existencias o falla la inserción del pedido. Esta lógica no es una transacción distribuida; para pagos reales, cancelaciones/reembolsos, idempotencia o concurrencia de alto volumen, integra un proveedor de pagos y operaciones transaccionales/compensatorias antes de producción.
