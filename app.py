import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta
import plotly.express as px

st.set_page_config(layout="wide", page_title="📊 Relatório de Ponto")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], format='%H:%M:%S', errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], format='%H:%M:%S', errors='coerce').dt.time
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce').dt.time

    return df

def diff_minutes(t1, t2):
    try:
        dt1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        dt2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        return int((dt2 - dt1).total_seconds() / 60)
    except:
        return None

def minutes_to_hms(minutos):
    if minutos is None or minutos <= 0:
        return "00:00:00"
    h = minutos // 60
    m = minutos % 60
    return f"{h:02d}:{m:02d}:00"

@st.cache_data
def analisar_ponto(df):
    df['Minutos_entrada'] = df['Entrada 1'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_entrada'] = df['Turnos.ENTRADA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_saida'] = df['Turnos.SAIDA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)

    # Fora do turno = ±1 hora
    df['Entrada_fora_turno'] = df.apply(
        lambda row: (
            row['Minutos_entrada'] is not None and 
            row['Minutos_turno_entrada'] is not None and 
            abs(row['Minutos_entrada'] - row['Minutos_turno_entrada']) > 60
        ),
        axis=1
    )

    df['Minutos_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if row['Entrada 1'] and row['Saída 1'] else None,
        axis=1
    )

    df['Minutos_extras'] = df.apply(
        lambda row: row['Minutos_trabalhados'] - (row['Minutos_turno_saida'] - row['Minutos_turno_entrada'])
        if row['Minutos_trabalhados'] and row['Minutos_turno_saida'] and row['Minutos_turno_entrada']
        else 0,
        axis=1
    )

    df['Hora_extra'] = df['Minutos_extras'] > 15

    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m/%Y')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['AnoMes'] = df['Data'].dt.to_period('M').astype(str)

    return df

df = carregar_dados()
df = analisar_ponto(df)

# Filtros
meses = sorted(df['AnoMes'].dropna().unique())
mes_selecionado = st.sidebar.selectbox("Selecione o mês:", ["Todos"] + meses)

if mes_selecionado != "Todos":
    df = df[df['AnoMes'] == mes_selecionado]

# Rankings
ranking_horas = (
    df[df['Hora_extra']]
    .groupby('Nome')['Minutos_extras']
    .sum()
    .reset_index()
    .rename(columns={'Minutos_extras': 'Total_minutos_extras'})
)

ranking_horas['Horas_fmt'] = ranking_horas['Total_minutos_extras'].apply(minutes_to_hms)

ranking_turno = (
    df[df['Entrada_fora_turno']]
    .groupby('Nome')
    .size()
    .reset_index(name='Dias_fora_do_turno')
)

# Ordena rankings
ranking_horas = ranking_horas.sort_values(by='Total_minutos_extras', ascending=False)
ranking_turno = ranking_turno.sort_values(by='Dias_fora_do_turno', ascending=False)

# Cards métricas topo
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Funcionários com Hora Extra", ranking_horas.shape[0])
with col2:
    st.metric("Funcionários Fora do Turno", ranking_turno.shape[0])
with col3:
    st.metric("Mês Selecionado", mes_selecionado)

# Gráficos lado a lado
col1, col2 = st.columns(2)

fig = px.bar(
    ranking_horas.sort_values(by='Total_minutos_extras'),
    x='Total_minutos_extras', y='Nome', orientation='h',
    labels={'Total_minutos_extras': 'Minutos'},
    hover_data=['Horas_fmt'],
    template='plotly_white',
    title='Ranking: Total de Horas Extras'
)

fig2 = px.bar(
    ranking_turno.sort_values(by='Dias_fora_do_turno'),
    x='Dias_fora_do_turno', y='Nome', orientation='h',
    labels={'Dias_fora_do_turno': 'Dias'},
    template='plotly_white',
    title='Ranking: Dias Fora do Turno'
)

with col1:
    st.plotly_chart(fig, use_container_width=True)
with col2:
    st.plotly_chart(fig2, use_container_width=True)

# Detalhamento - Top 50 infratores
st.markdown("---")
st.subheader("🔍 Detalhamento dos 50 maiores infratores")

infratores_hora_extra = df[df['Hora_extra']]
infratores_fora_turno = df[df['Entrada_fora_turno']]
infratores = pd.concat([infratores_hora_extra, infratores_fora_turno]).drop_duplicates()

top_50 = infratores['Nome'].value_counts().head(50).index

for nome in top_50:
    with st.expander(f"👤 {nome}"):
        pessoa = infratores[infratores['Nome'] == nome].copy()
        pessoa['Horas_fmt'] = pessoa['Minutos_extras'].apply(minutes_to_hms)
        pessoa['Status'] = pessoa.apply(
            lambda row: "Hora Extra" if row['Hora_extra'] else ("Fora do Turno" if row['Entrada_fora_turno'] else "OK"),
            axis=1
        )
        st.dataframe(
            pessoa[['AnoMes', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Horas_fmt', 'Status']].sort_values(by='Data_fmt'),
            use_container_width=True
        )
