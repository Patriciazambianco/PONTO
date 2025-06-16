import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import timedelta, time

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    # Converter colunas de data
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')

    # Converter colunas de horário para time
    for col in ['Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA']:
        df[col] = pd.to_datetime(df[col].astype(str), errors='coerce').dt.time

    return df

def time_to_minutes(t):
    if isinstance(t, time):
        return t.hour * 60 + t.minute
    return None

def diff_minutes(t1, t2):
    if isinstance(t1, time) and isinstance(t2, time):
        dt1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        dt2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        delta = dt2 - dt1
        return delta.total_seconds() / 60
    return None

def analisar_ponto(df):
    df['Minutos_entrada'] = df['Entrada 1'].apply(time_to_minutes)
    df['Minutos_turno_entrada'] = df['Turnos.ENTRADA'].apply(time_to_minutes)
    df['Entrada_fora_turno'] = df.apply(
        lambda row: (row['Minutos_entrada'] is not None and row['Minutos_turno_entrada'] is not None and
                     row['Minutos_entrada'] > row['Minutos_turno_entrada'] + 60),
        axis=1
    )

    df['Minutos_trabalhados'] = df.apply(lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']), axis=1)

    df['Minutos_turno'] = df.apply(lambda row: diff_minutes(row['Turnos.ENTRADA'], row['Turnos.SAIDA']), axis=1)

    df['Minutos_extra'] = df.apply(
        lambda row: (row['Minutos_trabalhados'] - row['Minutos_turno'])
        if row['Minutos_trabalhados'] is not None and row['Minutos_turno'] is not None and (row['Minutos_trabalhados'] - row['Minutos_turno'] > 15)
        else 0,
        axis=1
    )

    df['Hora_extra_flag'] = df['Minutos_extra'] > 15
    df['Horas_extra'] = df['Minutos_extra'] / 60

    return df

def ranking_reincidentes(df):
    df_entrada_fora = df[df['Entrada_fora_turno']]
    df_hora_extra = df[df['Hora_extra_flag']]

    reincidentes_entrada = df_entrada_fora.groupby('Nome').size().reset_index(name='Dias_fora_turno')
    reincidentes_extra = df_hora_extra.groupby('Nome')['Horas_extra'].sum().reset_index(name='Total_horas_extra')

    ranking = pd.merge(reincidentes_entrada, reincidentes_extra, on='Nome', how='outer').fillna(0)
    ranking = ranking.sort_values(by=['Dias_fora_turno', 'Total_horas_extra'], ascending=False).reset_index(drop=True)

    return ranking

df = carregar_dados()
df = analisar_ponto(df)
ranking = ranking_reincidentes(df)

st.title("Análise de Ponto - Correção de Horários")

st.subheader("Dados com flags de fora do turno e hora extra")
st.dataframe(df[['Nome', 'Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Entrada_fora_turno', 'Hora_extra_flag', 'Horas_extra']])

st.subheader("Ranking de reincidentes (fora do turno e horas extras)")
st.dataframe(ranking)

total_horas_extras = df['Horas_extra'].sum()
st.markdown(f"### Total de horas extras (considerando só acima de 15 minutos): **{total_horas_extras:.2f} horas**")
