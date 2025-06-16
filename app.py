import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import timedelta
import plotly.express as px

st.set_page_config(layout="wide", page_title="📊 Relatório de Ponto Dark")

# Inject CSS for dark theme and button styling
st.markdown(
    """
    <style>
    /* Dark background */
    .main {
        background-color: #121212;
        color: #e0e0e0;
    }
    /* Streamlit header fix */
    header, footer, .css-18e3th9 {
        background-color: #121212 !important;
        color: #e0e0e0 !important;
    }
    /* Buttons custom */
    div.stButton > button {
        background-color: #1f77b4;
        color: white;
        border-radius: 8px;
        padding: 8px 24px;
        font-weight: 600;
        transition: background-color 0.3s ease;
    }
    div.stButton > button:hover {
        background-color: #5599ee;
        color: #fff;
        cursor: pointer;
    }
    /* Table header */
    .css-1d391kg tr th {
        background-color: #333 !important;
        color: white !important;
    }
    /* Dataframe row highlight */
    .stDataFrame div[data-row-index][data-selected="true"] {
        background-color: #2a2a2a !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

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

# Lista meses e adiciona botão "Selecionar tudo"
meses = sorted(df['AnoMes'].dropna().unique())
todos_meses = ["Todos"] + meses

st.sidebar.title("Filtros 📅")
mes_selecionado = st.sidebar.selectbox("Selecionar mês:", todos_meses, index=0)

tipo_filtro = st.sidebar.multiselect(
    "Mostrar infrações:",
    ['Hora Extra', 'Fora do Turno'],
    default=['Hora Extra', 'Fora do Turno']
)

# Filtra meses
if mes_selecionado != "Todos":
    df = df[df['AnoMes'] == mes_selecionado]

# Filtra tipos de infração
df_filtrado = pd.DataFrame()
if 'Hora Extra' in tipo_filtro:
    df_filtrado = pd.concat([df_filtrado, df[df['Hora_extra']]])
if 'Fora do Turno' in tipo_filtro:
    df_filtrado = pd.concat([df_filtrado, df[df['Entrada_fora_turno']]])
df_filtrado = df_filtrado.drop_duplicates()

# Ranking Hora Extra
ranking_horas = (
    df_filtrado[df_filtrado['Hora_extra']]
    .groupby('Nome')['Minutos_extras']
    .sum()
    .reset_index()
    .rename(columns={'Minutos_extras': 'Total_minutos_extras'})
)
ranking_horas['Horas_fmt'] = ranking_horas['Total_minutos_extras'].apply(minutes_to_hms)
ranking_horas = ranking_horas.sort_values('Total_minutos_extras', ascending=False)

# Ranking Fora do Turno
ranking_turno = (
    df_filtrado[df_filtrado['Entrada_fora_turno']]
    .groupby('Nome')
    .size()
    .reset_index(name='Dias_fora_do_turno')
)
ranking_turno = ranking_turno.sort_values('Dias_fora_do_turno', ascending=False)

# Destacar reincidentes (quem aparece em mais de 1 mês)
reincidentes = df.groupby('Nome')['AnoMes'].nunique()
reincidentes = reincidentes[reincidentes > 1].index.to_list()

def highlight_reincidentes(nome):
    return 'background-color: #ffa500;' if nome in reincidentes else ''

# Métricas topo
col1, col2, col3 = st.columns([1,1,2])
col1.metric("Funcionários com Hora Extra", ranking_horas.shape[0])
col2.metric("Funcionários Fora do Turno", ranking_turno.shape[0])
col3.markdown(f"**Mês Selecionado:** {mes_selecionado}")

# Gráficos lado a lado
col1, col2 = st.columns(2)

fig_horas = px.bar(
    ranking_horas.sort_values('Total_minutos_extras'),
    x='Total_minutos_extras', y='Nome', orientation='h',
    labels={'Total_minutos_extras': 'Minutos'},
    hover_data=['Horas_fmt'],
    template='plotly_dark',
    title='⏳ Ranking: Total de Horas Extras'
)

fig_turno = px.bar(
    ranking_turno.sort_values('Dias_fora_do_turno'),
    x='Dias_fora_do_turno', y='Nome', orientation='h',
    labels={'Dias_fora_do_turno': 'Dias'},
    template='plotly_dark',
    title='🚨 Ranking: Dias Fora do Turno'
)

col1.plotly_chart(fig_horas, use_container_width=True)
col2.plotly_chart(fig_turno, use_container_width=True)

# Detalhamento - top 50 infratores com expanders e destaque de reincidentes
st.markdown("---")
st.subheader("🔍 Detalhamento dos 50 maiores infratores")

infratores = df_filtrado.copy()
top_50 = infratores['Nome'].value_counts().head(50).index

for nome in top_50:
    st.markdown(
        f"<div style='padding: 10px; border-radius: 6px; margin-bottom: 8px; "
        f"background-color: {'#ffa500' if nome in reincidentes else '#222'}; color: black; font-weight: 600;'>"
        f"👤 {nome}</div>", 
        unsafe_allow_html=True
    )
    pessoa = infratores[infratores['Nome'] == nome].copy()
    pessoa['Horas_fmt'] = pessoa['Minutos_extras'].apply(minutes_to_hms)
    pessoa['Status'] = pessoa.apply(
        lambda row: "Hora Extra" if row['Hora_extra'] else ("Fora do Turno" if row['Entrada_fora_turno'] else "OK"),
        axis=1
    )
    st.dataframe(
        pessoa[['AnoMes', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Horas_fmt', 'Status']].sort_values(by='Data_fmt'),
        use_container_width=True,
        height=250
    )
