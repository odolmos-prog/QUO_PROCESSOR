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

# --- 2. FUNCIONES MOTORAS (LÓGICA ESTADÍSTICA BLINDADA) ---
def calcular_sustituto(serie, metodo):
    metodo = metodo.upper()
    # Calculamos sobre la serie limpia de NaNs
    s_clean = serie.dropna()
    if metodo == "MEDIA": return s_clean.mean()
    elif metodo == "MEDIANA": return s_clean.median()
    elif metodo == "MODA":
        m = s_clean.mode()
        return m[0] if not m.empty else 0
    return np.nan # Para 0 o NAN

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

# --- 3. GESTIÓN DE MEMORIA (CON LOG DETALLADO) ---
if 'df_master' not in st.session_state: st.session_state['df_master'] = None
if 'grupos_multiples' not in st.session_state: st.session_state['grupos_multiples'] = []
# Diccionario para rastrear el estatus detallado de limpieza por variable
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
    
    if st.session_state['df_master'] is None or st.sidebar.button("Cargar Hoja Seleccionada"):
        raw = pd.read_excel(archivo, sheet_name=hoja_sel)
        raw = raw.loc[:, ~raw.columns.str.contains('^Unnamed')]
        st.session_state['df_master'] = raw.dropna(axis=0, how='all')
        st.rerun()

    df = st.session_state['df_master']
    st.markdown('<p class="main-title">🌟 QUO Processor Powered by Doble O y Elisa</p>', unsafe_allow_html=True)
    
    tabs = st.tabs(["🛠️ Limpieza Sekuencial", "📉 Univariado", "📊 Bivariado", "🔢 R. Múltiple"])

    # --- 1. TAB LIMPIEZA (MOTOR SECUENCIAL RECUPERADO) ---
    with tabs[0]:
        v_sel = st.selectbox("Selecciona Variable", df.columns)
        
        # 1. Monitor Inicial Blindado
        s_num = pd.to_numeric(df[v_sel], errors='coerce')
        v_i, c_i = s_num.isna().sum(), (s_num == 0).sum()
        
        # Mostramos Monitores de Estado Actual
        log = st.session_state['limpieza_log'].get(v_sel, {"err": "Ninguna", "cero": "Ninguna", "total": 0})
        st.subheader("📊 Estatus de Transformación")
        c1, c2, c3 = st.columns([1,1,2])
        c1.metric("Errores/Vacíos", v_i)
        c2.metric("Valores CERO", c_i)
        
        # Monitor Final de Decisiones (Petición de Omar)
        resumen_decisiones = f"Err:{log['err']} | Ceros:{log['cero']}"
        with c3:
            st.write("**Decisiones Tomadas**")
            st.markdown(f"<h3 style='font-size: 20px; color: #2E5077; margin-top: -10px;'>{resumen_decisiones}</h3>", unsafe_allow_html=True)
            st.caption(f"✅ {log['total']} reg. procesados")

        st.markdown("---")
        
        # 2. Lógica del PASO 1 (Solo Errores)
        if v_i > 0:
            st.write(f"### PASO 1: Tratar los {v_i} errores/vacíos")
            metodo_v = st.selectbox(f"Sustituir errores por:", 
                                  ["Mantener", "MEDIA", "MEDIANA", "MODA", "0", "NAN"], key="web_err")
            
            if st.button(f"🚀 Aplicar Paso 1 a {v_sel}"):
                if metodo_v != "Mantener":
                    val = calcular_sustituto(s_num, metodo_v)
                    nuevo_s = s_num.fillna(val if metodo_v not in ["NAN", "0"] else 0.0 if metodo_v=="0" else np.nan)
                    
                    st.session_state['df_master'][v_sel] = nuevo_s
                    # Actualizamos log del Paso 1
                    current_log = st.session_state['limpieza_log'].get(v_sel, {"err": "Ninguna", "cero": "Ninguna", "total": 0})
                    current_log['err'] = metodo_v
                    current_log['total'] = v_i # Reseteamos total para este paso
                    st.session_state['limpieza_log'][v_sel] = current_log
                    
                    st.toast(f"¡Errores de {v_sel} limpiados!")
                    st.rerun()
        else:
            st.success("✔️ No se detectaron errores de texto o celdas vacías.")

        st.markdown("---")

        # 3. Lógica del PASO 2 (Solo Ceros)
        # Solo aparece si el Paso 1 se completó o no hay errores
        if c_i > 0:
            st.write(f"### PASO 2: Tratar los {c_i} valores en CERO")
            confirm_cero = st.radio("¿Son valores reales?", ["Sí (Mantener)", "No (Sustituir)"], horizontal=True, key="web_radio_cero")
            
            if confirm_cero == "No (Sustituir)":
                metodo_c = st.selectbox("Sustituir ceros por:", 
                                         ["MEDIA", "MEDIANA", "MODA", "NAN"], key="web_cero")
                
                if st.button(f"🚀 Aplicar Paso 2 a {v_sel}"):
                    # Para calcular, ignoramos los ceros actuales
                    base_calculo = s_num.replace(0, np.nan)
                    val_c = calcular_sustituto(base_calculo, metodo_c)
                    
                    # Reemplazamos ceros por el valor calculado
                    nuevo_s = s_num.replace(0, val_c)
                    
                    st.session_state['df_master'][v_sel] = nuevo_s
                    # Actualizamos log completo
                    current_log = st.session_state['limpieza_log'].get(v_sel, {"err": "Ninguna", "cero": "Ninguna", "total": 0})
                    current_log['cero'] = metodo_c
                    current_log['total'] = v_i + c_i # Sumamos total
                    st.session_state['limpieza_log'][v_sel] = current_log
                    
                    st.toast(f"¡Ceros de {v_sel} sustituidos!")
                    st.rerun()
        else:
            st.success("✔️ No se detectaron valores en cero.")

    # --- TAB 2: UNIVARIADO (CON PERCENTILES Y MODA ANTES QUE STD) ---
    with tabs[1]:
        dn = df.select_dtypes(include=[np.number])
        if not dn.empty:
            st.subheader("📈 Estadísticos Numéricos")
            # 1. Baseagg
            res_u = dn.agg(['count', 'min', 'max', 'mean', 'median', 'std']).T
            # 2. Moda y Percentiles
            res_u['Moda'] = [dn[c].mode()[0] if not dn[c].mode().empty else np.nan for c in dn.columns]
            res_u['P5'] = dn.quantile(0.05); resumen['P95'] = dn.quantile(0.95)
            # 3. REORDENAR (Media, Mediana, Moda, Std, P5, P95)
            res_u = res_u[['count', 'min', 'max', 'mean', 'median', 'Moda', 'std', 'P5', 'P95']]
            st.dataframe(res_u.round(2))
        
        st.subheader("📊 Frecuencias Cualitativas")
        for c in df.select_dtypes(exclude=[np.number]).columns:
            with st.expander(f"Variable: {c}"):
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Cat', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1); st.table(f)

    # --- TAB 3: BIVARIADO (CRUCES) ---
    with tabs[2]:
        v_cols = st.multiselect("Selecciona Variables Columnas (Cruces)", df.columns)

    # --- TAB 4: MÚLTIPLE (HASTA 5) ---
    with tabs[3]:
        if len(st.session_state['grupos_multiples']) < 5:
            with st.form("multiple_form"):
                nm = st.text_input("Nombre Conjunto"); cs = st.multiselect("Variables", df.columns)
                if st.form_submit_button("Añadir Conjunto"):
                    ds = df[cs]; npers = ds.notna().any(axis=1).sum(); mc = ds.stack().value_counts()
                    t = pd.DataFrame({'N': mc, '% Casos': (mc/npers*100).round(1), '% Resp': (mc/mc.sum()*100).round(1)})
                    st.session_state['grupos_multiples'].append({'nombre': nm, 'tabla': t})
                    st.rerun()
        else: st.warning("Límite de 5 conjuntos alcanzado.")
        
        for i, g in enumerate(st.session_state['grupos_multiples']):
            with st.expander(f"✔️ {g['nombre']}"):
                st.table(g['tabla'])
                if st.button(f"Eliminar {i}", key=f"del_{i}"):
                    st.session_state['grupos_multiples'].pop(i)
                    st.rerun()

    # --- REPORTE EXCEL (TODO TOTALES Y CELDAS VERDES) ---
    st.sidebar.markdown("---")
    if st.sidebar.button("📊 GENERAR REPORTE EXCEL"):
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            wb = writer.book
            f_bold = wb.add_format({'bold':True, 'border':1})
            f_sig = wb.add_format({'bg_color':'#C6EFCE', 'font_color':'#006100', 'bold':True, 'border':1})

            # UNIVARIADO (CON TOTALES)
            sh1 = wb.add_worksheet('UNIVARIADO'); r_u = 1
            if not dn.empty: res_u.to_excel(writer, sheet_name='UNIVARIADO', startrow=r_u); r_u += len(res_u)+4
            for c in df.select_dtypes(exclude=[np.number]).columns:
                sh1.write(r_u, 0, c, f_bold)
                f = df[c].value_counts(dropna=False).reset_index()
                f.columns = ['Cat', 'N']; f['%'] = (f['N']/f['N'].sum()*100).round(1)
                f.loc[len(f)] = ['TOTAL', f['N'].sum(), 100.0] # TOTALES
                f.to_excel(writer, sheet_name='UNIVARIADO', startrow=r_u+1, index=False); r_u += len(f)+3

            # BIVARIADOS (Z Y T CON CELDAS VERDES)
            sh_b1 = wb.add_worksheet('BIVARIADO'); sh_b2 = wb.add_worksheet('BIVARIADO_MEDIAS')
            r_b1, r_b2 = 1, 1
            if v_cols:
                for vc in v_cols:
                    for vf in [c for c in df.columns if c not in v_cols]:
                        en, ef = pd.api.types.is_numeric_dtype(df[vc]), pd.api.types.is_numeric_dtype(df[vf])
                        
                        # Z-TEST (Texto vs Texto)
                        if not en and not ef:
                            sh_b1.write(r_b1, 0, f"{vf} vs {vc}", f_bold)
                            ct_abs = pd.crosstab(df[vf], df[vc], margins=True, margins_name="TOTAL")
                            ct_abs.to_excel(writer, sheet_name='BIVARIADO', startrow=r_b1+1)
                            sigs = realizar_test_proporciones(ct_abs); r_b1 += len(ct_abs)+2
                            ct_per = (pd.crosstab(df[vf], df[vc], normalize='columns')*100).round(1)
                            ct_per.to_excel(writer, sheet_name='BIVARIADO', startrow=r_b1+1)
                            fi, ci = ct_per.index.tolist(), ct_per.columns.tolist()
                            for fs, cs in sigs:
                                try: sh_b1.write(fi.index(fs)+r_b1+2, ci.index(cs)+1, ct_per.loc[fs,cs], f_sig)
                                except: pass
                            r_b1 += len(ct_per)+4

                        # T-TEST (Número vs Texto)
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
                            r_b2 += len(rb)+4

            # MÚLTIPLES
            sh_m = wb.add_worksheet('MÚLTIPLE'); r_m = 1
            for g in st.session_state['grupos_multiples']:
                sh_m.write(r_m, 0, g['nombre'], f_bold)
                g['tabla'].to_excel(writer, sheet_name='MÚLTIPLE', startrow=r_m+1); r_m += len(g['tabla'])+4

        st.sidebar.download_button("⬇️ DESCARGAR REPORTE", out.getvalue(), "Reporte_QUO_Final.xlsx")

else: st.info("Sube tu archivo para comenzar.")
