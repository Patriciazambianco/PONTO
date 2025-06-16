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

    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')

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

st.title("Análise de Ponto - Ranking Reincidentes")

st.subheader("Ranking de reincidentes (fora do turno e horas extras)")

# Mostrar o ranking com botão expansível para detalhes
for i, row in ranking.iterrows():
    nome = row['Nome']
    dias_fora = int(row['Dias_fora_turno'])
    horas_extra = row['Total_horas_extra']

    with st.expander(f"{nome} - Dias fora do turno: {dias_fora}, Horas extras: {horas_extra:.2f}"):
        # Filtrar os registros desse funcionário que estão fora do turno ou com hora extra
        detalhes = df[
            (df['Nome'] == nome) & ((df['Entrada_fora_turno']) | (df['Hora_extra_flag']))
        ].copy()

        # Formatar as datas no padrão dd/mm/yyyy
        detalhes['Data_formatada'] = detalhes['Data'].dt.strftime('%d/%m/%Y')

        # Mostrar uma tabela com as datas e horários do erro
        st.dataframe(detalhes[[
            'Data_formatada', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA',
            'Entrada_fora_turno', 'Hora_extra_flag', 'Horas_extra'
        ]].rename(columns={
            'Data_formatada': 'Data',
            'Entrada 1': 'Entrada Real',
            'Saída 1': 'Saída Real',
            'Turnos.ENTRADA': 'Entrada do Turno',
            'Turnos.SAIDA': 'Saída do Turno',
            'Entrada_fora_turno': 'Fora do Turno',
            'Hora_extra_flag': 'Hora Extra?',
            'Horas_extra': 'Horas Extras (h)'
        }))

# Mostrar total geral de horas extras
total_horas_extras = df['Horas_extra'].sum()
st.markdown(f"### Total de horas extras (considerando só acima de 15 minutos): **{total_horas_extras:.2f} horas**")
