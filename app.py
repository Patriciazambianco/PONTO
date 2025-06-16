import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta, time

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

def convert_to_time(x):
    try:
        if pd.isnull(x):
            return None
        if isinstance(x, time):
            return x
        if isinstance(x, str):
            return datetime.strptime(x.strip(), '%H:%M:%S').time()
        if isinstance(x, pd.Timestamp):
            return x.time()
        # Tenta converter string no formato HH:MM sem segundos
        if isinstance(x, (int, float)):
            # pode ser Excel datetime decimal - aqui não vamos tratar, retorna None
            return None
    except Exception:
        return None
    return None

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')

    for col in ['Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA']:
        df[col] = df[col].apply(convert_to_time)

    return df

def time_to_minutes(t):
    return t.hour * 60 + t.minute if t else None

def diff_minutes(t1, t2):
    if t1 and t2:
        dt1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        dt2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        delta = dt2 - dt1
        return delta.total_seconds() / 60
    return None

def analisar_ponto(df):
    # Calcula se a entrada está fora do turno (entrada > turno.entrada + 60 minutos)
    df['Minutos_entrada'] = df['Entrada 1'].apply(lambda x: time_to_minutes(x))
    df['Minutos_turno_entrada'] = df['Turnos.ENTRADA'].apply(lambda x: time_to_minutes(x))
    df['Entrada_fora_turno'] = df.apply(
        lambda row: row['Minutos_entrada'] > (row['Minutos_turno_entrada'] + 60) if row['Minutos_entrada'] and row['Minutos_turno_entrada'] else False,
        axis=1
    )

    # Calcula minutos trabalhados (Saída - Entrada)
    df['Minutos_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if row['Entrada 1'] and row['Saída 1'] else None,
        axis=1
    )
    # Minutos do turno oficial (Turnos.SAIDA - Turnos.ENTRADA)
    df['Minutos_turno'] = df.apply(
        lambda row: diff_minutes(row['Turnos.ENTRADA'], row['Turnos.SAIDA']) if row['Turnos.ENTRADA'] and row['Turnos.SAIDA'] else None,
        axis=1
    )
    # Calcular minutos extras (acima de 15 minutos)
    df['Minutos_extra'] = df.apply(
        lambda row: row['Minutos_trabalhados'] - row['Minutos_turno'] if row['Minutos_trabalhados'] and row['Minutos_turno'] and (row['Minutos_trabalhados'] - row['Minutos_turno'] > 15) else 0,
        axis=1
    )
    # Flag hora extra (se passou de 15 minutos)
    df['Hora_extra_flag'] = df['Minutos_extra'] > 15

    # Converter minutos_extra para horas (float)
    df['Horas_extra'] = df['Minutos_extra'] / 60

    return df

def ranking_reincidentes(df):
    # Agrupa por nome somando as horas extras e contando dias fora do turno
    df_entrada_fora = df[df['Entrada_fora_turno'] == True]
    df_hora_extra = df[df['Hora_extra_flag'] == True]

    reincidentes_entrada = df_entrada_fora.groupby('Nome').size().reset_index(name='Dias_fora_turno')
    reincidentes_extra = df_hora_extra.groupby('Nome')['Horas_extra'].sum().reset_index(name='Total_horas_extra')

    # Junta os dois rankings (fora do turno + hora extra)
    ranking = pd.merge(reincidentes_entrada, reincidentes_extra, on='Nome', how='outer').fillna(0)

    # Ordena por mais dias fora do turno e mais horas extras
    ranking = ranking.sort_values(by=['Dias_fora_turno', 'Total_horas_extra'], ascending=False).reset_index(drop=True)
    return ranking

df = carregar_dados()
df = analisar_ponto(df)
ranking = ranking_reincidentes(df)

st.title("Análise de Ponto")

st.subheader("Dados completos com flags")
st.dataframe(df[['Nome', 'Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Entrada_fora_turno', 'Hora_extra_flag', 'Horas_extra']])

st.subheader("Ranking de reincidentes (fora do turno e horas extras)")
st.dataframe(ranking)

total_horas_extras = df['Horas_extra'].sum()
st.markdown(f"### Total de horas extras (considerando só acima de 15 minutos): **{total_horas_extras:.2f} horas**")
