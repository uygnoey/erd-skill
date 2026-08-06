# Guía de instalación

[English](INSTALL.md) · [한국어](INSTALL.ko.md) · [日本語](INSTALL.ja.md) · **Español**

## Una línea

```bash
unzip erd-skill.zip && bash erd/install.sh
```

Eso es todo. `install.sh` se ocupa de lo siguiente:

1. Comprueba que haya Python 3.9+
2. Copia la skill a `~/.claude/skills/erd`
3. Instala `python-docx` y `pillow` desde `requirements.txt`
4. Comprueba si `psql` / `docker` están presentes
5. Descarga e instala la **fuente Pretendard** si falta (preguntando antes)

Lo de *preguntando* es literal: si no hay terminal donde preguntar (CI, una tubería), no se
descarga nada ni se sobrescribe nada de lo que ya haya en disco. El instalador lo dice y
sigue adelante.

Al terminar, **iniciar una nueva sesión de Claude Code.** Las skills se leen al arrancar,
así que una sesión que ya estaba en marcha no la verá. Después, decir «dibuja el ERD».

El instalador habla inglés, coreano, japonés y español; sigue la configuración regional
(`LANG` / `LC_ALL`). Para fijar un idioma, definir `ERD_LANG=es` (o `en`, `ko`, `ja`).

### Opciones

| Comando | Qué hace |
|---|---|
| `bash install.sh` | Instala en `~/.claude/skills/erd` (por defecto) |
| `bash install.sh --project` | Instala en `./.claude/skills/erd` del proyecto actual |
| `bash install.sh --here` | Instala solo las dependencias, deja los archivos donde están |
| `bash install.sh --check` | Solo comprueba, no cambia nada — para cuando algo ha ido mal |

Las cuatro son mutuamente excluyentes: dar dos se rechaza en vez de resolverse en silencio.
`--check --project` acababa siendo `--project` y escribía 38 archivos.

## Instalación manual

Si `install.sh` no es una opción (permisos, política, sin conexión), hacer estas cuatro
cosas a mano.

**① Descomprimir** — el zip contiene la carpeta `erd/` completa, así que se descomprime
directamente en el directorio de skills.

```bash
mkdir -p ~/.claude/skills && unzip erd-skill.zip -d ~/.claude/skills
```

La ruta debe quedar como `~/.claude/skills/erd/SKILL.md`. Un nivel más profundo
(`skills/erd/erd/SKILL.md`) o uno menos profundo, y Claude Code no la encontrará.

**② Paquetes de Python**

```bash
pip3 install -r ~/.claude/skills/erd/requirements.txt
```

Solo `python-docx` y `pillow`. Con un virtualenv, ejecutar los scripts desde una shell con
ese entorno activado.

**③ Un cliente de base de datos** — `psql` o `docker`. En macOS,
`brew install libpq && brew link --force libpq`; en Debian, `apt install postgresql-client`.

**④ Fuentes** — el cuerpo del texto usa Pretendard; las columnas, una fuente monoespaciada.

```bash
# Pretendard — solo hacen falta Regular y Bold
curl -fsSLo /tmp/p.zip https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip
unzip -j /tmp/p.zip 'public/static/Pretendard-Regular.otf' 'public/static/Pretendard-Bold.otf' \
  -d ~/Library/Fonts            # en Linux, ~/.local/share/fonts  (ejecutar fc-cache -f después)
```

Sin ella, el renderizador recurre a una fuente del sistema que cubra la escritura
necesaria (Apple SD Gothic Neo, Nanum Gothic, Noto CJK). El diagrama sale igual; solo
cambia la tipografía. Si **ninguna** fuente da cobertura, los caracteres se renderizan
como □.

## Verificar la instalación

```bash
bash ~/.claude/skills/erd/install.sh --check
```

Una ejecución sana se ve así:

```
1. Python
  ✓ Python 3.12.13  (/usr/bin/python3)

2. Colocación de la skill (omitida — check)
  ✓ ubicación actual: /path/to/erd-skill
  ✓ SKILL.md encontrado  (~/.claude/skills/erd)

3. Paquetes de Python
  ✓ requirements.txt  (~/.claude/skills/erd/requirements.txt)
  ✓ python-docx 1.2.0  (>= 1.1.0)
  ✓ pillow 12.3.0  (>= 10.0.0)

4. Cliente de base de datos (uno de los dos)
  ✓ psql   psql (PostgreSQL) 16.2

5. Fuentes de renderizado
  ✓ texto:  …/Pretendard-Regular.otf
  ✓ mono:   …/Menlo.ttc

6. Prueba de regresión
  ✓ all 257 passed
  ! 6 cases need a real server and were NOT run (ERD_SELFTEST_DOCKER=1 …)

Resultado
  ✓ instalación completada
```

`--check` no cambia nada, así que omite la colocación. Aun así lee el árbol donde lo habría
instalado: es lo primero que hay que comprobar cuando `/erd` no aparece.

**Elige un árbol y mide ese árbol hasta el final.** Los candidatos, en orden, son
`~/.claude/skills/erd`, `./.claude/skills/erd` y el directorio donde está el propio
`install.sh`; gana el primero que *exista*, y su ruta se imprime en la línea de `SKILL.md`.
La prueba de regresión de la sección 6 se ejecuta desde ese mismo árbol. Por eso, ejecutar
`--check` desde un clon recién hecho teniendo la skill instalada informa sobre la copia
**instalada**, no sobre el clon que tiene en la mano: la instalada es la que Claude Code lee.

La sección 6 no es opcional. Si el árbol elegido no tiene un `scripts/selftest.py` legible,
eso es un fallo, no un paso omitido: una instalación que nadie ha medido no es una
instalación que funcione. La línea encima del recuento dice cuántos casos necesitaban un
servidor real y por eso no se ejecutaron; esa línea no se descarta.

`SKILL.md` tiene que *ser* un archivo de skill, no solo existir: la línea 1 debe ser `---`,
el frontmatter debe cerrarse con un segundo `---` y debe contener `name: erd`. Un
`SKILL.md` vacío o truncado se informa como roto.

Las versiones de los paquetes se comparan con los mínimos declarados en `requirements.txt`.
Un paquete presente pero anterior al mínimo declarado es un fallo: esos números se miden,
no son decorativos.

## Primera ejecución

Para ejecutarlo directamente en vez de dejárselo a Claude:

```bash
cd ~/.claude/skills/erd/scripts

export ERD_PROJ=/path/to/project                              # dónde se escriben los documentos
export ERD_WORK=/tmp/erd-build                                # artefactos intermedios
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='ERD de Nuestro Servicio'

python3 introspect.py && python3 merge_desc.py && \
python3 build_erd.py && python3 build_docx.py
```

Si la base de datos está dentro de docker, usar `export ERD_DB='container:user:db'` en
lugar de `ERD_PSQL`.

Cuando `introspect.py` imprime un recuento de tablas, la conexión funcionó. Si imprime 0,
cambiar `ERD_SCHEMAS` (por defecto `public`) al nombre real del esquema. Para el resto de
variables de entorno y para escribir un spec, ver `SKILL.md`.

## Variables de entorno de fuentes

Sirven para anular la detección automática.

| Variable | Propósito |
|---|---|
| `ERD_FONT` / `ERD_FONT_BOLD` | Ruta del archivo de fuente del cuerpo para PNG (por defecto: Pretendard, detectada automáticamente) |
| `ERD_MONO` / `ERD_MONO_BOLD` | Ruta del archivo de fuente monoespaciada para PNG |
| `ERD_DOC_FONT` | **Nombre de fuente** del cuerpo en docx (por defecto sigue `ERD_LANG` — `Calibri` en español, `Pretendard` en coreano) |
| `ERD_DOC_MONO` | Nombre de fuente monoespaciada en docx (por defecto `Consolas` en español, `D2Coding` en coreano) |

PNG recibe una ruta de archivo; docx, un nombre de fuente — un docx solo se ve bien si la
máquina que lo abre tiene esa fuente; si no, Word la sustituye. Con `ERD_LANG=es` el valor
por defecto es `Calibri`, que viene con Word, así que normalmente no hay nada que tocar.
Solo si el documento lleva otra escritura (coreano, japonés…), indicar una fuente que los
destinatarios tengan, p. ej. `export ERD_DOC_FONT='Malgun Gothic'`.

## Tropiezos habituales

**`ModuleNotFoundError: No module named 'docx'`**
El paquete es `python-docx`, no `docx`. Los nombres difieren. Ejecutar `install.sh --check`
también indica qué Python está mirando.

**Se instaló pero el import falla**
`pip3` y `python3` son dos instalaciones distintas. Instalar con el **mismo Python**:
`python3 -m pip install -r requirements.txt`. Es lo que hace install.sh.

**`/erd` no aparece en la lista**
Comprobar, en este orden: ① si `ls ~/.claude/skills/erd/SKILL.md` devuelve algo ② si se
reinició Claude Code ③ si `SKILL.md` empieza con `---` en la línea 1 y contiene `name: erd`.
`install.sh --check` hace ① y ③ por usted, y nombra el árbol que ha mirado.

**`[aviso] falló la consulta a la base de datos`**
Comprobar el valor de `ERD_PSQL` / `ERD_DB`. Ejecutar primero el mismo comando en la shell
y ver si conecta. Si ambas están definidas, gana `ERD_PSQL`.

**`N diagramas son más antiguos que …/schema.json` y no se escribe ningún documento**
Es una puerta, no un fallo. `build_html.py`, `build_docx.py` y `build_erd.py` se niegan a
meter en un documento figuras dibujadas a partir de un esquema anterior, porque las tablas
dirían una cosa y las imágenes otra. La solución es volver a ejecutar
`python3 build_erd.py`. Si sólo cambió la redacción y las figuras siguen siendo correctas,
`ERD_STALE=warn` (o `ERD_STALE=1`) las deja pasar — y aun así imprime una línea diciéndolo.
`ERD_STALE` sigue la misma regla de sí/no que los demás interruptores: `true`, `on` e `y`
lo activan, un `ERD_STALE=` vacío significa **desactivado**, y una errata se nombra en la
salida en lugar de tomarse como un sí.

**El texto del PNG sale como □**
Ninguna fuente cubre esos caracteres. Volver a ejecutar `install.sh` para instalar
Pretendard, o apuntar `ERD_FONT` a una fuente a mano.

**Imprimió una lista de columnas sin descripción**
Es el comportamiento previsto. Rellenarlas en el diccionario `MANUAL` de `merge_desc.py` y
volver a ejecutarlo. Ver la sección «descripciones de columna» de `SKILL.md`.

**No aparece la salida**
`.graphml` y `.docx` están en `$ERD_PROJ`; los PNG, en `$ERD_WORK/out/`.
