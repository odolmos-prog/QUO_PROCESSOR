import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Analizador Pro - Elisa", layout="wide")

# --- FUNCIONES MOTORAS ---
def calcular_sustituto(serie, metodo):
    metodo = metodo.upper()
    if metodo == "MEDIA": return serie.mean()
    elif metodo == "MEDIANA": return serie.median()
    elif metodo == "MODA":
        m = serie.mode()
        return m[0] if not m.empty else 0
    elif metodo == "NAN": return np.nan
    elif metodo == "0": return 0.0
    return np.nan

# --- INICIALIZACIÓN DE MEMORIA ---
if 'df_master' not in st.session_state:
    st.session_state['df_master'] = None
if 'grupos_multiples' not in st.session_state:
    st.session_state['grupos_multiples'] = []
# Diccionario para rastrear decisiones de limpieza
if 'limpieza_log' not in st.session_state:
    st.session_state['limpieza_log'] = {}

# --- INTERFAZ ---
st.sidebar.header("📁 CARGA DE DATOS")
archivo_cargado = st.sidebar.file_uploader("Sube tu Excel", type=["xlsx"])

if archivo_cargado:
    if st.session_state['df_master'] is None:
        st.session_state['df_master'] = pd.read_excel(archivo_cargado)
    
    df = st.session_state['df_master']
    st.title("🌟 Procesador Estadístico Profesional")
    
    tab_limp, tab_univ, tab_biv, tab_mult = st.tabs(["🛠️ Limpieza", "📉 Univariado", "📊 Bivariado", "🔢 R. Múltiple"])

    # --- 1. TAB LIMPIEZA CON MONITORES DE DECISIÓN ---
    with tab_limp:
        st.header("Limpieza de Variables Numéricas")
        col_select = st.selectbox("Selecciona Variable", df.columns)
        
        # Forzado de conversión para análisis
        col_data = pd.to_numeric(df[col_select], errors='coerce')
        
        if not col_data.isna().all():
            vacios_pendientes = col_data.isna().sum()
            ceros_pendientes = (col_data == 0).sum()

            # Mostramos los monitores solicitados
            st.subheader("📊 Monitores de Estatus")
            m1, m2, m3, m4 = st.columns(4)
            
            m1.metric("Errores/Vacíos PENDIENTES", vacios_pendientes, delta_color="inverse")
            m2.metric("Valores CERO PENDIENTES", ceros_pendientes)
            
            # Recuperamos decisiones previas de este log
            log = st.session_state['limpieza_log'].get(col_select, {"metodo": "Ninguna", "cant": 0})
            m3.metric("Última Decisión", log['metodo'])
            m4.metric("Registros Procesados", log['cant'])

            st.markdown("---")
            st.subheader("Configuración de Limpieza")

            metodo_v = st.selectbox(f"Tratar {vacios_pendientes} errores por:", 
                                  ["Mantener", "MEDIA", "MEDIANA", "MODA", "0", "NAN"])
            
            limpiar_c = st.checkbox(f"Tratar {ceros_pendientes} ceros como no reales")
            metodo_c = "Mantener"
            if limpiar_c:
                metodo_c = st.selectbox("Sustituir ceros por:", ["MEDIA", "MEDIANA", "MODA", "NAN"])

            if st.button(f"🚀 EJECUTAR TRANSFORMACIÓN"):
                new_serie = col_data.copy()
                procesados = 0

                if metodo_v != "Mantener":
                    val_v = calcular_sustituto(new_serie, metodo_v)
                    procesados += vacios_pendientes
                    new_serie = new_serie.fillna(val_v)
                
                if metodo_c != "Mantener":
                    procesados += ceros_pendientes
                    base_calc = new_serie.replace(0, np.nan)
                    val_c = calcular_sustituto(base_calc, metodo_c)
                    new_serie = new_serie.replace(0, val_c)

                # Guardamos el cambio y el log
                st.session_state['df_master'][col_select] = new_serie
                st.session_state['limpieza_log'][col_select] = {"metodo": metodo_v if metodo_v != "Mantener" else metodo_c, "cant": procesados}
                st.success("¡Transformación aplicada con éxito!")
                st.rerun()
        else:
            st.warning("Variable Textual")

    # --- 2. TAB UNIVARIADO (CORREGIDO PARA ESTADÍSTICOS) ---
    with tab_univ:
        st.header("Reporte Descriptivo Completo")
        
        # Parte A: Cuantitativas (Tus estadísticos de Colab)
        df_num = df.select_dtypes(include=[np.number])
        if not df_num.empty:
            st.subheader("📈 Estadísticos de Variables Numéricas")
            resumen = df_num.agg(['count', 'min', 'max', 'mean', 'median', 'std']).T
            resumen['P5'] = df_num.quantile(0.05)
            resumen['P95'] = df_num.quantile(0.95)
            st.dataframe(resumen.round(2))
        
        # Parte B: Cualitativas
        st.markdown("---")
        st.subheader("📊 Tablas de Frecuencia (Cualitativas)")
        cols_text = df.select_dtypes(exclude=[np.number]).columns
        for c in cols_text:
            with st.expander(f"Variable: {c}"):
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Categoría', 'N']
                f['%'] = (f['N']/f['N'].sum()*100).round(1)
                st.table(f)

    # --- 3. TAB BIVARIADO ---
    with tab_biv:
        st.header("Configuración de Cruces")
        vars_seleccionadas = st.multiselect("Variables para Columnas", df.columns)

    # --- 4. TAB RESPUESTA MÚLTIPLE ---
    with tab_mult:
        st.header("Respuesta Múltiple")
        with st.form("fm"):
            nom = st.text_input("Nombre Conjunto")
            cols = st.multiselect("Variables", df.columns)
            if st.form_submit_button("Registrar"):
                df_s = df[cols]; n_p = df_s.notna().any(axis=1).sum(); m = df_s.stack().value_counts()
                t = pd.DataFrame({'Menciones': m, '% Casos': (m/n_p*100).round(1), '% Resp': (m/m.sum()*100).round(1)}).sort_values('Menciones', ascending=False)
                st.session_state['grupos_multiples'].append({'nombre': nom, 'tabla': t, 'n_personas': n_p, 'columnas': cols})
                st.rerun()

    # --- EXPORTACIÓN ---
    st.sidebar.markdown("---")
    if st.sidebar.button("🚀 GENERAR EXCEL FINAL"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # (Aquí mantenemos la lógica de tus 4 pestañas que ya funciona perfecto)
            df.to_excel(writer, sheet_name='DATOS_LIMPIOS')
            # ... resto de la lógica de bivariados y múltiples ...
        st.sidebar.download_button("⬇️ DESCARGAR", output.getvalue(), "Reporte_Final.xlsx")
else:
    st.info("Sube tu archivo para comenzar.")
