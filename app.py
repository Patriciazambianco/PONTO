import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Relatório de Ponto")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    df = pd.read_excel(BytesIO(response.content))

    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], errors='coerce')
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], errors='coerce')
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce')
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce')

    df['Ano-Mês'] = df['Data'].dt.to_period('M').astype(str)
    return df

df = carregar_dados()

# 🎯 Filtro por mês
meses = df['Ano-Mês'].sort_values().unique()
mes_selecionado = st.selectbox("Selecione o mês", meses)
df = df[df['Ano-Mês'] == mes_selecionado]

# 🎯 Análise de ponto
def calcular_minutos(t1, t2):
    if pd.isnull(t1) or pd.isnull(t2):
        return None
    return (t2 - t1).total_seconds() / 60

df['Minutos Trabalhados'] = df.apply(lambda row: calcular_minutos(row['Entrada 1'], row['Saída 1']), axis=1)

TURNO_PADRAO_MIN = 588  # 9h48min
df['Hora Extra (min)'] = df['Minutos Trabalhados'] - TURNO_PADRAO_MIN
df['Hora Extra (min)'] = df['Hora Extra (min)'].apply(lambda x: x if x and x > 15 else 0)
df['Hora Extra (h)'] = df['Hora Extra (min)'] / 60

def fora_turno(row):
    if pd.isnull(row['Entrada 1']) or pd.isnull(row['Turnos.ENTRADA']):
        return False
    diff = abs((row['Entrada 1'] - row['Turnos.ENTRADA']).total_seconds()) / 60
    return diff > 60

df['Fora do Turno'] = df.apply(fora_turno, axis=1)
df['Reincidente'] = df['Fora do Turno'] | (df['Hora Extra (min)'] > 0)

# 🎯 Ranking de reincidentes
ranking = df[df['Reincidente']].groupby('Nome').agg({
    'Fora do Turno': 'sum',
    'Hora Extra (h)': 'sum',
    'Reincidente': 'count'
}).rename(columns={'Reincidente': 'Total Ocorrências'}).sort_values(by='Total Ocorrências', ascending=False).reset_index()

# 🎨 Estilo
st.title("📊 Relatório de Ponto - Funcionários")
st.markdown(f"### 🔎 Analisando mês: **{mes_selecionado}**")

# 🎯 Gráficos
col1, col2 = st.columns(2)
with col1:
    fig = px.bar(ranking.head(10), x='Nome', y='Total Ocorrências', color='Total Ocorrências',
                 title="Top 10 Reincidentes (Fora do turno ou HE)",
                 color_continuous_scale="Reds")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig2 = px.pie(ranking, values='Total Ocorrências', names='Nome',
                  title="Distribuição de Ocorrências")
    st.plotly_chart(fig2, use_container_width=True)

# 🧾 Relatório Detalhado
st.markdown("### 📋 Relatório Detalhado")
funcionario_clicado = st.selectbox("Clique no nome do funcionário para ver os detalhes", ranking['Nome'].unique())

detalhes = df[(df['Nome'] == funcionario_clicado) & (df['Reincidente'])]
detalhes_exibir = detalhes[['Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA',
                            'Hora Extra (h)', 'Fora do Turno']].copy()

# Formata datas
detalhes_exibir['Data'] = detalhes_exibir['Data'].dt.strftime('%d/%m/%Y')
detalhes_exibir['Entrada 1'] = detalhes_exibir['Entrada 1'].dt.strftime('%H:%M')
detalhes_exibir['Saída 1'] = detalhes_exibir['Saída 1'].dt.strftime('%H:%M')
detalhes_exibir['Turnos.ENTRADA'] = detalhes_exibir['Turnos.ENTRADA'].dt.strftime('%H:%M')
detalhes_exibir['Turnos.SAIDA'] = detalhes_exibir['Turnos.SAIDA'].dt.strftime('%H:%M')

st.dataframe(detalhes_exibir, use_container_width=True)
