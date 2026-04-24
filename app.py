import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest
import io
import itertools

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="QUO Processor", layout="wide")

st.markdown("""
    <style>
    .stButton>button { background-color: #2E5077; color: white; border-radius: 8px; font-weight: bold; }
    .stDownloadButton>button { background-color: #008000; color: white; border-radius: 8px; font-weight: bold; }
    .main-title { font-size: 22px !important; font-weight: bold; color: #2E5077; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES ESTADÍSTICAS ---
def realizar_test_proporciones(ct_abs):
    try:
        df_t = ct_abs.drop('TOTAL', axis=0, errors='ignore').drop('TOTAL', axis=1, errors='ignore')
        col_totals = df_t.sum()
        cols = df_t.columns.tolist()
        sigs = []
        for idx, row in df_t.iterrows():
            for c1, c2 in itertools.combinations(cols, 2):
                counts = np.array([row[c1], row[c2]])
                nobs = np.array([col_totals[c1], col_totals[c2]])
                if np.any(nobs < 5) or np.any(counts == 0): continue
                _, pval = proportions_ztest(counts, nobs)
                if pval < 0.05:
                    ganadora = c1 if (counts[0]/nobs[0]) > (counts[1]/nobs[1]) else c2
                    sigs.append((idx, ganadora))
        return sigs
    except: return []

def realizar_test_medias(df, v_num, v_cat):
    try:
        grupos = df.groupby(v_cat)[v_num].mean().dropna().index.tolist()
        sigs = []
        for g1, g2 in itertools.combinations(grupos, 2):
            d1 = df[df[v_cat] == g1][v_num].dropna()
            d2 = df[df[v_cat] == g2][v_num].dropna()
            if len(d1) < 5 or len(d2) < 5: continue
            _, pval = stats.ttest_ind(d1, d2, equal_var=False)
            if pval < 0.05:
                sigs.append(g1 if d1.mean() > d2.mean() else g2)
        return sigs
    except: return []

# --- 3. GESTIÓN DE MEMORIA ---
if 'df_master' not in st.session_state: st.session_state['df_master'] = None
if 'grupos_multiples' not in st.session_state: st.session_state['grupos_multiples'] = []
if 'limpieza_log' not in st.session_state: st.session_state['limpieza_log'] = {}

def reset_data():
    st.session_state['df_master'] = None
    st.session_state['grupos_multiples'] = []
    st.session_state['limpieza_log'] = {}

# --- 4. INTERFAZ PRINCIPAL ---
archivo = st.sidebar.file_uploader("Sube tu Excel", type=["xlsx"], on_change=reset_data)

if archivo:
    if st.session_state['df_master'] is None:
        st.session_state['df_master'] = pd.read_excel(archivo)
    
    df = st.session_state['df_master']
    st.markdown('<p class="main-title">🌟 QUO Processor Powered by Doble O y Elisa</p>', unsafe_allow_html=True)
    
    t1, t2, t3, t4 = st.tabs(["🛠️ Limpieza", "📉 Univariado", "📊 Bivariado", "🔢 R. Múltiple"])

    # --- TAB LIMPIEZA ---
    with t1:
        st.header("Limpieza de Datos")
        # Quitamos columnas fantasma de la vista pero no de la base
        cols_limpias = [c for c in df.columns if "Unnamed" not in str(c)]
        v_sel = st.selectbox("Variable a procesar", cols_limpias)
        
        if v_sel in df.columns:
            s_num = pd.to_numeric(df[v_sel], errors='coerce')
            v_i, c_i = s_num.isna().sum(), (s_num == 0).sum()
            
            c1, c2, c3 = st.columns([1,1,2])
            c1.metric("Errores/Vacíos", v_i)
            c2.metric("Valores CERO", c_i)
            log = st.session_state['limpieza_log'].get(v_sel, {"txt": "Ninguna", "n": 0})
            c3.markdown(f"**Estatus:** <span style='color:blue'>{log['txt']}</span> ({log['n']} reg.)", unsafe_allow_html=True)

            met_v = st.selectbox("Sustituir errores por:", ["Mantener", "MEDIA", "MEDIANA", "MODA", "0", "NAN"])
            limp_c = st.checkbox("Sustituir ceros")
            met_c = st.selectbox("Ceros por:", ["MEDIA", "MEDIANA", "MODA", "NAN"]) if limp_c else "Mantener"

            if st.button("🚀 APLICAR TRANSFORMACIÓN"):
                temp_s = s_num.copy()
                if met_v != "Mantener":
                    val = temp_s.mean() if met_v=="MEDIA" else temp_s.median() if met_v=="MEDIANA" else temp_s.mode()[0] if met_v=="MODA" else 0 if met_v=="0" else np.nan
                    temp_s = temp_s.fillna(val)
                if met_c != "Mantener":
                    val_c = temp_s.replace(0, np.nan).mean() if met_c=="MEDIA" else temp_s.replace(0, np.nan).median() if met_c=="MEDIANA" else temp_s.replace(0, np.nan).mode()[0] if met_c=="MODA" else np.nan
                    temp_s = temp_s.replace(0, val_c)
                st.session_state['df_master'][v_sel] = temp_s
                st.session_state['limpieza_log'][v_sel] = {"txt": f"Err:{met_v}|0:{met_c}", "n": v_i+c_i if limp_c else v_i}
                st.rerun()

    # --- TAB UNIVARIADO ---
    with t2:
        st.header("Análisis Descriptivo")
        dn = df.select_dtypes(include=[np.number])
        if not dn.empty:
            res = dn.agg(['count', 'min', 'max', 'mean', 'median']).T
            res['Moda'] = [dn[c].mode()[0] if not dn[c].mode().empty else np.nan for c in dn.columns]
            st.dataframe(res.round(2))
        
        for c in df.select_dtypes(exclude=[np.number]).columns:
            with st.expander(f"Variable: {c}"):
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Cat', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1)
                st.table(f)

    # --- TAB BIVARIADO ---
    with t3:
        st.header("Cruces de Variables")
        v_cols = st.multiselect("Variables para Columnas", df.columns)

    # --- TAB MÚLTIPLE ---
    with t4:
        with st.form("multi"):
            nom = st.text_input("Nombre Grupo"); cs = st.multiselect("Columnas", df.columns)
            if st.form_submit_button("Registrar"):
                ds = df[cs]; npers = ds.notna().any(axis=1).sum(); mc = ds.stack().value_counts()
                t = pd.DataFrame({'N': mc, '% Casos': (mc/npers*100).round(1), '% Resp': (mc/mc.sum()*100).round(1)})
                st.session_state['grupos_multiples'].append({'nombre': nom, 'tabla': t, 'n_personas': npers})
                st.rerun()
        for g in st.session_state['grupos_multiples']: st.write(f"✔️ {g['nombre']}")

    # --- REPORTE EXCEL (EL DIAMANTE FINAL) ---
    if st.sidebar.button("📊 GENERAR REPORTE"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            wb = writer.book
            f_tit = wb.add_format({'bold':True, 'bg_color':'#2E5077', 'font_color':'white', 'border':1})
            f_bold = wb.add_format({'bold':True, 'border':1})
            f_sig = wb.add_format({'bg_color':'#C6EFCE', 'font_color':'#006100', 'bold':True, 'border':1})

            # UNIVARIADO
            sh1 = wb.add_worksheet('UNIVARIADO'); r_u = 1
            if not dn.empty: 
                res.to_excel(writer, sheet_name='UNIVARIADO', startrow=r_u); r_u += len(res)+3
            for c in df.select_dtypes(exclude=[np.number]).columns:
                sh1.write(r_u, 0, c, f_bold)
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Cat', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1)
                f.loc[len(f)] = ['TOTAL', f['N'].sum(), 100.0] # TOTALES
                f.to_excel(writer, sheet_name='UNIVARIADO', startrow=r_u+1, index=False); r_u += len(f)+3

            # BIVARIADOS
            sh_b1 = wb.add_worksheet('BIVARIADO'); sh_b2 = wb.add_worksheet('BIVARIADO 2')
            r_b1, r_b2 = 1, 1
            if v_cols:
                for vc in v_cols:
                    for vf in [c for c in df.columns if c not in v_cols]:
                        en, ef = pd.api.types.is_numeric_dtype(df[vc]), pd.api.types.is_numeric_dtype(df[vf])
                        if not en and not ef:
                            # CUALI-CUALI (N y %)
                            sh_b1.write(r_b1, 0, f"{vf} vs {vc}", f_bold)
                            ct_abs = pd.crosstab(df[vf], df[vc], margins=True, margins_name="TOTAL")
                            ct_abs.to_excel(writer, sheet_name='BIVARIADO', startrow=r_b1+1)
                            sigs = realizar_test_proporciones(ct_abs); r_b1 += len(ct_abs)+3
                            ct_per = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).round(1)
                            ct_per.loc['TOTAL'] = ["100.0%" for _ in ct_per.columns]
                            ct_per.to_excel(writer, sheet_name='BIVARIADO', startrow=r_b1+1)
                            # Celdas verdes
                            f_idx, c_idx = ct_per.index.tolist(), ct_per.columns.tolist()
                            for fs, cs in sigs:
                                try: sh_b1.write(f_idx.index(fs)+r_b1+2, c_idx.index(cs)+1, ct_per.loc[fs,cs], f_sig)
                                except: pass
                            r_b1 += len(ct_per)+5
                        elif (en != ef):
                            # CUANTI-CUALI (Medias)
                            v_n, v_c = (vc, vf) if en else (vf, vc)
                            sh_b2.write(r_b2, 0, f"Medias de {v_n} por {v_c}", f_bold)
                            rb = df.groupby(v_c)[v_n].agg(['count','mean','std']).round(2)
                            rb.to_excel(writer, sheet_name='BIVARIADO 2', startrow=r_b2+1)
                            sigs_m = realizar_test_medias(df, v_n, v_c)
                            f_idx = rb.index.tolist()
                            for sc in sigs_m:
                                try: sh_b2.write(f_idx.index(sc)+r_b2+2, 2, rb.loc[sc, 'mean'], f_sig)
                                except: pass
                            r_b2 += len(rb)+5

            # MULTIPLE
            sh4 = wb.add_worksheet('MÚLTIPLE'); r_m = 1
            for g in st.session_state['grupos_multiples']:
                sh4.write(r_m, 0, g['nombre'], f_bold)
                gt = g['tabla'].copy()
                gt.loc['TOTAL'] = [gt['N'].sum(), f"{gt['% Casos'].sum()}%", "100.0%"]
                gt.to_excel(writer, sheet_name='MÚLTIPLE', startrow=r_m+1); r_m += len(gt)+6

        st.sidebar.download_button("⬇️ DESCARGAR REPORTE", out.getvalue(), "Reporte_Final.xlsx")
else: st.info("Sube tu archivo.")
