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

    # --- 1. TAB LIMPIEZA (MOTOR MEJORADO) ---
    with tab_limp:
        st.header("Limpieza de Variables")
        col_select = st.selectbox("Selecciona Variable para Revisar", df.columns)
        
        # FORZAMOS LA CONVERSIÓN para detectar errores (como en Colab)
        serie_orig = df[col_select]
        serie_num = pd.to_numeric(serie_orig, errors='coerce')
        
        # Determinamos si es numérica o textual basándonos en si pudimos convertir datos
        es_realmente_num = not serie_num.isna().all()

        if es_realmente_num:
            st.success(f"Variable '{col_select}' tratada como NUMÉRICA")
            
            # Detectar Errores de Texto (Caracteres extraños)
            mask_texto = serie_num.isna() & serie_orig.notna()
            cant_texto = mask_texto.sum()
            
            # Detectar Ceros
            cant_ceros = (serie_num == 0).sum()
            
            # Detectar Vacíos Reales
            cant_vacios = serie_orig.isna().sum()

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Errores de texto", cant_texto)
            with col2:
                st.metric("Valores en Cero", cant_ceros)
            with col3:
                st.metric("Celdas Vacías", cant_vacios)

            st.markdown("---")
            st.write("### ¿Cómo deseas limpiar esta variable?")
            
            metodo = st.selectbox("Sustituir fallos por:", 
                                ["Mantener originales", "MEDIA", "MEDIANA", "MODA", "0", "NAN", "Número específico"])
            
            valor_manual = 0.0
            if metodo == "Número específico":
                valor_manual = st.number_input("Escribe el número:", value=0.0)

            if st.button(f"🚀 Aplicar Limpieza a {col_select}"):
                if metodo != "Mantener originales":
                    if metodo == "Número específico":
                        final_val = valor_manual
                    else:
                        final_val = calcular_sustituto(serie_num, metodo)
                    
                    # Aplicamos la misma lógica de Colab:
                    # 1. Errores de texto se limpian
                    # 2. Vacíos se limpian
                    # 3. Ceros (solo si el usuario quiere, aquí lo simplificamos a que limpie todo lo no-numérico)
                    nuevo_df = st.session_state['df_master'].copy()
                    nuevo_df[col_select] = serie_num.fillna(final_val)
                    
                    st.session_state['df_master'] = nuevo_df
                    st.toast(f"¡Variable {col_select} limpiada con éxito!")
                    st.rerun()
        else:
            st.warning(f"La variable '{col_select}' parece ser puramente TEXTUAL.")

    # --- 2. TAB UNIVARIADO ---
    with tab_univ:
        st.header("Análisis Descriptivo")
        if st.checkbox("Mostrar tablas de frecuencia (Texto)"):
            for col in df.select_dtypes(exclude=[np.number]).columns:
                with st.expander(f"Frecuencias: {col}"):
                    f = df[col].value_counts(dropna=False).reset_index()
                    f.columns = ['Categoría', 'N']
                    f['%'] = (f['N'] / f['N'].sum() * 100).round(1)
                    st.table(f)

    # --- 3. TAB BIVARIADO ---
    with tab_biv:
        st.header("Configuración de Cruces para el Excel")
        st.info("Selecciona las variables que aparecerán en las COLUMNAS del reporte final.")
        vars_seleccionadas = st.multiselect("Variables de Cruce (Columnas)", df.columns)

    # --- 4. TAB RESPUESTA MÚLTIPLE ---
    with tab_mult:
        st.header("Configuración de Conjuntos")
        with st.form("fm_multi"):
            nom_g = st.text_input("Nombre del Conjunto (ej: Marcas)", value=f"Grupo {len(st.session_state['grupos_multiples'])+1}")
            cols_g = st.multiselect("Selecciona las columnas a agrupar", df.columns)
            if st.form_submit_button("✅ Registrar este Grupo"):
                if cols_g:
                    df_s = df[cols_g]
                    n_p = df_s.notna().any(axis=1).sum()
                    menc = df_s.stack().value_counts()
                    t_mr = pd.DataFrame({
                        'Menciones (f)': menc,
                        '% de Casos (Base Personas)': (menc / n_p * 100).round(1),
                        '% de Respuestas (Base Menciones)': (menc / menc.sum() * 100).round(1)
                    }).sort_values('Menciones (f)', ascending=False)
                    
                    st.session_state['grupos_multiples'].append({
                        'nombre': nom_g, 'tabla': t_mr, 'n_personas': n_p, 
                        'columnas': cols_g, 'total_menciones': menc.sum()
                    })
                    st.rerun()
        
        for g in st.session_state['grupos_multiples']:
            st.write(f"✔️ **{g['nombre']}** ({len(g['columnas'])} variables registradas)")

    # --- BOTÓN GENERAR EXCEL ---
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

                        if es_vc_num or es_vf_num:
                            v_num, v_cat = (vc, vf) if es_vc_num else (vf, vc)
                            res = df.groupby(v_cat)[v_num].agg(['count', 'mean', 'std']).round(2)
                            sh_bi2.write(r_b2, 0, f"Análisis: {v_num} por {v_cat}", fmt_bold)
                            res.to_excel(writer, sheet_name='BIVARIADO 2', startrow=r_b2+1)
                            r_b2 += len(res) + 4
                        else:
                            sh_bi1.write(r_b1, 0, f"Cruce: {vf} vs {vc}", fmt_bold)
                            ct = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).round(1)
                            col_sums = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).sum()
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

        st.sidebar.download_button("⬇️ DESCARGAR EXCEL FINAL", output.getvalue(), "Reporte_Papanajaco.xlsx")
else:
    st.info("Sube tu archivo para comenzar el análisis.")
