# bcv-tasa

Tasa oficial del Banco Central de Venezuela publicada como JSON estático.
Un workflow de GitHub Actions la consulta los días hábiles y GitHub Pages la sirve.

## Endpoints

| URL | Contenido |
|---|---|
| `https://tonydacamaram-web.github.io/bcv-tasa/latest.json` | Última tasa publicada + la anterior |
| `https://tonydacamaram-web.github.io/bcv-tasa/history/<año>.json` | Todas las tasas del año, por fecha valor |

### `latest.json`

```json
{
  "fecha_valor": "2026-10-05",
  "usd": 871.3689,
  "eur": 981.17880877,
  "cny": 129.97746121,
  "try": 17.73255527,
  "rub": 10.39904073,
  "fuente": "bcv.org.ve",
  "anterior": { "fecha_valor": "2026-10-02", "usd": 866.5612, "eur": 973.92813268, "fuente": "ve.dolarapi.com" },
  "actualizado": "2026-10-03T11:22:51Z"
}
```

- `fecha_valor`: día desde el que rige la tasa. El BCV la publica la tarde del día hábil anterior,
  así que puede ser una fecha futura.
- `anterior`: la tasa que estaba vigente antes. Puede ser `null`.
- `cny`, `try` y `rub` solo aparecen cuando la fuente fue `bcv.org.ve`.

### Tasa vigente para una fecha

```
si hoy >= fecha_valor   → usd
si no                   → anterior.usd
```

Para fechas más antiguas se usa `history/<año>.json`: la entrada con la mayor `fecha_valor <= fecha`.

## Uso desde otros sistemas

```kotlin
// Kotlin (OkHttp)
val json = JSONObject(client.newCall(Request.Builder().url(URL).build()).execute().body!!.string())
```

```python
# Python
tasa = requests.get(URL, timeout=10).json()
```

```js
// JavaScript
const tasa = await (await fetch(URL)).json();
```

GitHub Pages envía `Access-Control-Allow-Origin: *`, por lo que también se puede leer desde el navegador.
Pages cachea unos 10 minutos.

## Cómo funciona

- [`scraper/fetch.py`](scraper/fetch.py) usa solo la librería estándar de Python.
  1. Lee `https://www.bcv.org.ve/`, con la tasa y la fecha valor.
  2. Si falla, usa `https://ve.dolarapi.com`, que solo da USD y EUR.
  3. Rechaza la tasa si el USD varía más de 20 % frente a la anterior. El workflow falla y GitHub avisa por correo.
     Si la variación es real, se ejecuta a mano con `force`.
  4. Solo escribe archivos si hubo cambios.
- `bcv.org.ve` envía una cadena de certificados incompleta.
  [`scraper/sectigo-intermedios.pem`](scraper/sectigo-intermedios.pem) contiene los intermedios correctos de Sectigo,
  así que la verificación SSL queda **activa**. El certificado R36 vence en 2036.
- [`.github/workflows/daily.yml`](.github/workflows/daily.yml) se ejecuta de lunes a viernes a las 9:00, 16:00 y 19:00 (hora de Venezuela),
  y también a mano desde la pestaña Actions.

## Ejecutar localmente

```sh
python scraper/fetch.py
FORCE=1 python scraper/fetch.py   # sin la validación de variación
```
