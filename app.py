import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto – Análise de Infrações por Mês")

# URL do Excel
URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

# Função para carregar
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

# Utilitários
def diff_minutes(t1, t2):
    try:
        dt1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        dt2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        return int((dt2 - dt1).total_seconds() / 60)
    except:
        return None

def minutes_to_hms(minutes):
    if pd.isna(minutes) or minutes is None or minutes <= 0:
        return "00:00:00"
    h = int(minutes) // 60
    m = int(minutes) % 60
    return f"{h:02d}:{m:02d}:00"

# Processamento
@st.cache_data
def analisar_ponto(df):
    df['Minutos_entrada'] = df['Entrada 1'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_entrada'] = df['Turnos.ENTRADA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_saida'] = df['Turnos.SAIDA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)

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
        if (row['Minutos_trabalhados'] is not None and
            row['Minutos_turno_saida'] is not None and
            row['Minutos_turno_entrada'] is not None)
        else 0,
        axis=1
    )

    df['Hora_extra'] = df['Minutos_extras'] > 15
    df['AnoMes'] = df['Data'].dt.to_period('M').astype(str)

    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m/%Y')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    return df

# Carregar e processar
df = carregar_dados()
df = analisar_ponto(df)

# ---------------- BOTÕES ----------------
st.markdown("### 📅 Selecione o Mês e Tipo de Infração")

col1, col2 = st.columns([3, 2])
with col1:
    meses_disponiveis = sorted(df['AnoMes'].dropna().unique())
    mes_atual = st.radio("Escolha o mês:", meses_disponiveis, horizontal=True)
with col2:
    tipo = st.radio("Tipo de Infração:", ['Horas Extras', 'Fora do Turno'], horizontal=True)

# Filtro
df_mes = df[df['AnoMes'] == mes_atual]

# ---------------- RANKING ----------------
st.markdown("---")

if tipo == "Horas Extras":
    st.subheader(f"🚀 Ranking - Horas Extras em {mes_atual}")
    ranking = df_mes[df_mes['Hora_extra']].groupby('Nome').agg({'Minutos_extras': 'sum'}).reset_index()
    ranking['Horas Extras'] = ranking['Minutos_extras'].apply(minutes_to_hms)
    ranking = ranking.sort_values(by='Minutos_extras', ascending=False).reset_index(drop=True)

    st.dataframe(ranking[['Nome', 'Horas Extras']], use_container_width=True)

    # DETALHAMENTO
    st.markdown("### 📋 Detalhamento por Funcionário com Horas Extras")
    df_detalhe = df_mes[df_mes['Hora_extra']].copy()
    df_detalhe['Horas Extras'] = df_detalhe['Minutos_extras'].apply(minutes_to_hms)
    df_detalhe = df_detalhe[['Nome', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Horas Extras']]
    df_detalhe = df_detalhe.sort_values(by=['Nome', 'Data_fmt'])

    st.dataframe(df_detalhe, use_container_width=True)

else:
    st.subheader(f"⏰ Ranking - Dias Fora do Turno em {mes_atual}")
    ranking = df_mes[df_mes['Entrada_fora_turno']].groupby('Nome').size().reset_index(name='Dias Fora do Turno')
    ranking = ranking.sort_values(by='Dias Fora do Turno', ascending=False).reset_index(drop=True)

    st.dataframe(ranking, use_container_width=True)

    # DETALHAMENTO
    st.markdown("### 📋 Detalhamento por Funcionário Fora do Turno")
    df_detalhe = df_mes[df_mes['Entrada_fora_turno']].copy()
    df_detalhe['Turno Entrada'] = df_detalhe['Turnos.ENTRADA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df_detalhe['Turno Saída'] = df_detalhe['Turnos.SAIDA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df_detalhe = df_detalhe[['Nome', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turno Entrada', 'Turno Saída']]
    df_detalhe = df_detalhe.sort_values(by=['Nome', 'Data_fmt'])

    st.dataframe(df_detalhe, use_container_width=True)
