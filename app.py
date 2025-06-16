import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, time, timedelta

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

# Função para converter horas robusta
def to_time_safe(x):
    if pd.isna(x):
        return None
    if isinstance(x, pd.Timestamp) or isinstance(x, datetime):
        return x.time()
    if isinstance(x, float) or isinstance(x, int):
        try:
            total_seconds = int(x * 24 * 3600)
            hour = total_seconds // 3600
            minute = (total_seconds % 3600) // 60
            second = total_seconds % 60
            return time(hour, minute, second)
        except:
            return None
    if isinstance(x, str):
        for fmt in ("%H:%M:%S", "%H:%M", "%H.%M", "%H-%M", "%H:%M:%S.%f"):
            try:
                return datetime.strptime(x.strip(), fmt).time()
            except:
                continue
    return None

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    # Converter datas
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')

    # Converter colunas de hora usando a função robusta
    for col in ['Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA']:
        df[col] = df[col].apply(to_time_safe)

    return df

df = carregar_dados()

st.title("Análise de Ponto")

# Mostrar dados carregados
st.write("Dados carregados:")
st.dataframe(df)

# Função auxiliar para converter time em minutos (para cálculo)
def time_to_minutes(t):
    if t is None:
        return None
    return t.hour * 60 + t.minute + t.second / 60

# Calcular se funcionário está fora do turno na entrada
def esta_fora_do_turno(row):
    entrada_real = time_to_minutes(row['Entrada 1'])
    entrada_turno = time_to_minutes(row['Turnos.ENTRADA'])
    if entrada_real is None or entrada_turno is None:
        return False
    # Se entrar mais de 1 hora depois do turno começar, está fora
    return entrada_real > entrada_turno + 60

# Calcular se fez hora extra (> 15 minutos além da saída do turno)
def fez_hora_extra(row):
    saida_real = time_to_minutes(row['Saída 1'])
    saida_turno = time_to_minutes(row['Turnos.SAIDA'])
    if saida_real is None or saida_turno is None:
        return False
    return saida_real > saida_turno + 15

# Criar colunas novas com essas infos
df['Fora do Turno?'] = df.apply(esta_fora_do_turno, axis=1)
df['Hora Extra?'] = df.apply(fez_hora_extra, axis=1)

# Ranking: contar quantos dias cada funcionário está fora do turno ou fez hora extra
fora_turno_count = df[df['Fora do Turno?']].groupby('Nome').size().reset_index(name='Dias Fora do Turno')
hora_extra_count = df[df['Hora Extra?']].groupby('Nome').size().reset_index(name='Dias com Hora Extra')

# Juntar rankings numa tabela única
ranking = pd.merge(fora_turno_count, hora_extra_count, on='Nome', how='outer').fillna(0)
ranking['Dias Fora do Turno'] = ranking['Dias Fora do Turno'].astype(int)
ranking['Dias com Hora Extra'] = ranking['Dias com Hora Extra'].astype(int)

# Mostrar rankings ordenados
st.subheader("Ranking - Dias Fora do Turno")
st.dataframe(ranking.sort_values('Dias Fora do Turno', ascending=False))

st.subheader("Ranking - Dias com Hora Extra")
st.dataframe(ranking.sort_values('Dias com Hora Extra', ascending=False))

# Mostrar reincidentes (que aparecem mais de 1 vez em fora do turno ou hora extra)
reincidentes_fora_turno = ranking[ranking['Dias Fora do Turno'] > 1]
reincidentes_hora_extra = ranking[ranking['Dias com Hora Extra'] > 1]

st.subheader("Reincidentes Fora do Turno (mais de 1 dia)")
st.dataframe(reincidentes_fora_turno)

st.subheader("Reincidentes em Hora Extra (mais de 1 dia)")
st.dataframe(reincidentes_hora_extra)
