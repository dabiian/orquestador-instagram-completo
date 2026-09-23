# Bot Instagram — Entrega final estable

Esta carpeta contiene la version corregida para entrega.

## Puesta en marcha

1. Crear/activar el entorno virtual.
2. Instalar dependencias:

```powershell
pip install -r requirements.txt
```

3. Copiar `.env.example` a `.env` y completar las variables del entorno.
4. Ejecutar:

```powershell
$env:PYTHONIOENCODING="utf-8"
python -u main.py
```

El bot escribe su log persistente en `logs/bot.log` con UTF-8.

## Validacion

Consultar `VALIDACION_FINAL.txt`. La suite ejecutada en la entrega obtuvo 15 pruebas PASS y 9/9 configuraciones de reglas validadas.

## Nota sobre logs de PowerShell

No se incluye el `bot_log.txt` de una ejecucion anterior. En Windows PowerShell 5.1, `Tee-Object` puede crear archivos Unicode/UTF-16 independientemente del encoding de Python. Para auditoria usa el `logs/bot.log` generado por el propio bot, o ejecuta PowerShell 7 si necesitas capturar stdout con herramientas del shell.

## Contrato de puntuación

La puntuación principal de clasificación (`commercial_intent_score`) usa una escala de **0-100** y **60** como umbral de engagement. La decisión es `QUALIFIED` desde 60, `REVIEW` por debajo de 60 cuando el candidato no fue descartado, y `DISCARDED` cuando las reglas obligan a omitirlo. El campo backend legado `qualification_score` continúa siendo entero 0-10 y se deriva de esa puntuación.
