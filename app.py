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
    
    df_fat = pd.read_excel(os.path.join(base_path, "faturamento_realizado.xlsx"))
    df_meta = pd.read_excel(os.path.join(base_path, "meta_faturamento.xlsx"))
    df_rca = pd.read_excel(os.path.join(base_path, "dim_rca.xlsx"))
    df_filial = pd.read_excel(os.path.join(base_path, "dim_filial.xlsx"))
    df_supervisor = pd.read_excel(os.path.join(base_path, "dim_supervisor.xlsx"))
    df_meta_televendas = pd.read_excel(os.path.join(base_path, "meta_faturamento_televendas.xlsx"))
    df_televendas = pd.read_excel(os.path.join(base_path, "dim_televendas.xlsx"))
    
    for df in [df_fat, df_meta, df_rca, df_filial, df_supervisor, df_meta_televendas, df_televendas]:
        df.columns = [c.lower() for c in df.columns]
        
    if 'cod_telenvenda' in df_fat.columns:
        df_fat.rename(columns={'cod_telenvenda': 'cod_televenda'}, inplace=True)
        
    df_meta_televendas.rename(columns={
        'cod_televendas': 'cod_televenda',
        'valor_mea_televendas': 'valor_meta'
    }, inplace=True)
        
    df_fat['data'] = pd.to_datetime(df_fat['data']).dt.to_period('M')
    df_meta['data'] = pd.to_datetime(df_meta['data']).dt.to_period('M')
    df_meta_televendas['data'] = pd.to_datetime(df_meta_televendas['data']).dt.to_period('M')
    
    return df_fat, df_meta, df_rca, df_filial, df_supervisor, df_meta_televendas, df_televendas

# ==========================================
# 2. Motor de Regras de Negócio (ETL)
# ==========================================
def processar_kpis(df_fat, df_meta_atual, df_dim_atual, visao):
    if visao == "RCA":
        origens_validas = ['FORÇA DE VENDAS', 'OPERADOR LOGÍSTICO', 'E-COMMERCE', 'PEDIDO ELETRÔNICO']
        fat_filtrado = df_fat[df_fat['origempedido'].isin(origens_validas)]
        chave = 'cod_rca'
        nome_col = 'nm_rca'
    else:
        origens_validas = ['TELEMARKETING']
        fat_filtrado = df_fat[df_fat['origempedido'].isin(origens_validas)]
        chave = 'cod_televenda'
        nome_col = 'nm_televenda'

    fat_agg = fat_filtrado.groupby([chave, 'data'])['valor_venda_mes'].sum().reset_index()
    meta_agg = df_meta_atual.groupby([chave, 'data'])['valor_meta'].sum().reset_index()
    
    df_kpi = pd.merge(meta_agg, fat_agg, on=[chave, 'data'], how='left')
    df_kpi['valor_venda_mes'] = df_kpi['valor_venda_mes'].fillna(0)
    
    df_kpi = df_kpi[df_kpi['valor_meta'] > 0]
    df_kpi = pd.merge(df_kpi, df_dim_atual, on=chave, how='inner')
    
    df_kpi['atingimento'] = df_kpi.apply(
        lambda row: row['valor_venda_mes'] / row['valor_meta'] if row['valor_meta'] > 0 else 0, 
        axis=1
    )
    
    df_kpi['nome_entidade'] = df_kpi[nome_col]

    if visao == "RCA":
        df_kpi['filial_kpi'] = df_kpi['cod_filial']
    else:
        df_kpi['filial_kpi'] = df_kpi['filial']
        
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
        :root {
            --bg-card: #161925; --text-main: #f8fafc; --text-muted: #94a3b8;   
            --neon-green: #34d399; --neon-blue: #60a5fa; --neon-pink: #f472b6; 
        }
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
    

    df_ordenado = df_acumulado.sort_values(by='filial_kpi')
    
    for filial, group in df_ordenado.groupby('filial_kpi'):
        try:
            num_filial = int(filial)
        except ValueError:
            num_filial = filial
            
        total_entidades = len(group)
        na_meta = len(group[group['atingimento'] >= 1.0])
        pct_na_meta = (na_meta / total_entidades) if total_entidades > 0 else 0
        
        meta_global = group['meta_total'].sum()
        fat_global = group['fat_total'].sum()
        ating_global = fat_global / meta_global if meta_global > 0 else 0
        
        _, text_class, icone = obter_cores_kpi(ating_global)
        
        html += f"""
        <div class='kpi-card'>
            <div class='kpi-title'>🏢 Filial {num_filial}</div>
            <div class='kpi-value'>{pct_na_meta:.0%}</div>
            <div class='kpi-sub'><strong>{na_meta}</strong> de {total_entidades} atingiram >= 100%</div>
            
            <div class='divider'></div>
            
            <div class='kpi-sub' style='margin-bottom: 8px;'>Desempenho Financeiro</div>
            <div class='kpi-value {text_class}' style='font-size: 22px; margin-bottom: 8px;'>{icone} {ating_global:.0%}</div>
            <div class='kpi-sub'>Meta: <strong>R$ {formata_br(meta_global)}</strong></div>
            <div class='kpi-sub'>Real: <strong>R$ {formata_br(fat_global)}</strong></div>
        </div>
        """
        
    html += "</div>"
    return html

def gerar_html_matriz(df):
    css = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        :root {
            --bg-card: #161925; --bg-track: #0d0f16; --text-main: #f8fafc; --text-muted: #94a3b8;   
            --neon-green: linear-gradient(90deg, #10b981, #34d399); 
            --neon-blue:  linear-gradient(90deg, #2563eb, #60a5fa); 
            --neon-pink:  linear-gradient(90deg, #e11d48, #f472b6); 
        }
        body { font-family: 'Inter', system-ui, sans-serif; margin: 0; padding: 10px; background: transparent; }
        .dashboard-container { display: flex; flex-direction: column; gap: 24px; width: 100%; }
        .rca-card { background-color: var(--bg-card); border-radius: 12px; padding: 24px; border: 1px solid rgba(255, 255, 255, 0.05); }
        .rca-title { color: var(--text-main); font-size: 16px; font-weight: 700; margin-bottom: 24px; }
        .mes-row { margin-bottom: 20px; }
        .mes-row:last-child { margin-bottom: 0; }
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
            meta, fat, ating = row['valor_meta'], row['valor_venda_mes'], row['atingimento']
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
        :root {
            --bg-card: #161925; --bg-track: #0d0f16; --text-main: #f8fafc; --text-muted: #94a3b8;   
            --neon-green: linear-gradient(90deg, #10b981, #34d399); 
            --neon-blue:  linear-gradient(90deg, #2563eb, #60a5fa); 
            --neon-pink:  linear-gradient(90deg, #e11d48, #f472b6); 
        }
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

    st.title("Dashboard Analítico: Acompanhamento de Metas")
    
    df_fat, df_meta, df_rca, df_filial, df_supervisor, df_meta_tv, df_televendas = carregar_dados()
    
    # ------------------ TOP BAR ------------------
    st.markdown("### 📊 Seleção de Visão")
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
    
    # ------------------ FILTROS GLOBAIS ------------------
    st.markdown("### 🔍 Filtros Analíticos")
    
    lista_filiais = sorted(df_filial['codfilial'].dropna().astype(int).unique().tolist())
    visao = st.session_state.visao_ativa

    if visao == "RCA":
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: filiais_selecionadas = st.multiselect("📌 Filial (Código)", lista_filiais)
        with col_f2: sups_selecionados = st.multiselect("👥 Supervisor", sorted(df_supervisor['nm_supervisor'].dropna().unique().tolist()))
        with col_f3: rcas_selecionados = st.multiselect("💼 RCA", sorted(df_rca['nm_rca'].dropna().unique().tolist()))
            
        df_dim_filtrada = df_rca.copy()
        
        if filiais_selecionadas: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['cod_filial'].isin(filiais_selecionadas)]
        if sups_selecionados: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['cod_supervisor'].isin(df_supervisor[df_supervisor['nm_supervisor'].isin(sups_selecionados)]['cod_supervisor'].tolist())]
        if rcas_selecionados: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['nm_rca'].isin(rcas_selecionados)]
        df_meta_atual = df_meta
        
    else: 
        col_f1, col_f2 = st.columns(2)
        with col_f1: filiais_selecionadas = st.multiselect("📌 Filial (Código)", lista_filiais)
        with col_f2: tvs_selecionados = st.multiselect("🎧 Operador de Televendas", sorted(df_televendas['nm_televenda'].dropna().unique().tolist()))
            
        df_dim_filtrada = df_televendas.copy()
        
        if filiais_selecionadas: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['filial'].isin(filiais_selecionadas)]
        if tvs_selecionados: df_dim_filtrada = df_dim_filtrada[df_dim_filtrada['nm_televenda'].isin(tvs_selecionados)]
        df_meta_atual = df_meta_tv

    st.markdown("---")

    # ------------------ COMPUTAÇÃO & NAVEGAÇÃO ------------------
    with st.spinner(f"Processando modelo de dados para a visão {visao}..."):
        df_kpi = processar_kpis(df_fat, df_meta_atual, df_dim_filtrada, visao)
    
    if df_kpi.empty:
        st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados ou nenhuma meta cadastrada neste contexto.")
    else:
        # Prepara o DataFrame Acumulado preservando a Filial para os Cards
        df_acumulado = df_kpi.groupby(['nome_entidade', 'filial_kpi']).agg(
            meta_total=('valor_meta', 'sum'),
            fat_total=('valor_venda_mes', 'sum')
        ).reset_index()
        
        df_acumulado['atingimento'] = df_acumulado.apply(
            lambda row: row['fat_total'] / row['meta_total'] if row['meta_total'] > 0 else 0, axis=1
        )
        
        # Ordenação Global para o Ranking
        df_acumulado = df_acumulado.sort_values(by='atingimento', ascending=False).reset_index(drop=True)

        tab_resumo, tab_mensal, tab_ranking = st.tabs([
            "📈 Resumo Executivo (Filiais)", 
            "📅 Visão Mensal (Evolução)", 
            "🏆 Ranking Acumulado"
        ])
        
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