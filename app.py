import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto – Análise de Horas Extras e Fora do Turno")

# URL do Excel
URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    # Ajusta os tipos de dados
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], format='%H:%M:%S', errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], format='%H:%M:%S', errors='coerce').dt.time
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce').dt.time

    return df

# Função para calcular minutos de diferença entre dois horários
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

    # Entrada fora do turno = diferença > 60 minutos
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

    # Minutos extras = minutos trabalhados - minutos previstos no turno
    df['Minutos_extras'] = df.apply(
        lambda row: (row['Minutos_trabalhados'] - (row['Minutos_turno_saida'] - row['Minutos_turno_entrada']))
        if (row['Minutos_trabalhados'] is not None and row['Minutos_turno_saida'] is not None and row['Minutos_turno_entrada'] is not None)
        else 0,
        axis=1
    )

    df['Hora_extra'] = df['Minutos_extras'] > 15  # Só conta se passar de 15 min

    # Formatação para exibição
    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    return df

# ---------------------------- RODANDO ----------------------------

df = carregar_dados()
df = analisar_ponto(df)

# --- FILTRO POR MÊS ---
df['AnoMes'] = df['Data'].dt.to_period('M')
meses_disponiveis = sorted(df['AnoMes'].dropna().unique())
meses_fmt = [str(m) for m in meses_disponiveis]

mes_selecionado = st.sidebar.selectbox("Selecione o mês:", meses_fmt)

# Filtra o dataframe pelo mês escolhido
df_filtrado = df[df['AnoMes'].astype(str) == mes_selecionado]

# --- RANKINGS ---

# Ranking: total horas extras (somando minutos extras) por funcionário no mês
ranking_excesso = (
    df_filtrado[df_filtrado['Hora_extra']]
    .groupby('Nome')['Minutos_extras']
    .sum()
    .reset_index()
    .rename(columns={'Minutos_extras': 'Total_Minutos_Extras'})
)
ranking_excesso['Total_Horas_Extras'] = (ranking_excesso['Total_Minutos_Extras'] / 60).round(2)

# Ranking: total de dias fora do turno por funcionário no mês
ranking_turno = (
    df_filtrado[df_filtrado['Entrada_fora_turno']]
    .groupby('Nome')['Data']
    .nunique()  # conta os dias únicos
    .reset_index()
    .rename(columns={'Data': 'Dias_Fora_do_Turno'})
)

# Mostrando rankings
col1, col2 = st.columns(2)
with col1:
    st.subheader("🚀 Ranking - Total de Horas Extras no mês")
    st.dataframe(
        ranking_excesso.sort_values(by='Total_Horas_Extras', ascending=False),
        use_container_width=True,
        column_config={
            'Nome': 'Funcionário',
            'Total_Horas_Extras': 'Horas Extras'
        }
    )
with col2:
    st.subheader("⏰ Ranking - Dias Fora do Turno no mês")
    st.dataframe(
        ranking_turno.sort_values(by='Dias_Fora_do_Turno', ascending=False),
        use_container_width=True,
        column_config={
            'Nome': 'Funcionário',
            'Dias_Fora_do_Turno': 'Dias Fora do Turno'
        }
    )

# --- DETALHAMENTO POR FUNCIONÁRIO ---

st.markdown("---")
st.subheader("🔎 Detalhamento por Funcionário")

# Lista dos funcionários com alguma irregularidade no mês
nomes_extras = set(ranking_excesso['Nome'].tolist())
nomes_fora_turno = set(ranking_turno['Nome'].tolist())
todos_func = sorted(list(nomes_extras.union(nomes_fora_turno)))

funcionario = st.selectbox("Escolha um funcionário para ver os dias e horários de irregularidade:", todos_func)

if funcionario:
    df_func = df_filtrado[df_filtrado['Nome'] == funcionario].copy()

    # Criar status detalhado
    def status_linha(row):
        if row['Hora_extra']:
            return "Hora Extra"
        elif row['Entrada_fora_turno']:
            return "Fora do Turno"
        else:
            return "OK"

    df_func['Status'] = df_func.apply(status_linha, axis=1)
    df_func = df_func[df_func['Status'] != "OK"].copy()

    df_func['Horas_extras'] = df_func['Minutos_extras'].apply(lambda x: round(x/60, 2) if x > 0 else 0)

    # Mostrar os dados detalhados na tabela com cores
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

    gb = GridOptionsBuilder.from_dataframe(df_func[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Status', 'Horas_extras']])
    gb.configure_columns(['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Status', 'Horas_extras'], 
                         header_checkbox=True)
    gb.configure_column('Horas_extras', type=['numericColumn','numberColumnFilter','customNumericFormat'], precision=2)
    gb.configure_grid_options(domLayout='normal')
    grid_options = gb.build()

    AgGrid(
        df_func[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Status', 'Horas_extras']],
        gridOptions=grid_options,
        enable_enterprise_modules=False,
        update_mode=GridUpdateMode.NO_UPDATE,
        theme='alpine',
        height=300,
        fit_columns_on_grid_load=True,
        reload_data=True
    )
