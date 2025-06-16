import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import requests
from datetime import datetime

st.set_page_config(layout="wide", page_title="Relatório de Ponto")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    df = pd.read_excel(BytesIO(response.content))

    # Conversões seguras
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df[pd.notnull(df['Data'])]  # remove linhas com Data inválida

    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], errors='coerce')
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], errors='coerce')
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce')
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce')

    df['Ano-Mês'] = df['Data'].dt.to_period('M').astype(str)
    return df

df = carregar_dados()

# Visualização inicial
st.subheader("👀 Pré-visualização dos dados carregados")
st.dataframe(df.head(), use_container_width=True)

# 🎯 Filtro por mês
meses = df['Ano-Mês'].sort_values().unique()
mes_selecionado = st.selectbox("🗓️ Selecione o mês", meses)
df = df[df['Ano-Mês'] == mes_selecionado]

# 🎯 Cálculo de horas extras
def calcular_minutos(t1, t2):
    if pd.isnull(t1) or pd.isnull(t2):
        return None
    return (t2 - t1).total_seconds() / 60

df['Minutos Trabalhados'] = df.apply(lambda row: calcular_minutos(row['Entrada 1'], row['Saída 1']), axis=1)

TURNO_PADRAO_MIN = 588  # 9h48min
df['Hora Extra (min)'] = df['Minutos Trabalhados'] - TURNO_PADRAO_MIN
df['Hora Extra (min)'] = df['Hora Extra (min)'].apply(lambda x: x if x and x > 15 else 0)
df['Hora Extra (h)'] = df['Hora Extra (min)'] / 60

# 🎯 Cálculo fora do turno
def fora_turno(row):
    if pd.isnull(row['Entrada 1']) or pd.isnull(row['Turnos.ENTRADA']):
        return False
    diff = abs((row['Entrada 1'] - row['Turnos.ENTRADA']).total_seconds()) / 60
    return diff > 60

df['Fora do Turno'] = df.apply(fora_turno, axis=1)
df['Reincidente'] = df['Fora do Turno'] | (df['Hora Extra (min)'] > 0)

# 🎯 Ranking
ranking = df[df['Reincidente']].groupby('Nome').agg({
    'Fora do Turno': 'sum',
    'Hora Extra (h)': 'sum',
    'Reincidente': 'count'
}).rename(columns={'Reincidente': 'Total Ocorrências'}).sort_values(by='Total Ocorrências', ascending=False).reset_index()

st.title("📊 Relatório de Ponto - Funcionários")
st.markdown(f"### 🔎 Mês Selecionado: **{mes_selecionado}**")

# 🎯 Gráficos
col1, col2 = st.columns(2)
with col1:
    st.subheader("🔝 Top Reincidentes")
    fig = px.bar(ranking.head(10), x='Nome', y='Total Ocorrências', color='Fora do Turno',
                 title="Top 10 (Fora do Turno e Hora Extra)",
                 color_continuous_scale="OrRd")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("📊 Distribuição Geral")
    fig2 = px.pie(ranking, values='Total Ocorrências', names='Nome',
                  title="Distribuição de Ocorrências")
    st.plotly_chart(fig2, use_container_width=True)

# 🧾 Relatório Detalhado
st.markdown("### 📋 Detalhamento por Funcionário")
funcionario_clicado = st.selectbox("Selecione um funcionário para ver os detalhes", ranking['Nome'].unique())

detalhes = df[(df['Nome'] == funcionario_clicado) & (df['Reincidente'])].copy()

# Formatando datas e horários
detalhes['Data'] = detalhes['Data'].dt.strftime('%d/%m/%Y')
for col in ['Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA']:
    detalhes[col] = detalhes[col].dt.strftime('%H:%M')

detalhes['Tipo de Ocorrência'] = detalhes.apply(
    lambda row: "Ambos" if row['Fora do Turno'] and row['Hora Extra (min)'] > 0 else (
        "Fora do Turno" if row['Fora do Turno'] else "Hora Extra"
    ), axis=1
)

st.dataframe(
    detalhes[['Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA',
              'Hora Extra (h)', 'Tipo de Ocorrência']],
    use_container_width=True
)

