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
# Registro de limpieza más detallado
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

    # --- 1. TAB LIMPIEZA CON MONITORES DUALES ---
    with tab_limp:
        st.header("Limpieza de Variables Numéricas")
        col_select = st.selectbox("Selecciona Variable", df.columns)
        col_data = pd.to_numeric(df[col_select], errors='coerce')
        
        if not col_data.isna().all():
            vacios_ini = col_data.isna().sum()
            ceros_ini = (col_data == 0).sum()

            st.subheader("📊 Estatus de Transformación")
            m1, m2, m3 = st.columns([1, 1, 2])
            m1.metric("Errores/Vacíos", vacios_ini)
            m2.metric("Valores CERO", ceros_ini)
            
            # Monitor Dual de Decisiones
            log = st.session_state['limpieza_log'].get(col_select, {"err": "Ninguna", "cero": "Ninguna", "total": 0})
            resumen_decisiones = f"Err: {log['err']} | Ceros: {log['cero']}"
            m3.metric("Decisiones Tomadas", resumen_decisiones, f"{log['total']} reg. procesados")

            st.markdown("---")
            metodo_v = st.selectbox(f"Tratar errores/vacíos por:", ["Mantener", "MEDIA", "MEDIANA", "MODA", "0", "NAN"])
            limpiar_c = st.checkbox(f"Tratar ceros como no reales")
            metodo_c = "Mantener"
            if limpiar_c:
                metodo_c = st.selectbox("Sustituir ceros por:", ["MEDIA", "MEDIANA", "MODA", "NAN"])

            if st.button(f"🚀 EJECUTAR TRANSFORMACIÓN"):
                new_serie = col_data.copy()
                total_cambios = 0
                
                # Proceso de Errores
                dec_err = log['err']
                if metodo_v != "Mantener":
                    val_v = calcular_sustituto(new_serie, metodo_v)
                    new_serie = new_serie.fillna(val_v)
                    dec_err = metodo_v
                    total_cambios += vacios_ini
                
                # Proceso de Ceros
                dec_cero = log['cero']
                if metodo_c != "Mantener":
                    val_c = calcular_sustituto(new_serie.replace(0, np.nan), metodo_c)
                    new_serie = new_serie.replace(0, val_c)
                    dec_cero = metodo_c
                    total_cambios += ceros_ini

                st.session_state['df_master'][col_select] = new_serie
                st.session_state['limpieza_log'][col_select] = {
                    "err": dec_err, 
                    "cero": dec_cero, 
                    "total": total_cambios
                }
                st.success("¡Transformación aplicada!")
                st.rerun()
        else: st.warning("Variable Textual")

    # --- 2. TAB UNIVARIADO (CON MODA) ---
    with tab_univ:
        st.header("Reporte Descriptivo Completo")
        df_num = df.select_dtypes(include=[np.number])
        if not df_num.empty:
            st.subheader("📈 Estadísticos de Variables Numéricas")
            resumen = df_num.agg(['count', 'min', 'max', 'mean', 'median', 'std']).T
            resumen['Moda'] = [df_num[c].mode()[0] if not df_num[c].mode().empty else np.nan for c in df_num.columns]
            resumen['P5'] = df_num.quantile(0.05)
            resumen['P95'] = df_num.quantile(0.95)
            resumen = resumen[['count', 'min', 'max', 'mean', 'median', 'Moda', 'std', 'P5', 'P95']]
            st.dataframe(resumen.round(2))
        
        st.markdown("---")
        st.subheader("📊 Tablas de Frecuencia (Cualitativas)")
        for c in df.select_dtypes(exclude=[np.number]).columns:
            with st.expander(f"Variable: {c}"):
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Categoría', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1)
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
        for g in st.session_state['grupos_multiples']: st.write(f"✔️ **{g['nombre']}**")

    # --- EXPORTACIÓN ---
    st.sidebar.markdown("---")
    if st.sidebar.button("🚀 GENERAR EXCEL FINAL"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            f_tit = workbook.add_format({'bold': True, 'bg_color': '#2E5077', 'font_color': 'white', 'border': 1})
            f_bold = workbook.add_format({'bold': True})

            # UNIVARIADO
            sh1 = workbook.add_worksheet('UNIVARIADO')
            if not df_num.empty: resumen.round(2).to_excel(writer, sheet_name='UNIVARIADO', startrow=2)
            
            # BIVARIADOS
            sh_bi1 = workbook.add_worksheet('BIVARIADO'); sh_bi2 = workbook.add_worksheet('BIVARIADO 2'); r1, r2 = 2, 2
            if vars_seleccionadas:
                for vc in vars_seleccionadas:
                    for vf in [c for c in df.columns if c not in vars_seleccionadas]:
                        if pd.api.types.is_numeric_dtype(df[vc]) and pd.api.types.is_numeric_dtype(df[vf]): continue
                        if pd.api.types.is_numeric_dtype(df[vc]) or pd.api.types.is_numeric_dtype(df[vf]):
                            v_n, v_c = (vc, vf) if pd.api.types.is_numeric_dtype(df[vc]) else (vf, vc)
                            res = df.groupby(v_c)[v_n].agg(['count', 'mean', 'std']).round(2)
                            sh_bi2.write(r2, 0, f"Análisis: {v_n} por {v_c}", f_bold); res.to_excel(writer, sheet_name='BIVARIADO 2', startrow=r2+1); r2 += len(res) + 4
                        else:
                            sh_bi1.write(r1, 0, f"Cruce: {vf} vs {vc}", f_bold); ct = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).round(1)
                            ct.loc['TOTAL'] = ["MULTIPLE" if s > 100.1 else "100.0%" for s in ct.sum()]
                            ct.to_excel(writer, sheet_name='BIVARIADO', startrow=r1+1); r1 += len(ct) + 4

            # CONJUNTOS_MULTIPLES
            sh4 = workbook.add_worksheet('CONJUNTOS_MULTIPLES')
            r_m = 1
            for g in st.session_state['grupos_multiples']:
                sh4.write(r_m, 0, f"CONJUNTO: {g['nombre']}", f_bold)
                dt = g['tabla'].copy()
                dt.loc['TOTAL'] = [dt['Menciones'].sum(), f"{dt['% Casos'].sum().round(1)}% (MULTIPLE)", "100.0%"]
                dt.to_excel(writer, sheet_name='CONJUNTOS_MULTIPLES', startrow=r_m+1); r_m += len(dt) + 6

        st.sidebar.download_button("⬇️ DESCARGAR REPORTE", output.getvalue(), "Analisis_Final.xlsx")
else: st.info("Sube tu archivo para comenzar.")
