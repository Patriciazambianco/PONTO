  import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(layout="wide")

# URL do Excel
URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], errors='coerce').dt.time
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce').dt.time
    return df

def diff_minutes(t1, t2):
    if pd.isna(t1) or pd.isna(t2):
        return None
    dt1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
    dt2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
    return int((dt2 - dt1).total_seconds() / 60)

def analisar_ponto(df):
    df['Minutos_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1'])
        if pd.notna(row['Entrada 1']) and pd.notna(row['Saída 1'])
        else None,
        axis=1,
    )

    df['Minutos_esperados'] = df.apply(
        lambda row: diff_minutes(row['Turnos.ENTRADA'], row['Turnos.SAIDA'])
        if pd.notna(row['Turnos.ENTRADA']) and pd.notna(row['Turnos.SAIDA'])
        else None,
        axis=1,
    )

    df['Hora Extra'] = df.apply(
        lambda row: (row['Minutos_trabalhados'] - row['Minutos_esperados']) > 15
        if pd.notna(row['Minutos_trabalhados']) and pd.notna(row['Minutos_esperados'])
        else False,
        axis=1,
    )

    def fora_turno(row):
        if pd.isna(row['Entrada 1']) or pd.isna(row['Turnos.ENTRADA']):
            return False
        entrada1 = timedelta(hours=row['Entrada 1'].hour, minutes=row['Entrada 1'].minute)
        turno = timedelta(hours=row['Turnos.ENTRADA'].hour, minutes=row['Turnos.ENTRADA'].minute)
        diff = abs((entrada1 - turno).total_seconds() / 60)
        return diff > 60  # Mais de 1 hora para mais ou menos

    df['Fora do Turno'] = df.apply(fora_turno, axis=1)

    df['Ano-Mês'] = df['Data'].dt.to_period('M').astype(str)
    df['Data_formatada'] = df['Data'].dt.strftime('%d/%m/%Y')

    return df

def gerar_ranking(df):
    reincidentes = df.groupby('Nome')[['Fora do Turno', 'Hora Extra']].sum().reset_index()
    reincidentes = reincidentes.sort_values(by=['Fora do Turno', 'Hora Extra'], ascending=False)
    reincidentes['Rank'] = range(1, len(reincidentes) + 1)

    def medalha(rank):
        return '🥇' if rank == 1 else '🥈' if rank == 2 else '🥉' if rank == 3 else ''

    reincidentes['Medalha'] = reincidentes['Rank'].apply(medalha)
    return reincidentes

def baixar_excel(df):
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return output

# Interface principal
df = carregar_dados()
df = analisar_ponto(df)
ranking = gerar_ranking(df)

st.title("📊 Análise de Ponto - Dashboard Interativo")

# Filtros
col1, col2 = st.columns(2)

with col1:
    periodo = st.selectbox("Selecione o período:", ["Últimos 30 dias", "Mês atual"])

# Filtragem por período
hoje = pd.to_datetime("today")
if periodo == "Últimos 30 dias":
    data_inicio = hoje - pd.Timedelta(days=30)
else:
    data_inicio = hoje.replace(day=1)

df_filtrado = df[df['Data'] >= data_inicio]

# Layout com colunas para métricas
col1, col2, col3 = st.columns(3)
col1.metric("🕐 Fora do Turno", df_filtrado['Fora do Turno'].sum())
col2.metric("⏱️ Hora Extra", df_filtrado['Hora Extra'].sum())
col3.metric("👥 Total de Funcionários", df_filtrado['Nome'].nunique())

# Ranking
st.subheader("🏆 Ranking de Reincidentes")
ranking_filtrado = gerar_ranking(df_filtrado)
st.dataframe(ranking_filtrado[['Medalha', 'Nome', 'Fora do Turno', 'Hora Extra']], use_container_width=True)

# Detalhamento ao clicar no nome
nome_selecionado = st.selectbox("Selecione um funcionário para ver os dias e horários com erro:", ranking_filtrado['Nome'])

if nome_selecionado:
    detalhes = df_filtrado[
        (df_filtrado['Nome'] == nome_selecionado) &
        ((df_filtrado['Fora do Turno']) | (df_filtrado['Hora Extra']))
    ][['Data_formatada', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Fora do Turno', 'Hora Extra']]
    st.write(f"### Dias com erros de {nome_selecionado}")
    st.dataframe(detalhes)

# Gráficos
st.subheader("📈 Distribuição de Erros")
fig1 = px.histogram(df_filtrado[df_filtrado['Fora do Turno']], x='Nome', color_discrete_sequence=['orange'], title="Fora do Turno", labels={'count': 'Ocorrências'})
fig2 = px.histogram(df_filtrado[df_filtrado['Hora Extra']], x='Nome', color_discrete_sequence=['red'], title="Hora Extra", labels={'count': 'Ocorrências'})
st.plotly_chart(fig1, use_container_width=True)
st.plotly_chart(fig2, use_container_width=True)

# Botão para baixar
st.subheader("📥 Baixar relatório em Excel")
relatorio = baixar_excel(df_filtrado)
st.download_button("Baixar Excel", data=relatorio, file_name="relatorio_ponto.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
