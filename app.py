import streamlit as st
import pandas as pd
import os
import streamlit.components.v1 as components

# ==========================================
# 1. Configuração da Página e Cache
# ==========================================
st.set_page_config(page_title="Dashboard Analítico - Metas", layout="wide", initial_sidebar_state="collapsed")

@st.cache_data
def carregar_dados():
    base_path = "data"
    
    # 1. Ingestão Faturamento e Dimensões
    df_fat = pd.read_excel(os.path.join(base_path, "faturamento_realizado.xlsx"))
    df_meta = pd.read_excel(os.path.join(base_path, "meta_faturamento.xlsx"))
    df_rca = pd.read_excel(os.path.join(base_path, "dim_rca.xlsx"))
    df_filial = pd.read_excel(os.path.join(base_path, "dim_filial.xlsx"))
    df_supervisor = pd.read_excel(os.path.join(base_path, "dim_supervisor.xlsx"))
    df_meta_televendas = pd.read_excel(os.path.join(base_path, "meta_faturamento_televendas.xlsx"))
    df_televendas = pd.read_excel(os.path.join(base_path, "dim_televendas.xlsx"))
    
    # 1.1 Ingestão Marcas Exclusivas
    df_marcas_meta = pd.read_csv(os.path.join(base_path, "marcas_meta.csv"), sep=';', decimal=',', encoding='utf-8-sig')
    df_marcas_realizado = pd.read_csv(os.path.join(base_path, "marcas_realizado.csv"), sep=';', decimal=',', encoding='utf-8-sig')
    
    # 2. Sanitização Universal
    dfs_todas = [df_fat, df_meta, df_rca, df_filial, df_supervisor, df_meta_televendas, df_televendas, df_marcas_meta, df_marcas_realizado]
    for df in dfs_todas:
        df.columns = [str(c).strip().lower() for c in df.columns]
        
    # 3. Padronização de Chaves
    if 'cod_telenvenda' in df_fat.columns:
        df_fat.rename(columns={'cod_telenvenda': 'cod_televenda'}, inplace=True)
    if 'cod_telenvenda' in df_marcas_realizado.columns:
        df_marcas_realizado.rename(columns={'cod_telenvenda': 'cod_televenda'}, inplace=True)
        
    # 3.1 Abstração de Métricas
    df_fat.rename(columns={'valor_venda_mes': 'valor_realizado'}, inplace=True)
    df_marcas_realizado.rename(columns={'valor_marcas_exclusivas': 'valor_realizado'}, inplace=True)
    
    if 'valor_meta_acumulado' in df_meta.columns:
        df_meta.rename(columns={'valor_meta_acumulado': 'valor_meta'}, inplace=True)
        
    df_meta_televendas.rename(columns={'cod_televendas': 'cod_televenda', 'valor_mea_televendas': 'valor_meta'}, inplace=True)
    df_marcas_meta.rename(columns={'valor_meta_exclusivas': 'valor_meta'}, inplace=True)
    
    # ==========================================
    # 🛡️ DATA QUALITY & TYPE CASTING
    # ==========================================
    # 4.1 Blindagem Numérica
    def garantir_numerico(df, coluna):
        if coluna in df.columns:
            if df[coluna].dtype == 'object':
                df[coluna] = df[coluna].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[coluna] = pd.to_numeric(df[coluna], errors='coerce').fillna(0)

    for df_temp in [df_fat, df_marcas_realizado]:
        garantir_numerico(df_temp, 'valor_realizado')
        
    for df_temp in [df_meta, df_meta_televendas, df_marcas_meta]:
        garantir_numerico(df_temp, 'valor_meta')

    # 4.2 Blindagem de Strings
    for df_temp in [df_fat, df_marcas_realizado]:
        if 'origempedido' in df_temp.columns:
            df_temp['origempedido'] = df_temp['origempedido'].astype(str).str.strip().str.upper()

    def sanitizar_chave(df, coluna):
        if coluna in df.columns:
            df[coluna] = df[coluna].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

    for df_temp in dfs_todas:
        sanitizar_chave(df_temp, 'cod_rca')
        sanitizar_chave(df_temp, 'cod_televenda')
        sanitizar_chave(df_temp, 'cod_supervisor') # Garantia de cruzamento para os supervisores

    # 5. Transformação Temporal Adaptativa
    dicionario_tabelas = {
        "Faturamento": df_fat, "Meta RCA": df_meta, "Meta Televendas": df_meta_televendas,
        "Marcas Realizado": df_marcas_realizado, "Marcas Meta": df_marcas_meta
    }
    
    for nome, df_temp in dicionario_tabelas.items():
        if 'data' not in df_temp.columns:
            st.error(f"🚨 **Erro de Estrutura:** A coluna 'data' não foi encontrada na tabela de {nome}.")
            st.stop()
            
        if df_temp['data'].astype(str).str.contains('/').any():
            df_temp['data'] = pd.to_datetime(df_temp['data'], dayfirst=True, errors='coerce').dt.to_period('M')
        else:
            df_temp['data'] = pd.to_datetime(df_temp['data'], errors='coerce').dt.to_period('M')
    
    return df_fat, df_meta, df_rca, df_filial, df_supervisor, df_meta_televendas, df_televendas, df_marcas_meta, df_marcas_realizado

# ==========================================
# 2. Motor de Regras de Negócio (ETL)
# ==========================================
def processar_kpis(df_fato_base, df_meta_base, df_dim_atual, visao):
    if visao == "RCA":
        origens_validas = ['FORÇA DE VENDAS', 'OPERADOR LOGÍSTICO', 'E-COMMERCE', 'PEDIDO ELETRÔNICO', 'TELEMARKETING']
        chave = 'cod_rca'
        nome_col = 'nm_rca'
    else:
        origens_validas = ['TELEMARKETING']
        chave = 'cod_televenda'
        nome_col = 'nm_televenda'

    df_fato_seguro = df_fato_base.copy()
    
    if 'origempedido' in df_fato_seguro.columns:
        df_fato_seguro['origempedido'] = df_fato_seguro['origempedido'].replace(['NAN', 'nan', ''], None)
        
        if visao == "TELEVENDAS" and chave in df_fato_seguro.columns:
            df_fato_seguro.loc[df_fato_seguro[chave].astype(str).str.replace(r'\.0$', '', regex=True) != 'nan', 'origempedido'] = 'TELEMARKETING'
        elif visao == "RCA":
            df_fato_seguro['origempedido'] = df_fato_seguro['origempedido'].fillna('FORÇA DE VENDAS')
            
        fat_filtrado = df_fato_seguro[df_fato_seguro['origempedido'].isin(origens_validas)].copy()
    else:
        fat_filtrado = df_fato_seguro.copy()

    df_meta_atual = df_meta_base.copy()
    df_dim_atual = df_dim_atual.copy()
    
    if chave in fat_filtrado.columns:
        fat_filtrado[chave] = fat_filtrado[chave].astype(str).str.replace(r'\.0$', '', regex=True)
    else:
        fat_filtrado[chave] = 'SEM_CHAVE'
        
    if chave not in df_meta_atual.columns:
        df_meta_atual[chave] = 'SEM_META'
    else:
        df_meta_atual[chave] = df_meta_atual[chave].astype(str).str.replace(r'\.0$', '', regex=True)
        
    df_dim_atual[chave] = df_dim_atual[chave].astype(str).str.replace(r'\.0$', '', regex=True)

    fat_agg = fat_filtrado.groupby([chave, 'data'])['valor_realizado'].sum().reset_index()
    meta_agg = df_meta_atual.groupby([chave, 'data'])['valor_meta'].sum().reset_index()

    #Diagnóstico ###################################################################################################
    with st.expander(f"🛠️ AUTO-DIAGNÓSTICO: (Visão: {visao})", expanded=False):
        if df_fato_base.empty: st.error("❌ ERRO 0: Filtro de Mês vazio.")
        elif fat_filtrado.empty: st.error("❌ ERRO 1: Origem/Filtro não bateu.")
        else:
            st.success("✅ Diagnóstico estrutural OK. Dados em processamento.")

    df_kpi = pd.merge(meta_agg, fat_agg, on=[chave, 'data'], how='left')
    df_kpi['valor_realizado'] = df_kpi['valor_realizado'].fillna(0)
    
    df_kpi = df_kpi[df_kpi['valor_meta'] > 0]
    df_kpi = pd.merge(df_kpi, df_dim_atual, on=chave, how='inner')
    
    df_kpi['atingimento'] = df_kpi.apply(
        lambda row: row['valor_realizado'] / row['valor_meta'] if row['valor_meta'] > 0 else 0, 
        axis=1
    )
    
    df_kpi['nome_entidade'] = df_kpi[nome_col]
    df_kpi['filial_kpi'] = df_kpi['cod_filial'] if visao == "RCA" else df_kpi['filial']
    df_kpi = df_kpi.sort_values(by=['nome_entidade', 'data'])
    
    return df_kpi

# ==========================================
# 3. Motores de Renderização HTML/CSS
# ==========================================
def formata_br(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def obter_cores_kpi(ating):
    if ating >= 1: return "var(--neon-green)", "text-success", "🟩"
    elif ating >= 0.8: return "var(--neon-blue)", "text-warning", "🟦"
    else: return "var(--neon-pink)", "text-danger", "🟪"

def gerar_html_resumo(df_acumulado):
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        :root { --bg-card: #161925; --text-main: #f8fafc; --text-muted: #94a3b8; --neon-green: #34d399; --neon-blue: #60a5fa; --neon-pink: #f472b6; }
        body { font-family: 'Inter', system-ui, sans-serif; margin: 0; padding: 10px; background: transparent; }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px; width: 100%; }
        .kpi-card { background-color: var(--bg-card); border-radius: 12px; padding: 24px; border: 1px solid rgba(255, 255, 255, 0.05); display: flex; flex-direction: column; align-items: center; text-align: center; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.4); transition: transform 0.2s; }
        .kpi-card:hover { transform: translateY(-4px); border-color: rgba(255,255,255,0.15); }
        .kpi-title { color: var(--text-main); font-size: 15px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 16px; }
        .kpi-value { color: var(--text-main); font-size: 36px; font-weight: 800; margin-bottom: 4px; }
        .kpi-sub { color: var(--text-muted); font-size: 13px; font-weight: 500; margin-bottom: 4px; }
        .divider { width: 100%; border-top: 1px solid rgba(255,255,255,0.08); margin: 16px 0; }
        .text-success { color: var(--neon-green); } .text-warning { color: var(--neon-blue); } .text-danger { color: var(--neon-pink); }
    </style>
    """
    html = f"{css}<div class='kpi-grid'>"
    
    # 1. Pré-Agregação de Métricas por Filial
    lista_filiais = []
    for filial, group in df_acumulado.groupby('filial_kpi'):
        try: num_filial = int(float(filial))
        except ValueError: num_filial = str(filial).replace('.0', '')
            
        total_entidades = len(group)
        na_meta = len(group[group['atingimento'] >= 1.0])
        pct_na_meta = (na_meta / total_entidades) if total_entidades > 0 else 0
        
        meta_global = group['meta_total'].sum()
        fat_global = group['fat_total'].sum()
        ating_global = fat_global / meta_global if meta_global > 0 else 0
        
        lista_filiais.append({
            'num_filial': num_filial,
            'total_entidades': total_entidades,
            'na_meta': na_meta,
            'pct_na_meta': pct_na_meta,
            'meta_global': meta_global,
            'fat_global': fat_global,
            'ating_global': ating_global
        })
        
    # 2. Conversão e Ordenação (Ranking por Volume de Entidades na Meta)
    df_resumo = pd.DataFrame(lista_filiais)
    if not df_resumo.empty:
        df_resumo = df_resumo.sort_values(by=['pct_na_meta', 'ating_global'], ascending=[False, False])
        
    # 3. Motor de Renderização HTML
    for _, row in df_resumo.iterrows():
        _, text_class, icone = obter_cores_kpi(row['ating_global'])
        
        # Sanitização forçada: corta os dois últimos caracteres se terminar em '.0'
        filial_str = str(row['num_filial'])
        if filial_str.endswith('.0'):
            filial_str = filial_str[:-2]

        na_meta_str = str(row['na_meta'])
        if na_meta_str.endswith('.0'):
            na_meta_str = na_meta_str[:-2]

        total_entidades_str = str(row['total_entidades'])
        if total_entidades_str.endswith('.0'):
            total_entidades_str = total_entidades_str[:-2]
            
        html += f"""
        <div class='kpi-card'>
            <div class='kpi-title'>🏢 Filial {filial_str}</div>
            <div class='kpi-value'>{row['pct_na_meta']:.0%}</div>
            <div class='kpi-sub'><strong>{na_meta_str}</strong> de {total_entidades_str} atingiram >= 100%</div>
            <div class='divider'></div>
            <div class='kpi-sub' style='margin-bottom: 8px;'>Desempenho Financeiro</div>
            <div class='kpi-value {text_class}' style='font-size: 22px; margin-bottom: 8px;'>{icone} {row['ating_global']:.0%}</div>
            <div class='kpi-sub'>Meta: <strong>R$ {formata_br(row['meta_global'])}</strong></div>
            <div class='kpi-sub'>Real: <strong>R$ {formata_br(row['fat_global'])}</strong></div>
        </div>
        """
    html += "</div>"
    return html

def gerar_html_matriz(df):
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        :root { --bg-card: #161925; --bg-track: #0d0f16; --text-main: #f8fafc; --text-muted: #94a3b8; --neon-green: linear-gradient(90deg, #10b981, #34d399); --neon-blue: linear-gradient(90deg, #2563eb, #60a5fa); --neon-pink: linear-gradient(90deg, #e11d48, #f472b6); }
        body { font-family: 'Inter', system-ui, sans-serif; margin: 0; padding: 10px; background: transparent; }
        .dashboard-container { display: flex; flex-direction: column; gap: 24px; width: 100%; }
        .rca-card { background-color: var(--bg-card); border-radius: 12px; padding: 24px; border: 1px solid rgba(255, 255, 255, 0.05); }
        .rca-title { color: var(--text-main); font-size: 16px; font-weight: 700; margin-bottom: 24px; }
        .mes-row { margin-bottom: 20px; } .mes-row:last-child { margin-bottom: 0; }
        .mes-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .mes-name { font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .text-success { color: #34d399; } .text-warning { color: #60a5fa; } .text-danger { color: #f472b6; }
        .mes-stats { color: var(--text-muted); font-size: 12px; font-weight: 500; }
        .highlight-val { color: var(--text-main); font-weight: 600; }
        .barra-bg { width: 100%; height: 8px; background-color: var(--bg-track); border-radius: 8px; overflow: hidden; }
        .barra-fill { height: 100%; border-radius: 8px; animation: slideIn 1.5s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        @keyframes slideIn { from { width: 0%; } to { width: var(--alvo); } }
    </style>
    """
    html = f"{css}<div class='dashboard-container'>"
    for entidade, group in df.groupby('nome_entidade'):
        html += f"<div class='rca-card'><div class='rca-title'>{entidade}</div>"
        for _, row in group.iterrows():
            mes_str = str(row['data'])
            meta, fat, ating = row['valor_meta'], row['valor_realizado'], row['atingimento']
            largura = min(ating * 100, 100)
            gradiente, text_class, icone = obter_cores_kpi(ating)
            
            html += f"""
            <div class='mes-row'>
                <div class='mes-header'>
                    <div class='mes-name {text_class}'>{icone} {mes_str}</div>
                    <div class='mes-stats'>
                        Meta: <span class='highlight-val'>R$ {formata_br(meta)}</span> &nbsp;|&nbsp; 
                        Faturado: <span class='highlight-val'>R$ {formata_br(fat)}</span> &nbsp;|&nbsp; 
                        <span class='{text_class}'>{ating:.0%}</span>
                    </div>
                </div>
                <div class='barra-bg'><div class='barra-fill' style='background: {gradiente}; --alvo: {largura:.1f}%;'></div></div>
            </div>
            """
        html += "</div>"
    html += "</div>"
    return html

def gerar_html_ranking(df):
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        :root { --bg-card: #161925; --bg-track: #0d0f16; --text-main: #f8fafc; --text-muted: #94a3b8; --neon-green: linear-gradient(90deg, #10b981, #34d399); --neon-blue: linear-gradient(90deg, #2563eb, #60a5fa); --neon-pink: linear-gradient(90deg, #e11d48, #f472b6); }
        body { font-family: 'Inter', system-ui, sans-serif; margin: 0; padding: 10px; background: transparent; }
        .ranking-container { display: flex; flex-direction: column; gap: 12px; width: 100%; }
        .rank-card { display: flex; align-items: center; background-color: var(--bg-card); border-radius: 12px; padding: 16px 20px; border: 1px solid rgba(255, 255, 255, 0.05); transition: transform 0.2s; }
        .rank-card:hover { transform: translateX(5px); border-color: rgba(255,255,255,0.15); }
        .rank-pos { font-size: 24px; font-weight: 700; width: 60px; text-align: center; color: var(--text-main); }
        .rank-info { flex: 1; display: flex; flex-direction: column; gap: 6px; margin-left: 12px; }
        .rank-name { font-size: 15px; font-weight: 700; color: var(--text-main); }
        .rank-stats { font-size: 12px; font-weight: 500; color: var(--text-muted); }
        .rank-stats span { color: var(--text-main); font-weight: 600; }
        .text-success { color: #34d399; } .text-warning { color: #60a5fa; } .text-danger { color: #f472b6; }
        .barra-bg { width: 100%; height: 6px; background-color: var(--bg-track); border-radius: 8px; overflow: hidden; margin-top: 2px; }
        .barra-fill { height: 100%; border-radius: 8px; animation: slideIn 1.5s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        .rank-pct { font-size: 18px; font-weight: 700; width: 100px; text-align: right; }
        @keyframes slideIn { from { width: 0%; } to { width: var(--alvo); } }
    </style>
    """
    html = f"{css}<div class='ranking-container'>"
    
    for idx, row in df.iterrows():
        entidade, meta, fat, ating = row['nome_entidade'], row['meta_total'], row['fat_total'], row['atingimento']
        rank = idx + 1
        
        if rank == 1: pos_visual = "🥇"
        elif rank == 2: pos_visual = "🥈"
        elif rank == 3: pos_visual = "🥉"
        else: pos_visual = f"{rank}º"

        largura = min(ating * 100, 100)
        gradiente, text_class, _ = obter_cores_kpi(ating)
        
        html += f"""
        <div class='rank-card'>
            <div class='rank-pos'>{pos_visual}</div>
            <div class='rank-info'>
                <div class='rank-name'>{entidade}</div>
                <div class='rank-stats'>Meta: <span>R$ {formata_br(meta)}</span> &nbsp;|&nbsp; Faturado: <span>R$ {formata_br(fat)}</span></div>
                <div class='barra-bg'><div class='barra-fill' style='background: {gradiente}; --alvo: {largura:.1f}%;'></div></div>
            </div>
            <div class='rank-pct {text_class}'>{ating:.0%}</div>
        </div>
        """
    html += "</div>"
    return html

# ==========================================
# 4. Orquestração da Aplicação (UI/UX)
# ==========================================
def main():
    if 'visao_ativa' not in st.session_state:
        st.session_state.visao_ativa = "RCA"
    if 'indicador_ativo' not in st.session_state:
        st.session_state.indicador_ativo = "FATURAMENTO"

    st.title("Dashboard Analítico: Acompanhamento de Metas")
    
    df_fat, df_meta, df_rca, df_filial, df_supervisor, df_meta_tv, df_televendas, df_marcas_meta, df_marcas_realizado = carregar_dados()
    
    # ------------------ TOP BAR: SELEÇÃO DE INDICADOR ------------------
    st.markdown("### 🎯 Seleção de Indicador")
    col_ind1, col_ind2, _ = st.columns([1, 1, 4])
    
    with col_ind1:
        if st.button("💰 Faturamento Geral", use_container_width=True, type="primary" if st.session_state.indicador_ativo == "FATURAMENTO" else "secondary"):
            st.session_state.indicador_ativo = "FATURAMENTO"
            st.rerun()
    with col_ind2:
        if st.button("🏷️ Marcas Exclusivas", use_container_width=True, type="primary" if st.session_state.indicador_ativo == "MARCAS" else "secondary"):
            st.session_state.indicador_ativo = "MARCAS"
            st.rerun()
            
    # ------------------ TOP BAR: SELEÇÃO DE VISÃO ------------------
    st.markdown("### 📊 Visão Hierárquica")
    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
    
    with col_btn1:
        if st.button("💼 Visão RCA", use_container_width=True, type="primary" if st.session_state.visao_ativa == "RCA" else "secondary"):
            st.session_state.visao_ativa = "RCA"
            st.rerun()
            
    with col_btn2:
        if st.button("🎧 Visão Televendas", use_container_width=True, type="primary" if st.session_state.visao_ativa == "TELEVENDAS" else "secondary"):
            st.session_state.visao_ativa = "TELEVENDAS"
            st.rerun()
            
    st.markdown("---")
    
    visao = st.session_state.visao_ativa
    indicador = st.session_state.indicador_ativo
    
    if indicador == "FATURAMENTO":
        df_fato_ativo = df_fat
        df_meta_base = df_meta if visao == "RCA" else df_meta_tv
    else:
        df_fato_ativo = df_marcas_realizado
        df_meta_base = df_marcas_meta  
    
    # ------------------ FILTROS GLOBAIS ------------------
    st.markdown("### 🔍 Filtros Analíticos")
    
    lista_filiais = sorted(df_filial['codfilial'].dropna().astype(int).unique().tolist())
    lista_meses = sorted(list(set(df_meta_base['data'].astype(str).unique()) | set(df_fato_ativo['data'].astype(str).unique())))

    if visao == "RCA":
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1: filiais_selecionadas = st.multiselect("📌 Filial (Código)", lista_filiais)
        with col_f2: meses_selecionados = st.multiselect("📅 Mês", lista_meses)
        with col_f3: sups_selecionados = st.multiselect("👥 Supervisor", sorted(df_supervisor['nm_supervisor'].dropna().unique().tolist()))
        with col_f4: rcas_selecionados = st.multiselect("💼 RCA", sorted(df_rca['nm_rca'].dropna().unique().tolist()))
            
        df_dim_filtrada = df_rca.copy()
        
        if filiais_selecionadas: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['cod_filial'].isin(filiais_selecionadas)]
        if sups_selecionados: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['cod_supervisor'].isin(df_supervisor[df_supervisor['nm_supervisor'].isin(sups_selecionados)]['cod_supervisor'].tolist())]
        if rcas_selecionados: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['nm_rca'].isin(rcas_selecionados)]
        df_meta_atual = df_meta_base.copy()
        
    else: 
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: filiais_selecionadas = st.multiselect("📌 Filial (Código)", lista_filiais)
        with col_f2: meses_selecionados = st.multiselect("📅 Mês", lista_meses)
        with col_f3: tvs_selecionados = st.multiselect("🎧 Operador de Televendas", sorted(df_televendas['nm_televenda'].dropna().unique().tolist()))
            
        df_dim_filtrada = df_televendas.copy()
        
        if filiais_selecionadas: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['filial'].isin(filiais_selecionadas)]
        if tvs_selecionados: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['nm_televenda'].isin(tvs_selecionados)]
        df_meta_atual = df_meta_base.copy()

    df_fato_filtrado = df_fato_ativo.copy()
    if meses_selecionados:
        df_fato_filtrado = df_fato_filtrado[df_fato_filtrado['data'].astype(str).isin(meses_selecionados)]
        df_meta_atual = df_meta_atual[df_meta_atual['data'].astype(str).isin(meses_selecionados)]

    st.markdown("---")

    # ------------------ COMPUTAÇÃO & NAVEGAÇÃO ------------------
    with st.spinner(f"Processando modelo de {indicador} para a visão {visao}..."):
        df_kpi = processar_kpis(df_fato_filtrado, df_meta_atual, df_dim_filtrada, visao)
    
    if df_kpi.empty:
        st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados ou nenhuma meta cadastrada neste contexto.")
    else:
        # Acumulado padrão por Entidade (RCA ou Operador)
        df_acumulado = df_kpi.groupby(['nome_entidade', 'filial_kpi']).agg(
            meta_total=('valor_meta', 'sum'),
            fat_total=('valor_realizado', 'sum')
        ).reset_index()
        
        df_acumulado['atingimento'] = df_acumulado.apply(
            lambda row: row['fat_total'] / row['meta_total'] if row['meta_total'] > 0 else 0, axis=1
        )
        df_acumulado = df_acumulado.sort_values(by='atingimento', ascending=False).reset_index(drop=True)

        # Geração Dinâmica das Abas (Supervisor só aparece na visão RCA)
        if visao == "RCA":
            # 1. Traz o nome do supervisor para a tabela base cruzando com a dim_supervisor
            df_kpi_sup = pd.merge(df_kpi, df_supervisor[['cod_supervisor', 'nm_supervisor']], on='cod_supervisor', how='left')
            df_kpi_sup['nm_supervisor'] = df_kpi_sup['nm_supervisor'].fillna('SEM SUPERVISOR')
            
            # 2. Agrupa a performance inteira na figura do Supervisor
            df_sup = df_kpi_sup.groupby('nm_supervisor').agg(
                meta_total=('valor_meta', 'sum'),
                fat_total=('valor_realizado', 'sum')
            ).reset_index()
            
            df_sup['atingimento'] = df_sup.apply(
                lambda row: row['fat_total'] / row['meta_total'] if row['meta_total'] > 0 else 0, axis=1
            )
            df_sup = df_sup.sort_values(by='atingimento', ascending=False).reset_index(drop=True)
            
            # Renomeia para 'nome_entidade' para reutilizar o motor de HTML já existente
            df_sup.rename(columns={'nm_supervisor': 'nome_entidade'}, inplace=True)
            
            # Montagem das 4 Abas
            tab_resumo, tab_mensal, tab_ranking, tab_ranking_sup = st.tabs([
                "📈 Resumo Executivo (Filiais)", 
                "📅 Visão Mensal (Evolução)", 
                "🏆 Ranking Acumulado (RCA)",
                "👥 Ranking de Supervisores"
            ])
            
            with tab_ranking_sup:
                html_ranking_sup = gerar_html_ranking(df_sup)
                components.html(html_ranking_sup, height=950, scrolling=True)
                
        else:
            # Visão Televendas: Mantém as 3 Abas Originais
            tab_resumo, tab_mensal, tab_ranking = st.tabs([
                "📈 Resumo Executivo (Filiais)", 
                "📅 Visão Mensal (Evolução)", 
                "🏆 Ranking Acumulado"
            ])
        
        # Renderização das Abas Compartilhadas
        with tab_resumo:
            html_resumo = gerar_html_resumo(df_acumulado)
            components.html(html_resumo, height=800, scrolling=True)

        with tab_mensal:
            html_mensal = gerar_html_matriz(df_kpi)
            components.html(html_mensal, height=700, scrolling=True)
            
        with tab_ranking:
            html_ranking = gerar_html_ranking(df_acumulado)
            components.html(html_ranking, height=950, scrolling=True)

if __name__ == "__main__":
    main()