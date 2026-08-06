# erd — ERD de PostgreSQL · documentación del esquema, generada

[English](README.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · **Español**

Una skill de [Claude Code](https://claude.com/claude-code) que se conecta a la base de
datos, lee el esquema real y **produce el ERD y la referencia del esquema en una sola
pasada.**

Nada se dibuja a mano, así que **el diagrama no puede desviarse de la base de datos.**
Cuando el esquema cambia, basta con ejecutarlo de nuevo.

```bash
python3 introspect.py && python3 merge_desc.py && python3 build_erd.py && python3 build_html.py
```

En una base de datos de 100 tablas y 1235 columnas, el resultado es **un único archivo
HTML de 3.1 MB** — índice, diagrama de conjunto, 17 ERD por área, tablas de columnas por
tabla y el ERD detallado completo, todo dentro de él.

## Qué se obtiene

| Salida | Propósito |
|---|---|
| `<docname>.html` | **Referencia del esquema** — índice · ERD de conjunto · ERD por área · tablas de columnas por tabla · ERD completo. Un único HTML autocontenido con los diagramas incrustados |
| `<docname>.docx` | Para entrega e impresión (diagramas + tablas de descripción de columnas + lista de FK) |
| `<docname>.graphml` | Se abre en yEd para reorganizar y reexportar a mano |
| `out/erd_*.png` · `.svg` | Vista de conjunto · detalle por área · diagrama completo |

El HTML salta directamente del índice a cualquier tabla, y **al hacer clic en un ERD se
abre a tamaño completo.** Es vectorial (SVG), así que el texto se mantiene nítido por
mucho que se amplíe. Compartirlo es enviar un archivo, nada más.

## Por qué

La documentación de bases de datos es fácil de escribir y difícil de mantener. El esquema
avanza, el diagrama es lo primero que envejece, nadie mira un diagrama desactualizado y,
al final, nadie confía en el documento.

Por eso se imponen tres reglas.

**① El diagrama sale de la base de datos.** Nadie lo dibuja. Se leen `information_schema`
y `pg_catalog` para obtener tablas, columnas, tipos, PK, FK (incluidas las reglas de
borrado), restricciones únicas, índices y CHECK.

**② Las descripciones nunca se pierden.** Un ERD vale por las descripciones de sus
columnas — y si la redacción que alguien pulió desaparece cada vez que se regenera el
documento, nadie vuelve a escribir descripciones. Por eso **las descripciones se heredan
de la edición anterior del documento.**

```bash
ERD_DOC_HTML=anterior.html python3 merge_desc.py
#   descripciones de columna heredadas de anterior.html: 1123
#   columnas por fuente de la descripción: {'ddl': 268, 'doc': 951, 'orm': 0, 'manual': 16, 'common': 0, 'none': 0}
```

Si `none` no es 0, se muestra la lista de columnas que siguen vacías. **Las columnas sin
descripción no pasan de largo en silencio.**

**③ La calidad del diagrama no se juzga a ojo.** Cada renderizado imprime su propia
verificación.

```
verificación erd_area_A.png: etiqueta↔tabla 0 · etiqueta↔etiqueta 0 · línea↔tabla 0 · solape vertical 0 · solape horizontal 0
verificación erd_overview.png: etiqueta↔tabla n/d · etiqueta↔etiqueta n/d · línea↔tabla 0 · solape vertical 0 · solape horizontal 0
```

Una etiqueta que cubre una tabla, o líneas montadas una sobre otra, se manifiestan como un
número. Todos los contadores deben dar 0; cualquier valor que deba ser 0 y no lo sea añade
una cola `[aviso]` en la misma línea. `n/d` significa que esa comprobación no se aplica a
ese diagrama — el diagrama general no dibuja etiquetas de relación, así que los contadores
de etiquetas no tienen nada que medir, e imprimir 0 afirmaría un resultado limpio de una
comprobación que nunca se ejecutó.

## Instalación

```bash
git clone git@github.com:uygnoey/erd-skill.git
bash erd-skill/install.sh
```

`install.sh` se encarga de la colocación (`~/.claude/skills/erd`), las dependencias
(`python-docx`, `pillow`) y la fuente Pretendard. Al terminar, **iniciar una nueva sesión
de Claude Code** y decir «dibuja el ERD» o invocar `/erd`.

| Comando | Qué hace |
|---|---|
| `bash install.sh` | Instala en `~/.claude/skills/erd` (por defecto) |
| `bash install.sh --project` | Instala en `./.claude/skills/erd` del proyecto actual |
| `bash install.sh --check` | Solo comprueba, no cambia nada |

Los detalles están en [INSTALL.es.md](INSTALL.es.md).

### Requisitos

- Python 3.9+ / `python-docx` / `pillow`
- `psql` o `docker`
- PostgreSQL **9.4 o posterior** en el servidor (verificado en 9.4, 9.6, 10, 11, 12, 16
  y 17). Cualquier versión anterior se rechaza con un mensaje en lugar de producir un
  esquema leído a medias
- Una fuente con la cobertura que el esquema necesite — el cuerpo del texto usa Pretendard
  (se instala automáticamente); si falta, entra la fuente por defecto del sistema

## Uso

```bash
cd ~/.claude/skills/erd/scripts

export ERD_PROJ=/path/to/project        # dónde se escriben los documentos
export ERD_WORK=/tmp/erd-build          # artefactos intermedios
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='Referencia del esquema de Nuestro Servicio'
export ERD_LANG=es                      # en · ko · ja · es

python3 introspect.py    # ① DB → schema.json
python3 merge_desc.py    # ② rellenar las descripciones de columna
python3 build_erd.py     # ③ GraphML + PNG + SVG
python3 build_html.py    # ④ referencia del esquema en HTML
python3 build_docx.py    # ⑤ documento docx (opcional)
```

Para una base de datos dentro de docker, usar `export ERD_DB='container:user:db'` en lugar
de `ERD_PSQL`.

**Los pasos ④ y ⑤ se niegan a ejecutarse sobre figuras más antiguas que `schema.json`.**
Se detienen con `N diagramas son más antiguos que …` en vez de entregar un documento cuyas
tablas y cuyas imágenes describen dos esquemas distintos; vuelva a ejecutar ③. Cuando sólo
cambió la redacción y las figuras siguen siendo correctas, `ERD_STALE=warn` las incrusta y
lo dice en cada ejecución (`ERD_STALE=` vacío significa desactivado, como el resto de los
interruptores).

**Funciona sin archivo de configuración.** Las áreas se clasifican automáticamente a
partir de los nombres de esquema y los prefijos de los nombres de tabla, y se asignan los
colores.

Dicho esto, la clasificación automática sirve **para tener un primer borrador en
pantalla.** Salvo que la base de datos siga una nomenclatura consistente, las tablas que
no encajan en nada se acumulan en un área «Otros» — en una base de 80 tablas, el 24% acabó
allí. Cuanto más crece «Otros», más alto y más difícil de leer se vuelve ese diagrama.
**Si el resultado va a un documento, conviene definir las áreas a mano en
`erd.spec.json`** — las áreas se convierten en el índice del documento.

### Desde archivos DDL en lugar de la base de datos

Para documentar cambios que todavía no se han aplicado, ejecuta `parse_ddl.py` en lugar de
`introspect.py`: lee `$ERD_SQL_DIR/*.sql` (por defecto `$ERD_PROJ/sql`) y escribe el mismo
`schema.json`.

Los comentarios `--` de ese DDL se convierten en las descripciones, y **dónde está el
comentario decide de quién es la descripción:**

```sql
-- una fila por pedido          ← encima de CREATE TABLE → nota de la tabla
CREATE TABLE orders (           -- una fila por pedido  ← en esta línea → nota de la tabla, y esta gana
  id       bigint PRIMARY KEY,  -- id de fila          ← tras la coma → esta columna
  -- quién lo hizo              ← encima de una columna → esa columna (varias líneas se unen)
  user_id  bigint NOT NULL,
  code     text,
  -- único por inquilino        ← encima de una restricción → de nadie
  UNIQUE (user_id, code)
  -- TODO: añadir moneda        ← tras la última columna → de nadie
);
```

Un bloque `/* … */` nunca es una descripción, ni siquiera una línea `--` dentro de él.
`COMMENT ON TABLE/COLUMN` sobrescribe todo lo anterior, y por eso un archivo de `pg_dump` y
uno escrito a mano acaban igual.

### Idioma de la salida

Todo lo que lee una persona — la salida de consola, los documentos HTML y docx, la leyenda
del diagrama, el instalador — sigue `ERD_LANG`: **inglés, coreano, japonés, español.**
Sin ella decide la configuración regional (`LANG` / `LC_ALL`), con el inglés como último
recurso.

El texto escrito a mano en `erd.spec.json` — nombres de área, roles, el título del
documento — se usa tal cual, así que un documento en inglés con nombres de área en coreano
es perfectamente válido.

Añadir un idioma es un archivo en `scripts/lang/` — el propio directorio hace de lista de
idiomas admitidos. Lo que se omita cae al inglés, así que un catálogo traducido a medias
sigue funcionando.

### Varias bases de datos, un solo documento

```bash
ERD_LABEL=shop ERD_DB='shop-postgres:app:shop' python3 introspect.py
ERD_LABEL=mart ERD_PSQL='psql postgresql://app:pw@localhost:5433/mart' python3 introspect.py
python3 merge_schemas.py shop mart      # las claves de tabla pasan a ser p. ej. 'shop.orders'
```

Entre bases de datos no puede haber FK físicas, así que los flujos que las cruzan se
escriben como `derives` en el spec.

### erd.spec.json — el esqueleto del diagrama

Todo es opcional; lo que falta se infiere.

```json
{
  "areas":    [["A", "Pedidos", "public", ["orders", "order_items"]]],
  "layer_of": {"orders": "TX", "order_items": "TX"},
  "layers":   {"TX": ["#25324D", "#35507D", "#4A80C0", "Transaccional"]},
  "roles":    {"orders": "Cabecera de pedido"},
  "derives":  [["ext_feed", "orders", "Fuente externa"]],
  "doc":      {"title": "Referencia del esquema de la tienda"}
}
```

| Clave | Significado |
|---|---|
| `areas` | `[código, nombre de área, esquema, [tablas…]]` — a la vez caja de grupo y unidad de disposición |
| `layer_of` / `layers` | tabla→capa, capa→`[relleno, cabecera, borde, etiqueta de leyenda]` |
| `roles` | Nombre del rol de una tabla (si falta, se usa el comentario de la tabla en la DB) |
| `derives` | Flujo ETL — flujo de datos que no es una FK. Línea discontinua marrón |
| `doc` | Título del documento, portada, prefacio, notas por área |

Ejemplos: [`examples/minimal.spec.json`](examples/minimal.spec.json) (mínimo),
[`examples/full.spec.json`](examples/full.spec.json) (todo).

La lista completa de variables de entorno está en [SKILL.md](SKILL.md).

## Reglas de dibujo

Están pensadas para documentos que se revisan, así que hay cosas que no se negocian.

- **Color = capa, agrupación = esquema/área.** Las capas de origen y las derivadas nunca
  comparten color
- **Solo dos tipos de línea.** FK (gris continua), flujo ETL (marrón discontinua). Las
  reglas de borrado van en las tablas del documento, no en el diagrama
- **Enrutado ortogonal.** Las líneas nunca atraviesan una tabla. Salen de la **fila de la
  columna real**, no del centro del nodo
- **Los cruces saltan en semicírculo.** Para que un cruce no se lea como una conexión
- **Las etiquetas se dibujan después de los nodos.** De lo contrario, los nodos las tapan
- **El lienzo se mide en dos pasadas.** Todo se dibuja una vez sobre un lienzo ficticio de
  1×1 para medir la extensión real, y luego se añaden los márgenes. Dimensionar solo a
  partir de las posiciones de los nodos recorta las etiquetas y las líneas de relación que
  sobresalen de ellas

## PNG y SVG

Son el mismo trazado, dibujado dos veces. Las posiciones de las tablas y el tamaño de las
cajas salen de un único cálculo de disposición, así que una tabla queda en el mismo sitio en
ambos; solo cambia el backend de dibujo a vectorial (`svg_canvas.py` imita la interfaz de
`ImageDraw`). Sin embargo, la pasada del SVG corre a otra escala y los anchos de texto de
PIL no escalan de forma lineal: una etiqueta de relación puede caer en otro sitio en el SVG
(medido: una etiqueta a 134px, sobre 20 esquemas aleatorios). **Los contadores de
verificación que se imprimen en cada render miden el PNG.**

|  | Vista de conjunto | Por área | Detalle completo |
|---|---|---|---|
| PNG | 0.70 MB | 0.41 MB | 3.27 MB |
| **SVG** | **0.48 MB** | **0.23 MB** | **0.30 MB** |

Un SVG dibuja su texto con la fuente que tenga la máquina que lo abre, así que una fuente
ausente cambia el ancho y el texto se sale de su celda. Por eso cada `<text>` fija con
`textLength` el ancho que midió PIL. **La disposición no se rompe en una máquina sin la
fuente.**

## Estructura

```
install.sh        instalación automatizada (colocación · dependencias · fuentes)
scripts/
  selftest.py     prueba de regresión (sin base de datos)
  i18n.py         elige el idioma de la salida
  lang/           catálogos de mensajes (en · ko · ja · es)
  config.py       rutas · conexión a la DB · carga del spec · clasificación automática de áreas
  introspect.py   DB → schema.json
  parse_ddl.py    parseo de DDL → schema.json  (para incluir cambios aún no aplicados)
  merge_schemas.py esquemas de varias bases de datos en uno
  merge_desc.py   fusión de descripciones de columna
  erd.py          disposición · renderizado · GraphML
  svg_canvas.py   lienzo SVG compatible con ImageDraw
  build_erd.py    ejecutor de PNG · SVG · GraphML
  build_html.py   referencia del esquema en HTML
  build_docx.py   documento docx
examples/         ejemplos de spec
```

## Otras bases de datos

Las consultas de `introspect.py` apuntan a PostgreSQL. MySQL también tiene un
`information_schema` estándar, así que las consultas de columnas, PK y FK sirven casi sin
cambios — basta con usar `columns.column_comment` en lugar de `col_description`.

## Licencia

MIT
