# Cerro Tusa Experience

Plataforma web en español para presentar experiencias turísticas y gestionar solicitudes de reserva en Cerro Tusa, Venecia, Antioquia. Incluye sitio público, API FastAPI, almacenamiento MongoDB Atlas y panel administrativo.

> **Antes de producción:** el catálogo se inicia vacío. Un administrador debe confirmar y publicar cada experiencia. Completa los datos comerciales, de contacto y legales; revisa las rutas, permisos de acceso, seguridad del recorrido y precios con el operador. Enviar una solicitud no confirma una reserva.

## Fotografías y licencias

Las fotos locales de portada y galería son de Cerro Tusa y se descargaron en alta resolución desde Wikimedia Commons. Se recomprimieron a JPEG de calidad alta para web conservando sus dimensiones. La página muestra atribución, fuente y licencia junto a cada imagen:

- Johnny Cabrera, [Cerro Tusa Antioquia](https://commons.wikimedia.org/wiki/File:Cerro_Tusa_Antioquia.jpg), 5472 × 3648, CC BY-SA 3.0.
- Alejandro Bayer Tamayo, [Desde la vía a Pueblito](https://commons.wikimedia.org/wiki/File:Desde_la_v%C3%ADa_a_Pueblito_-_Camilo_C._-_Cerro_de_la_Tusa_-_Flickr_-_Alejandro_Bayer.jpg), 4608 × 3072, CC BY-SA 2.0.
- XalD, [Cerro Tusa desde Venecia](https://commons.wikimedia.org/wiki/File:Cerro_Tusa_desde_Venecia.jpg), 2976 × 3968, CC BY-SA 4.0.

La galería amplía las imágenes; el encuadre en las tarjetas puede recortarse según el tamaño de pantalla. Las copias optimizadas se ofrecen bajo la misma licencia CC BY-SA de cada fuente. Conserva la atribución y los enlaces de licencia si cambias, redistribuyes o adaptas las imágenes.

## Tecnologías y estructura

- Python 3.12+, FastAPI, Pydantic, PyMongo AsyncMongoClient, MongoDB Atlas.
- HTML semántico, CSS, JavaScript y Fetch API.
- JWT en cookies `HttpOnly`, contraseñas con hash Argon2 y roles separados para clientes y administradores.
- Registro/inicio de sesión de clientes y consulta privada del estado de sus solicitudes.
- `app/main.py`: aplicación, archivos estáticos, páginas y salud.
- `app/routers.py`: experiencias, reservas, contacto, autenticación y panel.
- `app/database.py`: ciclo de vida MongoDB e índices.
- `app/security.py`: hashing, tokens y autorización.
- `app/create_admin.py`: alta controlada del primer administrador.
- `app/static/`: sitio público, formulario, panel, bandeja de mensajes y estilos.
- `tests/`: pruebas de API.

## Requisitos

- Python 3.12 o superior.
- MongoDB Atlas o una instancia MongoDB accesible desde el entorno.
- PowerShell en Windows.

## Instalar y ejecutar en Windows

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env` con los valores de tu entorno. Genera un secreto JWT local con:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Guarda el resultado en `JWT_SECRET` (mínimo 32 caracteres) y configura `MONGODB_URI`. Luego inicia:

```powershell
uvicorn app.main:app --reload
```

Páginas disponibles: <http://127.0.0.1:8000/>, cuenta de clientes <http://127.0.0.1:8000/cuenta>, administración <http://127.0.0.1:8000/admin>, API <http://127.0.0.1:8000/docs> y salud <http://127.0.0.1:8000/health>. `/health` responde `503` cuando MongoDB no está configurado o no responde. La aplicación no afirma que la base de datos esté disponible hasta comprobar `ping`.

## MongoDB Atlas

1. Crea un proyecto y clúster en MongoDB Atlas.
2. Crea un usuario de base de datos dedicado con privilegios mínimos sobre la base configurada.
3. En Network Access autoriza únicamente las IP de salida necesarias para tu entorno.
4. En el clúster, elige **Connect → Drivers** y copia el URI de conexión `mongodb+srv://...` (el enlace web de Atlas no es un URI de base de datos). Reemplaza usuario, contraseña y nombre de base de datos; guarda el URI solo en `MONGODB_URI`.
5. Configura `MONGODB_DATABASE=cerro_tusa_turismo` (o un nombre propio).
6. Inicia la aplicación. Esta prueba la conexión y crea índices únicos para cuentas y códigos de reserva, así como índices de búsqueda.
7. Comprueba `/health`; una respuesta `200` indica que el `ping` a MongoDB funcionó.

No abras el acceso de red globalmente por comodidad. Render no garantiza IP de salida fija en todos los planes y configuraciones: confirma las capacidades del plan actual. Si necesitas IP estable, evalúa un servicio/plan de salida estática o una red privada compatible; restringe Atlas a esas direcciones. Permitir `0.0.0.0/0` implica exponer el acceso de red desde cualquier dirección y no es la opción recomendada.

## Variables de entorno

| Variable | Uso |
|---|---|
| `MONGODB_URI` | URI privado de conexión; obligatorio para datos |
| `MONGODB_DATABASE` | Base de datos; predeterminado `cerro_tusa_turismo` |
| `ADMIN_EMAIL` | Correo opcional preseleccionado para crear la primera cuenta |
| `JWT_SECRET` | Firma de sesiones, mínimo 32 caracteres |
| `ENVIRONMENT` | Usa `production` para cookies seguras HTTPS |
| `FRONTEND_URL` | Origen adicional autorizado por CORS, si aplica |
| `CORS_ORIGINS` | Orígenes separados por coma; mismo origen no requiere CORS |
| `WHATSAPP_NUMBER` | Número internacional, solo dígitos/código país recomendado |
| `CONTACT_EMAIL` | Correo comercial público |
| `BUSINESS_NAME` | Nombre mostrado en el sitio |
| `SMTP_HOST`, `SMTP_PORT` | Servidor SMTP y puerto para notificaciones de aceptación; Gmail usa `smtp.gmail.com:587` |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | Cuenta Gmail y contraseña de aplicación; ambas deben configurarse juntas |
| `SMTP_FROM_EMAIL` | Dirección remitente autorizada; para este Gmail se usa `josedavidmarin311@gmail.com` |
| `SMTP_USE_TLS`, `SMTP_USE_SSL` | STARTTLS (predeterminado) o conexión SSL SMTP |

Al cambiar una solicitud de reserva de pendiente a confirmada, el sistema envía al correo del cliente una confirmación con los datos de la ruta. Configura las variables SMTP antes de aceptar solicitudes; si el envío falla, la reserva queda confirmada y el panel informa que no se pudo enviar el correo.

Para Gmail, activa la verificación en dos pasos y crea una contraseña de aplicación en la configuración de seguridad de la cuenta Google. Añade esa contraseña como secreto `SMTP_PASSWORD` en el servicio de Render; no uses la contraseña normal de la cuenta ni la pegues en el repositorio, `.env.example` o el chat. Tras guardar la variable en Render, vuelve a desplegar el servicio.

No guardes `.env` en Git. La cookie administrativa es `HttpOnly`, `SameSite=Strict`, expira en 8 horas y usa `Secure` en producción. El límite de solicitudes para login, reservas y contacto reside en memoria del proceso; con múltiples instancias o reinicios frecuentes, añade un limitador compartido antes del despliegue. Mantén HTTPS en producción y revisa dependencias periódicamente.

## Crear el primer administrador

No existe registro público de administradores ni credencial por defecto. Configura MongoDB y, opcionalmente, `ADMIN_EMAIL` para preseleccionar el correo de la primera cuenta. Instala dependencias y ejecuta en una terminal privada:

```powershell
python -m app.create_admin
```

El comando solicita nombre y contraseña dos veces sin mostrar esta última (solicita el correo solo si `ADMIN_EMAIL` está vacío), exige 12 caracteres como mínimo y guarda solo un hash Argon2. No se puede crear una segunda cuenta con el mismo correo. No reutilices contraseñas cortas o usadas en otros sitios.

## API

La documentación OpenAPI está en `/docs` y `/redoc`. El panel `/admin` ofrece resumen visual, filtros y paginación de reservas, exportación CSV, detalle y notas privadas, gestión de mensajes de contacto, y catálogo de experiencias con creación, edición y activación.

| Método | Ruta | Acceso |
|---|---|---|
| `GET` | `/` | Público |
| `GET` | `/health` | Público; comprueba MongoDB |
| `GET` | `/api/configuracion` | Público; solo configuración no secreta |
| `GET` | `/api/experiencias` | Público; solo activas |
| `GET` | `/api/experiencias/{id}` | Público; solo activa |
| `POST` | `/api/experiencias` | Administrador |
| `PUT` | `/api/experiencias/{id}` | Administrador |
| `DELETE` | `/api/experiencias/{id}` | Administrador; desactivación |
| `POST` | `/api/reservas` | Público |
| `GET` | `/api/reservas` | Administrador; filtros y paginación |
| `GET` | `/api/reservas/{id}` | Administrador |
| `PATCH` | `/api/reservas/{id}/estado` | Administrador; transiciones validadas |
| `PATCH` | `/api/reservas/{id}/notas` | Administrador; notas internas |
| `POST` | `/api/contacto` | Público |
| `GET` | `/api/contactos` | Administrador; mensajes con filtros y paginación |
| `PATCH` | `/api/contactos/{id}/estado` | Administrador; organiza mensajes |
| `POST` | `/api/auth/login` | Público; crea cookie segura para administrador |
| `GET` | `/api/auth/me` | Administrador |
| `POST` | `/api/auth/logout` | Administrador |
| `POST` | `/api/clientes/auth/registro` | Público; crea cuenta de cliente y sesión |
| `POST` | `/api/clientes/auth/login` | Público; inicia sesión de cliente |
| `GET` | `/api/clientes/auth/me` | Cliente autenticado |
| `POST` | `/api/clientes/auth/logout` | Cliente autenticado |
| `GET` | `/api/clientes/me/reservas` | Cliente autenticado; solo sus solicitudes |
| `GET` | `/api/admin/dashboard` | Administrador |

Los valores de estado son `pendiente`, `confirmada`, `rechazada` y `cancelada`. Una solicitud empieza `pendiente`; no se ofrece consulta pública de datos de reservas. Las solicitudes creadas mientras el cliente ha iniciado sesión se asocian a su cuenta; las anteriores a la creación de la cuenta o las enviadas sin sesión no se vinculan automáticamente. Las búsquedas administrativas escapan expresiones regulares. Las solicitudes repetidas con mismo correo, experiencia y fecha se rechazan si ya existe una pendiente o confirmada.

## Pruebas

```powershell
pytest -q
```

Las pruebas automatizadas cubren validación y autorización con almacenamiento simulado, sin modificar reservas reales. Para la verificación integrada de MongoDB configura una base de pruebas y ejecuta también la aplicación local y `/health`.

## Despliegue en Render

1. Sube el proyecto a un repositorio privado de GitHub; verifica que `.env` no esté versionado.
2. En Render crea un Web Service desde ese repositorio o usa `render.yaml`.
3. Render detecta Python; el build es `pip install -r requirements.txt`.
4. El inicio está configurado como `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
5. Configura `MONGODB_URI`, `JWT_SECRET`, `MONGODB_DATABASE`, `WHATSAPP_NUMBER`, `CONTACT_EMAIL`, `BUSINESS_NAME`, `ENVIRONMENT=production` y las variables SMTP de la tabla para habilitar correos de confirmación; configura, solo si aplica, `FRONTEND_URL`/`CORS_ORIGINS`.
6. Define cuidadosamente Network Access de Atlas según las IP de salida disponibles para el plan de Render, sin permitir globalmente todas las IP.
7. Despliega y comprueba la URL asignada en `/`, `/health` y `/docs`.
8. Crea el administrador con un entorno conectado a la base de producción usando `python -m app.create_admin`, con acceso controlado a las variables seguras. Evita incluir la contraseña en comandos o registros.
9. Verifica el login, que las rutas administrativas devuelven `401` sin sesión, registra una solicitud de prueba acordada con el operador y comprueba el documento en Atlas.

La configuración de Render está preparada; este proyecto no está desplegado ni conectado a cuentas externas por esta implementación.

## Antes de habilitar uso real

- Define nombre legal/comercial, canales de contacto, redes, precios y política de cancelación.
- Publica solo recorridos, horarios, tarifas, rutas, capacidades y requisitos confirmados por el operador.
- Revisa con asesoría apropiada los textos legales y el tratamiento de datos personales.
- Evalúa el riesgo actual de cada recorrido, permisos de acceso, seguros, clima y protocolo de emergencia; el texto público no es una evaluación de riesgos.
- Añade protección antispam/limitación distribuida para formularios públicos si el volumen lo requiere.
- Verifica imágenes y licencias antes de reemplazar la ilustración conceptual; no uses una imagen genérica como si fuera Cerro Tusa.
