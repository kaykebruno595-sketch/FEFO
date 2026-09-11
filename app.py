import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# 1. MOTOR MATEMÁTICO (BACKEND FEFO)
# ==========================================
def processar_com_consumo_futuro(caminho_arquivo):
    df = pd.read_excel(caminho_arquivo)
    
    # Padronização e leitura correta da planilha
    df.columns = df.columns.str.strip().str.lower()
    df['validade'] = pd.to_datetime(df['validade'], format='%d/%m/%Y', errors='coerce')
    df['estoque'] = df['estoque'].fillna(0.0).astype(float)
    df['mrp'] = df['mrp'].fillna(0.0).astype(float)
    
    # Ordenação cronológica obrigatória
    df = df.dropna(subset=['validade']).sort_values(by='validade')
    
    total_geral_lixo = 0.0
    mrp_acumulado_pendente = 0.0 
    relatorio_lotes = []
    
    lixo_por_mes = {} 
    ruptura_por_mes = {} 
    
    for index, row in df.iterrows():
        estoque_linha = round(float(row['estoque']), 2)
        mrp_original_linha = round(float(row['mrp']), 2)
        validade_lote = row['validade']
        mes_ref = validade_lote.strftime('%m/%Y')
        
        # Garante que o mês exista no dicionário
        if mes_ref not in lixo_por_mes:
            lixo_por_mes[mes_ref] = 0.0
            
        # A demanda real é o MRP da linha + o que ficou devendo antes
        demanda_total_a_pagar = round(mrp_original_linha + mrp_acumulado_pendente, 2)
        
        if estoque_linha >= demanda_total_a_pagar:
            sobra = round(estoque_linha - demanda_total_a_pagar, 2)
            mrp_acumulado_pendente = 0.0  
        else:
            sobra = 0.0
            mrp_acumulado_pendente = round(demanda_total_a_pagar - estoque_linha, 2)
            
        # Tira a "fotografia" da dívida atual para este mês
        ruptura_por_mes[mes_ref] = mrp_acumulado_pendente
            
        status = "Totalmente Consumido"
        if sobra > 0.0:
            status = f"🚨 LIXO (Vence neste mês)"
            total_geral_lixo = round(total_geral_lixo + sobra, 2)
            lixo_por_mes[mes_ref] = round(lixo_por_mes[mes_ref] + sobra, 2)
            
        # Formatação Padrão Brasileiro
        sobra_fmt = f"{sobra:.2f}".replace('.', ',')
        estoque_fmt = f"{estoque_linha:.2f}".replace('.', ',')
        mrp_orig_fmt = f"{mrp_original_linha:.2f}".replace('.', ',')
        mrp_total_fmt = f"{demanda_total_a_pagar:.2f}".replace('.', ',')
            
        relatorio_lotes.append({
            "Mês Ref": mes_ref,
            "Lote": str(row['lote']),
            "Validade": validade_lote.strftime('%d/%m/%Y'),
            "Estoque Original": estoque_fmt,
            "MRP Base": mrp_orig_fmt,
            "Demanda Cobrada (com dívida)": mrp_total_fmt,
            "Sobra Final": sobra_fmt,
            "Status": status
        })
        
    return {
        "total_geral_lixo": total_geral_lixo,
        "lixo_mensal": lixo_por_mes,
        "ruptura_mensal": ruptura_por_mes,
        "detalhamento": relatorio_lotes
    }


# ==========================================
# 2. INTERFACE VISUAL (FRONTEND STREAMLIT)
# ==========================================
st.set_page_config(page_title="PlanSupri - Projeção FEFO", page_icon="📊", layout="wide")

st.title("📊 PlanSupri: Projeção de Validade e Ruptura")
st.markdown("Faça o upload da sua planilha de PCP para calcular o desperdício projetado (FEFO) e as rupturas de estoque mês a mês.")

# Botão de Upload na Tela
arquivo_enviado = st.file_uploader("Anexe a planilha preenchida (.xlsx)", type=["xlsx"])

if arquivo_enviado is not None:
    try:
        with st.spinner('Processando lotes e calculando rolagens de MRP...'):
            resultado = processar_com_consumo_futuro(arquivo_enviado)
            
        st.success("Cálculo concluído com sucesso!")
        
        # --- DESENHANDO OS CARDS DO RESUMO DIRETIVO ---
        st.header("📈 Resumo Diretivo por Mês")
        
        meses = list(resultado['lixo_mensal'].keys())
        # Cria colunas para organizar os meses lado a lado
        colunas_meses = st.columns(len(meses))
        
        for idx, mes in enumerate(meses):
            lixo = resultado['lixo_mensal'].get(mes, 0.0)
            ruptura = resultado['ruptura_mensal'].get(mes, 0.0)
            
            with colunas_meses[idx]:
                st.subheader(f"🗓️ {mes}")
                
                # Card de Lixo
                if lixo > 0:
                    st.error(f"🗑️ Lixo: {lixo:,.2f}".replace('.', ','))
                else:
                    st.success("✅ Lixo: Zero")
                    
                # Card de Ruptura
                if ruptura > 0:
                    st.warning(f"⚠️ Falta: {ruptura:,.2f}".replace('.', ','))
                else:
                    st.info("✅ Estoque OK")
        
        st.divider()
        
        # --- TABELA DETALHADA PARA A EQUIPE ---
        st.header("📋 Detalhamento de Lotes")
        df_detalhe = pd.DataFrame(resultado['detalhamento'])
        
        # Exibe a tabela interativa do Streamlit
        st.dataframe(df_detalhe, use_container_width=True)
            
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar a planilha. Verifique se as colunas estão corretas. Detalhe do erro: {e}")
