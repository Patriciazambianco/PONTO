import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto - Horas Extras e Fora do Turno")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

def minutos_para_horas(minutos):
    if minutos is None or minutos <= 0:
        return 0
    return round(minutos / 60, 2)

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
        dt1 = pd.Timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        dt2 = pd.Timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        return int((dt2 - dt1).total_seconds() / 60)
    except:
        return None

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
        if row['Minutos_trabalhados'] is not None and row['Minutos_turno_saida'] is not None and row['Minutos_turno_entrada'] is not None
        else 0,
        axis=1
    )

    df['Minutos_extras'] = df['Minutos_extras'].apply(lambda x: x if x > 0 else 0)

    df['Horas_extras'] = df['Minutos_extras'].apply(minutos_para_horas)

    df['Hora_extra_flag'] = df['Minutos_extras'] > 15

    df['Mes_Ano'] = df['Data'].dt.to_period('M').astype(str)

    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    return df

df = carregar_dados()
df = analisar_ponto(df)

# --- FILTROS EM CARDS LADOS A LADO ---
st.markdown("### Filtros")
col1, col2 = st.columns([1, 1])

with col1:
    meses_disponiveis = sorted(df['Mes_Ano'].dropna().unique(), reverse=True)
    mes_selecionado = st.selectbox("Selecione o mês:", meses_disponiveis)

with col2:
    coordenadores_disponiveis = sorted(df['COORDENADOR'].dropna().unique())
    coordenador_selecionado = st.selectbox("Selecione o coordenador:", ["Todos"] + coordenadores_disponiveis)

# Aplica filtro mês
df_filtrado = df[df['Mes_Ano'] == mes_selecionado]

# Aplica filtro coordenador
if coordenador_selecionado != "Todos":
    df_filtrado = df_filtrado[df_filtrado['COORDENADOR'] == coordenador_selecionado]

# Rankings top 20
ranking_horas = (
    df_filtrado[df_filtrado['Hora_extra_flag']]
    .groupby('Nome')['Horas_extras']
    .sum()
    .reset_index()
    .sort_values(by='Horas_extras', ascending=False)
    .head(20)
)

ranking_fora_turno = (
    df_filtrado[df_filtrado['Entrada_fora_turno']]
    .groupby('Nome')
    .size()
    .reset_index(name='Dias_fora_turno')
    .sort_values(by='Dias_fora_turno', ascending=False)
    .head(20)
)

# Layout alinhadinho com 2 linhas e 2 colunas cada
st.markdown("---")

# Linha 1: Horas Extras lado a lado
st.subheader("Horas Extras")
cols1 = st.columns(2)
with cols1[0]:
    st.markdown("**Top 20 Horas Extras (h)**")
    selecionado_horas = st.selectbox("Funcionário (Horas Extras):", ranking_horas['Nome'].tolist(), key='hora')
    st.dataframe(
        ranking_horas.rename(columns={'Nome': 'Funcionário', 'Horas_extras': 'Horas Extras (h)'}),
        use_container_width=True,
    )

with cols1[1]:
    st.markdown("**Detalhes Horas Extras**")
    detalhes_horas = df_filtrado[(df_filtrado['Nome'] == selecionado_horas) & (df_filtrado['Hora_extra_flag'])][
        ['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Horas_extras', 'Turnos.ENTRADA', 'Turnos.SAIDA']
    ]
    detalhes_horas = detalhes_horas.rename(
        columns={
            'Data_fmt': 'Data',
            'Entrada_fmt': 'Entrada',
            'Saida_fmt': 'Saída',
            'Horas_extras': 'Horas Extras (h)',
            'Turnos.ENTRADA': 'Jornada Início',
            'Turnos.SAIDA': 'Jornada Fim',
        }
    )
    st.dataframe(detalhes_horas, use_container_width=True)

st.markdown("---")

# Linha 2: Fora do Turno lado a lado
st.subheader("Fora do Turno")
cols2 = st.columns(2)
with cols2[0]:
    st.markdown("**Top 20 Fora do Turno (dias)**")
    selecionado_fora = st.selectbox("Funcionário (Fora do Turno):", ranking_fora_turno['Nome'].tolist(), key='fora')
    st.dataframe(
        ranking_fora_turno.rename(columns={'Nome': 'Funcionário', 'Dias_fora_turno': 'Dias Fora do Turno'}),
        use_container_width=True,
    )

with cols2[1]:
    st.markdown("**Detalhes Fora do Turno**")
    detalhes_fora = df_filtrado[(df_filtrado['Nome'] == selecionado_fora) & (df_filtrado['Entrada_fora_turno'])][
        ['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA']
    ]
    detalhes_fora = detalhes_fora.rename(
        columns={
            'Data_fmt': 'Data',
            'Entrada_fmt': 'Entrada Real',
            'Saida_fmt': 'Saída Real',
            'Turnos.ENTRADA': 'Jornada Início',
            'Turnos.SAIDA': 'Jornada Fim',
        }
    )
    st.dataframe(detalhes_fora, use_container_width=True)
