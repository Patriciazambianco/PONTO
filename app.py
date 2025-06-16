import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    # Ajusta tipos de data e hora
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)

    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], errors='coerce').dt.time

    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce').dt.time

    return df

def calcular_diferencas(df):
    # Função para converter time em datetime com data fixa para facilitar cálculo
    def to_datetime(t):
        if pd.isna(t):
            return None
        return datetime.combine(datetime(2000,1,1), t)

    # Calcular diferença em minutos entre Entrada 1 e Turnos.ENTRADA
    dif_entrada = []
    dif_saida = []

    for i, row in df.iterrows():
        entrada_real = to_datetime(row['Entrada 1'])
        entrada_turno = to_datetime(row['Turnos.ENTRADA'])
        saida_real = to_datetime(row['Saída 1'])
        saida_turno = to_datetime(row['Turnos.SAIDA'])

        # Diferença em minutos para chegada - positivo se chegou depois do turno
        if entrada_real and entrada_turno:
            delta_entrada = (entrada_real - entrada_turno).total_seconds() / 60
        else:
            delta_entrada = None

        # Diferença em minutos para saída - positivo se saiu depois do turno
        if saida_real and saida_turno:
            delta_saida = (saida_real - saida_turno).total_seconds() / 60
        else:
            delta_saida = None

        dif_entrada.append(delta_entrada)
        dif_saida.append(delta_saida)

    df['Minutos_de_atraso_na_entrada'] = dif_entrada
    df['Minutos_sobre_hora_saida'] = dif_saida

    # Considera Fora do Turno se atrasar mais que 60 minutos na entrada (mais de 1 hora)
    df['Fora_do_turno'] = df['Minutos_de_atraso_na_entrada'].apply(lambda x: x is not None and x > 60)

    # Considera Hora extra se sair pelo menos 15 minutos depois do horário do turno
    df['Hora_extra'] = df['Minutos_sobre_hora_saida'].apply(lambda x: x is not None and x > 15)

    return df

def gerar_rankings(df):
    # Ranking Fora do Turno
    ranking_fora_turno = (
        df[df['Fora_do_turno']]
        .groupby('Nome')
        .size()
        .reset_index(name='Dias Fora do Turno')
        .sort_values(by='Dias Fora do Turno', ascending=False)
    )

    # Ranking Hora Extra
    ranking_hora_extra = (
        df[df['Hora_extra']]
        .groupby('Nome')
        .size()
        .reset_index(name='Dias com Hora Extra')
        .sort_values(by='Dias com Hora Extra', ascending=False)
    )

    return ranking_fora_turno, ranking_hora_extra

# --- Fluxo principal ---

st.title("Análise de Ponto - Fora do Turno e Hora Extra")

df = carregar_dados()

df = calcular_diferencas(df)

st.subheader("Dados brutos com análise de atrasos e horas extras")
st.dataframe(df[['Nome','Data','Entrada 1','Saída 1','Turnos.ENTRADA','Turnos.SAIDA',
                 'Minutos_de_atraso_na_entrada','Fora_do_turno',
                 'Minutos_sobre_hora_saida','Hora_extra']])

ranking_fora_turno, ranking_hora_extra = gerar_rankings(df)

st.subheader("Ranking de Funcionários Fora do Turno (> 1 hora de atraso na entrada)")
if ranking_fora_turno.empty:
    st.write("Nenhum funcionário chegou fora do turno.")
else:
    st.dataframe(ranking_fora_turno)

st.subheader("Ranking de Funcionários com Hora Extra (> 15 minutos além do turno)")
if ranking_hora_extra.empty:
    st.write("Nenhum funcionário fez hora extra relevante.")
else:
    st.dataframe(ranking_hora_extra)
