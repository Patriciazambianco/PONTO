import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import timedelta, time
import io

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

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Detalhes')
        writer.save()
    processed_data = output.getvalue()
    return processed_data

# Carregando e preparando dados
df = carregar_dados()
df = analisar_ponto(df)
ranking = ranking_reincidentes(df)

st.title("Análise de Ponto - Ranking Reincidentes")

# Filtros
st.sidebar.header("Filtros")

nomes = ranking['Nome'].unique().tolist()
nomes_selecionados = st.sidebar.multiselect("Selecione funcionários", nomes, default=nomes)

mostrar_fora_turno = st.sidebar.checkbox("Mostrar só quem está fora do turno", value=False)
mostrar_hora_extra = st.sidebar.checkbox("Mostrar só quem tem hora extra", value=False)

# Aplicar filtros no ranking
ranking_filtrado = ranking[ranking['Nome'].isin(nomes_selecionados)]

if mostrar_fora_turno:
    ranking_filtrado = ranking_filtrado[ranking_filtrado['Dias_fora_turno'] > 0]

if mostrar_hora_extra:
    ranking_filtrado = ranking_filtrado[ranking_filtrado['Total_horas_extra'] > 0]

st.subheader("Ranking de reincidentes (fora do turno e horas extras)")

# Mostrar ranking com detalhes clicáveis
for i, row in ranking_filtrado.iterrows():
    nome = row['Nome']
    dias_fora = int(row['Dias_fora_turno'])
    horas_extra = row['Total_horas_extra']

    with st.expander(f"{nome} - Dias fora do turno: {dias_fora}, Horas extras: {horas_extra:.2f}"):
        detalhes = df[
            (df['Nome'] == nome) & ((df['Entrada_fora_turno']) | (df['Hora_extra_flag']))
        ].copy()

        detalhes['Data_formatada'] = detalhes['Data'].dt.strftime('%d/%m/%Y')

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

# Gráfico barras com top reincidentes (dias fora + horas extras)
import matplotlib.pyplot as plt

ranking_filtrado['Score'] = ranking_filtrado['Dias_fora_turno'] + ranking_filtrado['Total_horas_extra']
ranking_filtrado = ranking_filtrado.sort_values('Score', ascending=False)

fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(ranking_filtrado['Nome'], ranking_filtrado['Score'], color='tomato')
ax.invert_yaxis()
ax.set_xlabel('Score (Dias fora + Horas extras)')
ax.set_title('Ranking de reincidentes')

st.pyplot(fig)

# Botão para download dos detalhes filtrados
detalhes_para_download = df[
    df['Nome'].isin(ranking_filtrado['Nome'])
    & ((df['Entrada_fora_turno']) | (df['Hora_extra_flag']))
].copy()

detalhes_para_download['Data'] = detalhes_para_download['Data'].dt.strftime('%d/%m/%Y')

excel_bytes = to_excel(detalhes_para_download)

st.download_button(
    label="📥 Baixar detalhes dos reincidentes em Excel",
    data=excel_bytes,
    file_name='detalhes_reincidentes.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

# Total geral de horas extras
total_horas_extras = df['Horas_extra'].sum()
st.markdown(f"### Total de horas extras (considerando só acima de 15 minutos): **{total_horas_extras:.2f} horas**")
