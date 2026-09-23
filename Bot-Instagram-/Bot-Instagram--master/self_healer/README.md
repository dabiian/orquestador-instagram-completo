# Self Healer — Auto-Healing Locators para Web Automation

Self Healer es un servicio REST **inteligente de reparación de selectores** que usa IA (LLM) para mantener tus tests y bots de automatización web funcionando cuando los locators se rompen. Compatible con **Selenium**, **Playwright**, **Puppeteer** y cualquier herramienta que haga requests HTTP.

## 📋 Contenido

- [Qué es Self Healer](#qué-es-self-healer)
- [Instalación Inicial](#instalación-inicial)
- [Configuración](#configuración)
- [Ejecutar el Servidor API](#ejecutar-el-servidor-api)
- [Integración en tu Proyecto](#integración-en-tu-proyecto)
- [Ejemplos](#ejemplos)
- [Cómo Funciona](#cómo-funciona)
- [Endpoints de la API (Referencia)](#endpoints-de-la-api-referencia)
- [Troubleshooting](#troubleshooting)

---

## Qué es Self Healer

Self Healer es un **servidor REST** que:

1. **Recibe locators rotos** (XPath, CSS Selector, etc.) con contexto HTML
2. **Genera candidatos alternativos** usando un LLM (OpenAI, DeepSeek, Anthropic, etc.)
3. **Retorna múltiples opciones** ordenadas por confianza
4. **Persiste selectores funcionando** en SQLite local
5. **Aprende con feedback** para mejorar futuras sugerencias

Esto **elimina horas de debugging manual** cuando el HTML cambia.

---

## Instalación Inicial

### Requisitos

- Python >= 3.8
- pip (gestor de paquetes)
- Una clave de API de un proveedor LLM (OpenAI, DeepSeek, Anthropic, etc.)

### 1. Descargar o Clonar

```bash
# Si está en git
git clone <repository-url>
cd self_healer

# O si ya lo descargaste
cd /ruta/a/self_healer
```

### 2. Crear Entorno Virtual (Recomendado)

**PowerShell:**
```powershell
python -m venv venv
& ".\venv\Scripts\Activate.ps1"
```

**Bash/Linux/Mac:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Verificar Instalación

```bash
python -c "import self_healer; print('✓ Self Healer instalado')"
```

---

## Configuración

### Crear `.env` en la Carpeta `self_healer/`

Crea un archivo `self_healer/.env` con tus credenciales (elige UN proveedor):

```bash
# OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1

# O DeepSeek
# DEEPSEEK_API_KEY=your_deepseek_key
# DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# O Anthropic
# ANTHROPIC_API_KEY=your_anthropic_key
```

**Notas:**
- Solo necesitas UNA clave; el sistema usa la primera disponible
- No compartir este archivo (agrega a `.gitignore`)
- Deja comentado lo que no uses

---

## Ejecutar el Servidor API

### Inicio Rápido

**PowerShell:**
```powershell
& ".\venv\Scripts\Activate.ps1"
python -m self_healer.api.server --host 127.0.0.1 --port 8765 --provider openai
```

**Bash:**
```bash
source venv/bin/activate
python -m self_healer.api.server --host 127.0.0.1 --port 8765 --provider openai
```

### Verificar que Está Corriendo

```bash
curl http://127.0.0.1:8765/health
# Esperado: {"status": "ok"}
```

### Opciones del Servidor

```
--host HOST              Host donde escucha (default: 127.0.0.1)
--port PORT              Puerto (default: 8765)
--provider PROVIDER      openai|deepseek|anthropic|fake
--log-level LEVEL        debug|info|warning|error (default: info)
```

---

## Integración en tu Proyecto

### Cómo Funciona

Self Healer es **independiente** de tu herramienta de automatización. Tu código:

1. Intenta encontrar un elemento
2. Si falla, hace un request HTTP: `POST http://127.0.0.1:8765/v1/heal`
3. Recibe candidatos ordenados por confianza
4. Prueba cada uno hasta encontrar uno que funcione
5. (Opcional) Envía feedback para mejorar futuras sugerencias

### Patrón Recomendado: Un Solo Wrapper en la Frontera del Driver

La forma más limpia de integrarlo no es añadir reintentos en cada función ni repetir lógica de XPath en todo el proyecto. La idea es envolver el WebDriver una sola vez, en el punto donde creas el navegador, y dejar que ese wrapper intercepte las búsquedas:

1. Creas el cliente HTTP que habla con la API de Self Healer.
2. Envuelves el driver real con un proxy o adaptador.
3. Todo `find_element()` y `find_elements()` pasa por ese proxy.
4. Si el locator original falla, el proxy consulta `/v1/heal`, prueba candidatos y devuelve el elemento resuelto.
5. El resto del proyecto sigue igual, sin duplicar retries en cada función.

Ese enfoque mantiene el código de negocio limpio y concentra el healing en un único lugar.

### Ejemplo Real: `SelfHealerAPIClient` + `SelfHealerDriverProxy`

```python
from selenium import webdriver
from selenium.webdriver.common.by import By

from app.core.self_healer_client import SelfHealerAPIClient, SelfHealerDriverProxy

raw_driver = webdriver.Chrome()

client = SelfHealerAPIClient(
    base_url="http://127.0.0.1:8765",
    project_name="my-project",
    timeout_seconds=30,
)

# A partir de aquí usas `driver` como si fuera Selenium normal,
# pero con healing automático en las búsquedas.
driver = SelfHealerDriverProxy(raw_driver, client)

driver.get("https://example.com")

# Si este xpath falla, el proxy consulta Self Healer y prueba candidatos.
element = driver.find_element(By.XPATH, "//button[@id='submit']", description="Submit button")
element.click()

# También funciona con múltiples elementos.
items = driver.find_elements(By.CSS_SELECTOR, ".product-card", description="Product cards")
```

### Qué Hace `build_self_healer_wrapper` en la Práctica

En vez de crear la integración dentro de cada método de tu aplicación, el constructor del bot puede decidir si usa el driver normal o el driver envuelto:

1. Abres Chrome, Edge o el navegador que uses.
2. Creas el cliente de Self Healer solo una vez.
3. Si el feature está activo, reemplazas el driver crudo por el wrapper.
4. Desde ese momento, toda la app usa el mismo objeto `driver`.

Eso significa que tus funciones existentes no cambian: siguen llamando `driver.find_element(...)`, `driver.click(...)` o `driver.find_elements(...)`, y el healing ocurre detrás de escena cuando hace falta.

### Ejemplo de Integración con Selenium

```python
from selenium import webdriver

from app.core.self_healer_client import SelfHealerAPIClient, SelfHealerDriverProxy

raw_driver = webdriver.Chrome()

client = SelfHealerAPIClient(
    base_url="http://127.0.0.1:8765",
    project_name="my-selenium-project",
    timeout_seconds=30,
)

driver = SelfHealerDriverProxy(raw_driver, client)
driver.get("https://example.com")

# Todas las búsquedas pasan por el proxy y se reparan si fallan.
submit = driver.find_element("xpath", "//button[@id='submit']", description="Submit button")
submit.click()
```

### Ejemplo de Integración con Playwright

```python
import requests
from playwright.sync_api import sync_playwright

SELF_HEALER_URL = "http://127.0.0.1:8765"
PROJECT_NAME = "my-playwright-project"

def heal_locator(page, strategy, value, description=""):
    """Pide candidatos a Self Healer y prueba cada uno en Playwright."""
    response = requests.post(f"{SELF_HEALER_URL}/v1/heal", json={
        "identity": {
            "project_name": PROJECT_NAME,
            "framework": "playwright",
            "page_key": page.url,
            "element_key": description or value,
        },
        "url": page.url,
        "original_strategy": strategy,
        "original_value": value,
        "html": page.content()[:50000],
        "action": "find_element",
        "error": "locator failed",
        "target_description": description,
    }, timeout=30)

    for candidate in response.json().get("candidates", []):
        candidate_strategy = str(candidate.get("strategy", "xpath")).lower()
        candidate_value = str(candidate.get("value", "")).strip()

        if not candidate_value:
            continue

        if candidate_strategy == "xpath":
            locator = page.locator(f"xpath={candidate_value}")
        elif candidate_strategy == "css":
            locator = page.locator(candidate_value)
        else:
            continue

        if locator.count() > 0:
            requests.post(f"{SELF_HEALER_URL}/v1/feedback", json={
                "identity": {
                    "project_name": PROJECT_NAME,
                    "framework": "playwright",
                    "page_key": page.url,
                    "element_key": description or value,
                },
                "candidate": candidate,
                "status": "success",
                "error": "",
            }, timeout=30)
            return locator.first

    raise RuntimeError(f"No se pudo reparar el locator: {value}")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com")

    button = heal_locator(page, "xpath", "//button[@id='submit']", "Submit button")
    button.click()

    browser.close()
```

### Idea Clave para Playwright

En Playwright no se usa `SelfHealerDriverProxy` de forma directa porque el wrapper del proyecto está construido para Selenium. La forma práctica de integrarlo es crear un helper como `heal_locator(...)` y reutilizarlo en tus tests, pages o fixtures para que todo el healing viva en un solo módulo.

### Ejemplo: Selenium

```python
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By

SELF_HEALER_URL = "http://127.0.0.1:8765"
PROJECT_NAME = "my-project"

driver = webdriver.Chrome()
driver.get("https://example.com")

def find_element_with_healing(driver, xpath, description=""):
    """Encuentra elemento con auto-healing si falla."""
    try:
        # Intento 1: locator original
        return driver.find_element(By.XPATH, xpath)
    except Exception as error:
        print(f"⚠ Locator failed: {description or xpath}")
        
        # Solicita candidatos
        response = requests.post(f"{SELF_HEALER_URL}/v1/heal", json={
            "identity": {
                "project_name": PROJECT_NAME,
                "page_key": driver.current_url,
                "element_key": description or xpath
            },
            "url": driver.current_url,
            "original_strategy": "xpath",
            "original_value": xpath,
            "html": driver.page_source[:50000],  # Limita a 50KB
            "action": "find_element",
            "error": str(error),
            "target_description": description
        }, timeout=30)
        
        candidates = response.json().get("candidates", [])
        
        # Prueba cada candidato
        for idx, candidate in enumerate(candidates, 1):
            try:
                strategy = candidate.get("strategy", "xpath").lower()
                value = candidate.get("value", "")
                
                if strategy == "xpath":
                    element = driver.find_element(By.XPATH, value)
                elif strategy == "css":
                    element = driver.find_element(By.CSS_SELECTOR, value)
                else:
                    continue
                
                print(f"✓ Healed with candidate {idx}!")
                
                # Envía feedback
                requests.post(f"{SELF_HEALER_URL}/v1/feedback", json={
                    "identity": {
                        "project_name": PROJECT_NAME,
                        "page_key": driver.current_url,
                        "element_key": description or xpath
                    },
                    "candidate": candidate,
                    "status": "success"
                })
                
                return element
            except Exception:
                continue
        
        # Si nada funciona, lanza error original
        raise error

# Uso
button = find_element_with_healing(driver, "//button[@id='submit']", "Submit button")
button.click()
```

### Ejemplo: Playwright

```python
import requests
from playwright.sync_api import sync_playwright

SELF_HEALER_URL = "http://127.0.0.1:8765"
PROJECT_NAME = "my-playwright-project"

def find_with_healing(page, selector, description=""):
    """Encuentra elemento con healing en Playwright."""
    try:
        return page.locator(selector).first
    except Exception as error:
        # Solicita candidatos
        response = requests.post(f"{SELF_HEALER_URL}/v1/heal", json={
            "identity": {
                "project_name": PROJECT_NAME,
                "page_key": page.url,
                "element_key": description or selector
            },
            "url": page.url,
            "original_strategy": "xpath",
            "original_value": selector,
            "html": page.content()[:50000],
            "action": "find_element",
            "error": str(error),
            "target_description": description
        }, timeout=30)
        
        candidates = response.json().get("candidates", [])
        
        for idx, candidate in enumerate(candidates, 1):
            try:
                value = candidate.get("value", "")
                strategy = candidate.get("strategy", "xpath").lower()
                
                if strategy == "xpath":
                    element = page.locator(f"xpath={value}").first
                elif strategy == "css":
                    element = page.locator(value).first
                else:
                    continue
                
                if element.is_visible():
                    print(f"✓ Healed with candidate {idx}!")
                    
                    # Feedback
                    requests.post(f"{SELF_HEALER_URL}/v1/feedback", json={
                        "identity": {
                            "project_name": PROJECT_NAME,
                            "page_key": page.url,
                            "element_key": description or selector
                        },
                        "candidate": candidate,
                        "status": "success"
                    })
                    
                    return element
            except Exception:
                continue
        
        raise error

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com")
    
    button = find_with_healing(page, "//button[@id='submit']")
    button.click()
```

### Wrapper Reutilizable (Recomendado)

Crea `healing_client.py`:

```python
import requests

class HealingClient:
    def __init__(self, api_url="http://127.0.0.1:8765", project_name="my-project"):
        self.api_url = api_url
        self.project_name = project_name
    
    def get_candidates(self, current_url, html, xpath, description="", error=""):
        """Solicita candidatos a Self Healer."""
        try:
            response = requests.post(f"{self.api_url}/v1/heal", json={
                "identity": {
                    "project_name": self.project_name,
                    "page_key": current_url,
                    "element_key": description or xpath
                },
                "url": current_url,
                "original_strategy": "xpath",
                "original_value": xpath,
                "html": html[:50000],
                "action": "find_element",
                "error": error,
                "target_description": description
            }, timeout=30)
            return response.json().get("candidates", [])
        except Exception as e:
            print(f"Healing request failed: {e}")
            return []
    
    def send_feedback(self, current_url, candidate, status, description="", error=""):
        """Envía feedback sobre un candidato."""
        try:
            requests.post(f"{self.api_url}/v1/feedback", json={
                "identity": {
                    "project_name": self.project_name,
                    "page_key": current_url,
                    "element_key": description
                },
                "candidate": candidate,
                "status": status,
                "error": error
            }, timeout=30)
        except Exception as e:
            print(f"Feedback failed: {e}")
```

---

## Ejemplos

### Ejemplo Completo: Selenium + Healing

```python
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SELF_HEALER_URL = "http://127.0.0.1:8765"
PROJECT_NAME = "my-automation"

driver = webdriver.Chrome()
driver.get("https://example.com")

def find_with_healing(xpath, description=""):
    try:
        element = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        return element
    except Exception as error:
        print(f"⚠ Locator failed: {description}")
        
        response = requests.post(f"{SELF_HEALER_URL}/v1/heal", json={
            "identity": {
                "project_name": PROJECT_NAME,
                "page_key": driver.current_url,
                "element_key": description or xpath
            },
            "url": driver.current_url,
            "original_strategy": "xpath",
            "original_value": xpath,
            "html": driver.page_source[:50000],
            "action": "find_element",
            "error": str(error),
            "target_description": description
        }, timeout=30)
        
        candidates = response.json().get("candidates", [])
        
        for idx, candidate in enumerate(candidates, 1):
            try:
                element = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, candidate["value"]))
                )
                print(f"✓ Healed with candidate {idx}!")
                
                requests.post(f"{SELF_HEALER_URL}/v1/feedback", json={
                    "identity": {
                        "project_name": PROJECT_NAME,
                        "page_key": driver.current_url,
                        "element_key": description or xpath
                    },
                    "candidate": candidate,
                    "status": "success"
                })
                
                return element
            except Exception:
                pass
        
        raise error

# Uso
try:
    button = find_with_healing("//button[@id='old-id']", "Submit button")
    button.click()
except Exception as e:
    print(f"Failed: {e}")

driver.quit()
```

### Ejemplo: Pytest + Healing

```python
import pytest
from selenium import webdriver
from healing_client import HealingClient

@pytest.fixture
def browser():
    driver = webdriver.Chrome()
    yield driver
    driver.quit()

@pytest.fixture
def healing(browser):
    return HealingClient(api_url="http://127.0.0.1:8765", project_name="tests")

def test_login(healing, browser):
    browser.get("https://example.com/login")
    
    # Tu código que usa healing
    candidates = healing.get_candidates(
        browser.current_url,
        browser.page_source,
        "//input[@name='username']",
        "Username field"
    )
```

---

## Cómo Funciona

### Flujo

```
┌──────────────────────────────────────────┐
│ 1. Intenta find_element(xpath)           │
└──────────────┬───────────────────────────┘
               │
        ┌──────┴──────┐
        │             │
        ▼ ✓ Funciona! ▼ ✗ Error
      Return        ↓
              ┌──────────────────────────────────────┐
              │ 2. POST /v1/heal a Self Healer      │
              │    - XPath original                  │
              │    - HTML actual                     │
              │    - Descripción                     │
              └──────────────┬───────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │ 3. LLM genera candidatos   │
              │    ["xpath1", "css1", ...] │
              └──────────────┬──────────────┘
                             │
              ┌──────────────▼──────────────┐
              │ 4. Prueba cada candidato   │
              │    try: find_element(...)  │
              └──────────────┬──────────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
                    ▼ ✓ Funciona!     ▼ ✗ Falla
                ┌─────────────────────────────┐
                │ 5. Feedback "success"       │
                │ 6. Retorna elemento         │
                │ 7. Próximas búsquedas son   │
                │    más rápidas (caché)      │
                └─────────────────────────────┘
```

### Base de Datos Local

Selectores funcionando se guardan en:
```
.self_healer/
├── healer.db  (SQLite)
└── ...
```

**En futuras búsquedas:**
1. Busca en caché local (muy rápido ✓)
2. Si encuentra, lo usa sin llamar a API
3. Si no, solicita candidatos frescos

---

## Endpoints de la API (Referencia)

### POST /v1/heal

Solicita candidatos para un locator roto.

**Request:**
```json
{
  "identity": {
    "project_name": "my-project",
    "page_key": "https://example.com/login",
    "element_key": "username_field"
  },
  "url": "https://example.com/login",
  "original_strategy": "xpath",
  "original_value": "//input[@name='username']",
  "html": "<html>...</html>",
  "action": "find_element",
  "error": "NoSuchElementException",
  "target_description": "Username input field"
}
```

**Response:**
```json
{
  "candidates": [
    {
      "strategy": "xpath",
      "value": "//input[@id='username']",
      "confidence": 0.98
    },
    {
      "strategy": "css",
      "value": "input#user-email",
      "confidence": 0.92
    }
  ]
}
```

### POST /v1/feedback

Envía feedback sobre un candidato.

**Request:**
```json
{
  "identity": {
    "project_name": "my-project",
    "page_key": "https://example.com/login",
    "element_key": "username_field"
  },
  "candidate": {
    "strategy": "xpath",
    "value": "//input[@id='username']"
  },
  "status": "success",
  "error": ""
}
```

**Response:** `{"status": "ok"}`

### GET /health

Verifica si el servidor está corriendo.

**Response:**
```json
{"status": "ok"}
```

---

## Troubleshooting

### "Connection refused" a http://127.0.0.1:8765

**Solución:**
```bash
# Inicia el servidor en otra terminal
python -m self_healer.api.server --host 127.0.0.1 --port 8765 --provider openai
```

### "OPENAI_API_KEY not set"

**Solución:**
```bash
# Crea self_healer/.env
echo "OPENAI_API_KEY=sk-your-key" > self_healer/.env
```

### El healing es lento

**Causa:** Llamadas a LLM tardan ~2-5 segundos

**Soluciones:**
- Aumenta timeouts (`timeout=30` en requests)
- Usa proveedor más rápido (DeepSeek vs OpenAI)
- Caché local acelera futuras búsquedas

### Los candidatos no funcionan

**Pasos:**
1. Verifica que el elemento existe en la página
2. Proporciona descripción más clara
3. Abre un issue si persiste

---

## Próximos Pasos

1. **Instala:** `pip install -r requirements.txt`
2. **Configura:** `self_healer/.env` con clave de API
3. **Inicia servidor:** `python -m self_healer.api.server ...`
4. **Integra:** Usa ejemplos de arriba en tu proyecto
5. **Monitorea:** Usa `--log-level debug` para debug

---

## Tests

```bash
pip install pytest
pytest -v tests/
```

---

## Soporte

- **Documentación:** Revisa ejemplos arriba
- **Tests:** `tests/`
- **Issues:** Abre un issue si algo falla
- **Debug:** Usa `--log-level debug` en servidor

---

**¡Self Healer listo! Integra en tu proyecto ahora.**
