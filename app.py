import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# FUNÇÃO AUXILIAR: FORMATAR MOEDA (R$ BRASIL)
# ==========================================
def formatar_moeda(valor):
    # Transforma 1234.56 em "R$ 1.234,56"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# 1. MOTOR MATEMÁTICO (BACKEND FEFO + CUSTOS)
# ==========================================
def processar_com_consumo_futuro(caminho_pcp, caminho_precos=None):
    df = pd.read_excel(caminho_pcp)
    df.columns = df.columns.str.strip().str.lower()
    
    df['validade'] = pd.to_datetime(df['validade'], format='%d/%m/%Y', errors='coerce')
    df['estoque'] = df['estoque'].fillna(0.0).astype(float)
    df['mrp'] = df['mrp'].fillna(0.0).astype(float)
    
    df = df.dropna(subset=['validade']).sort_values(by='validade')
    
    # ---------------------------------------------------------
    # NOVO: DICIONÁRIO DE PREÇOS (O PROCV DO PYTHON)
    # ---------------------------------------------------------
    tem_preco = False
    dict_precos = {}
    
    if caminho_precos is not None:
        df_precos = pd.read_excel(caminho_precos)
        df_precos.columns = df_precos.columns.str.strip().str.lower()
        
        # Procura as colunas de material e preco na planilha anexada
        col_mat_preco = 'material' if 'material' in df_precos.columns else df_precos.columns[0]
        col_val_preco = 'preco' if 'preco' in df_precos.columns else df_precos.columns[1]
        
        # Cria um dicionário rápido na memória: {"Cafe_Em_Po": 15.50}
        dict_precos = dict(zip(df_precos[col_mat_preco].astype(str).str.strip(), df_precos[col_val_preco].astype(float)))
        tem_preco = True
        
    # Verifica como a coluna do material se chama na planilha principal
    col_mat_main = 'material' if 'material' in df.columns else 'codigo' if 'codigo' in df.columns else None

    total_geral_lixo = 0.0
    total_geral_reais = 0.0 # NOVO: Acumulador de Dinheiro
    mrp_acumulado_pendente = 0.0 
    relatorio_lotes = []
    
    lixo_por_mes = {} 
    lixo_reais_por_mes = {} # NOVO: Dinheiro por mês
    ruptura_por_mes = {} 
    
    for index, row in df.iterrows():
        estoque_linha = round(float(row['estoque']), 2)
        mrp_original_linha = round(float(row['mrp']), 2)
        validade_lote = row['validade']
        mes_ref = validade_lote.strftime('%m/%Y')
        
        # Resgata o preço unitário do material desta linha
        preco_unitario = 0.0
        nome_material = "Item Único"
        if tem_preco and col_mat_main in df.columns:
            nome_material = str(row[col_mat_main]).strip()
            preco_unitario = dict_precos.get(nome_material, 0.0)
        elif col_mat_main in df.columns:
            nome_material = str(row[col_mat_main]).strip()
        
        if mes_ref not in lixo_por_mes:
            lixo_por_mes[mes_ref] = 0.0
            lixo_reais_por_mes[mes_ref] = 0.0
            
        demanda_total_a_pagar = round(mrp_original_linha + mrp_acumulado_pendente, 2)
        
        if estoque_linha >= demanda_total_a_pagar:
            sobra = round(estoque_linha - demanda_total_a_pagar, 2)
            mrp_acumulado_pendente = 0.0  
        else:
            sobra = 0.0
            mrp_acumulado_pendente = round(demanda_total_a_pagar - estoque_linha, 2)
            
        ruptura_por_mes[mes_ref] = mrp_acumulado_pendente
            
        status = "Totalmente Consumido"
        meta_extra = 0.0
        perda_financeira = 0.0
        
        if sobra > 0.0:
            status = f"🚨 LIXO"
            meta_extra = sobra
            perda_financeira = sobra * preco_unitario # A CONTA FINANCEIRA AQUI!
            
            total_geral_lixo = round(total_geral_lixo + sobra, 2)
            total_geral_reais = round(total_geral_reais + perda_financeira, 2)
            
            lixo_por_mes[mes_ref] = round(lixo_por_mes[mes_ref] + sobra, 2)
            lixo_reais_por_mes[mes_ref] = round(lixo_reais_por_mes[mes_ref] + perda_financeira, 2)
            
        relatorio_lotes.append({
            "Mês Ref": mes_ref,
            "Material": nome_material,
            "Lote": str(row['lote']),
            "Validade": validade_lote.strftime('%d/%m/%Y'),
            "Estoque Original": f"{estoque_linha:.2f}".replace('.', ','),
            "Sobra Física": f"{sobra:.2f}".replace('.', ','),
            "💸 Prejuízo Projetado (R$)": formatar_moeda(perda_financeira) if tem_preco else "-",
            "🎯 Meta Extra (Un)": f"{meta_extra:.2f}".replace('.', ','),
            "Status": status
        })
        
    return {
        "total_lixo": total_geral_lixo,
        "total_reais": total_geral_reais,
        "lixo_mensal": lixo_por_mes,
        "reais_mensal": lixo_reais_por_mes,
        "ruptura_mensal": ruptura_por_mes,
        "detalhamento": relatorio_lotes,
        "tem_preco": tem_preco
    }

# ==========================================
# 2. INTERFACE VISUAL (FRONTEND STREAMLIT)
# ==========================================
st.set_page_config(page_title="PlanSupri - Projeção FEFO", page_icon="📊", layout="wide")

st.title("📊 PlanSupri: Projeção FEFO Financeira")
st.markdown("Calcule desperdícios, rupturas e o **Impacto Financeiro (R$)** anexando sua planilha de PCP e o Dicionário de Preços.")

# Layout de duas colunas para os botões de upload
col1, col2 = st.columns(2)
with col1:
    arquivo_pcp = st.file_uploader("1. Planilha de PCP (.xlsx)", type=["xlsx"])
with col2:
    arquivo_precos = st.file_uploader("2. Planilha de Preços (.xlsx) - Opcional", type=["xlsx"])

if arquivo_pcp is not None:
    try:
        with st.spinner('Cruzando dados e calculando perdas financeiras...'):
            resultado = processar_com_consumo_futuro(arquivo_pcp, arquivo_precos)
            
        st.success("Cálculo concluído com sucesso!")
        
        # --- PAINEL DE TOTAIS GERAIS ---
        if resultado['tem_preco'] and resultado['total_reais'] > 0:
            st.error(f"🔴 PREJUÍZO GERAL ACUMULADO: {formatar_moeda(resultado['total_reais'])}")
        
        # --- CARDS MENSAIS ---
        st.header("📈 Visão Diretiva por Mês")
        
        meses = list(resultado['lixo_mensal'].keys())
        colunas_meses = st.columns(len(meses))
        
        for idx, mes in enumerate(meses):
            lixo = resultado['lixo_mensal'].get(mes, 0.0)
            reais = resultado['reais_mensal'].get(mes, 0.0)
            ruptura = resultado['ruptura_mensal'].get(mes, 0.0)
            
            with colunas_meses[idx]:
                st.subheader(f"🗓️ {mes}")
                
                if lixo > 0:
                    st.error(f"🗑️ Lixo (Un/Kg): {lixo:,.2f}".replace('.', ','))
                    if resultado['tem_preco']:
                        st.error(f"💸 Custo: {formatar_moeda(reais)}")
                    st.info(f"🎯 Meta Venda: +{lixo:,.2f}".replace('.', ','))
                else:
                    st.success("✅ Zero Perdas")
                    
                if ruptura > 0:
                    st.warning(f"⚠️ Ruptura: {ruptura:,.2f}".replace('.', ','))
        
        st.divider()
        
        # --- TABELA DETALHADA ---
        st.header("📋 Detalhamento Físico e Financeiro por Lote")
        df_detalhe = pd.DataFrame(resultado['detalhamento'])
        st.dataframe(df_detalhe, use_container_width=True)
            
    except Exception as e:
        st.error(f"Erro ao processar as planilhas. Certifique-se de que a coluna 'Material' exista em ambas. Detalhe do erro: {e}")
