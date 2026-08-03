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
    'verify.v_overlap': 'solape vertical',
    'verify.h_overlap': 'solape horizontal',

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
    'err.no_tables': 'No se pudo leer ninguna tabla. '
                     'Compruebe ERD_DB / ERD_PSQL / ERD_SCHEMAS.',
    'err.font_env': 'la fuente indicada en {env} no existe: {path}',
    'err.font_none': 'No se encontró ninguna fuente {kind}. Ejecute install.sh o defina '
                     '{env} manualmente.\n  Rutas revisadas: {looked}',
    'err.merge_usage': 'uso: python3 merge_schemas.py <etiqueta> <etiqueta> …',
    'err.merge_missing': '{path} no existe. Ejecute antes introspect.py con '
                         'ERD_LABEL={label}.',
    'err.no_sql_dir': 'no existe el directorio de DDL: {path}  (defínalo con ERD_SQL_DIR)',

    # ── salida de progreso ────────────────────────────────────────────────
    'log.query_fail': '  [aviso] falló la consulta a la base de datos: {err}',
    'log.introspected': 'tablas: {tables} · columnas: {columns} · FK: {fks} → {path}',
    'log.desc_from_db': '  descripciones de columna tomadas de comentarios de la BD: {n}/{total}',
    'log.desc_rest': '  → complete el resto con merge_desc.py',
    'log.exclude_rule': '  regla de exclusión: {rule}',
    'log.fk_dropped': '  FK descartadas por apuntar fuera del objetivo: {n}',
    'log.per_schema': '  [{schema}] {n}',
    'log.doc_missing': '  [aviso] no se encontró el documento ERD_DOC_HTML: {path}',
    'log.doc_inherited': '  descripciones de columna heredadas de {name}: {n}',
    'log.by_source': 'columnas por fuente de la descripción:',
    'log.no_desc': 'columnas aún sin descripción:',
    'log.merge_part': '  {label} tablas: {tables} · columnas: {columns}',
    'log.merge_total': 'total — tablas: {tables} · columnas: {columns} · FK: {fks} → {path}',
    'log.ddl_parsed': 'tablas: {n} → {path}',
    'log.ddl_row': 'cols {columns}{added} FK {fks}  · {note}',
    'log.ddl_added': ' (nuevas: +{n})',
    'log.graphml': 'GraphML  nodos: {nodes} · relaciones: {edges}  → {name}',
    'log.png_overview': 'PNG  vista general → {name} {size}',
    'log.png_full': 'PNG  ERD completo → {name} {size}',
    'log.png_area': 'PNG  área {code} {name} ({n} + {ext} refs) → {file}  {size}',
    'log.scale_down': '    [nota] {name}: diagrama demasiado grande, escala reducida a {s}×',
    'log.overlap_at': '      solape: en {a}  [{s0}~{s1}] vs [{t0}~{t1}]',
    'log.verify': '    verificación {name}: {report}',
    'log.html_done': 'HTML  tablas: {tables} · áreas: {areas} · figuras: {figs}  '
                     '{mb}MB → {name}',
    'log.html_missing': '  [aviso] áreas sin diagrama ({n}): {list}  '
                        '→ ejecute antes build_erd.py',
    'log.docx_saved': 'guardado: {name} ({kb} KB)',
}
