import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest
import io
import itertools

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="QUO Processor by Doble O & Elisa", layout="wide")
st.markdown("""
    <style>
    .stButton>button { background-color: #2E5077; color: white; border-radius: 8px; font-weight: bold; }
    .stDownloadButton>button { background-color: #008000; color: white; border-radius: 8px; font-weight: bold; width: 100%; }
    .main-title { font-size: 20px !important; font-weight: bold; color: #2E5077; margin-top: -20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNCIONES MOTORAS ESTADÍSTICAS ---
def calcular_sustituto(serie, metodo):
    metodo = metodo.upper()
    s_clean = serie.dropna()
    if metodo == "MEDIA": return s_clean.mean()
    elif metodo == "MEDIANA": return s_clean.median()
    elif metodo == "MODA":
        m = s_clean.mode()
        return m[0] if not m.empty else 0
    return np.nan

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
                if np.any(nobs < 10) or np.any(counts == 0): continue 
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
            if len(d1) < 10 or len(d2) < 10: continue
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
    xl = pd.ExcelFile(archivo)
    hoja_sel = st.sidebar.selectbox("Selecciona la pestaña con los datos:", xl.sheet_names)
    
    if st.session_state['df_master'] is None or st.sidebar.button("Cargar/Refrescar Hoja"):
        raw = pd.read_excel(archivo, sheet_name=hoja_sel)
        raw = raw.loc[:, ~raw.columns.str.contains('^Unnamed')]
        st.session_state['df_master'] = raw.dropna(axis=0, how='all')
        st.rerun()

    df = st.session_state['df_master']
    st.markdown('<p class="main-title">🌟 QUO Processor by Doble O y Elisa</p>', unsafe_allow_html=True)
    tabs = st.tabs(["🛠️ Limpieza", "📉 Univariado", "📊 Bivariado", "🔢 R. Múltiple"])

    # --- TAB LIMPIEZA (FRONT RESTAURADO) ---
    with tabs[0]:
        st.header("Limpieza de Datos")
        v_sel = st.selectbox("Selecciona Variable", df.columns)
        s_num = pd.to_numeric(df[v_sel], errors='coerce')
        v_i, c_i = s_num.isna().sum(), (s_num == 0).sum()
        
        log = st.session_state['limpieza_log'].get(v_sel, {"err": "Ninguna", "cero": "Ninguna", "total": 0})
        st.subheader("📊 Estatus de Transformación")
        c1, c2, c3 = st.columns([1,1,2])
        c1.metric("Errores/Vacíos", v_i)
        c2.metric("Valores CERO", c_i)
        with c3:
            st.markdown(f"**Última Decisión:** Err: {log['err']} | Ceros: {log['cero']}")
            st.caption(f"✅ {log['total']} registros procesados en total")

        st.markdown("---")
        st.write("### Opciones de Limpieza")
        
        # Bloque de Errores
        col_err, col_zero = st.columns(2)
        with col_err:
            met_v = st.selectbox("Tratar errores/vacíos por:", ["Mantener", "MEDIA", "MEDIANA", "MODA", "0", "NAN"])
        
        # Bloque de Ceros
        with col_zero:
            limp_c = st.checkbox(f"Sustituir los {c_i} ceros")
            met_c = st.selectbox("Sustituir ceros por:", ["MEDIA", "MEDIANA", "MODA", "NAN"]) if limp_c else "Mantener"

        if st.button(f"🚀 EJECUTAR TRANSFORMACIÓN EN {v_sel}"):
            temp_s = s_num.copy()
            t_cambios = 0
            
            if met_v != "Mantener":
                val_v = calcular_sustituto(temp_s, met_v)
                temp_s = temp_s.fillna(val_v if met_v not in ["NAN", "0"] else 0.0 if met_v=="0" else np.nan)
                t_cambios += v_i
            
            if met_c != "Mantener":
                val_c = calcular_sustituto(temp_s.replace(0, np.nan), met_c)
                temp_s = temp_s.replace(0, val_c)
                t_cambios += c_i
            
            st.session_state['df_master'][v_sel] = temp_s
            st.session_state['limpieza_log'][v_sel] = {"err": met_v, "cero": met_c, "total": t_cambios}
            st.success("¡Variable procesada!")
            st.rerun()

    # --- TAB UNIVARIADO ---
    with tabs[1]:
        dn = df.select_dtypes(include=[np.number])
        if not dn.empty:
            res_u = dn.agg(['count', 'min', 'max', 'mean', 'median', 'std']).T
            res_u['Moda'] = [dn[c].mode()[0] if not dn[c].mode().empty else np.nan for c in dn.columns]
            res_u['P5'] = dn.quantile(0.05); res_u['P95'] = dn.quantile(0.95)
            st.dataframe(res_u[['count', 'min', 'max', 'mean', 'median', 'Moda', 'std', 'P5', 'P95']].round(2))
        for c in df.select_dtypes(exclude=[np.number]).columns:
            with st.expander(f"Variable: {c}"):
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Cat', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1); st.table(f)

    # --- TAB BIVARIADO ---
    with tabs[2]:
        v_cols = st.multiselect("Variables Columnas", df.columns)

    # --- TAB MÚLTIPLE ---
    with tabs[3]:
        with st.form("fm"):
            nm = st.text_input("Nombre"); cs = st.multiselect("Variables", df.columns)
            if st.form_submit_button("Añadir Conjunto"):
                ds = df[cs]; npers = ds.notna().any(axis=1).sum(); mc = ds.stack().value_counts()
                t = pd.DataFrame({'N': mc, '% Casos': (mc/npers*100).round(1), '% Resp': (mc/mc.sum()*100).round(1)})
                st.session_state['grupos_multiples'].append({'nombre': nm, 'tabla': t}); st.rerun()
        for i, g in enumerate(st.session_state['grupos_multiples']):
            with st.expander(f"✔️ {g['nombre']}"):
                st.table(g['tabla'])

    # --- REPORTE EXCEL (AJUSTES FINALES) ---
    st.sidebar.markdown("---")
    if st.sidebar.button("📊 GENERAR REPORTE FINAL"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            wb = writer.book
            f_bold = wb.add_format({'bold':True, 'border':1})
            f_sig = wb.add_format({'bg_color':'#C6EFCE', 'font_color':'#006100', 'bold':True, 'border':1})

            # 1. UNIVARIADO
            sh1 = wb.add_worksheet('UNIVARIADO'); r_u = 1
            if not dn.empty: res_u[['count', 'min', 'max', 'mean', 'median', 'Moda', 'std', 'P5', 'P95']].round(2).to_excel(writer, sheet_name='UNIVARIADO', startrow=r_u); r_u += len(res_u)+4
            for c in df.select_dtypes(exclude=[np.number]).columns:
                sh1.write(r_u, 0, c, f_bold)
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Cat', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1)
                f.loc[len(f)] = ['TOTAL', f['N'].sum(), 100.0]
                f.to_excel(writer, sheet_name='UNIVARIADO', startrow=r_u+1, index=False); r_u += len(f)+3

            # 2. BIVARIADOS
            sh_b1 = wb.add_worksheet('BIVARIADO'); sh_b2 = wb.add_worksheet('BIVARIADO_MEDIAS')
            r_b1, r_b2 = 1, 1
            if v_cols:
                for vc in v_cols:
                    for vf in [c for c in df.columns if c not in v_cols]:
                        en, ef = pd.api.types.is_numeric_dtype(df[vc]), pd.api.types.is_numeric_dtype(df[vf])
                        if not en and not ef:
                            sh_b1.write(r_b1, 0, f"{vf} vs {vc}", f_bold)
                            ct_abs = pd.crosstab(df[vf], df[vc], margins=True, margins_name="TOTAL")
                            ct_abs.to_excel(writer, sheet_name='BIVARIADO', startrow=r_b1+1)
                            sigs = realizar_test_proporciones(ct_abs); r_b1 += len(ct_abs)+2
                            ct_per = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).round(1)
                            ct_per.loc['TOTAL'] = [100.0 for _ in ct_per.columns] # TOTAL EN BIVARIADO
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
                            rb.to_excel(writer, sheet_name='BIVARIADO_MEDIAS', startrow=r_b2+1)
                            sigs_m = realizar_test_medias(df, vn, vca)
                            fi = rb.index.tolist()
                            for sc in sigs_m:
                                try: sh_b2.write(fi.index(sc)+r_b2+2, 2, rb.loc[sc, 'mean'], f_sig)
                                except: pass
                            r_b2 += len(rb)+5

            # 3. MÚLTIPLES
            sh_m = wb.add_worksheet('MÚLTIPLE'); r_m = 1
            for g in st.session_state['grupos_multiples']:
                sh_m.write(r_m, 0, g['nombre'], f_bold)
                gt = g['tabla'].copy()
                gt.loc['TOTAL'] = [gt['N'].sum(), f"{gt['% Casos'].sum().round(1)}%", "100.0%"] # TOTAL EN MÚLTIPLE
                gt.to_excel(writer, sheet_name='MÚLTIPLE', startrow=r_m+1); r_m += len(gt)+4

        st.sidebar.download_button("⬇️ DESCARGAR", out.getvalue(), "Reporte_QUO_Final.xlsx")
else: st.info("Sube tu archivo.")
