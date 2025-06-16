import pandas as pd
import streamlit as st

# 📥 LINK DIRETO DO EXCEL NO GITHUB
URL = "https://raw.githubusercontent.com/seu_usuario/relatorio-ponto/main/registro_ponto.xlsx"

# Leitura do Excel hospedado no GitHub
@st.cache_data
def carregar_dados():
    df = pd.read_excel(URL)
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], errors='coerce').dt.time
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M').dt.time
    return df

df = carregar_dados()

# Verificações de irregularidade
def verificar_irregularidade(row):
    if pd.isnull(row['Entrada 1']) or pd.isnull(row['Saída 1']):
        return "FALTA"
    irregularidades = []
    if row['Entrada 1'] > row['Turnos.ENTRADA']:
        irregularidades.append("ATRASO")
    if row['Entrada 1'] < row['Turnos.ENTRADA']:
        irregularidades.append("ADIANTADO")
    if row['Saída 1'] > row['Turnos.SAIDA']:
        irregularidades.append("HORA EXTRA")
    if row['Saída 1'] < row['Turnos.SAIDA']:
        irregularidades.append("SAÍDA ANTECIPADA")
    return ", ".join(irregularidades) if irregularidades else "DENTRO DO HORÁRIO"

df['IRREGULARIDADE'] = df.apply(verificar_irregularidade, axis=1)

# Sidebar com filtros
st.sidebar.header("Filtros")
funcionario = st.sidebar.multiselect("Funcionário", df["Nome"].unique())
coordenador = st.sidebar.multiselect("Coordenador", df["MICROSIGA.COORDENADOR_IMEDIATO"].unique())

filtro = df.copy()
if funcionario:
    filtro = filtro[filtro["Nome"].isin(funcionario)]
if coordenador:
    filtro = filtro[filtro["MICROSIGA.COORDENADOR_IMEDIATO"].isin(coordenador)]

st.title("📋 Relatório de Ponto - Análise Completa")

# Métricas rápidas
st.metric("Total de Registros", len(filtro))
st.metric("Dias com Irregularidades", filtro[filtro['IRREGULARIDADE'] != "DENTRO DO HORÁRIO"].shape[0])
st.metric("Faltas", filtro[filtro['IRREGULARIDADE'].str.contains("FALTA", na=False)].shape[0])

# Tabela
st.subheader("📄 Tabela com Irregularidades")
st.dataframe(filtro[['Nome', 'Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'IRREGULARIDADE']])

# Gráfico por tipo
st.subheader("📊 Irregularidades por Tipo")
st.bar_chart(filtro['IRREGULARIDADE'].value_counts())

# Download
st.download_button("📥 Baixar Dados Filtrados", data=filtro.to_csv(index=False).encode(), file_name="relatorio_filtrado.csv")
