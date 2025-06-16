import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto – Análise de Horas Extras e Fora do Turno")

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

    # Fora do turno = ±1 hora
    df['Entrada_fora_turno'] = df.apply(
        lambda row: (
            row['Minutos_entrada'] is not None and 
            row['Minutos_turno_entrada'] is not None and 
            abs(row['Minutos_entrada'] - row['Minutos_turno_entrada']) > 60
        ),
        axis=1
    )

    # Minutos trabalhados no dia
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

    df['Hora_extra'] = df['Minutos_extras'] > 15

    # Formatação para exibição
    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    # Coluna de mês para filtro
    df['AnoMes'] = df['Data'].dt.to_period('M')

    return df

df = carregar_dados()
df = analisar_ponto(df)

# Filtro por mês
meses_disponiveis = sorted(df['AnoMes'].dropna().unique())
mes_selecionado = st.selectbox("Selecione o mês para análise:", meses_disponiveis)

df = df[df['AnoMes'] == mes_selecionado]

# Ranking - Total de Horas Extras por funcionário (em horas)
ranking_horas = df[df['Hora_extra']].groupby('Nome')['Minutos_extras'].sum().reset_index()
ranking_horas['Horas_extras'] = (ranking_horas['Minutos_extras'] / 60).round(2)
ranking_horas = ranking_horas.sort_values(by='Horas_extras', ascending=False)

# Ranking - Total de Dias Fora do Turno por funcionário
ranking_fora_turno = df[df['Entrada_fora_turno']].groupby('Nome').size().reset_index(name='Dias_fora_turno')
ranking_fora_turno = ranking_fora_turno.sort_values(by='Dias_fora_turno', ascending=False)

# Exibir rankings lado a lado
col1, col2 = st.columns(2)

with col1:
    st.subheader("🚀 Ranking - Total de Horas Extras")
    gb = GridOptionsBuilder.from_dataframe(ranking_horas)
    gb.configure_selection(selection_mode='single', use_checkbox=True)
    grid_horas = AgGrid(
        ranking_horas,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        theme='fresh',
        fit_columns_on_grid_load=True
    )
    
with col2:
    st.subheader("⏰ Ranking - Total de Dias Fora do Turno")
    gb2 = GridOptionsBuilder.from_dataframe(ranking_fora_turno)
    gb2.configure_selection(selection_mode='single', use_checkbox=True)
    grid_fora_turno = AgGrid(
        ranking_fora_turno,
        gridOptions=gb2.build(),
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        theme='fresh',
        fit_columns_on_grid_load=True
    )

# Mostrar detalhes ao clicar no nome do funcionário (nas duas tabelas)
st.markdown("---")
st.subheader("🔎 Detalhes das Infrações")

selected_rows_horas = grid_horas['selected_rows']
selected_rows_fora = grid_fora_turno['selected_rows']

# Função para exibir detalhes das infrações de um funcionário
def mostrar_infracoes(nome):
    df_func = df[df['Nome'] == nome].copy()
    df_func = df_func[(df_func['Hora_extra']) | (df_func['Entrada_fora_turno'])].copy()

    if df_func.empty:
        st.write(f"Nenhuma infração encontrada para {nome} no mês selecionado.")
        return

    df_func['Tipo de Infração'] = df_func.apply(
        lambda row: "Hora Extra" if row['Hora_extra'] else ("Fora do Turno" if row['Entrada_fora_turno'] else "OK"),
        axis=1
    )
    df_func['Horas_extras'] = df_func['Minutos_extras'].apply(lambda x: round(x/60, 2) if x > 0 else 0)

    df_func_display = df_func[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Tipo de Infração', 'Horas_extras']].copy()

    # Formatando colunas de turno
    df_func_display['Turno Entrada'] = df_func_display['Turnos.ENTRADA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df_func_display['Turno Saída'] = df_func_display['Turnos.SAIDA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    df_func_display = df_func_display.drop(columns=['Turnos.ENTRADA', 'Turnos.SAIDA'])
    df_func_display = df_func_display.rename(columns={
        'Data_fmt': 'Data',
        'Entrada_fmt': 'Entrada',
        'Saida_fmt': 'Saída',
        'Tipo de Infração': 'Infração',
        'Horas_extras': 'Horas Extras'
    })

    st.write(f"Infrações para **{nome}**:")
    st.dataframe(df_func_display, use_container_width=True)

# Verificar seleção em horas extras
if selected_rows_horas is not None and len(selected_rows_horas) > 0:
    nome_selecionado = selected_rows_horas[0]['Nome']
    mostrar_infracoes(nome_selecionado)

# Verificar seleção em fora do turno
elif selected_rows_fora is not None and len(selected_rows_fora) > 0:
    nome_selecionado = selected_rows_fora[0]['Nome']
    mostrar_infracoes(nome_selecionado)
