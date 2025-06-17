import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from datetime import datetime
import plotly.express as px

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto - Horas Extras e Fora do Turno")

URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

def minutos_para_horas(minutos):
    if pd.isna(minutos) or minutos <= 0:
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

    df['Hora_extra'] = df['Minutos_extras'] > 15

    df['Semana_Ano'] = df['Data'].dt.strftime('%Y-%U')
    df['Coordenador'] = df['MICROSIGA.COORDENADOR_IMEDIATO'].fillna('Sem Coordenador')
    df['Nome'] = df['Nome'].fillna('Sem Nome')

    return df

df = carregar_dados()
df = analisar_ponto(df)

coordenadores = sorted(df['Coordenador'].unique())
selecionado_coordenador = st.selectbox("Selecione o Coordenador:", ['Todos'] + coordenadores)

if selecionado_coordenador != 'Todos':
    df_filtrado = df[df['Coordenador'] == selecionado_coordenador]
else:
    df_filtrado = df.copy()

# Ranking Top 20 Horas Extras (soma minutos extras por funcionário)
ranking_horas_extras = (
    df_filtrado.groupby('Nome')['Minutos_extras']
    .sum()
    .reset_index()
    .sort_values('Minutos_extras', ascending=False)
    .head(20)
)
ranking_horas_extras['Horas_extras'] = ranking_horas_extras['Minutos_extras'].apply(minutos_para_horas)

# Ranking Top 20 Jornadas Fora do Turno (contagem por funcionário)
ranking_fora_turno = (
    df_filtrado[df_filtrado['Entrada_fora_turno']]
    .groupby('Nome')
    .size()
    .reset_index(name='Dias_fora_turno')
    .sort_values('Dias_fora_turno', ascending=False)
    .head(20)
)

# Colunas de seleção para mostrar os dois rankings lado a lado
col1, col2 = st.columns(2)

with col1:
    st.subheader("Top 20 Horas Extras (Horas)")
    sel_he = st.radio("Selecionar Funcionário para Detalhes:", ['Nenhum'] + ranking_horas_extras['Nome'].tolist())
    st.dataframe(ranking_horas_extras[['Nome', 'Horas_extras']].set_index('Nome'))

with col2:
    st.subheader("Top 20 Fora do Turno (Dias)")
    sel_ft = st.radio("Selecionar Funcionário para Detalhes:", ['Nenhum'] + ranking_fora_turno['Nome'].tolist())
    st.dataframe(ranking_fora_turno.set_index('Nome'))

# Mostrar detalhes do funcionário selecionado (de qualquer ranking)
nome_selecionado = None
if sel_he != 'Nenhum':
    nome_selecionado = sel_he
elif sel_ft != 'Nenhum':
    nome_selecionado = sel_ft

if nome_selecionado:
    st.markdown(f"### Detalhes de {nome_selecionado}")

    detalhes = df_filtrado[df_filtrado['Nome'] == nome_selecionado].copy()
    detalhes['Hora_extra_h'] = detalhes['Minutos_extras'].apply(minutos_para_horas)
    detalhes['Data_fmt'] = detalhes['Data'].dt.strftime('%d/%m/%Y')

    # Mostrar horas extras detalhadas por dia
    st.write("**Horas Extras Detalhadas:**")
    st.dataframe(detalhes[['Data_fmt', 'Hora_extra_h']].rename(columns={
        'Data_fmt': 'Data',
        'Hora_extra_h': 'Horas Extras'
    }))

    # Mostrar dias com entrada fora do turno
    fora_turno_detalhes = detalhes[detalhes['Entrada_fora_turno']]
    if not fora_turno_detalhes.empty:
        st.write("**Dias com Entrada Fora do Turno:**")
        fora_turno_detalhes = fora_turno_detalhes.copy()
        fora_turno_detalhes['Data_fmt'] = fora_turno_detalhes['Data'].dt.strftime('%d/%m/%Y')
        st.dataframe(fora_turno_detalhes[['Data_fmt', 'Turnos.ENTRADA', 'Entrada 1']].rename(columns={
            'Data_fmt': 'Data',
            'Turnos.ENTRADA': 'Hora de Entrada Esperada',
            'Entrada 1': 'Hora de Entrada Real'
        }))
    else:
        st.write("Nenhum dia com entrada fora do turno.")

# Tendência semanal (soma minutos extras e contagem fora do turno por semana)
tendencia = (
    df_filtrado.groupby(['Semana_Ano', 'Nome'])
    .agg(
        Minutos_extras_totais=pd.NamedAgg(column='Minutos_extras', aggfunc='sum'),
        Dias_fora_turno=pd.NamedAgg(column='Entrada_fora_turno', aggfunc='sum')
    )
    .reset_index()
)

tendencia['Horas_extras'] = tendencia['Minutos_extras_totais'].apply(minutos_para_horas)

st.subheader("Tendência Semanal (Horas Extras e Dias Fora do Turno)")

fig = px.line(
    tendencia,
    x='Semana_Ano',
    y='Horas_extras',
    color='Nome',
    title='Horas Extras Semanais',
    labels={'Semana_Ano': 'Semana (Ano-Semana)', 'Horas_extras': 'Horas Extras'}
)
st.plotly_chart(fig, use_container_width=True)

fig2 = px.line(
    tendencia,
    x='Semana_Ano',
    y='Dias_fora_turno',
    color='Nome',
    title='Dias Fora do Turno Semanais',
    labels={'Semana_Ano': 'Semana (Ano-Semana)', 'Dias_fora_turno': 'Dias Fora do Turno'}
)
st.plotly_chart(fig2, use_container_width=True)

# Botão para exportar os dados filtrados detalhados para Excel
def to_excel(dados_extras, dados_fora_turno):
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        dados_extras.to_excel(writer, index=False, sheet_name='Horas_Extras')
        dados_fora_turno.to_excel(writer, index=False, sheet_name='Fora_do_Turno')
        writer.save()
    processed_data = output.getvalue()
    return processed_data

if st.button("Exportar Dados Filtrados para Excel"):
    df_extras_export = df_filtrado[df_filtrado['Minutos_extras'] > 0][
        ['Nome', 'Data', 'Minutos_extras']
    ].copy()
    df_extras_export['Horas Extras'] = df_extras_export['Minutos_extras'].apply(minutos_para_horas)
    df_extras_export.drop(columns=['Minutos_extras'], inplace=True)

    df_fora_turno_export = df_filtrado[df_filtrado['Entrada_fora_turno']][
        ['Nome', 'Data', 'Turnos.ENTRADA', 'Entrada 1']
    ].copy()

    excel_bytes = to_excel(df_extras_export, df_fora_turno_export)
    st.download_button(
        label="Clique para baixar o Excel",
        data=excel_bytes,
        file_name="Relatorio_Ponto.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
