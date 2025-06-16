import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(layout="wide", page_title="📊 Relatório de Ponto")

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

    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    df['Mês'] = df['Data'].dt.strftime('%Y-%m')
    df['Status'] = df.apply(
        lambda row: "Hora Extra" if row['Hora_extra'] else ("Fora do Turno" if row['Entrada_fora_turno'] else "OK"),
        axis=1
    )

    df['Horas_extras'] = df['Minutos_extras'].apply(lambda x: round(x/60, 2) if x > 0 else 0)
    return df

# ---------------------- CARREGANDO DADOS ----------------------
df = carregar_dados()
df = analisar_ponto(df)

# ---------------------- FILTRO POR MÊS ----------------------
meses = sorted(df['Mês'].dropna().unique(), reverse=True)
mes_selecionado = st.selectbox("📅 Selecione o mês:", meses)
df = df[df['Mês'] == mes_selecionado]

# ---------------------- RANKING ----------------------
ranking_excesso = df[df['Hora_extra']].groupby('Nome').size().reset_index(name='Dias com hora extra')
ranking_turno = df[df['Entrada_fora_turno']].groupby('Nome').size().reset_index(name='Dias fora do turno')

st.markdown("### 🏆 Rankings de Reincidência")

col1, col2 = st.columns(2)

with col1:
    st.subheader("🚀 Horas Extras")
    gb1 = GridOptionsBuilder.from_dataframe(ranking_excesso)
    gb1.configure_selection('single', use_checkbox=True)
    grid1 = AgGrid(ranking_excesso, gridOptions=gb1.build(), update_mode=GridUpdateMode.SELECTION_CHANGED)
    selecionado_1 = grid1["selected_rows"]

with col2:
    st.subheader("⏰ Fora do Turno")
    gb2 = GridOptionsBuilder.from_dataframe(ranking_turno)
    gb2.configure_selection('single', use_checkbox=True)
    grid2 = AgGrid(ranking_turno, gridOptions=gb2.build(), update_mode=GridUpdateMode.SELECTION_CHANGED)
    selecionado_2 = grid2["selected_rows"]

# ---------------------- DETALHAMENTO ----------------------
st.markdown("---")
st.subheader("🔎 Detalhamento do Funcionário Selecionado")

nome_selecionado = None
if selecionado_1:
    nome_selecionado = selecionado_1[0]['Nome']
elif selecionado_2:
    nome_selecionado = selecionado_2[0]['Nome']

if nome_selecionado:
    df_func = df[df['Nome'] == nome_selecionado]
    df_func = df_func[df_func['Status'] != "OK"]

    st.markdown(f"**{nome_selecionado} teve {len(df_func)} dias com irregularidades em {mes_selecionado}.**")

    st.dataframe(
        df_func[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Status', 'Horas_extras']],
        use_container_width=True,
        column_config={
            'Data_fmt': st.column_config.TextColumn("Data"),
            'Entrada_fmt': st.column_config.TextColumn("Entrada"),
            'Saida_fmt': st.column_config.TextColumn("Saída"),
            'Status': st.column_config.TextColumn("Status"),
            'Horas_extras': st.column_config.NumberColumn("Horas Extras (h)")
        }
    )
else:
    st.info("Selecione um nome em qualquer ranking para ver os detalhes.")
