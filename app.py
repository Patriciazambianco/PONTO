import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
import requests
from datetime import datetime, timedelta

st.set_page_config(layout="wide", page_title="Relatório de Ponto")

# Tema personalizado
PRIMARY_COLOR = "#0074B7"  # azul
SECONDARY_COLOR = "#00B773"  # verde
WARNING_COLOR = "#FFA500"  # laranja
DANGER_COLOR = "#FF4B4B"  # vermelho

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

def calcular_minutos(t1, t2):
    if pd.isnull(t1) or pd.isnull(t2):
        return None
    return (t2 - t1).total_seconds() / 60

def fora_turno(row):
    if pd.isnull(row['Entrada 1']) or pd.isnull(row['Turnos.ENTRADA']):
        return False
    diff = abs((row['Entrada 1'] - row['Turnos.ENTRADA']).total_seconds()) / 60
    return diff > 60

def aplicar_analise(df):
    TURNO_PADRAO_MIN = 588  # 9h48min
    df['Minutos Trabalhados'] = df.apply(lambda row: calcular_minutos(row['Entrada 1'], row['Saída 1']), axis=1)
    df['Hora Extra (min)'] = df['Minutos Trabalhados'] - TURNO_PADRAO_MIN
    df['Hora Extra (min)'] = df['Hora Extra (min)'].apply(lambda x: x if x and x > 15 else 0)
    df['Hora Extra (h)'] = df['Hora Extra (min)'] / 60
    df['Fora do Turno'] = df.apply(fora_turno, axis=1)
    df['Reincidente'] = df['Fora do Turno'] | (df['Hora Extra (min)'] > 0)
    return df

def gerar_ranking(df):
    ranking = df[df['Reincidente']].groupby('Nome').agg({
        'Fora do Turno': 'sum',
        'Hora Extra (h)': 'sum',
        'Reincidente': 'count'
    }).rename(columns={'Reincidente': 'Total Ocorrências'}).sort_values(by='Total Ocorrências', ascending=False).reset_index()
    return ranking

def aplicar_medalhas(ranking):
    medalhas = ['🥇', '🥈', '🥉']
    for i in range(min(3, len(ranking))):
        ranking.loc[i, 'Nome'] = f"{medalhas[i]} {ranking.loc[i, 'Nome']}"
    return ranking

df = carregar_dados()

# 🌟 Filtros por período
hoje = datetime.today()
periodo = st.selectbox("Período", ["Últimos 30 dias", "Mês atual"])
if periodo == "Últimos 30 dias":
    df = df[df['Data'] >= hoje - timedelta(days=30)]
else:
    df = df[(df['Data'].dt.month == hoje.month) & (df['Data'].dt.year == hoje.year)]

# Análise e ranking
df = aplicar_analise(df)
ranking = aplicar_medalhas(gerar_ranking(df))

st.title("📊 Relatório de Ponto - Funcionários")

# 📊 Gráficos
col1, col2 = st.columns(2)
with col1:
    fig = px.bar(ranking.head(10), x='Nome', y='Total Ocorrências', color='Total Ocorrências',
                 title="Top 10 Reincidentes", color_continuous_scale=[PRIMARY_COLOR, WARNING_COLOR, DANGER_COLOR])
    st.plotly_chart(fig, use_container_width=True)

with col2:
    fig2 = px.sunburst(ranking, path=['Nome'], values='Total Ocorrências',
                       title="Distribuição de Ocorrências")
    st.plotly_chart(fig2, use_container_width=True)

# 📅 Detalhes por funcionário
st.markdown("### 👍 Detalhes por Funcionário")
funcionario = st.selectbox("Clique para ver os dias com erro", ranking['Nome'].unique())
sem_medalha = funcionario.replace('🥇', '').replace('🥈', '').replace('🥉', '').strip()
detalhes = df[(df['Nome'].str.contains(sem_medalha)) & df['Reincidente']].copy()
detalhes['Data'] = detalhes['Data'].dt.strftime('%d/%m/%Y')
detalhes['Entrada 1'] = detalhes['Entrada 1'].dt.strftime('%H:%M')
detalhes['Saída 1'] = detalhes['Saída 1'].dt.strftime('%H:%M')
detalhes['Turnos.ENTRADA'] = detalhes['Turnos.ENTRADA'].dt.strftime('%H:%M')
detalhes['Turnos.SAIDA'] = detalhes['Turnos.SAIDA'].dt.strftime('%H:%M')
st.dataframe(detalhes[['Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Hora Extra (h)', 'Fora do Turno']], use_container_width=True)

# 📂 Botão para download do relatório
st.download_button(
    label="📅 Baixar Relatório Excel",
    data=detalhes.to_excel(index=False, engine='openpyxl'),
    file_name=f"relatorio_ponto_{funcionario.strip()}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
