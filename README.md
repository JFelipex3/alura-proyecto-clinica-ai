# Agente IA — Clínica Bienestar Integral

---

## Descripción general del proyecto

Este proyecto es un **asistente conversacional corporativo** desarrollado para la
Clínica Bienestar Integral. Permite que pacientes y colaboradores hagan preguntas
en lenguaje natural y reciban respuestas precisas basadas exclusivamente en los
documentos internos de la clínica.

El agente utiliza la técnica **RAG (Retrieval-Augmented Generation)**: en lugar de
depender solo del conocimiento del modelo de lenguaje, primero busca los fragmentos
más relevantes en los documentos de la clínica y luego genera la respuesta usando
ese contexto. Esto garantiza que la información entregada sea siempre fiel a las
políticas y procedimientos reales de la organización, sin inventar datos.

Los documentos incluidos por defecto cubren:

| Documento | Categoría |
|---|---|
| Política de privacidad y protección de datos | Privacidad y Datos |
| Preguntas frecuentes sobre consultas y turnos | FAQ |
| Política de cancelaciones y reagendamiento | Políticas |
| Guía de convenios y coberturas médicas | Convenios y Coberturas |
| Instrucciones pre y post consulta médica | Instrucciones Médicas |
| Tabla de convenios EPS | Convenios y Coberturas |

La base de conocimiento puede ampliarse o modificarse en cualquier momento desde la interfaz, sin necesidad de comandos ni reiniciar la aplicación (ver [Gestión de documentos desde la interfaz](#gestión-de-documentos-desde-la-interfaz)).

---

## Arquitectura de la solución

El sistema opera en dos fases independientes:

### Fase 1 — Ingesta de documentos

```
docs/
├── *.pdf            ──►  ingestion.py  ──►  fragmentos ~800 chars
└── convenios.csv          (chunking)         + metadatos
                                                    │
                                                    ▼
                                        Gemini gemini-embedding-001
                                           (vectoriza cada fragmento)
                                                    │
                                                    ▼
                                             ChromaDB
                                        (almacenamiento persistente
                                          en chroma_db/)
```

La ingesta inicial se realiza con `python scripts/ingest_docs.py`. Las operaciones posteriores (agregar, actualizar o eliminar documentos) se pueden hacer directamente desde la pestaña **📂 Documentos** de la interfaz web, sin necesidad de la línea de comandos.

### Fase 2 — Conversación en tiempo real

```
Pregunta del usuario
        │
        ▼
Gemini gemini-embedding-001  →  vector de la pregunta
        │
        ▼
ChromaDB  →  recupera los fragmentos más similares semánticamente
        │
        ▼
Gemini gemini-2.0-flash  →  genera respuesta citando fuentes
        │
        ▼
Streamlit  →  muestra la respuesta y los documentos consultados
```

### Diagrama general

```
┌──────────────┐   pregunta    ┌──────────────────┐
│   Streamlit  │ ────────────► │    ChromaDB      │
│   (Chat UI)  │               │  (Vector Store)  │
│              │ ◄─ fragmentos─│                  │
│              │               └──────────────────┘
│              │  contexto +           ▲
│              │  pregunta     ┌───────┴──────┐
│              │ ────────────► │  Gemini API  │
│              │ ◄─ respuesta ─│  2.0 Flash   │
└──────────────┘               └──────────────┘
       ▲
  ingesta inicial
       │
┌──────┴─────────────────────┐
│  Pipeline de ingesta        │
│  PDF · CSV                  │
│  → chunking → embeddings    │
│  gemini-embedding-001       │
└─────────────────────────────┘
```

---

## Tecnologías y herramientas

| Categoría | Tecnología | Versión | Uso en el proyecto |
|---|---|---|---|
| Lenguaje | Python | 3.11+ | Backend completo |
| LLM | Google Gemini 2.5 Flash Lite | gemini-2.5-flash-lite | Generación de respuestas |
| Embeddings | Gemini Embedding | gemini-embedding-001 | Vectorización de texto |
| Vector store | ChromaDB | ≥ 0.5.0 | Almacenamiento y búsqueda semántica |
| Interfaz | Streamlit | ≥ 1.38.0 | Chat web interactivo |
| Lectura de PDFs | pypdf | ≥ 4.0.0 | Extracción de texto de PDFs |
| Variables de entorno | python-dotenv | ≥ 1.0.0 | Gestión segura de credenciales |
| Contenerización | Docker + Docker Compose | — | Empaquetado y despliegue |
| Nube | Oracle Cloud Infrastructure | — | Hosting en producción |
| SDK Google | google-genai | ≥ 0.3.0 | Cliente de embeddings |
| SDK Google | google-generativeai | ≥ 0.8.0 | Cliente de generación |

---

## Instrucciones para ejecutar el proyecto

### Opción A — Ejecución local

**Requisitos:** Python 3.11+ y una API Key de [Google AI Studio](https://aistudio.google.com/app/apikey).

```bash
# 1. Clonar el repositorio
git clone https://github.com/JFelipex3/alura-proyecto-clinica-ai.git
cd alura-proyecto-clinica-ai

# 2. Crear entorno virtual con Python 3.14.6
python -m venv .venv
source .venv/bin/activate        # Linux / Mac
.venv\Scripts\activate           # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar la API Key
cp .env.example .env
# Editar .env y agregar: GOOGLE_API_KEY=<tu-clave>

# 5. Indexar los documentos (primera vez, ~2 minutos)
python scripts/ingest_docs.py

# 6. Iniciar la aplicación
streamlit run src/app.py
```

Abrir `http://localhost:8501` en el navegador.

---

### Opción B — Docker Compose

```bash
cp .env.example .env
# Editar .env con tu GOOGLE_API_KEY

docker-compose up --build -d

# Indexar documentos dentro del contenedor
docker-compose exec agent python scripts/ingest_docs.py
```

Abrir `http://localhost:8501`.

---

### Opción C — Despliegue en OCI

```bash
# Autenticarse en OCI Container Registry
docker login <region>.ocir.io

# Construir y subir la imagen
docker build -t <region>.ocir.io/<namespace>/clinica-agente:latest .
docker push <region>.ocir.io/<namespace>/clinica-agente:latest

# En la VM de OCI
ssh opc@<ip-publica>
sudo dnf install -y docker && sudo systemctl start docker
docker login <region>.ocir.io
docker run -d \
  -p 8501:8501 \
  -e GOOGLE_API_KEY=<tu-key> \
  -v /home/opc/chroma_db:/app/chroma_db \
  <region>.ocir.io/<namespace>/clinica-agente:latest

docker exec -it <container-id> python scripts/ingest_docs.py
```

Agregar regla de entrada en la VCN: puerto `8501` TCP desde `0.0.0.0/0`.

Acceder en: `http://localhost:8501`

---

## Gestión de documentos desde la interfaz

La aplicación incluye una pestaña **📂 Documentos** que permite administrar la base de conocimiento sin necesidad de usar la línea de comandos.

### Agregar un documento nuevo

1. Ir a la pestaña **📂 Documentos**.
2. Seleccionar uno o más archivos con el selector (formatos soportados: PDF, DOCX, XLSX, PPTX, CSV, JSON, HTML, MD, TXT).
3. El botón mostrará la cantidad de archivos nuevos a indexar.
4. Al confirmar, cada archivo se guarda en `docs/` y se indexa automáticamente en ChromaDB.

### Actualizar un documento existente

El proceso es idéntico al de agregar: si el archivo subido tiene el mismo nombre que uno ya indexado, el sistema elimina los fragmentos anteriores del índice y los reemplaza con los del nuevo archivo. El botón indicará cuántos documentos serán actualizados.

### Eliminar un documento

En la sección **Documentos indexados** aparece la lista completa de archivos en el índice con su categoría y cantidad de fragmentos. Cada fila tiene un botón 🗑️ que solicita confirmación antes de:

1. Eliminar todos los fragmentos del documento en ChromaDB.
2. Eliminar el archivo físico de la carpeta `docs/`.

### Formatos de archivo soportados

| Extensión | Tipo |
|---|---|
| `.pdf` | PDF |
| `.docx`, `.doc` | Word |
| `.xlsx`, `.xls` | Excel |
| `.pptx`, `.ppt` | PowerPoint |
| `.csv` | Hoja de cálculo delimitada |
| `.json` | JSON |
| `.html`, `.htm` | HTML |
| `.md`, `.txt` | Texto plano / Markdown |

---

## Ejemplos de preguntas que el agente puede responder

- ¿Con cuánta anticipación debo sacar un turno?
- ¿Qué pasa si necesito cancelar mi cita?
- ¿Qué debo llevar para un examen de laboratorio?
- ¿La EPS Sura tiene cobertura en la clínica?
- ¿Cómo protegen mis datos personales?
- ¿Qué especialidades médicas están disponibles?
- ¿Puedo reagendar una cita el mismo día?
- ¿Cuáles son los pasos para una consulta por primera vez?

---

## Ejemplos de respuestas generadas por el agente

---

**Pregunta:** ¿Con cuánta anticipación debo sacar un turno?

**Respuesta del agente:**
>Puedes agendar citas con hasta 3 meses de anticipación. Para especialidades con alta demanda como Cardiología, Ortopedia y Dermatología, recomendamos reservar con al menos 2 semanas de antelación.
>
>*Fuente: faq_consultas_turnos.pdf*

---

**Pregunta:** ¿Qué pasa si necesito cancelar mi cita?

**Respuesta del agente:**
> Hola, gracias por tu consulta.
>
>Si necesitas cancelar tu cita, debes notificarlo con al menos 4 horas de anticipación. Puedes hacerlo a través de nuestra app móvil en la sección "Mis citas" → "Cancelar", por WhatsApp al +56 9 2234 5634, llamando al (32) 223 4512, o enviando un correo electrónico a citas@clinicabienestar.cl.
>
>Si cancelas con 4 o más horas de anticipación, no tendrá ningún costo para ti y la cita quedará liberada.
>
>*Fuente: politica_cancelaciones.pdf*

---

**Pregunta:** ¿Qué debo llevar para un examen de laboratorio?

**Respuesta del agente:**
> Hola, para un examen de laboratorio, debes tener en cuenta lo siguiente:
>
> - Ayuno: Para hemograma, química sanguínea y glicemia en ayunas, el ayuno es obligatorio de 8 a 12 horas, permitiéndose solo agua sin gas. (Fuente: instrucciones_pre_post_consulta.pdf)
> - Evitar: 24 horas antes, evita ejercicio intenso, alcohol y medicamentos (a menos que tu médico indique lo contrario). (Fuente: instrucciones_pre_post_consulta.pdf)
> - Horario: El horario ideal para la toma de muestra de hemograma, química sanguínea y glicemia en ayunas es entre las 6:30 a.m. (Fuente: instrucciones_pre_post_consulta.pdf)
> - Examen de Orina (Orina Completa): Debes recoger la orina de la primera micción de la mañana, usar el envase estéril entregado por el laboratorio, realizar aseo genital antes de la recolección (descartando el primer chorro), y entregar la muestra en el laboratorio antes de 2 horas de recolectada. (Fuente: instrucciones_pre_post_consulta.pdf)
> - Coproparasitológico: Debes entregar una muestra de deposiciones frescas (recolectadas en las últimas 2 horas) en el recipiente estéril del laboratorio, sin mezclarla con orina ni papel higiénico. (Fuente: instrucciones_pre_post_consulta.pdf)
>
>Te recomiendo confirmar con tu médico o con el laboratorio los detalles específicos para tu examen.

---

**Pregunta:** ¿Colmena Golden Cross tiene cobertura en la clínica?

**Respuesta del agente:**
> Sí, Colmena Golden Cross tiene cobertura en la clínica para consulta, urgencias y hospitalización, y su convenio se encuentra activo con convenio pleno.
>
> *Fuente: guia_convenios_coberturas.pdf*
> *Categoría: Convenios y Coberturas*
>
> *Fuente: convenios_eps.csv*
> *Categoría: Convenios y Coberturas*

---

**Pregunta:** ¿Cómo protegen mis datos personales?

**Respuesta del agente:**
> En la Clínica Bienestar Integral protegemos tus datos personales implementando diversas medidas de seguridad. Estas incluyen:
>
> - Cifrado SSL/TLS para la transmisión de datos.
> - Control de acceso basado en roles (RBAC).
> - Copias de seguridad diarias con almacenamiento cifrado.
> - Capacitación continua del personal en el manejo de datos sensibles.
> - Auditorías de seguridad semestrales.
> - Política de escritorio limpio y pantalla limpia.
> - Acuerdos de confidencialidad con todos los empleados.
>
> *Fuente: politica_privacidad_datos.pdf*
> *Categoría: Privacidad y Datos)*

---

## Demo en OCI

URL App: http://148.116.104.135:8000

Se realiza instalación y despliegue en OCI

> ![Aplicativo Ejecutando en OCI](assets/InstalaciónOCI.jpg)

Se accede a la app para consultas

> ![Ingresar a APP](assets/AppEjecutando.jpg)

Ejemplo de consulta API

> ![Ingresar a APP](assets/AppFuncionando.jpg)

---

## Estructura del proyecto

```
pamv-alura/
├── docs/
│   ├── convenios_eps.csv
│   ├── faq_consultas_turnos.pdf
│   ├── guia_convenios_coberturas.pdf
│   ├── instrucciones_pre_post_consulta.pdf
│   ├── politica_cancelaciones.pdf
│   └── politica_privacidad_datos.pdf
├── src/
│   ├── ingestion.py        # Carga multi-formato + chunking
│   ├── vectorstore.py      # ChromaDB + embeddings Gemini (incluye list/delete por documento)
│   ├── agent.py            # Integración con Gemini 2.0 Flash
│   └── app.py              # Interfaz Streamlit (chat + gestión de documentos)
├── scripts/
│   └── ingest_docs.py      # CLI de indexación
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Seguridad

- La API Key nunca está en el código — se carga desde variables de entorno (`.env`).
- En producción se recomienda gestionar el secreto con **OCI Vault**.
- ChromaDB persiste en volumen Docker; los documentos no se exponen externamente.

---

## Licencia

MIT — libre uso con atribución.

---

> Proyecto desarrollado como parte del desafío **ONE — Alura + Oracle Next Education**.
