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
    .stDownloadButton>button { background-color: #008000; color: white; border-radius: 8px; font-weight: bold; width: 100%; }
    .main-title { font-size: 20px !important; font-weight: bold; color: #2E5077; margin-top: -20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES ESTADÍSTICAS ---
def calcular_sustituto(serie, metodo):
    metodo = metodo.upper()
    if metodo == "MEDIA": return serie.mean()
    elif metodo == "MEDIANA": return serie.median()
    elif metodo == "MODA":
        m = serie.mode()
        return m[0] if not m.empty else 0
    return np.nan

def realizar_test_proporciones(ct_abs):
    try:
        df_t = ct_abs.drop('TOTAL', axis=0, errors='ignore').drop('TOTAL', axis=1, errors='ignore')
        col_totals = df_t.sum()
        cols = df_t.columns.tolist()
        sigs = []
        for idx, row in df_test.iterrows():
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
        df_c = df[[v_num, v_cat]].dropna()
        grupos = df_c.groupby(v_cat)[v_num].mean().index.tolist()
        sigs = []
        for g1, g2 in itertools.combinations(grupos, 2):
            d1 = df_c[df_c[v_cat] == g1][v_num].values
            d2 = df_c[df_c[v_cat] == g2][v_num].values
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

def reset_all():
    st.session_state['df_master'] = None
    st.session_state['grupos_multiples'] = []
    st.session_state['limpieza_log'] = {}

# --- 4. INTERFAZ ---
archivo = st.sidebar.file_uploader("Sube tu Excel", type=["xlsx"], on_change=reset_all)

if archivo:
    # NUEVO: Selector de Hoja para evitar errores de carga
    xl = pd.ExcelFile(archivo)
    hoja_sel = st.sidebar.selectbox("Selecciona la pestaña con los datos:", xl.sheet_names)
    
    if st.session_state['df_master'] is None or st.sidebar.button("Cargar Hoja Seleccionada"):
        raw = pd.read_excel(archivo, sheet_name=hoja_sel)
        # Limpieza: quitar columnas/filas totalmente vacías (Unnamed)
        raw = raw.loc[:, ~raw.columns.str.contains('^Unnamed')]
        st.session_state['df_master'] = raw.dropna(axis=0, how='all')
        st.session_state['limpieza_log'] = {}
        st.rerun()

    df = st.session_state['df_master']
    st.markdown('<p class="main-title">🌟 QUO Processor Powered by Doble O y Elisa</p>', unsafe_allow_html=True)
    
    t1, t2, t3, t4 = st.tabs(["🛠️ Limpieza", "📉 Univariado", "📊 Bivariado", "🔢 R. Múltiple"])

    # --- TAB LIMPIEZA ---
    with t1:
        st.header("Limpieza de Datos")
        v_sel = st.selectbox("Variable a procesar", df.columns)
        s_num = pd.to_numeric(df[v_sel], errors='coerce')
        v_i, c_i = s_num.isna().sum(), (s_num == 0).sum()
        
        c1, c2, c3 = st.columns([1,1,2])
        c1.metric("Errores/Vacíos Iniciales", v_i)
        c2.metric("Valores CERO Iniciales", c_i)
        log = st.session_state['limpieza_log'].get(v_sel, {"txt": "Ninguna", "n": 0})
        with c3:
            st.write("**Estatus Final**")
            st.markdown(f"<p style='color:blue; font-size:20px; font-weight:bold;'>{log['txt']} | {log['n']} procesados</p>", unsafe_allow_html=True)

        met_v = st.selectbox("Tratar errores por:", ["Mantener", "MEDIA", "MEDIANA", "MODA", "0", "NAN"])
        met_c = "Mantener"
        if c_i > 0:
            if st.checkbox("Tratar ceros como no reales"):
                met_c = st.selectbox("Sustituir ceros por:", ["MEDIA", "MEDIANA", "MODA", "NAN"])

        if st.button("🚀 APLICAR TRANSFORMACIÓN"):
            new_s = s_num.copy()
            if met_v != "Mantener":
                val = calcular_sustituto(new_s, met_v)
                new_s = new_s.fillna(val if met_v != "NAN" else np.nan)
            if met_c != "Mantener":
                val_c = calcular_sustituto(new_s.replace(0, np.nan), met_c)
                new_s = new_s.replace(0, val_c)
            st.session_state['df_master'][v_sel] = new_s
            st.session_state['limpieza_log'][v_sel] = {"txt": f"{met_v}/{met_c}", "n": v_i + (c_i if met_c != "Mantener" else 0)}
            st.rerun()

    # --- TAB UNIVARIADO ---
    with t2:
        dn = df.select_dtypes(include=[np.number])
        if not dn.empty:
            st.subheader("📈 Estadísticos Numéricos")
            res_u = dn.agg(['count', 'min', 'max', 'mean', 'median', 'std']).T
            res_u['Moda'] = [dn[c].mode()[0] if not dn[c].mode().empty else np.nan for c in dn.columns]
            st.dataframe(res_u.round(2))
        st.subheader("📊 Frecuencias Cualitativas")
        for c in df.select_dtypes(exclude=[np.number]).columns:
            with st.expander(f"Variable: {c}"):
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Cat', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1); st.table(f)

    # --- TAB BIVARIADO ---
    with t3:
        v_cols = st.multiselect("Selecciona Variables para Columnas ( Cruces )", df.columns)

    # --- TAB MÚLTIPLE ---
    with t4:
        with st.form("fm"):
            nm = st.text_input("Nombre Conjunto"); cs = st.multiselect("Seleccionar Columnas", df.columns)
            if st.form_submit_button("✅ Registrar"):
                ds = df[cs]; npers = ds.notna().any(axis=1).sum(); mc = ds.stack().value_counts()
                t = pd.DataFrame({'N': mc, '% Casos': (mc/npers*100).round(1), '% Resp': (mc/mc.sum()*100).round(1)})
                st.session_state['grupos_multiples'].append({'nombre': nm, 'tabla': t})
                st.rerun()
        for g in st.session_state['grupos_multiples']: st.write(f"✔️ {g['nombre']}")

    # --- REPORTE EXCEL PRO ---
    st.sidebar.markdown("---")
    if st.sidebar.button("📊 GENERAR REPORTE EXCEL"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            wb = writer.book
            f_tit = wb.add_format({'bold':True, 'bg_color':'#2E5077', 'font_color':'white', 'border':1})
            f_bold = wb.add_format({'bold':True, 'border':1})
            f_sig = wb.add_format({'bg_color':'#C6EFCE', 'font_color':'#006100', 'bold':True, 'border':1})

            sh1 = wb.add_worksheet('UNIVARIADO'); r_u = 1
            if not dn.empty: res_u.to_excel(writer, sheet_name='UNIVARIADO', startrow=r_u); r_u += len(res_u)+4
            for c in df.select_dtypes(exclude=[np.number]).columns:
                sh1.write(r_u, 0, f"Variable: {c}", f_bold)
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Cat', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1)
                f.loc[len(f)] = ['TOTAL', f['N'].sum(), 100.0]
                f.to_excel(writer, sheet_name='UNIVARIADO', startrow=r_u+1, index=False); r_u += len(f)+3

            sh_b1 = wb.add_worksheet('BIVARIADO'); sh_b2 = wb.add_worksheet('BIVARIADO 2')
            r_b1, r_b2 = 1, 1
            if v_cols:
                for vc in v_cols:
                    for vf in [c for c in df.columns if c not in v_cols]:
                        en, ef = pd.api.types.is_numeric_dtype(df[vc]), pd.api.types.is_numeric_dtype(df[vf])
                        if not en and not ef:
                            sh_b1.write(r_b1, 0, f"{vf} vs {vc}", f_bold)
                            ct_abs = pd.crosstab(df[vf], df[vc], margins=True, margins_name="TOTAL")
                            ct_abs.to_excel(writer, sheet_name='BIVARIADO', startrow=r_b1+1)
                            sigs = realizar_test_proporciones(ct_abs); r_b1 += len(ct_abs)+3
                            ct_per = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).round(1)
                            ct_per.loc['TOTAL'] = ["100.0%" for _ in ct_per.columns]
                            ct_per.to_excel(writer, sheet_name='BIVARIADO', startrow=r_b1+1)
                            fi, ci = ct_per.index.tolist(), ct_per.columns.tolist()
                            for fs, cs in sigs:
                                try: sh_b1.write(fi.index(fs)+r_b1+2, ci.index(cs)+1, ct_per.loc[fs,cs], f_sig)
                                except: pass
                            r_b1 += len(ct_per)+5
                        elif en != ef:
                            vn, vca = (vc, vf) if en else (vf, vc)
                            sh_b2.write(r_b2, 0, f"Medias de {vn} por {vca}", f_bold)
                            rb = df.groupby(vca)[vn].agg(['count','mean','std']).round(2)
                            rb.to_excel(writer, sheet_name='BIVARIADO 2', startrow=r_b2+1)
                            sigs_m = realizar_test_medias(df, vn, vca)
                            fi = rb.index.tolist()
                            for sc in sigs_m:
                                try: sh_b2.write(fi.index(sc)+r_b2+2, 2, rb.loc[sc, 'mean'], f_sig)
                                except: pass
                            r_b2 += len(rb)+5

            sh4 = wb.add_worksheet('MÚLTIPLE'); r_m = 1
            for g in st.session_state['grupos_multiples']:
                sh4.write(r_m, 0, g['nombre'], f_bold)
                gt = g['tabla'].copy()
                gt.loc['TOTAL'] = [gt['N'].sum(), f"{gt['% Casos'].sum()}%", "100.0%"]
                gt.to_excel(writer, sheet_name='MÚLTIPLE', startrow=r_m+1); r_m += len(gt)+6

        st.sidebar.download_button("⬇️ DESCARGAR EXCEL FINAL", out.getvalue(), "Reporte_Final.xlsx")
else: st.info("Sube tu archivo para comenzar.")
