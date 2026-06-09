# Sanctions / PEP Screening — AHC Intelligence

Motor de screening KYC/AML para sujetos obligados de SENACLAFT (Uruguay).
Consulta listas OFAC y fuentes abiertas. Nunca emite determinaciones legales.

---

## Estructura

```
sanctions/
├── ofac_loader.py     Descarga, caché y parsing de listas SDN + Consolidated
├── matcher.py         Matching fuzzy con normalización de nombres
├── pep_screener.py    Búsqueda adverse media / posibles indicios PEP
├── report_builder.py  Construcción del reporte JSON final
├── main.py            CLI end-to-end
├── requirements.txt   Dependencias adicionales
└── cache/             XMLs cacheados localmente (excluir del repo)
```

---

## Instalación

Desde `local-infrastructure/`:

```bash
pip install -r sanctions/requirements.txt
```

Dependencias: `rapidfuzz`, `duckduckgo-search`, `requests` (ya incluido en el proyecto).

---

## Uso rápido

```bash
# Desde local-infrastructure/
python -m sanctions.main --nombre "Juan García López"

# Con umbral personalizado y guardado a archivo
python -m sanctions.main --nombre "Petróleo de Venezuela S.A." --umbral 80 --output reporte.json

# Forzar descarga de listas aunque el caché sea reciente
python -m sanctions.main --nombre "John Smith" --forzar
```

### Uso como módulo Python

```python
from sanctions import actualizar_listas, buscar_en_ofac, screening_pep_adverse
from sanctions import construir_reporte, reporte_a_json

db            = actualizar_listas()
coincidencias = buscar_en_ofac("Juan García López", db, umbral=85)
pep           = screening_pep_adverse("Juan García López")
reporte       = construir_reporte("Juan García López", coincidencias, pep, db)
print(reporte_a_json(reporte))
```

---

## Formato del reporte

```json
{
  "consulta": "Juan García López",
  "timestamp": "2026-06-09T10:30:00Z",
  "ofac": {
    "coincidencias": [
      {
        "uid": "12345",
        "nombre": "GARCIA LOPEZ, JUAN",
        "score": 97.5,
        "tipo_match": "nombre_principal",
        "lista": "SDN",
        "programas": ["SDGT"],
        "paises": ["Venezuela"],
        "fuente": "https://sanctionssearch.ofac.treas.gov/Details.aspx?id=12345"
      }
    ],
    "riesgo": "alto"
  },
  "pep_adverse_media": {
    "posibles_coincidencias": [
      {
        "titulo": "...",
        "extracto": "...",
        "url": "https://...",
        "tipo": "posible_pep",
        "confianza": "medio",
        "fuente_nombre": "DuckDuckGo Web Search"
      }
    ],
    "nota": "Requiere verificación humana. No constituye determinación legal..."
  },
  "listas_actualizadas_al": "2026-06-09T08:00:00",
  "publicacion_ofac": "06/09/2026"
}
```

### Niveles de riesgo OFAC

| Nivel    | Criterio                                                               |
|----------|------------------------------------------------------------------------|
| `alto`   | Score ≥ 95 en nombre principal; o ≥ 90 + programa crítico (SDGT, etc) |
| `revisar`| Coincidencia sobre umbral que no alcanza "alto"                        |
| `ninguno`| Sin coincidencias sobre el umbral configurado                          |

### Niveles de confianza PEP

| Nivel   | Criterio                                                     |
|---------|--------------------------------------------------------------|
| `alto`  | ≥ 5 resultados, o coincidencia en Wikipedia                  |
| `medio` | 2–4 resultados en fuentes web                                |
| `bajo`  | 1 resultado                                                  |

---

## Caché de listas OFAC

Las listas se descargan de:
- **SDN**: `https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN_XML.ZIP`
- **Consolidated**: `https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/CONS_PRIM.ZIP`

Fallback si el SLS no responde: `https://www.treasury.gov/ofac/downloads/`

El caché se refresca automáticamente cada **12 horas**. Los archivos XML se guardan
en `sanctions/cache/` junto con `meta.json` (timestamp + status HTTP de cada descarga).

Agregar al `.gitignore`:
```
local-infrastructure/sanctions/cache/*.xml
local-infrastructure/sanctions/cache/meta.json
```

---

## Cron job — refresco 2x/día

### Linux / Cloud Run (cron del sistema)

```bash
# Agregar a crontab (crontab -e):
# Refresca listas OFAC a las 06:00 y 18:00 UTC
0 6,18 * * * cd /app && python -m sanctions.main --nombre "_warmup_" --forzar > /dev/null 2>&1
```

O, más limpio, un script dedicado de warmup:

```bash
# /app/refresh_ofac.sh
#!/bin/bash
cd /app
python -c "from sanctions.ofac_loader import actualizar_listas; actualizar_listas(forzar=True)"
```

```bash
# crontab
0 6,18 * * * /app/refresh_ofac.sh >> /var/log/ofac_refresh.log 2>&1
```

### Integración con el polling loop existente (main_processor.py)

En `main_processor.py`, agregar al loop principal:

```python
from sanctions.ofac_loader import actualizar_listas, _cache_vigente

# Al inicio del proceso, y cada 12 horas dentro del loop:
if not _cache_vigente():
    actualizar_listas()
```

### Windows (Task Scheduler)

```powershell
# Crear tarea programada que corre 2x/día
$action  = New-ScheduledTaskAction -Execute "python" `
           -Argument "-m sanctions.main --nombre _warmup_ --forzar" `
           -WorkingDirectory "C:\ruta\local-infrastructure"
$trigger = New-ScheduledTaskTrigger -Daily -At "06:00AM"
Register-ScheduledTask -TaskName "OFAC-Refresh-AM" -Action $action -Trigger $trigger

$trigger2 = New-ScheduledTaskTrigger -Daily -At "06:00PM"
Register-ScheduledTask -TaskName "OFAC-Refresh-PM" -Action $action -Trigger $trigger2
```

---

## Notas de compliance

- El módulo nunca afirma que una persona "es PEP" ni que está sancionada.
  Solo reporta coincidencias con scores y fuentes para que el oficial decida.
- Cada coincidencia OFAC incluye UID y URL del portal oficial para trazabilidad.
- Toda salida de `pep_screener` incluye la fuente citada; sin fuente = no se reporta.
- Los umbrales de matching son configurables para ajustar sensibilidad / especificidad.
- Recomendación: umbral ≥ 85 para producción; 75 para revisión ampliada.
