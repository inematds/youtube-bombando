# YouTube bombando — radar de lo que explota

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

[![Radar de lo que explota](guia/assets/banner-es.jpg)](https://inematds.github.io/youtube-bombando/guia/es/)

## Qué es

**youtube-bombando** es un pequeño sistema que corre solo en tu computadora, cada mañana. Busca en YouTube los videos de la semana en los temas que elijas, anota las vistas de cada uno durante 7 días y arma un panel con lo que está creciendo más rápido. Para cada video, compara las vistas con lo normal del propio canal y dice si la señal es de **contenido**, de **quién publica** (canal grande) o de **quién habla** (invitado). Es para quien graba videos o quiere empezar un canal. Solo necesita Python y una herramienta gratis que lee YouTube; no usa clave ni API de pago.

## 📖 Guía de uso

Guía completa (landing + paso a paso): **https://inematds.github.io/youtube-bombando/guia/es/**

## Requisitos

Python 3.9+ y biblioteca estándar, sin pip, API ni claves. La recolección real usa el ejecutable `yt-dlp` disponible en el PATH; las pruebas no lo ejecutan. Linux con systemd de usuario solo es necesario para instalar el timer. La búsqueda real requiere internet; el modo fixtures y el panel funcionan sin conexión.
## Empezar localmente

```bash
python3 -m unittest discover -s tests -v
python3 bombando/rodada.py --fixtures tests/fixtures
# Abre dados/teste/painel/index.html en el navegador, incluso vía file://.
python3 bombando/rodada.py --so-painel
```

Las fixtures son ejemplos fijos, identificados en el panel; la edad crece a medida que pasa el tiempo. Se graban en `dados/teste/`, con base de datos y panel separados de producción. Repetir la ronda el mismo día conserva la foto única diaria y la caché de los canales. Las pruebas unitarias usan directorios temporales aislados.

Recolección real (ejecútala cuando quieras consultar YouTube):

```bash
python3 bombando/rodada.py
python3 bombando/rodada.py --nicho 'claude code'
```

## Instalación diaria

```bash
bash deploy/instalar.sh
systemctl --user list-timers youtube-bombando.timer
journalctl --user -u youtube-bombando.service
```

El instalador reemplaza `@REPO@` en las units, las copia a `~/.config/systemd/user/`, recarga systemd, activa el timer e inicia/reinicia el servidor del panel. Se puede repetir. La recolección ocurre a las **07:15 en la zona horaria de la máquina**, con `Persistent=true` (recupera la ejecución perdida), tope de 45 minutos, memoria de 1 GB y Nice 10. El timer depende de que el gestor de usuario esté activo; la ejecución después de cerrar sesión requiere linger configurado por el administrador.

Panel en `http://localhost:8795`; el servidor escucha en `0.0.0.0` según la especificación y también queda accesible en la red local. Para detenerlo:

```bash
systemctl --user disable --now youtube-bombando.timer youtube-bombando-painel.service
```

La instalación y la recolección real no forman parte de las pruebas sin conexión.

## Configuración

Edita `config.json`. Cada elemento de `nichos` contiene `nome`, `busca` y `ativo` (booleano). Un video puede pertenecer a varios nichos sin duplicar sus fotos. Desactivar un nicho impide nuevas búsquedas, pero conserva su historial; los videos ya descubiertos se siguen hasta el final de la ventana.

| Campo | Predeterminado | Función |
|---|---:|---|
| `por_nicho_busca` | 40 | Máximo de resultados por búsqueda semanal |
| `dias_acompanhar` | 7 | Ventana desde el primer descubrimiento |
| `max_detalhes_por_rodada` | 250 | Tope de consultas de detalles |
| `max_canais_por_rodada` | 120 (este repo usa 200) | Tope de intentos de consulta de canales por ronda |
| `pausa_s` | 1.5 | Intervalo mínimo entre el fin y el inicio de las llamadas |
| `idioma` | pt | Reservado; no se pasa a yt-dlp (con `lang=pt` lee "3,4 mil" como 34) |
| `regiao` | BR | País informado al mecanismo geo-bypass de yt-dlp |

La región no garantiza resultados geolocalizados; YouTube también considera la conexión. El filtro semanal es el parámetro de búsqueda solicitado a YouTube. El sistema conserva los resultados devueltos por el extractor.

Cada subproceso tiene timeout de 120 segundos, socket de 20 segundos y reintentos limitados. Los errores se registran por nicho/video y la ronda continúa. Los videos explícitamente privados/eliminados quedan como no disponibles; timeout y 429 no provocan esa marca. Las fotos ya recolectadas hoy se saltan. El tope prioriza la velocidad de la última foto; como esta solo guarda el día, usa el mediodía UTC como referencia de esa prioridad, con desempate por descubrimiento e ID. Los videos todavía sin fotos tienen prioridad de velocidad cero.

## Métricas y nota

Las fechas se almacenan en UTC. `timestamp` tiene preferencia sobre `upload_date`; este último representa la medianoche UTC, una aproximación cuando no se proporciona la hora.

- **Edad (h):** horas desde la publicación hasta la generación del panel, limitada a cero para fechas futuras.
- **Velocidad:** vistas de la foto más reciente / `max(idade_h, 1)`; es el promedio desde la publicación, no la velocidad instantánea.
- **Ganancia 24 h:** `(vistas de hoy − vistas de la foto anterior) / días entre fotos`. Sin foto de hoy o sin anterior, queda ausente. Las caídas de conteo se conservan.
- **Multiplicador:** vistas / suscriptores. Suscriptores ausentes o cero dejan la métrica ausente.
- **Nota:** `z-score(velocidad dentro del nicho) + ln(1 + multiplicador)`. El z-score usa la desviación estándar poblacional; con desviación cero o velocidad ausente, vale cero. Un multiplicador ausente aporta cero. La nota puede ser negativa. En “Todos”, usa la mayor nota entre los nichos del video; al seleccionar un nicho, usa la nota de ese nicho. Los no disponibles quedan al final y no entran en las estadísticas ni en los destacados.

Cero y ausencia son distintos: `—` indica dato desconocido. Las vistas de la búsqueda quedan en la base como estimación inicial, separadas de las fotos. La tabla muestra las fotos confirmadas. El **gráfico de crecimiento** (columna “Crescimento”, haz clic para ampliar, y en el video más caliente de cada nicho) pone las vistas en el eje vertical y las horas desde la publicación en el horizontal. Empieza en 0 vistas en la publicación; el tramo punteado va hasta la 1.ª medición (solo el promedio, no hay puntos intermedios) y la línea continua une las mediciones diarias de las 07:15, cada una en la edad que tenía el video ese día.

**Ordenar por** (el panel explica la opción elegida debajo del selector):

| Opción | Qué mide |
|---|---|
| Nota | z-score de las vistas/h dentro del nicho + ln(1 + multiplicador): lo más caliente ahora |
| Velocidad | vistas ÷ edad en horas; favorece videos nuevos |
| Ganancia en 24 h | vistas ganadas desde la medición anterior (necesita 2 días de recolección) |
| Multiplicador | vistas ÷ suscriptores; por encima de 1× superó el tamaño del canal |
| × canal | vistas ÷ mediana de los últimos videos del canal; ≥ 3× rompió la burbuja |
| Vistas | total de vistas, sin mirar edad ni canal |
| Más nuevos | menor edad primero |

**Edad** = tiempo desde que el video fue publicado en YouTube (no desde que el sistema lo encontró); aparece en horas hasta 48 h y después en días + horas.

**Temas en alza:** top 30 videos por nota en cada nicho (y top 30 general sin duplicar IDs). Con al menos 5 videos, un término debe aparecer en dos títulos; en grupos menores, basta uno. Extrae palabras y bigramas adyacentes, elimina stopwords PT/EN, palabras de una letra y números aislados. Cada término recibe una contribución por título, igual a la velocidad del video. Muestra los 15 mayores pesos. Es una heurística léxica, sin IA ni interpretación semántica.

## ¿Por qué explotó? — método y límites

La señal principal es **fator_canal = vistas / mediana de vistas del propio canal**.
Consulta los últimos 20 videos del canal una vez y guarda la muestra en SQLite.
La mediana excluye el propio video analizado y las publicaciones con menos de 3 días.
Cuando la fecha de una entrada no está disponible, excluye esa entrada si está
entre las dos primeras de la lista. Las vistas desconocidas no entran; cero es válido.
Cada video tiene su mediana y `n_amostra` recalculados a partir de la caché, incluso
cuando hay varios videos del mismo canal. En la tabla `canais`, la mediana y el tamaño
representan el video prioritario en la recolección; `amostra` conserva los datos para los demás.

La caché vale hasta 7 días inclusive; solo se renueva después de ese plazo. Los canales de los
videos seguidos (disponibles, dentro de `dias_acompanhar`) con mayor nota tienen
prioridad. El tope cuenta intentos, incluidas las fallas. Los errores conservan la caché
anterior y quedan en el log. La fecha de la caché aparece en `canal_atualizado` en los datos.
No hay llamada extra para la descripción: se guarda cuando llega en el detalle.

`pessoas` en `config.json` es la lista editable de nombres conocidos. El detector
busca nombres completos sin distinguir mayúsculas y minúsculas, en el título y en la
descripción disponible, además de señales de formato: `com Nome Sobrenome`, `ft.`,
`feat.`, entrevista, podcast, palestra, `| Nome Sobrenome`, `- NOME SOBRENOME`
y `#123`. El fragmento encontrado acompaña el motivo. Una mención no comprueba
participación; el método es una heurística, no una demostración de causalidad.

Tamaño por suscriptores de la foto más reciente (o del canal, si faltan): pequeño
por debajo de 10 mil; mediano de 10 mil a 500 mil inclusive; grande por encima de 500 mil.
Sin suscriptores, el tamaño es desconocido. Reglas, en este orden:

| Condición | Categoría |
|---|---|
| Sin vistas confirmadas o mediana ausente/cero | Sin datos |
| Factor ≥ 3 y persona/formato de invitado | Contenido + quién habla |
| Factor ≥ 3 sin persona/formato de invitado | Contenido |
| Factor ≥ 1,5 y persona/formato de invitado | Quién habla |
| Factor < 1,5 y canal grande | Quién publica |
| Demás casos | Mixto |

La regla combinada va primero para que no la absorba “Quién habla”. Los umbrales
son constantes al inicio de `metricas.py`. La ausencia nunca se estima por suscriptores.
Los motivos muestran factor, mediana, tamaño y evidencia de invitado.

El resumen general y por nicho considera videos disponibles con vistas confirmadas,
sin duplicación dentro de cada grupo. La leyenda muestra conteos y porcentajes de
videos y vistas en las **seis categorías**, incluida la combinada por separado para
no contar sus vistas dos veces. Sin vistas totales, los porcentajes son cero. La
conclusión prioriza la insuficiencia de datos (≥ 50% de las vistas sin base); después,
la mayoría estricta (> 50%) de contenido (puro + combinado), quién publica o quién habla;
sin mayoría, informa señales mixtas. “Rompieron la burbuja” lista hasta 5 videos con
factor ≥ 3 de canales pequeños/medianos, ordenados por el factor.

Para completar solo las líneas de base ya existentes, manteniendo intactos el descubrimiento y
las fotos (consulta real de canales):

```bash
python3 bombando/rodada.py --so-canais
python3 bombando/rodada.py --so-canais --nicho 'claude code'
# Variante totalmente sin conexión, usando la base de demostración:
python3 bombando/rodada.py --so-canais --fixtures tests/fixtures
```

`--so-canais` y `--so-painel` son mutuamente excluyentes. En el modo canales, que ninguna
consulta sea necesaria (caché válida o selección vacía) es éxito; la falla en todas las
consultas intentadas devuelve 1, y el éxito parcial devuelve 0. El panel muestra los errores.

## Archivos y operación

`dados/bombando.db` contiene videos, nichos, vínculos, fotos únicas por `(id, dia)`, rondas y canales con sus muestras. Al abrir la base se migra el esquema antiguo sin borrar datos. `dados/.lock` usa `flock` no bloqueante para evitar concurrencia. `dados/logs/AAAA-MM-DD.log` guarda fallas y resumen. `painel/index.html` contiene CSS, JS, datos y SVG inline; `painel/dados.json` tiene los mismos datos y `painel/historico/AAAA-MM-DD.html` es la última copia de ese día. Las miniaturas solo cargan después de hacer clic en “Carregar miniaturas (internet)”; las fuentes usan fallback del sistema, sin CDN.

`--so-painel` mantiene el estado y el horario de la última recolección y regenera las métricas. `--nicho NOME` restringe búsqueda, seguimiento y canales, conservando los demás datos en el panel. El código de salida es cero cuando algún nicho tuvo una búsqueda válida, incluso con errores parciales; si ningún nicho tuvo éxito, devuelve 1. Las fallas estructurales (configuración, base o escritura) también devuelven 1. Un lock ocupado es una ejecución omitida con código cero.

Las fixtures están en `tests/fixtures/buscas.json` (mapa por término de búsqueda, con `entries`), `detalhes.json` (mapa por ID) y `canais.json` (mapa por channel_id con entries). `{"erro":"mensagem"}` simula una falla; `"indisponivel":true` simula una eliminación. No hay fallback de fixtures a la red.

## El proceso, de principio a fin

1. **🧠 sesión con Nei — elegir los nichos.** Comando: `python3 -m json.tool config.json`. Revisar nombres, búsquedas, límites y campos `ativo` después de editar el archivo.
2. **⚙️ script/timer — verificar sin red.** Comando: `python3 -m unittest discover -s tests -v`. Prueba métricas, persistencia, fallas y panel en directorios temporales.
3. **⚙️ script/timer — demostrar la ronda.** Comando: `python3 bombando/rodada.py --fixtures tests/fixtures`. Descubre ejemplos, graba fotos, consulta fixtures de los canales, calcula métricas y genera HTML en `dados/teste/painel/`.
4. **🧠 sesión con Nei — revisar el resultado.** Comando: `xdg-open dados/teste/painel/index.html`. Comparar nichos, notas, historial, temas y “¿Por qué explotó?”.
5. **⚙️ script/timer — consultar los videos reales.** Comando: `python3 bombando/rodada.py`. Ejecuta descubrimiento semanal → seguimiento diario → línea de base de los canales → métricas → panel, con lock y logs.
6. **⚙️ script — completar canales de videos seguidos.** Comando: `python3 bombando/rodada.py --so-canais`. Respeta caché, tope, ventana y filtro sin descubrimiento ni fotos. Para probar sin conexión, añadir `--fixtures tests/fixtures`.
7. **🧠 sesión con Nei — activar la rutina cuando quieras.** Comando: `bash deploy/instalar.sh`. Instala la programación y el servidor.
8. **⚙️ script/timer — repetir a diario.** Comando ejecutado por la unit: `python3 bombando/rodada.py`. A las 07:15, actualiza las fotos dentro de la ventana y la copia diaria.
9. **🧠 sesión con Nei — ajustar e investigar.** Comandos: `journalctl --user -u youtube-bombando.service` y `python3 bombando/rodada.py --so-painel`. Revisar errores, cambiar nichos y regenerar la visualización sin nueva recolección.
