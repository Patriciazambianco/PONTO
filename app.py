import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
import xlsxwriter
import plotly.express as px

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto - Ofensores")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

def minutos_para_hms(minutos):
    if pd.isnull(minutos) or minutos <= 0:
        return "00:00:00"
    h = int(minutos // 60)
    m = int(minutos % 60)
    return f"{h:02d}:{m:02d}:00"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
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
        dt1 = pd.Timedelta(hours=t1.hour, minutes=t1.minute)
        dt2 = pd.Timedelta(hours=t2.hour, minutes=t2.minute)
        return int((dt2 - dt1).total_seconds() // 60)
    except:
        return None

@st.cache_data
def analisar_ponto(df):
    df['Mes_Ano'] = df['Data'].dt.to_period('M').astype(str)
    df['Dia_Semana'] = df['Data'].dt.day_name()
    df['Minutos_entrada'] = df['Entrada 1'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_entrada'] = df['Turnos.ENTRADA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_saida'] = df['Turnos.SAIDA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)

    df['Entrada_fora_turno'] = df.apply(
        lambda row: abs(row['Minutos_entrada'] - row['Minutos_turno_entrada']) > 60
        if pd.notnull(row['Minutos_entrada']) and pd.notnull(row['Minutos_turno_entrada']) else False,
        axis=1
    )

    df['Minutos_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if pd.notnull(row['Entrada 1']) and pd.notnull(row['Saída 1']) else None,
        axis=1
    )

    df['Minutos_extras'] = df.apply(
        lambda row: row['Minutos_trabalhados'] - (row['Minutos_turno_saida'] - row['Minutos_turno_entrada'])
        if pd.notnull(row['Minutos_trabalhados']) and pd.notnull(row['Minutos_turno_saida']) and pd.notnull(row['Minutos_turno_entrada']) else 0,
        axis=1
    )

    df['Hora_extra'] = df['Minutos_extras'] > 15
    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    return df

# Carga e tratamento de dados
df = carregar_dados()
df = analisar_ponto(df)

meses = sorted(df['Mes_Ano'].unique(), reverse=True)
mes = st.selectbox("Selecione o mês:", meses)
coordenadores = sorted(df['MICROSIGA.COORDENADOR_IMEDIATO'].dropna().unique())
coord = st.selectbox("Filtrar por coordenador:", ["Todos"] + coordenadores)

filtro = (df['Mes_Ano'] == mes)
if coord != "Todos":
    filtro &= (df['MICROSIGA.COORDENADOR_IMEDIATO'] == coord)

df_mes = df[filtro]

# Tendência semanal
graf_dia = df_mes[df_mes['Hora_extra']].groupby('Dia_Semana')['Minutos_extras'].sum().reset_index()
graf_dia['Horas'] = graf_dia['Minutos_extras'].apply(lambda x: round(x / 60, 1))
fig = px.bar(graf_dia, x='Dia_Semana', y='Horas', title='Tendência Semanal - Horas Extras por Dia da Semana', text='Horas')
st.plotly_chart(fig, use_container_width=True)

# Continuar com rankings e detalhamento como antes...
