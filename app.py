import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="QUO PROCESSOR Powered by Elisa", layout="wide")

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
    
    df = st.session_state['df_master']
    st.title("🌟 QUO PROCESSOR Powered by Elisa")
    
    tab_limp, tab_univ, tab_biv, tab_mult = st.tabs(["🛠️ Limpieza", "📉 Univariado", "📊 Bivariado", "🔢 R. Múltiple"])

    # 1. TAB LIMPIEZA
    with tab_limp:
        st.header("Limpieza de Variables")
        col_select = st.selectbox("Selecciona Variable", df.columns)
        serie_num = pd.to_numeric(df[col_select], errors='coerce')
        if pd.api.types.is_numeric_dtype(df[col_select]):
            op = st.radio("Sustituir por:", ["Mantener", "MEDIA", "MEDIANA", "MODA", "0", "NAN"], horizontal=True)
            if st.button("Aplicar"):
                if op != "Mantener":
                    st.session_state['df_master'][col_select] = serie_num.fillna(calcular_sustituto(serie_num, op))
                    st.rerun()
        else: st.info("Variable Textual")

    # 2. TAB UNIVARIADO
    with tab_univ:
        st.header("Vista previa de frecuencias")
        if st.button("Ver tablas de texto"):
            for col in df.select_dtypes(exclude=[np.number]).columns:
                st.write(f"**{col}**")
                st.table((df[col].value_counts(normalize=True)*100).round(1))

    # 3. TAB BIVARIADO
    with tab_biv:
        st.header("Configuración de Cruces")
        vars_seleccionadas = st.multiselect("Variables para COLUMNAS del Excel", df.columns)

    # 4. TAB RESPUESTA MÚLTIPLE
    with tab_mult:
        with st.form("fm"):
            nom_g = st.text_input("Nombre del Conjunto")
            cols_g = st.multiselect("Variables a agrupar", df.columns)
            if st.form_submit_button("Añadir Conjunto"):
                df_s = df[cols_g]
                n_p = df_s.notna().any(axis=1).sum()
                menc = df_s.stack().value_counts()
                t_mr = pd.DataFrame({
                    'Menciones (f)': menc,
                    '% de Casos (Base Personas)': (menc / n_p * 100).round(1),
                    '% de Respuestas (Base Menciones)': (menc / menc.sum() * 100).round(1)
                }).sort_values('Menciones (f)', ascending=False)
                st.session_state['grupos_multiples'].append({'nombre': nom_g, 'tabla': t_mr, 'n_personas': n_p, 'columnas': cols_g, 'total_menciones': menc.sum()})
                st.rerun()

    # --- BOTÓN GENERAR EXCEL (4 PESTAÑAS) ---
    st.sidebar.markdown("---")
    if st.sidebar.button("🚀 GENERAR REPORTE INTEGRAL"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            fmt_tit = workbook.add_format({'bold': True, 'bg_color': '#2E5077', 'font_color': 'white', 'border': 1})
            fmt_bold = workbook.add_format({'bold': True})

            # PESTAÑA 1: UNIVARIADO
            sh1 = workbook.add_worksheet('UNIVARIADO')
            df.describe().T.to_excel(writer, sheet_name='UNIVARIADO', startrow=1)

            # PESTAÑAS BIVARIADAS
            sh_bi1 = workbook.add_worksheet('BIVARIADO')
            sh_bi2 = workbook.add_worksheet('BIVARIADO 2')
            r_b1, r_b2 = 2, 2

            if vars_seleccionadas:
                for vc in vars_seleccionadas:
                    for vf in [c for c in df.columns if c not in vars_seleccionadas]:
                        es_vc_num = pd.api.types.is_numeric_dtype(df[vc])
                        es_vf_num = pd.api.types.is_numeric_dtype(df[vf])

                        if es_vc_num and es_vf_num: continue

                        # CASO CUANTI-CUALI (Va a BIVARIADO 2)
                        if es_vc_num or es_vf_num:
                            v_num, v_cat = (vc, vf) if es_vc_num else (vf, vc)
                            res = df.groupby(v_cat)[v_num].agg(['count', 'mean', 'std']).round(2)
                            sh_bi2.write(r_b2, 0, f"Análisis: {v_num} por {v_cat}", fmt_bold)
                            res.to_excel(writer, sheet_name='BIVARIADO 2', startrow=r_b2+1)
                            r_b2 += len(res) + 4
                        
                        # CASO CUALI-CUALI (Va a BIVARIADO)
                        else:
                            sh_bi1.write(r_b1, 0, f"Cruce: {vf} vs {vc}", fmt_bold)
                            ct = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).round(1)
                            # Lógica MULTIPLE
                            col_sums = ct.sum()
                            ct.loc['TOTAL'] = ["MULTIPLE" if s > 100.1 else "100.0%" for s in col_sums]
                            ct.to_excel(writer, sheet_name='BIVARIADO', startrow=r_b1+1)
                            r_b1 += len(ct) + 4

            # PESTAÑA 4: CONJUNTOS_MULTIPLES
            sh4 = workbook.add_worksheet('CONJUNTOS_MULTIPLES')
            r_m = 1
            for g in st.session_state['grupos_multiples']:
                sh4.write(r_m, 0, f"CONJUNTO: {g['nombre']}", fmt_bold)
                df_t = g['tabla'].copy()
                sum_c = df_t['% de Casos (Base Personas)'].sum().round(1)
                df_t.loc['TOTAL'] = [df_t['Menciones (f)'].sum(), f"{sum_c}% (MULTIPLE)", "100.0%"]
                df_t.to_excel(writer, sheet_name='CONJUNTOS_MULTIPLES', startrow=r_m+1)
                r_m += len(df_t) + 6

        st.sidebar.download_button("⬇️ DESCARGAR EXCEL", output.getvalue(), "Reporte_Completo Papanajaco.xlsx")
else:
    st.info("Sube tu archivo para comenzar.")
