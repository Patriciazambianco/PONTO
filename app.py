import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime, timedelta

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
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if (pd.notnull(row['Entrada 1']) and pd.notnull(row['Saída 1'])) else None,
        axis=1
    )

    df['Minutos_extras'] = df.apply(
        lambda row: (
            row['Minutos_trabalhados'] - (row['Minutos_turno_saida'] - row['Minutos_turno_entrada'])
            if (row['Minutos_trabalhados'] is not None and 
                row['Minutos_turno_saida'] is not None and 
                row['Minutos_turno_entrada'] is not None)
            else 0
        ),
        axis=1
    )

    df['Hora_extra'] = df['Minutos_extras'] > 15

    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Turno_entrada_fmt'] = df['Turnos.ENTRADA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Turno_saida_fmt'] = df['Turnos.SAIDA'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')

    return df

# Load and process
df = carregar_dados()
df = analisar_ponto(df)

# Filtro mês
meses_disponiveis = df['Data'].dt.to_period('M').dropna().unique()
meses_disponiveis = sorted(meses_disponiveis, reverse=True)

mes_selecionado = st.sidebar.selectbox(
    "Escolha o mês para análise:",
    options=meses_disponiveis,
    format_func=lambda x: x.strftime('%m/%Y')
)

df_mes = df[df['Data'].dt.to_period('M') == mes_selecionado]

# Rankings
ranking_excesso = df_mes[df_mes['Hora_extra']].groupby('Nome').agg(
    Dias_com_hora_extra=('Hora_extra', 'count'),
    Total_Minutos_Extras=('Minutos_extras', 'sum')
).reset_index()
ranking_excesso['Total_Horas_Extras'] = (ranking_excesso['Total_Minutos_Extras'] / 60).round(2)

ranking_turno = df_mes[df_mes['Entrada_fora_turno']].groupby('Nome').agg(
    Dias_fora_do_turno=('Entrada_fora_turno', 'count')
).reset_index()

col1, col2 = st.columns(2)
with col1:
    st.subheader("🚀 Ranking - Horas Extras (horas totais no mês)")
    st.dataframe(
        ranking_excesso.sort_values(by='Total_Horas_Extras', ascending=False)[['Nome', 'Dias_com_hora_extra', 'Total_Horas_Extras']],
        use_container_width=True,
        column_config={
            'Nome': 'Funcionário',
            'Dias_com_hora_extra': 'Dias com Hora Extra',
            'Total_Horas_Extras': 'Horas Extras'
        }
    )
with col2:
    st.subheader("⏰ Ranking - Dias Fora do Turno")
    st.dataframe(
        ranking_turno.sort_values(by='Dias_fora_do_turno', ascending=False),
        use_container_width=True,
        column_config={
            'Nome': 'Funcionário',
            'Dias_fora_do_turno': 'Dias Fora do Turno'
        }
    )

# Detalhamento fixo para todos os infratores
st.markdown("---")
st.subheader("🔎 Detalhamento dos Infratores")

# Pega só quem tem alguma irregularidade
infratores = pd.merge(
    ranking_excesso[['Nome', 'Total_Horas_Extras']],
    ranking_turno[['Nome', 'Dias_fora_do_turno']],
    on='Nome',
    how='outer'
).fillna(0)

# Ordena pelo total de horas extras
infratores = infratores.sort_values(by='Total_Horas_Extras', ascending=False)

# Merge com dados do mês para detalhes por funcionário
df_irregular = df_mes[
    (df_mes['Hora_extra']) | (df_mes['Entrada_fora_turno'])
].copy()

# Para ordenar pelo ranking, criamos uma coluna 'Ordem' com a posição na tabela de infratores
df_irregular = df_irregular.merge(
    infratores[['Nome']],
    on='Nome',
    how='left'
)

df_irregular['Horas_extras'] = df_irregular['Minutos_extras'].apply(lambda x: round(x / 60, 2) if x > 0 else 0)

# Ordena por funcionário com mais horas extras e depois pela data
df_irregular = df_irregular.sort_values(
    by=['Nome', 'Data']
)

# Mostrar tabela com as colunas pedidas
st.dataframe(
    df_irregular[['Nome', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turno_entrada_fmt', 'Turno_saida_fmt', 'Horas_extras', 'Entrada_fora_turno', 'Hora_extra']],
    use_container_width=True,
    column_config={
        'Nome': 'Funcionário',
        'Data_fmt': 'Data',
        'Entrada_fmt': 'Entrada',
        'Saida_fmt': 'Saída',
        'Turno_entrada_fmt': 'Turno Entrada',
        'Turno_saida_fmt': 'Turno Saída',
        'Horas_extras': 'Horas Extras',
        'Entrada_fora_turno': 'Fora do Turno',
        'Hora_extra': 'Hora Extra'
    }
)


