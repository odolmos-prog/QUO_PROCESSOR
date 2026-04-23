import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest
import io
import itertools

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="QUO Processor Powered by Doble O y Elisa", layout="wide")
st.markdown("""
    <style>
    .stButton>button { background-color: #2E5077; color: white; border-radius: 8px; font-weight: bold; }
    .stDownloadButton>button { background-color: #008000; color: white; border-radius: 8px; font-weight: bold; width: 100%; }
    .main-title { font-size: 28px !important; font-weight: bold; color: #2E5077; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

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

def realizar_test_proporciones(ct_abs):
    try:
        df_test = ct_abs.drop('TOTAL', axis=0, errors='ignore').drop('TOTAL', axis=1, errors='ignore')
        col_totals = df_test.sum()
        columnas = df_test.columns.tolist()
        significancias = [] 
        for index, row in df_test.iterrows():
            for col1, col2 in itertools.combinations(columnas, 2):
                count = np.array([row[col1], row[col2]])
                nobs = np.array([col_totals[col1], col_totals[col2]])
                if np.any(nobs < 5) or np.any(count == 0): continue
                stat, pval = proportions_ztest(count, nobs, alternative='two-sided')
                if pval < 0.05:
                    ganadora = col1 if (count[0]/nobs[0]) > (count[1]/nobs[1]) else col2
                    significancias.append((index, ganadora))
        return significancias
    except: return []

def realizar_test_medias(df, v_num, v_cat):
    try:
        # Aseguramos limpieza absoluta de datos para el test T
        df_clean = df[[v_num, v_cat]].dropna()
        columnas = df_clean.groupby(v_cat)[v_num].mean().index.tolist()
        significancias = [] 
        for g1, g2 in itertools.combinations(columnas, 2):
            d1 = df_clean[df_clean[v_cat] == g1][v_num].values
            d2 = df_clean[df_clean[v_cat] == g2][v_num].values
            if len(d1) < 5 or len(d2) < 5: continue
            stat, pval = stats.ttest_ind(d1, d2, equal_var=False)
            if pval < 0.05:
                ganadora = g1 if d1.mean() > d2.mean() else g2
                significancias.append(ganadora)
        return significancias
    except: return []

# --- INICIALIZACIÓN ---
if 'df_master' not in st.session_state: st.session_state['df_master'] = None
if 'grupos_multiples' not in st.session_state: st.session_state['grupos_multiples'] = []
if 'limpieza_log' not in st.session_state: st.session_state['limpieza_log'] = {}

archivo_cargado = st.sidebar.file_uploader("Sube tu Excel", type=["xlsx"])

if archivo_cargado:
    if st.session_state['df_master'] is None:
        # CARGA ULTRA-LIMPIA: Eliminamos columnas sin nombre o vacías de raíz
        temp_df = pd.read_excel(archivo_cargado)
        temp_df = temp_df.loc[:, ~temp_df.columns.str.contains('^Unnamed')]
        st.session_state['df_master'] = temp_df.dropna(axis=1, how='all')
    
    df = st.session_state['df_master']
    st.markdown('<p class="main-title">🌟 QUO Processor Powered by Doble O y Elisa</p>', unsafe_allow_html=True)
    tab_limp, tab_univ, tab_biv, tab_mult = st.tabs(["🛠️ Limpieza", "📉 Univariado", "📊 Bivariado", "🔢 R. Múltiple"])

    with tab_limp:
        st.header("Limpieza de Variables Numéricas")
        col_select = st.selectbox("Selecciona Variable", df.columns)
        col_data = pd.to_numeric(df[col_select], errors='coerce')
        if not col_data.isna().all():
            v_i, c_i = col_data.isna().sum(), (col_data == 0).sum()
            st.subheader("📊 Estatus de Transformación")
            m1, m2, m3 = st.columns([1, 1, 2])
            m1.metric("Errores/Vacíos", v_i); m2.metric("Valores CERO", c_i)
            log = st.session_state['limpieza_log'].get(col_select, {"err": "Ninguna", "cero": "Ninguna", "total": 0})
            with m3:
                st.write("**Decisiones Tomadas**")
                st.markdown(f"<h3 style='font-size: 20px; color: #2E5077; margin-top: -10px;'>Err: {log['err']} | Ceros: {log['cero']}</h3>", unsafe_allow_html=True)
                st.caption(f"✅ {log['total']} reg. procesados")
            st.markdown("---")
            met_v = st.selectbox(f"Tratar errores/vacíos por:", ["Mantener", "MEDIA", "MEDIANA", "MODA", "0", "NAN"])
            limp_c = st.checkbox(f"Tratar ceros como no reales")
            met_c = "Mantener"
            if limp_c: met_c = st.selectbox("Sustituir ceros por:", ["MEDIA", "MEDIANA", "MODA", "NAN"])
            if st.button(f"🚀 EJECUTAR TRANSFORMACIÓN"):
                new_s = col_data.copy(); tot = 0; d_e, d_c = log['err'], log['cero']
                if met_v != "Mantener": new_s = new_s.fillna(calcular_sustituto(new_s, met_v)); d_e = met_v; tot += v_i
                if met_c != "Mantener": new_s = new_s.replace(0, calcular_sustituto(new_s.replace(0, np.nan), met_c)); d_c = met_c; tot += c_i
                st.session_state['df_master'][col_select] = new_s
                st.session_state['limpieza_log'][col_select] = {"err": d_e, "cero": d_c, "total": tot}; st.rerun()
        else: st.warning("Variable Textual")

    with tab_univ:
        st.header("Reporte Descriptivo Completo")
        df_num = df.select_dtypes(include=[np.number])
        if not df_num.empty:
            st.subheader("📈 Estadísticos Numéricos")
            res = df_num.agg(['count', 'min', 'max', 'mean', 'median', 'std']).T
            res['Moda'] = [df_num[c].mode()[0] if not df_num[c].mode().empty else np.nan for c in df_num.columns]
            res['P5'] = df_num.quantile(0.05); res['P95'] = df_num.quantile(0.95)
            res = res[['count', 'min', 'max', 'mean', 'median', 'Moda', 'std', 'P5', 'P95']]
            st.dataframe(res.round(2))
        st.markdown("---")
        for c in df.select_dtypes(exclude=[np.number]).columns:
            with st.expander(f"Variable: {c}"):
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Categoría', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1); st.table(f)

    with tab_biv:
        st.header("Configuración de Cruces")
        vars_sel = st.multiselect("Variables para Columnas", df.columns)

    with tab_mult:
        st.header("Respuesta Múltiple")
        with st.form("fm"):
            n = st.text_input("Nombre Conjunto"); cs = st.multiselect("Variables", df.columns)
            if st.form_submit_button("Registrar"):
                if cs:
                    ds = df[cs]; npers = ds.notna().any(axis=1).sum(); mc = ds.stack().value_counts()
                    t = pd.DataFrame({'Menciones': mc, '% Casos': (mc/npers*100).round(1), '% Resp': (mc/mc.sum()*100).round(1)}).sort_values('Menciones', ascending=False)
                    st.session_state['grupos_multiples'].append({'nombre': n, 'tabla': t, 'n_personas': npers, 'columnas': cs}); st.rerun()
        for g in st.session_state['grupos_multiples']: st.write(f"✔️ **{g['nombre']}**")

    st.sidebar.markdown("---")
    if st.sidebar.button("📊 GENERAR REPORTE"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            f_tit = workbook.add_format({'bold': True, 'font_size': 14, 'bg_color': '#2E5077', 'font_color': 'white', 'border': 1})
            f_sub = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
            f_bold = workbook.add_format({'bold': True, 'border': 1})
            f_sig = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100', 'bold': True, 'border': 1})

            sh1 = workbook.add_worksheet('UNIVARIADO'); sh1.write(0, 0, "ANÁLISIS UNIVARIADO", f_tit)
            row_u = 2
            if not df_num.empty:
                res.round(2).to_excel(writer, sheet_name='UNIVARIADO', startrow=row_u+1); row_u += len(res) + 4
            for c in df.select_dtypes(exclude=[np.number]).columns:
                sh1.write(row_u, 0, f"Variable: {c}", f_bold)
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Categoría', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1)
                f.loc[len(f)] = ['TOTAL', f['N'].sum(), 100.0]
                f.to_excel(writer, sheet_name='UNIVARIADO', startrow=row_u+1, index=False); row_u += len(f) + 3

            sh_bi1 = workbook.add_worksheet('BIVARIADO'); sh_bi2 = workbook.add_worksheet('BIVARIADO 2')
            r1, r2 = 2, 2
            if vars_sel:
                for vc in vars_sel:
                    for vf in [c for c in df.columns if c not in vars_sel]:
                        es_vc_n, es_vf_n = pd.api.types.is_numeric_dtype(df[vc]), pd.api.types.is_numeric_dtype(df[vf])
                        if es_vc_n and es_vf_n: continue
                        if not es_vc_n and not es_vf_n:
                            sh_bi1.write(r1, 0, f"Cruce: {vf} vs {vc}", f_bold)
                            ct_abs = pd.crosstab(df[vf], df[vc], margins=True, margins_name="TOTAL")
                            ct_abs.to_excel(writer, sheet_name='BIVARIADO', startrow=r1+1)
                            sigs = realizar_test_proporciones(ct_abs); r1 += len(ct_abs) + 3
                            ct_per = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).round(1)
                            ct_per.loc['TOTAL'] = ["MULTIPLE" if s > 100.1 else "100.0%" for s in ct_per.sum()]
                            ct_per.to_excel(writer, sheet_name='BIVARIADO', startrow=r1+1)
                            f_idx, c_idx = ct_per.index.tolist(), ct_per.columns.tolist()
                            for f_s, c_s in sigs:
                                try: writer.sheets['BIVARIADO'].write(f_idx.index(f_s)+r1+2, c_idx.index(c_s)+1, ct_per.loc[f_s, c_s], f_sig)
                                except: continue
                            r1 += len(ct_per) + 5
                        else:
                            v_n, v_c = (vc, vf) if es_vc_n else (vf, vc)
                            sh_bi2.write(r2, 0, f"Análisis de {v_n} por {v_c}", f_bold)
                            sigs_m = realizar_test_medias(df, v_n, v_c)
                            rb = df.groupby(v_c)[v_n].agg(['count', 'mean', 'std']).round(2)
                            rb.to_excel(writer, sheet_name='BIVARIADO 2', startrow=r2+1)
                            f_idx = rb.index.tolist()
                            for s_cat in sigs_m:
                                try: writer.sheets['BIVARIADO 2'].write(f_idx.index(s_cat)+r2+2, 2, rb.loc[s_cat, 'mean'], f_sig)
                                except: continue
                            r2 += len(rb) + 5

            sh4 = workbook.add_worksheet('CONJUNTOS_MULTIPLES'); r_m = 1
            for g in st.session_state['grupos_multiples']:
                sh4.write(r_m, 0, f"CONJUNTO: {g['nombre']}", f_bold); dt = g['tabla'].copy()
                dt.loc['TOTAL'] = [dt['Menciones'].sum(), f"{dt['% Casos'].sum().round(1)}% (MULTIPLE)", "100.0%"]
                dt.to_excel(writer, sheet_name='CONJUNTOS_MULTIPLES', startrow=r_m+1); r_m += len(dt) + 6

        st.sidebar.download_button("⬇️ DESCARGAR REPORTE", output.getvalue(), "Reporte_Final.xlsx")
else: st.info("Sube tu archivo para comenzar.")
