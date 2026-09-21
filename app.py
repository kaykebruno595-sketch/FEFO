import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==========================================
# FUNÇÃO AUXILIAR: FORMATAR MOEDA
# ==========================================
def formatar_moeda(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# ==========================================
# 1. MOTOR MATEMÁTICO (BACKEND FEFO + CUSTOS FIXOS)
# ==========================================
def processar_com_consumo_futuro(caminho_pcp, nome_arquivo_precos="mm60.xlsx"):
    df = pd.read_excel(caminho_pcp)
    df.columns = df.columns.str.strip().str.lower()
    
    df['validade'] = pd.to_datetime(df['validade'], format='%d/%m/%Y', errors='coerce')
    df['estoque'] = df['estoque'].fillna(0.0).astype(float)
    df['mrp'] = df['mrp'].fillna(0.0).astype(float)
    
    df = df.dropna(subset=['validade']).sort_values(by='validade')
    
    # ---------------------------------------------------------
    # LEITURA AUTOMÁTICA DA MM60 NO SERVIDOR
    # ---------------------------------------------------------
    tem_preco = False
    dict_precos = {}
    
    # Verifica se a planilha mm60.xlsx foi colocada lá no GitHub
    if os.path.exists(nome_arquivo_precos):
        df_precos = pd.read_excel(nome_arquivo_precos)
        df_precos.columns = df_precos.columns.str.strip().str.lower()
        
        col_mat_preco = 'material' if 'material' in df_precos.columns else df_precos.columns[0]
        col_val_preco = 'preco' if 'preco' in df_precos.columns else df_precos.columns[1]
        
        dict_precos = dict(zip(df_precos[col_mat_preco].astype(str).str.strip(), df_precos[col_val_preco].astype(float)))
        tem_preco = True
        
    col_mat_main = 'material' if 'material' in df.columns else 'codigo' if 'codigo' in df.columns else None

    total_geral_lixo = 0.0
    total_geral_reais = 0.0 
    mrp_acumulado_pendente = 0.0 
    relatorio_lotes = []
    
    lixo_por_mes = {} 
    lixo_reais_por_mes = {} 
    ruptura_por_mes = {} 
    
    for index, row in df.iterrows():
        estoque_linha = round(float(row['estoque']), 2)
        mrp_original_linha = round(float(row['mrp']), 2)
        validade_lote = row['validade']
        mes_ref = validade_lote.strftime('%m/%Y')
        
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
            perda_financeira = sobra * preco_unitario 
            
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
st.markdown("Faça o upload da planilha de PCP. Os custos serão calculados automaticamente usando a MM60 cadastrada no sistema.")

# Agora temos apenas um botão limpo e direto
arquivo_pcp = st.file_uploader("Anexe a planilha de PCP (.xlsx)", type=["xlsx"])

if arquivo_pcp is not None:
    try:
        with st.spinner('Cruzando dados com a MM60 e calculando perdas financeiras...'):
            resultado = processar_com_consumo_futuro(arquivo_pcp)
            
        st.success("Cálculo concluído com sucesso!")
        
        if not resultado['tem_preco']:
            st.warning("⚠️ Aviso: O arquivo 'mm60.xlsx' não foi encontrado no servidor. O painel exibirá apenas os dados físicos.")
        
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
        st.error(f"Erro ao processar as planilhas. Detalhe do erro: {e}")
