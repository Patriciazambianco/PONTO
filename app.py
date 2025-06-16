import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto")

# URL do Excel
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

def minutes_to_hms(minutes):
    if pd.isna(minutes) or minutes is None or minutes <= 0:
        return "00:00:00"
    h = int(minutes) // 60
    m = int(minutes) % 60
    return f"{h:02d}:{m:02d}:00"

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

df = carregar_dados()
df = analisar_ponto(df)

# -------------------- FILTROS ----------------------
st.markdown("### 📅 Selecione os Meses e Tipo de Infração")

meses_disponiveis = sorted(df['AnoMes'].dropna().unique())
todos_selecionados = st.checkbox("Selecionar todos os meses", value=True)
meses_selecionados = meses_disponiveis if todos_selecionados else st.multiselect("Meses:", meses_disponiveis, default=meses_disponiveis[:1])

tipo = st.radio("Tipo de Infração:", ['Horas Extras', 'Fora do Turno'], horizontal=True)

# Filtrando meses
df_filtrado = df[df['AnoMes'].isin(meses_selecionados)]

if tipo == "Horas Extras":
    st.subheader("🚀 Ranking - Horas Extras")
    ranking = df_filtrado[df_filtrado['Hora_extra']].groupby(['Nome']).agg({'Minutos_extras': 'sum'}).reset_index()
    ranking['Horas Extras'] = ranking['Minutos_extras'].apply(minutes_to_hms)
    ranking = ranking.sort_values(by='Minutos_extras', ascending=False).reset_index(drop=True)

    st.dataframe(ranking[['Nome', 'Horas Extras']], use_container_width=True)

    st.markdown("### 📋 Detalhamento")
    detalhes = df_filtrado[df_filtrado['Hora_extra']].copy()
    detalhes['Horas Extras'] = detalhes['Minutos_extras'].apply(minutes_to_hms)
    detalhes = detalhes[['Nome', 'AnoMes', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Horas Extras']]
    st.dataframe(detalhes.sort_values(by=['Nome', 'AnoMes', 'Data_fmt']), use_container_width=True)

else:
    st.subheader("⏰ Ranking - Fora do Turno")
    ranking = df_filtrado[df_filtrado['Entrada_fora_turno']].groupby(['Nome']).size().reset_index(name='Dias Fora do Turno')
    ranking = ranking.sort_values(by='Dias Fora do Turno', ascending=False).reset_index(drop=True)

    st.dataframe(ranking, use_container_width=True)

    st.markdown("### 📋 Detalhamento")
    detalhes = df_filtrado[df_filtrado['Entrada_fora_turno']].copy()
    detalhes['Turno Entrada'] = detalhes['Turnos.ENTRADA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    detalhes['Turno Saída'] = detalhes['Turnos.SAIDA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    detalhes = detalhes[['Nome', 'AnoMes', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turno Entrada', 'Turno Saída']]
    st.dataframe(detalhes.sort_values(by=['Nome', 'AnoMes', 'Data_fmt']), use_container_width=True)
