"""Textos en español."""

M = {
    # ── palabras ──────────────────────────────────────────────────────────
    'word.tables': 'Tablas',
    'word.columns': 'Columnas',
    'word.areas': 'Áreas',
    'word.layer': 'Capa',
    'word.schema': 'Esquema',
    'word.fkeys': 'FK',
    'word.pk': 'clave primaria',
    'word.fk': 'clave foránea',
    'word.unique': 'única',
    'word.kind': 'Clase',
    'word.content': 'Contenido',
    'word.basis': 'Fuente',
    'word.notation': 'Notación',
    'word.meaning': 'Significado',
    'word.lines': 'Líneas',
    'word.added': '[nueva]',
    'word.source': 'origen',
    'word.extended': 'extendida',
    'word.existing': 'existente',
    'word.external': 'externa',
    'word.solid': 'línea continua',
    'word.dashed': 'línea discontinua (marrón)',
    'word.semicircle': 'semicírculo',
    'word.crowfoot': 'pata de gallo / extremo simple',
    'word.child_table': 'Tabla hija',
    'word.parent_table': 'Tabla padre',
    'word.delete_rule': 'Regla de borrado',
    'word.src_side': 'Origen (esquema ref)',
    'word.dst_side': 'Destino (esquema public)',
    'word.priority': 'Pri.',
    'word.item': 'Ítem',
    'word.target': 'Objetivo',
    'word.current': 'Estado actual',
    'word.action': 'Acción requerida',
    'word.proposed': 'Diseño propuesto',
    'word.actual_table': 'Tabla real',
    'word.applied': 'Aplicado',
    'word.reason': 'Motivo',
    'word.fig_no': '[Fig. {n}]',
    'word.area_other': '{schema} otros',
    'word.font_body': 'de texto',
    'word.font_mono': 'monoespaciada',

    # ── tabla de columnas ─────────────────────────────────────────────────
    'col.name': 'Columna',
    'col.type': 'Tipo',
    'col.null': 'Nulo',
    'col.default': 'Por defecto',
    'col.key': 'Clave / Ref',
    'col.desc': 'Descripción',

    # ── referencia de esquema HTML ────────────────────────────────────────
    'html.single_db': '(base de datos única)',
    'html.fig_zoom': '— clic para abrir a tamaño completo',
    'html.meta_area_layer': 'Área {area} · capa {layer}',
    'html.role': 'Rol',
    'html.constraints': 'Restricciones · índices ({n})',
    'html.rows_note': 'rows ≈ es una estimación basada en estadísticas',
    'html.toc': 'Índice',
    'html.db_tables': 'BD: {db} · tablas: {n}',
    'html.badge_cols': 'cols: {n}',
    'html.badge_tables': '{n} tablas',
    'html.overall': 'Estructura general',
    'html.overview_cap': '{title} — vista general de la estructura (tablas: {n} · solo relaciones)',
    'html.area_cap': '{name} — ERD detallado del área',
    'html.full_cap': '{title} — ERD detallado completo (todas las tablas · todas las columnas)',
    'html.appendix': 'Apéndice. ERD detallado completo',
    'html.appendix_desc': 'Todas las tablas y columnas en una sola lámina. '
                          'En pantalla, se amplía con un clic.',
    'html.zoomhint': 'clic o Esc para cerrar',

    # ── diagrama ERD ──────────────────────────────────────────────────────
    'erd.ref_of': '[ref] {area} · {role}',
    'erd.readonly_src': '{schema} (solo lectura)',
    'erd.group_label': 'esquema {schema} · {code} {name}',
    'erd.node_desc': '[{layer}] [área {code} {area}] {note}',
    'erd.lg_new': 'tabla nueva',
    'erd.lg_ext': 'tabla existente · columnas añadidas',
    'erd.lg_src': 'origen en el esquema ref',
    'erd.lg_fk': 'clave foránea (FK) · etiqueta = columna hija : columna padre',
    'erd.lg_etl': 'flujo de carga ETL (no es una FK)',
    'erd.lg_hop': 'cruce (la línea salta por encima)',
    'erd.sub_overview': 'color = capa / agrupación = esquema y área',
    'erd.sub_full': 'tablas: {tables} · columnas: {columns} · claves foráneas: {fks}',
    'erd.sub_etl': ' · flujos ETL: {n}',
    'erd.sub_area': 'esquema {schema} · tablas: {n}',
    'erd.sub_ext': ' · referencias externas: {n}',
    'verify.label_table': 'etiqueta↔tabla',
    'verify.thru': 'línea↔tabla',
    'verify.label_x': 'etiqueta↔etiqueta',
    'verify.v_overlap': 'solape vertical',
    'verify.h_overlap': 'solape horizontal',
    'verify.tolerated': '{n}(tolerado)',
    'verify.na': 'n/d',
    'verify.warn': '  [aviso] debe ser 0: {list}',

    # ── documento docx ────────────────────────────────────────────────────
    'docx.doc_name': 'Documento',
    'docx.ch1': '1. Introducción',
    'docx.ch1_1': '1.1 Propósito',
    'docx.purpose': 'Presenta la estructura de tablas y las relaciones de la base de '
                    'datos objetivo en forma de ERD. Se genera leyendo el esquema real, '
                    'por lo que el diagrama no puede desviarse de la base de datos.',
    'docx.ch1_2': '1.2 Alcance',
    'docx.scope_in': 'Incluye: estructura, columnas y relaciones de {n} tablas, '
                     'además de la división por esquema y por capa.',
    'docx.scope_out': 'Excluye: procedimientos de migración, especificaciones de API, '
                      'diseño de pantallas.',
    'docx.ch1_3': '1.3 Fuentes',
    'docx.sources_note': 'Este ERD se generó leyendo la base de datos real y su DDL. '
                         'Por tanto, los nombres de tablas y columnas, los tipos y las '
                         'restricciones coinciden con el esquema real.',
    'docx.src_infoschema': 'valores reales de tablas, columnas, tipos, PK, FK y reglas de borrado',
    'docx.src_comment': 'comentarios de tablas y columnas',
    'docx.src_comment_d': 'primera fuente de las descripciones',
    'docx.src_orm': 'comentarios del modelo ORM',
    'docx.src_orm_d': 'descripciones de columnas sin comentario',
    'docx.ch1_4': '1.4 Notación',
    'docx.by_color': '{code} (por color)',
    'docx.nt_new': 'tabla de nueva creación',
    'docx.nt_ext': 'tabla existente · columnas añadidas',
    'docx.nt_src': 'origen externo · solo lectura',
    'docx.nt_added': 'columna añadida en esta revisión',
    'docx.nt_solid': 'clave foránea (FK) · la etiqueta se lee «columna hija : columna padre»',
    'docx.nt_dashed': 'flujo de carga ETL — un flujo de datos, no una FK',
    'docx.nt_hop': 'indica que una línea salta sobre otra (no es una conexión)',
    'docx.nt_card': 'el lado N (hijo) / el lado 1 (padre) de una relación',
    'docx.ch2': '2. Estructura de esquemas y capas',
    'docx.ch2_intro': 'En el diagrama siguiente, el color indica la capa y la agrupación '
                      'indica el esquema y el área funcional.',
    'docx.fig_overview': '{title} — vista general de relaciones',
    'docx.ch2_1': '2.1 ERD completo',
    'docx.ch2_1_intro': 'Todas las columnas y descripciones de las {n} tablas en una '
                        'sola lámina. En la versión impresa queda reducida y resulta '
                        'difícil de leer; para el detalle se usan los ERD por área del '
                        'capítulo 3 o la imagen original.',
    'docx.fig_full': '{title} — completo (columnas y descripciones)',
    'docx.ch3': '3. ERD por área',
    'docx.ch3_intro': 'Cada área se muestra con todas sus columnas y descripciones. '
                      'Las tablas referenciadas fuera del área aparecen como cajas '
                      'condensadas con borde gris.',
    'docx.ch3_area': '3.{no} Área {code} · {name} (esquema {schema} · tablas: {n})',
    'docx.fig_area': 'Área {code} · {name}',
    'docx.ch4': '4. Rol de las tablas y descripción de columnas',
    'docx.ch4_intro': 'Total — tablas: {tables} · columnas: {columns}. En la columna '
                      'Clase, PK es la clave primaria, FK una clave foránea y [nueva] '
                      'marca una columna añadida en esta revisión.',
    'docx.ch4_area': '4.{no} Área {code} · {name}',
    'docx.ch5': '5. Relaciones',
    'docx.ch5_1': '5.1 Claves foráneas (FK)',
    'docx.ch5_1_intro': '{n} en total. Cuando la regla de borrado es CASCADE, al borrar '
                        'el padre se borran con él las filas hijas; cuando es SET NULL, '
                        'solo se anula la referencia y la fila se conserva.',
    'docx.ch5_2': '5.2 Flujos de carga ETL',
    'docx.ch5_2_intro': 'Son flujos de datos, no FK. El esquema ref es de solo lectura, '
                        'por lo que no se le puede imponer ninguna restricción física.',
    'docx.ch6': '6. Diseño propuesto frente a lo construido',
    'docx.ch6_intro': 'Los nombres de tabla de la propuesta de diseño difieren de los '
                      'del DDL real. A continuación se coteja cada ítem para mostrar '
                      'cómo se implementó realmente.',
    'docx.ch7': '7. Puntos abiertos y decisiones pendientes',
    'docx.ch7_intro': 'Este ERD define la estructura; la estructura por sí sola no hace '
                      'funcionar el sistema. Los puntos siguientes requieren una '
                      'decisión ajena al esquema antes de poder completar sus valores.',

    # ── descripciones de columnas comunes ─────────────────────────────────
    'common.id': 'identificador de fila (PK)',
    'common.seq': 'identificador de fila (PK)',
    'common.uuid': 'identificador de fila (UUID)',
    'common.created_at': 'fecha de creación',
    'common.updated_at': 'fecha de modificación',
    'common.deleted_at': 'fecha de borrado (soft delete)',
    'common.created_by': 'creado por',
    'common.updated_by': 'modificado por',
    'common.loaded_at': 'fecha de carga',
    'common.started_at': 'fecha de inicio',
    'common.ended_at': 'fecha de fin',
    'common.status': 'estado',
    'common.note': 'observaciones',
    'common.remark': 'observaciones',
    'common.sort_order': 'orden de clasificación',
    'common.rank': 'posición',
    'common.version': 'versión',
    'common.is_active': 'indicador de activo',
    'common.active_yn': 'indicador de activo',

    # ── errores ───────────────────────────────────────────────────────────
    'err.no_conn': 'No hay conexión a la base de datos configurada. Debe definirse una de las dos.',
    'err.no_conn_db': "'contenedor:usuario:bd'        # vía docker",
    'err.no_schema_tables': 'No queda ninguna tabla que dibujar. {path} está vacío, o ERD_EXCLUDE lo excluyó todo.',
    'err.no_tables': 'No se pudo leer ninguna tabla. '
                     'Compruebe ERD_DB / ERD_PSQL / ERD_SCHEMAS / ERD_EXCLUDE.',
    'err.font_env': 'no se puede usar la fuente indicada en {env}: {path}',
    'err.font_none': 'No se encontró ninguna fuente {kind}. Ejecute install.sh o defina '
                     '{env} manualmente.\n  Rutas revisadas: {looked}',
    'err.merge_usage': 'uso: python3 merge_schemas.py <etiqueta> <etiqueta> …',
    'err.merge_missing': '{path} no existe. Ejecute antes introspect.py con '
                         'ERD_LABEL={label}.',
    'err.no_sql_dir': 'no existe el directorio de DDL: {path}  (defínalo con ERD_SQL_DIR)',
    'err.spec_no_area': 'las áreas de {path} no nombran ninguna tabla existente.',
    'err.spec_dup_code': '{path}: dos áreas usan el mismo código de área {code} (la otra se escribe {other}).\n'
                         '  Los códigos de área se convierten en nombres de archivo ({file}) y, en macOS y\n'
                         '  Windows, dos códigos que solo difieren en mayúsculas o en forma Unicode son el\n'
                         '  mismo archivo: un diagrama sobrescribiría al otro en silencio. Use códigos distintos.',
    'err.spec_layer': 'la capa {key} está mal formada: {value}\n'
                      '  se espera [relleno, cabecera, borde, etiqueta] con colores #rrggbb',
    'err.spec_json': '{path} no es JSON válido: {err}',
    'err.fig_unregistered': 'el diagrama {stem} no tiene número de figura — fig_numbers() de '
                            'build_erd.py no lo incluye.\n'
                            '  Cada diagrama que dibuja este script toma su número de esa lista, y ese '
                            'número se dibuja dentro de la propia imagen, no solo en el pie — un '
                            'diagrama sin registrar saldría con un número distinto al de su pie.\n'
                            '  Registrados: {known}',
    'err.stale_figs': '{n} diagramas son más antiguos que {path}: {list}\n'
                      '  Representan un esquema anterior — el documento diría una cosa '
                      'en las tablas y otra en las figuras.\n'
                      '  Ejecute build_erd.py de nuevo, o ponga ERD_STALE=warn para '
                      'incrustarlos tal cual.',
    'err.pg_too_old': 'PostgreSQL {found} es demasiado antiguo — se requiere {need} o '
                      'posterior.\n'
                      '  Los servidores anteriores no pasan el alias de una subconsulta a '
                      'row_to_json, así que todos los valores llegarían vacíos, y la '
                      'consulta de claves foráneas necesita WITH ORDINALITY.',
    'err.query_failed': 'no se pudo leer {what} de la base de datos: {err}\n'
                        '  No se escribió nada. Una ejecución que solo leyó parte del '
                        'esquema produce un documento que parece completo y no lo está.',
    'err.query_truncated': 'el resultado se cortó en medio de una fila',
    'err.env_not_dir': '{env}: {path} no es un directorio — ya hay otra cosa ahí.',
    'err.env_not_file': '{env}: {path} no es un archivo legible.',
    'err.env_bad': 'no se puede usar {env}: {why}\n  valor: {value}',
    'err.env_empty': '{env} está definido pero vacío. Dele un valor o quítelo para usar '
                     'el predeterminado.',
    'err.env_name': '{env}={value} no puede formar parte de un nombre de archivo. '
                    'Pruebe {safe}.',
    'err.spec_type': '{path}: "{key}" debe ser {want} — se recibió {got}.',
    'err.spec_root': '{path} debe ser un objeto JSON con claves como "areas" — '
                     'se recibió {got}.',

    # ── salida de progreso ────────────────────────────────────────────────
    'log.query_fail': '  [aviso] falló la consulta a la base de datos: {err}',
    'log.query_incomplete': '  [aviso] no se pudo leer: {list} — al documento le faltan '
                            'exactamente esas partes',
    'log.psql_undecodable': '  [aviso] la respuesta de la base de datos no era UTF-8 válido — '
                            'esos caracteres quedan como � en el documento.\n'
                            '          PGCLIENTENCODING={enc} se define para el psql que lanzamos, '
                            'pero un envoltorio (docker, ssh) no lo cruza.\n'
                            '          Póngalo dentro del propio comando ERD_PSQL: '
                            'docker exec -e PGCLIENTENCODING={enc} … / '
                            'ssh host PGCLIENTENCODING={enc} psql …',
    'log.ddl_not_in_db': '  [aviso] {n} tablas no se encontraron en los esquemas consultados '
                         '({schemas}) — se dibujan como cajas con solo el nombre: {list}',
    'log.spec_empty': '  [aviso] áreas sin ninguna tabla utilizable, omitidas: {list}',
    'log.spec_dup': '  [aviso] {n} tablas aparecen en más de un área — se quedan en la primera: {list}',
    'log.spec_missing': '  [aviso] el spec nombra {n} tablas que no están en el esquema: {list}',
    'log.max_areas_spec': '  [aviso] {env}={value}, pero {path} nombra sus propias áreas — se dibujan las {n}\n'
                          '          (el límite solo se aplica a las áreas automáticas; manda el spec)',
    'log.spec_orphan': '  [aviso] {n} tablas no están en ninguna área del spec — se agrupan '
                       'en un área adicional para que igual se dibujen: {list}',
    'log.spec_unknown': '  [aviso] {n} claves de primer nivel del spec no se reconocen y se '
                        'ignoraron: {list}\n'
                        '    claves conocidas: {known}  (las que empiezan por _ son comentarios)',
    'log.env_not_flag': '  [aviso] {env}={value} no es un valor sí/no — se usa {used} '
                        '(apagan: 0 false no off n, o vacío)',
    'log.env_not_number': '  [aviso] {env}={value} no es un número — se usa {default}',
    'log.env_clamped': '  [aviso] {env}={value} está por debajo del mínimo — se usa {used}',
    'log.default_pk_skipped': '  [aviso] ERD_DEFAULT_PK={column}: {n} tablas se quedan sin '
                              'clave primaria porque no tienen esa columna: {list}',
    'log.ref_tables_ignored': '  [aviso] ERD_REF_TABLES está definido pero ERD_REF_SCHEMA no — '
                              'no se trajeron {n} tablas: {list}',
    'log.introspected': 'tablas: {tables} · columnas: {columns} · FK: {fks} → {path}',
    'log.desc_from_db': '  descripciones de columna tomadas de comentarios de la BD: {n}/{total}',
    'log.desc_rest': '  → complete el resto con merge_desc.py',
    'log.dup_names': '  {n} nombres de tabla existen en más de un esquema — la clave pasa a ser esquema.tabla: {list}',
    'log.exclude_rule': '  regla de exclusión: {rule}',
    'log.exclude_dropped': '  la regla de exclusión quitó {n} tablas: {list}',
    'log.fk_dropped': '  FK descartadas por apuntar fuera del objetivo: {n}',
    'log.per_schema': '  [{schema}] {n}',
    'log.doc_missing': '  [aviso] no se encontró el documento ERD_DOC_HTML: {path}',
    'log.doc_inherited': '  descripciones de columna heredadas de {name}: {n}',
    'log.by_source': 'columnas por fuente de la descripción:',
    'log.no_desc': 'columnas aún sin descripción:',
    'log.desc_ambiguous': '  [aviso] {n} claves nombran una tabla que existe más de una '
                          'vez y se ignoraron — use la clave cualificada: {list}',
    'log.merge_part': '  {label} tablas: {tables} · columnas: {columns}',
    'log.merge_total': 'total — tablas: {tables} · columnas: {columns} · FK: {fks} → {path}',
    'log.ddl_parsed': 'tablas: {n} → {path}',
    'log.ddl_no_db': '  {n} tablas solo se referencian, nunca se definen en el DDL — se dibujan como cajas con solo el nombre (define ERD_DB/ERD_PSQL para rellenarlas): {list}',
    'log.ddl_row': 'cols {columns}{added} FK {fks}  · {note}',
    'log.ddl_added': ' (nuevas: +{n})',
    'log.graphml': 'GraphML  nodos: {nodes} · relaciones: {edges}  → {name}',
    'log.png_overview': 'PNG  vista general → {name} {size}',
    'log.png_full': 'PNG  ERD completo → {name} {size}',
    'log.png_area': 'PNG  área {code} {name} ({n} + {ext} refs) → {file}  {size}',
    'log.scale_down': '    [nota] {name}: diagrama demasiado grande, escala reducida a {s}×',
    'log.overlap_at': '      solape: en {a}  [{s0}~{s1}] vs [{t0}~{t1}]',
    'log.verify': '    verificación {name}: {report}',
    'log.verify_log_fail': '  [aviso] no se pudo escribir ERD_VERIFY_LOG, las figuras siguen '
                           'ahí: {path} — {err}',
    'log.html_done': 'HTML  tablas: {tables} · áreas: {areas} · figuras: {figs}  '
                     '{mb}MB → {name}',
    'log.stale_figs': '  [aviso] se incrustan {n} diagramas más antiguos que el esquema '
                      '(ERD_STALE): {list}',
    'log.docx_saved': 'guardado: {name} ({kb} KB)',
    'log.figs_missing': '  [aviso] diagramas no encontrados, omitidos del documento: '
                        '{n} ({list})  → ejecuta build_erd.py primero',
    'log.row_truncated': '  [aviso] {where}: {n} fila(s) llevan más celdas de las que '
                         'caben en esta tabla ({width}) — las celdas sobrantes se '
                         'descartaron: {list}',
}
