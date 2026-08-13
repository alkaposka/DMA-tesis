"""
Aplicación Streamlit para gestión de ensayos DMA con Supabase.
Incluye: agregar ensayos, gestionar muestras, visualizar datos y predecir resultados.
"""

import streamlit as st
import psycopg2
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import date

# ==============================
# CONFIGURACIÓN GENERAL
# ==============================
st.set_page_config(page_title="Ensayos DMA", layout="wide")

# Estilo sobrio y tabla más compacta
st.markdown("""
<style>
    .stDataFrame { font-size: 12px; }
    .stButton>button {
        background-color: #ffffff;
        color: #333333;
        border: 1px solid #cccccc;
        border-radius: 4px;
    }
    .stButton>button:hover {
        background-color: #f0f0f0;
    }
    h1, h2, h3 { color: #333333; }
</style>
""", unsafe_allow_html=True)

# ==============================
# CONEXIÓN A SUPABASE
# ==============================
def get_conn():
    """Conecta a PostgreSQL usando las credenciales de st.secrets."""
    conn = psycopg2.connect(
        host=st.secrets["supabase"]["host"],
        database=st.secrets["supabase"]["database"],
        user=st.secrets["supabase"]["user"],
        password=st.secrets["supabase"]["password"],
        port=st.secrets["supabase"]["port"]
    )
    return conn

# ==============================
# FUNCIONES DE CARGA DE DATOS
# ==============================
@st.cache_data(ttl=5)
def cargar_canteras():
    conn = get_conn()
    df = pd.read_sql("SELECT id_cantera, nombre FROM canteras ORDER BY nombre", conn)
    conn.close()
    return df

@st.cache_data(ttl=5)
def cargar_muestras():
    conn = get_conn()
    df = pd.read_sql("""
        SELECT m.id_muestra, m.nomenclatura, c.nombre AS cantera,
               m.densidad, m.humedad, m.tipo_emulsificante, m.porcentaje_emulsificante
        FROM muestras m
        JOIN canteras c ON m.id_cantera = c.id_cantera
        ORDER BY m.nomenclatura
    """, conn)
    conn.close()
    return df

@st.cache_data(ttl=5)
def cargar_ensayos():
    conn = get_conn()
    query = """
        SELECT e.id_ensayo, e.fecha,
               m.nomenclatura,
               c.nombre AS cantera,
               e.porcentaje_emulsion,
               e.altura_mm, e.diametro_mm,
               e.fuerza_estatica, e.min_des_din, e.max_des_din,
               e.max_fuer_din, e.min_fuer_din,
               e.resultado, e.observacion
        FROM ensayos_iniciales e
        LEFT JOIN muestras m ON e.id_muestra = m.id_muestra
        LEFT JOIN canteras c ON e.id_cantera = c.id_cantera
        ORDER BY e.fecha DESC, e.id_ensayo DESC
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# ==============================
# PESTAÑAS
# ==============================
# ---------- SEGURIDAD ----------
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

# Formulario de login en la barra lateral
with st.sidebar:
    if not st.session_state["autenticado"]:
        st.header("Acceso")
        password_input = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"):
            if password_input == st.secrets["APP_PASSWORD"]:
                st.session_state["autenticado"] = True
                st.success("Acceso concedido")
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
    else:
        st.success("Sesión iniciada")
        if st.button("Cerrar sesión"):
            st.session_state["autenticado"] = False
            st.rerun()
# -----------------------------------
tab1, tab2, tab3, tab4 = st.tabs(["Agregar Ensayo", "Gestionar Muestras", "Visualizar Datos", "Predecir Resultado"])

# ==============================
# PESTAÑA 1: AGREGAR ENSAYO
# ==============================
if not st.session_state["autenticado"]:
    st.warning("Debe ingresar la contraseña para agregar ensayos.")
    st.stop()
with tab1:
    
    st.header("Nuevo Ensayo DMA")
    muestras_df = cargar_muestras()
    opciones_muestras = ['Sin muestra'] + muestras_df['nomenclatura'].tolist()

    with st.form("form_nuevo_ensayo", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha = st.date_input("Fecha", value=date.today())
            muestra_sel = st.selectbox("Muestra (nomenclatura)", opciones_muestras)
            if muestra_sel == 'Sin muestra':
                canteras_df = cargar_canteras()
                cantera_sel = st.selectbox("Cantera", canteras_df['nombre'])
                p_emulsion = st.number_input("% Emulsión", min_value=0.0, max_value=100.0, value=10.0, step=0.5)
                id_muestra = None
                id_cantera = int(canteras_df[canteras_df['nombre'] == cantera_sel]['id_cantera'].iloc[0])
            else:
                muestra_info = muestras_df[muestras_df['nomenclatura'] == muestra_sel].iloc[0]
                cantera_sel = muestra_info['cantera']  # solo para mostrar
                p_emulsion = muestra_info['porcentaje_emulsificante'] if pd.notna(muestra_info['porcentaje_emulsificante']) else 0.0
                id_muestra = int(muestra_info['id_muestra'])
                id_cantera = None   # ya viene de la muestra
        with col2:
            altura = st.number_input("Altura (mm)", value=None, format="%.2f")
            diametro = st.number_input("Diámetro (mm)", value=None, format="%.2f")
            # Codigo probeta no se usa en la nueva tabla, lo omitimos
        with col3:
            f_estatica = st.number_input("Fuerza Estática [N]", value=-3.0, format="%.4f")
            min_des = st.number_input("Min Des Din [m]", value=0.0, format="%.6e")
            max_des = st.number_input("Max Des Din [m]", value=1.0e-4, format="%.6e")
            max_f_din = st.number_input("Max Fuer Din [N]", value=2.0, format="%.4f")
            min_f_din = st.number_input("Min Fuer Din [N]", value=0.0, format="%.4f")

        st.subheader("Resultado y observaciones")
        col_res, col_obs = st.columns([1, 2])
        with col_res:
            resultado = st.selectbox("Resultado", [
                "Exitoso",
                "Fallo de probeta",
                "separacion placa superior de probeta",
                "Funciono al comienzo pero se separaron los platos",
                "Funciono al comienzo pero hubo Fallo de probeta"
            ])
        with col_obs:
            observacion = st.text_area("Observación", height=80)

        enviado = st.form_submit_button("Guardar Ensayo")
        if enviado:
            # Comprobación básica de duplicados (misma fecha, muestra/cantera, %emulsion, fuerza)
            conn = get_conn()
            cur = conn.cursor()
            # Preparamos condiciones según si hay muestra o no
            if id_muestra is not None:
                duplicado_query = """
                    SELECT COUNT(*) FROM ensayos_iniciales
                    WHERE fecha = %s AND id_muestra = %s AND porcentaje_emulsion = %s AND fuerza_estatica = %s
                """
                duplicado_params = (fecha.isoformat(), id_muestra, p_emulsion if p_emulsion != 0.0 else None, f_estatica)
            else:
                duplicado_query = """
                    SELECT COUNT(*) FROM ensayos_iniciales
                    WHERE fecha = %s AND id_cantera = %s AND porcentaje_emulsion = %s AND fuerza_estatica = %s
                """
                duplicado_params = (fecha.isoformat(), id_cantera, p_emulsion if p_emulsion != 0.0 else None, f_estatica)

            cur.execute(duplicado_query, duplicado_params)
            existe = cur.fetchone()[0] > 0
            if existe:
                st.warning("⚠️ Ya existe un ensayo con la misma fecha, muestra/cantera, % emulsión y fuerza estática. Si es un duplicado real, no lo guarde.")
                # No detenemos, solo advertimos; puedes decidir cancelar con un botón adicional
                # Para simplicidad, seguimos con la inserción, pero puedes añadir lógica de confirmación.
                # Si quieres cancelar automáticamente, usa st.stop() aquí (descomenta)
                # st.stop()
            try:
                cur.execute("""
                    INSERT INTO ensayos_iniciales 
                    (fecha, id_muestra, id_cantera, porcentaje_emulsion, altura_mm, diametro_mm,
                     fuerza_estatica, min_des_din, max_des_din, max_fuer_din, min_fuer_din,
                     resultado, observacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    fecha.isoformat(),
                    id_muestra,
                    id_cantera,
                    p_emulsion if p_emulsion != 0.0 else None,
                    altura if altura != 0.0 else None,
                    diametro if diametro != 0.0 else None,
                    f_estatica,
                    min_des,
                    max_des,
                    max_f_din,
                    min_f_din,
                    resultado,
                    observacion if observacion != '' else None
                ))
                conn.commit()
                st.success("✅ Ensayo guardado correctamente.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")
            finally:
                conn.close()

# ==============================
# PESTAÑA 2: GESTIONAR MUESTRAS
# ==============================
if not st.session_state["autenticado"]:
    st.warning("Debe ingresar la contraseña para agregar ensayos.")
    st.stop()
with tab2:
    st.header("Muestras (Nomenclaturas)")
    muestras_df = cargar_muestras()
    st.dataframe(muestras_df, use_container_width=True)

    st.subheader("Agregar nueva muestra")
    with st.form("form_muestra"):
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            nomenclatura = st.text_input("Nomenclatura (ej. C1-D20,76-H7,2%-EM7%)")
            canteras_m = cargar_canteras()
            cantera_m = st.selectbox("Cantera", canteras_m['nombre'])
        with col_m2:
            densidad = st.number_input("Densidad (g/cm³)", min_value=0.0, format="%.2f")
            humedad = st.number_input("Humedad (%)", min_value=0.0, max_value=100.0, format="%.2f")
        with col_m3:
            tipo_emul = st.text_input("Tipo emulsificante (opcional)")
            pct_emul = st.number_input("% Emulsificante", min_value=0.0, max_value=100.0, value=7.0, step=0.5)

        guardar_muestra = st.form_submit_button("Guardar muestra")
        if guardar_muestra:
            if nomenclatura == '':
                st.error("La nomenclatura no puede estar vacía.")
            else:
                conn = get_conn()
                cur = conn.cursor()
                id_cantera = int(canteras_m[canteras_m['nombre'] == cantera_m]['id_cantera'].iloc[0])
                try:
                    cur.execute("""
                        INSERT INTO muestras (nomenclatura, id_cantera, densidad, humedad, tipo_emulsificante, porcentaje_emulsificante)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        nomenclatura,
                        id_cantera,
                        densidad if densidad != 0.0 else None,
                        humedad if humedad != 0.0 else None,
                        tipo_emul if tipo_emul != '' else None,
                        pct_emul if pct_emul != 0.0 else None
                    ))
                    conn.commit()
                    st.success("✅ Muestra agregada correctamente.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al guardar: {e}")
                finally:
                    conn.close()

# ==============================
# PESTAÑA 3: VISUALIZAR DATOS
# ==============================
with tab3:
    st.header("Exploración de Ensayos")
    df = cargar_ensayos()

    if df.empty:
        st.info("No hay datos todavía. Agregue ensayos en la pestaña correspondiente.")
    else:
        # Filtros (por defecto sin filtros activos)
        with st.expander("Filtros", expanded=False):
            colf1, colf2, colf3 = st.columns(3)
            with colf1:
                canteras_unicas = df['cantera'].dropna().unique().tolist()
                opciones_cantera = ['Sin cantera'] + canteras_unicas
                filtro_cantera = st.multiselect("Cantera", options=opciones_cantera, default=[])
            with colf2:
                resultados_unicos = df['resultado'].dropna().unique().tolist()
                filtro_resultado = st.multiselect("Resultado", options=resultados_unicos, default=[])
            with colf3:
                em_unicos = df['porcentaje_emulsion'].dropna().unique().tolist()
                opciones_emulsion = ['Sin % emulsión'] + sorted(em_unicos)
                filtro_emulsion = st.multiselect("% Emulsión", options=opciones_emulsion, default=[])

        # Aplicar filtros solo si el usuario seleccionó algo
        mask = pd.Series([True] * len(df))  # sin filtro por defecto

        if filtro_cantera:
            if 'Sin cantera' in filtro_cantera:
                mask_cantera = df['cantera'].isna() | df['cantera'].isin(
                    [c for c in filtro_cantera if c != 'Sin cantera']
                )
            else:
                mask_cantera = df['cantera'].isin(filtro_cantera)
            mask &= mask_cantera

        if filtro_resultado:
            mask &= df['resultado'].isin(filtro_resultado)

        if filtro_emulsion:
            if 'Sin % emulsión' in filtro_emulsion:
                mask_emulsion = df['porcentaje_emulsion'].isna() | df['porcentaje_emulsion'].isin(
                    [e for e in filtro_emulsion if e != 'Sin % emulsión']
                )
            else:
                mask_emulsion = df['porcentaje_emulsion'].isin(filtro_emulsion)
            mask &= mask_emulsion

        df_filtrado = df[mask]

        # ==========================
        # TABLA DE DATOS (¡agregada!)
        # ==========================
        st.subheader("Tabla de datos")
        st.dataframe(
            df_filtrado.style.format({
                'fuerza_estatica': '{:.4f}',
                'min_des_din': '{:.2e}',
                'max_des_din': '{:.2e}',
                'max_fuer_din': '{:.4f}',
                'min_fuer_din': '{:.4f}',
                'porcentaje_emulsion': '{:.1f}'
            }),
            use_container_width=True,
            height=400
        )

        # ==========================
        # GRÁFICOS
        # ==========================
        st.subheader("📈 Análisis visual")
        colg1, colg2 = st.columns(2)

        with colg1:
            st.markdown("**Resultados por % de emulsión**")
            if not df_filtrado.empty:
                pivote = df_filtrado.groupby(['porcentaje_emulsion', 'resultado']).size().unstack(fill_value=0)
                colors = sns.color_palette("pastel", n_colors=len(pivote.columns))
                fig, ax = plt.subplots(figsize=(6, 4))
                pivote.plot(kind='bar', stacked=True, ax=ax, color=colors)
                ax.set_xlabel("% Emulsión")
                ax.set_ylabel("Cantidad de ensayos")
                ax.legend(title="Resultado", bbox_to_anchor=(1.05, 1), loc='upper left')
                ax.grid(axis='y', linestyle='--', alpha=0.5)
                st.pyplot(fig)
            else:
                st.write("Sin datos para graficar.")

        with colg2:
            st.markdown("**Fuerza estática vs % Emulsión**")
            if not df_filtrado.empty:
                fig, ax = plt.subplots(figsize=(6, 4))
                res_unicos = df_filtrado['resultado'].unique()
                palette = sns.color_palette("husl", len(res_unicos))
                color_map = dict(zip(res_unicos, palette))
                for res in res_unicos:
                    subset = df_filtrado[df_filtrado['resultado'] == res]
                    ax.scatter(subset['porcentaje_emulsion'], subset['fuerza_estatica'],
                               label=res, color=color_map[res], alpha=0.7, edgecolor='k')
                ax.set_xlabel("% Emulsión")
                ax.set_ylabel("Fuerza Estática [N]")
                ax.legend(title="Resultado", bbox_to_anchor=(1.05, 1), loc='upper left')
                ax.grid(True, linestyle='--', alpha=0.5)
                st.pyplot(fig)
            else:
                st.write("Sin datos para graficar.")

        # ==========================
        # DESCARGA DE CSV
        # ==========================
        csv = df_filtrado.to_csv(index=False)
        st.download_button(
            label="⬇️ Descargar datos filtrados como CSV",
            data=csv,
            file_name="ensayos_filtrados.csv",
            mime="text/csv"
        )

# ==============================
# PESTAÑA 4: PREDECIR RESULTADO
# ==============================
with tab4:
    st.header("Predicción del resultado de un ensayo")
    st.warning("Modelo entrenado con los datos actuales. Con pocos registros, la predicción es orientativa.")

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import LabelEncoder, StandardScaler
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import cross_val_score

    df_model = cargar_ensayos()
    df_model = df_model.dropna(subset=['porcentaje_emulsion', 'resultado']).copy()

    # Crear variable objetivo
    df_model['exito'] = (df_model['resultado'] == 'Exitoso').astype(int)

    features = ['cantera', 'porcentaje_emulsion', 'fuerza_estatica', 'max_des_din', 'max_fuer_din']
    X = df_model[features]
    y = df_model['exito']

    if len(y.unique()) < 2:
        st.info("Aún no hay suficientes ejemplos de ambos resultados (éxito y fallo) para entrenar un modelo fiable.")
    else:
        # Preprocesamiento
        numeric_features = ['porcentaje_emulsion', 'fuerza_estatica', 'max_des_din', 'max_fuer_din']
        categorical_features = ['cantera']

        numeric_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler())
        ])
        categorical_transformer = Pipeline(steps=[
            ('imputer', SimpleImputer(strategy='most_frequent')),
            ('label', LabelEncoder())
        ])

        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, numeric_features),
                ('cat', categorical_transformer, categorical_features)
            ])

        model = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
        ])

        model.fit(X, y)

        # Validación cruzada
        scores = cross_val_score(model, X, y, cv=min(5, len(y)), scoring='accuracy')
        st.metric("Precisión promedio (validación cruzada)", f"{scores.mean():.2f}")

        # Importancia
        st.subheader("Importancia de variables")
        importances = model.named_steps['classifier'].feature_importances_
        fig_imp, ax_imp = plt.subplots()
        ax_imp.barh(features, importances, color='skyblue')
        ax_imp.set_xlabel("Importancia")
        st.pyplot(fig_imp)

        # Formulario de predicción
        st.subheader("🔎 Simular un nuevo ensayo")
        with st.form("form_prediccion"):
            colp1, colp2 = st.columns(2)
            with colp1:
                canteras_pred = cargar_canteras()
                p_cantera = st.selectbox("Cantera", canteras_pred['nombre'])
                p_emulsion_pred = st.number_input("% Emulsión", value=10.0)
                p_f_estatica = st.number_input("Fuerza Estática [N]", value=-3.0, format="%.4f")
            with colp2:
                p_max_des = st.number_input("Max Des Din [m]", value=1.0e-4, format="%.6e")
                p_max_fdin = st.number_input("Max Fuer Din [N]", value=2.0)
            predecir = st.form_submit_button("🔮 Predecir resultado")

            if predecir:
                input_data = pd.DataFrame({
                    'cantera': [p_cantera],
                    'porcentaje_emulsion': [p_emulsion_pred],
                    'fuerza_estatica': [p_f_estatica],
                    'max_des_din': [p_max_des],
                    'max_fuer_din': [p_max_fdin]
                })
                proba = model.predict_proba(input_data)[0][1]
                pred = model.predict(input_data)[0]
                if pred == 1:
                    st.success(f"🎉 Probabilidad de ÉXITO: {proba:.0%}")
                else:
                    st.error(f"⚠️ Probabilidad de FALLO: {1 - proba:.0%} (éxito: {proba:.0%})")
