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

# --- INTERFAZ ---
st.sidebar.header("📁 CARGA DE DATOS")
archivo_cargado = st.sidebar.file_uploader("Sube tu Excel", type=["xlsx"])

if archivo_cargado:
    if st.session_state['df_master'] is None:
        st.session_state['df_master'] = pd.read_excel(archivo_cargado)
    
    # Trabajamos siempre sobre la versión en memoria
    df = st.session_state['df_master']
    st.title("🌟 Procesador Estadístico Profesional")
    
    tab_limp, tab_univ, tab_biv, tab_mult = st.tabs(["🛠️ Limpieza", "📉 Univariado", "📊 Bivariado", "🔢 R. Múltiple"])

    # --- 1. TAB LIMPIEZA (VERSION DEFINITIVA) ---
    with tab_limp:
        st.header("Limpieza de Variables Numéricas")
        col_select = st.selectbox("Selecciona Variable para Revisar", df.columns)
        
        # 1. Intentamos convertir a número siempre
        serie_orig = df[col_select]
        serie_num = pd.to_numeric(serie_orig, errors='coerce')
        
        es_num = not serie_num.isna().all()

        if es_num:
            # Si detectamos que la columna original tiene textos pero es numérica, 
            # actualizamos la memoria para que ya sea float64 (como en Colab)
            if not np.issubdtype(df[col_select].dtype, np.number):
                st.session_state['df_master'][col_select] = serie_num
                st.rerun()

            # Conteos reales
            vacios = serie_num.isna().sum()
            ceros = (serie_num == 0).sum()

            c1, c2 = st.columns(2)
            c1.metric("Errores de texto (vacías o no números)", vacios)
            c2.metric("Valores en Cero", ceros)

            st.markdown("---")
            st.subheader("Configuración de Limpieza Integral")

            # Pregunta por Errores
            metodo_v = "Mantener"
            if vacios > 0:
                metodo_v = st.selectbox(f"¿Cómo sustituir los {vacios} errores/vacíos?", 
                                      ["Mantener", "NAN", "0", "MEDIA", "MEDIANA", "MODA"])
            
            # Pregunta por Ceros
            metodo_c = "Mantener"
            if ceros > 0:
                limpiar_c = st.checkbox(f"Sustituir los {ceros} valores en cero (no son reales)")
                if limpiar_c:
                    metodo_c = st.selectbox("Sustituir ceros por:", ["NAN", "MEDIA", "MEDIANA", "MODA"])

            st.markdown("---")
            if st.button(f"🚀 EJECUTAR LIMPIEZA DE {col_select}"):
                temp_df = st.session_state['df_master'].copy()
                col_data = temp_df[col_select]

                # Acción 1: Limpiar Vacíos
                if metodo_v != "Mantener":
                    val_v = calcular_sustituto(col_data, metodo_v)
                    col_data = col_data.fillna(val_v)
                
                # Acción 2: Limpiar Ceros
                if metodo_c != "Mantener":
                    # Para promedios, ignoramos los ceros actuales
                    base_calculo = col_data.replace(0, np.nan)
                    val_c = calcular_sustituto(base_calculo, metodo_c)
                    col_data = col_data.replace(0, val_c)

                st.session_state['df_master'][col_select] = col_data
                st.success(f"¡Variable {col_select} procesada!")
                st.rerun()
        else:
            st.warning("Variable detectada como TEXTUAL.")

    # --- 2. TAB UNIVARIADO ---
    with tab_univ:
        st.header("Análisis Descriptivo")
        if st.checkbox("Mostrar tablas de frecuencia (Texto)"):
            for col in df.select_dtypes(exclude=[np.number]).columns:
                with st.expander(f"Frecuencias: {col}"):
                    f = df[col].value_counts(dropna=False).reset_index()
                    f.columns = ['Categoría', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1)
                    st.table(f)

    # --- 3. TAB BIVARIADO ---
    with tab_biv:
        st.header("Configuración de Cruces")
        vars_seleccionadas = st.multiselect("Variables de Cruce (Columnas)", df.columns)

    # --- 4. TAB RESPUESTA MÚLTIPLE ---
    with tab_mult:
        st.header("Configuración de Conjuntos")
        with st.form("fm_multi"):
            nom_g = st.text_input("Nombre del Conjunto", value=f"Grupo {len(st.session_state['grupos_multiples'])+1}")
            cols_g = st.multiselect("Variables", df.columns)
            if st.form_submit_button("✅ Registrar"):
                if cols_g:
                    df_s = df[cols_g]; n_p = df_s.notna().any(axis=1).sum(); menc = df_s.stack().value_counts()
                    t_mr = pd.DataFrame({'Menciones': menc, '% Casos': (menc/n_p*100).round(1), '% Respuestas': (menc/menc.sum()*100).round(1)}).sort_values('Menciones', ascending=False)
                    st.session_state['grupos_multiples'].append({'nombre': nom_g, 'tabla': t_mr, 'n_personas': n_p, 'columnas': cols_g, 'total_menciones': menc.sum()})
                    st.rerun()
        for g in st.session_state['grupos_multiples']: st.write(f"✔️ **{g['nombre']}**")

    # --- BOTÓN GENERAR EXCEL ---
    st.sidebar.markdown("---")
    if st.sidebar.button("🚀 GENERAR REPORTE INTEGRAL"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            fmt_tit = workbook.add_format({'bold': True, 'bg_color': '#2E5077', 'font_color': 'white', 'border': 1}); fmt_bold = workbook.add_format({'bold': True})
            sh1 = workbook.add_worksheet('UNIVARIADO'); df.describe().T.to_excel(writer, sheet_name='UNIVARIADO', startrow=1)
            sh_bi1 = workbook.add_worksheet('BIVARIADO'); sh_bi2 = workbook.add_worksheet('BIVARIADO 2'); r_b1, r_b2 = 2, 2
            if vars_seleccionadas:
                for vc in vars_seleccionadas:
                    for vf in [c for c in df.columns if c not in vars_seleccionadas]:
                        es_vc_num = pd.api.types.is_numeric_dtype(df[vc]); es_vf_num = pd.api.types.is_numeric_dtype(df[vf])
                        if es_vc_num and es_vf_num: continue
                        if es_vc_num or es_vf_num:
                            v_num, v_cat = (vc, vf) if es_vc_num else (vf, vc); res = df.groupby(v_cat)[v_num].agg(['count', 'mean', 'std']).round(2)
                            sh_bi2.write(r_b2, 0, f"Análisis: {v_num} por {v_cat}", fmt_bold); res.to_excel(writer, sheet_name='BIVARIADO 2', startrow=r_b2+1); r_b2 += len(res) + 4
                        else:
                            sh_bi1.write(r_b1, 0, f"Cruce: {vf} vs {vc}", fmt_bold); ct = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).round(1); col_sums = ct.sum()
                            ct.loc['TOTAL'] = ["MULTIPLE" if s > 100.1 else "100.0%" for s in col_sums]; ct.to_excel(writer, sheet_name='BIVARIADO', startrow=r_b1+1); r_b1 += len(ct) + 4
            sh4 = workbook.add_worksheet('CONJUNTOS_MULTIPLES'); r_m = 1
            for g in st.session_state['grupos_multiples']:
                sh4.write(r_m, 0, f"CONJUNTO: {g['nombre']}", fmt_bold); df_t = g['tabla'].copy(); sum_c = df_t['% Casos'].sum().round(1)
                df_t.loc['TOTAL'] = [df_t['Menciones'].sum(), f"{sum_c}% (MULTIPLE)", "100.0%"]; df_t.to_excel(writer, sheet_name='CONJUNTOS_MULTIPLES', startrow=r_m+1); r_m += len(df_t) + 6
        st.sidebar.download_button("⬇️ DESCARGAR EXCEL", output.getvalue(), "Reporte_Estadistico.xlsx")
    st.sidebar.caption("⚠️ Oprimir solo después de haber limpiado todas las variables y definido todos los cruces y conjuntos.")
else: st.info("Sube tu archivo para comenzar.")
