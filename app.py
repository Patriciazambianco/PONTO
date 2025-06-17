import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime

# === Função para carregar e preparar os dados ===
@st.cache_data
def carregar_dados():
    # Aqui você troca o caminho para o seu arquivo, ou URL
    df = pd.read_excel('PONTO.xlsx')

    # Garantir que coluna COORDENADOR exista e preencher valores nulos
    if 'COORDENADOR' not in df.columns:
        st.error('Coluna "COORDENADOR" não encontrada no arquivo.')
        st.stop()

    df['COORDENADOR'] = df['COORDENADOR'].fillna('Sem Coordenador')

    # Criar colunas auxiliares de horas extras em horas (float)
    df['Hora_extra_horas'] = df['Hora_extra'].astype(float) / 60  # assumindo que Hora_extra está em minutos

    # Tratar dados de jornada fora do turno: garantir coluna e tipo
    if 'Entrada_fora_turno' not in df.columns:
        df['Entrada_fora_turno'] = False

    # Formatar datas e horas para exibição
    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m/%Y')
    df['Entrada_fmt'] = df['Entrada'].dt.strftime('%H:%M') if 'Entrada' in df.columns else ''
    df['Saida_fmt'] = df['Saida'].dt.strftime('%H:%M') if 'Saida' in df.columns else ''

    return df

# === Função para gerar Excel para exportar ===
def exportar_excel(df_export):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Relatorio')
        writer.save()
    processed_data = output.getvalue()
    return processed_data

# === Carrega dados ===
df = carregar_dados()

st.title("📊 Relatório de Ponto - Horas Extras e Fora do Turno")

# Filtros topo
meses_disponiveis = sorted(df['Data'].dt.to_period('M').astype(str).unique())
coordenadores_disponiveis = sorted(df['COORDENADOR'].unique())

col1, col2 = st.columns(2)
with col1:
    mes_selecionado = st.selectbox('Selecione o Mês', meses_disponiveis)
with col2:
    coordenador_selecionado = st.selectbox('Selecione o Coordenador', coordenadores_disponiveis)

# Filtra dados
df['Mes'] = df['Data'].dt.to_period('M').astype(str)
df_filtrado = df[(df['Mes'] == mes_selecionado) & (df['COORDENADOR'] == coordenador_selecionado)]

# Top 20 Horas Extras
top20_horas = (df_filtrado.groupby('Nome')['Hora_extra_horas']
               .sum()
               .reset_index()
               .sort_values(by='Hora_extra_horas', ascending=False)
               .head(20))
top20_horas['Hora_extra_horas'] = top20_horas['Hora_extra_horas'].round(2)

# Top 20 Fora do Turno (contagem de ocorrências)
top20_fora_turno = (df_filtrado[df_filtrado['Entrada_fora_turno'] == True]
                    .groupby('Nome')['Entrada_fora_turno']
                    .count()
                    .reset_index()
                    .rename(columns={'Entrada_fora_turno': 'Dias_fora_turno'})
                    .sort_values(by='Dias_fora_turno', ascending=False)
                    .head(20))

# Exibe rankings lado a lado
st.markdown("### Ranking Mensal")

col1, col2 = st.columns(2)
with col1:
    st.markdown("#### Top 20 Horas Extras (Horas)")
    nome_selecionado_hora = st.selectbox('Selecione Funcionário (Horas Extras):', top20_horas['Nome'].tolist())
    st.dataframe(top20_horas, use_container_width=True)
with col2:
    st.markdown("#### Top 20 Fora do Turno (Dias)")
    nome_selecionado_fora = st.selectbox('Selecione Funcionário (Fora do Turno):', top20_fora_turno['Nome'].tolist())
    st.dataframe(top20_fora_turno, use_container_width=True)

# Detalhes horas extras ao lado da seleção
st.markdown("### Detalhes do Funcionário")

col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**Horas Extras - {nome_selecionado_hora}**")
    detalhes_horas = df_filtrado[df_filtrado['Nome'] == nome_selecionado_hora][
        ['Data_fmt', 'Hora_extra_horas']
    ].copy()
    detalhes_horas['Hora_extra_horas'] = detalhes_horas['Hora_extra_horas'].round(2)
    st.dataframe(detalhes_horas.rename(columns={'Data_fmt': 'Data', 'Hora_extra_horas': 'Horas Extras (h)'}), use_container_width=True)
with col2:
    st.markdown(f"**Fora do Turno - {nome_selecionado_fora}**")
    detalhes_fora = df_filtrado[(df_filtrado['Nome'] == nome_selecionado_fora) & (df_filtrado['Entrada_fora_turno'] == True)][
        ['Data_fmt', 'Entrada_fmt', 'Saida_fmt']
    ].copy()
    detalhes_fora.rename(columns={'Data_fmt': 'Data', 'Entrada_fmt': 'Entrada', 'Saida_fmt': 'Saída'}, inplace=True)
    st.dataframe(detalhes_fora, use_container_width=True)

# Botão para exportar Excel com filtro do coordenador e mês
df_export = df_filtrado.copy()
btn_exportar = st.download_button(
    label="📥 Exportar Relatório Excel (Filtrado)",
    data=exportar_excel(df_export),
    file_name=f'relatorio_ponto_{coordenador_selecionado}_{mes_selecionado}.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

