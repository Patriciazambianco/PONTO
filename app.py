import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import datetime
import io

# URL do arquivo Excel no GitHub raw
URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

# Paleta de cores personalizada
COLOR_MAP = {
    'fora_do_turno_total': '#0057b7',  # azul
    'hora_extra_total': '#008000',     # verde
    'agravante': '#ff6600',            # laranja
    'critico': '#cc0000'               # vermelho
}

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    # Ajuste datas
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True)

    # Ajuste horários para datetime.time (pode ter NaT)
    for col in ['Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA']:
        df[col] = pd.to_datetime(df[col], errors='coerce').dt.time

    st.write("Colunas disponíveis:", df.columns.tolist())
    return df

def diff_minutes(t1, t2):
    if pd.isna(t1) or pd.isna(t2):
        return None
    dt1 = datetime.timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
    dt2 = datetime.timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
    return abs((dt1 - dt2).total_seconds() / 60)

def fora_do_turno(entrada_real, entrada_turno):
    if pd.isna(entrada_real) or pd.isna(entrada_turno):
        return False
    diff = diff_minutes(entrada_real, entrada_turno)
    return diff > 60  # mais de 1 hora de diferença

def calc_hora_extra(entrada_real, saida_real, entrada_turno, saida_turno):
    if pd.isna(entrada_real) or pd.isna(saida_real) or pd.isna(entrada_turno) or pd.isna(saida_turno):
        return 0
    dt_entrada_real = datetime.timedelta(hours=entrada_real.hour, minutes=entrada_real.minute, seconds=entrada_real.second)
    dt_saida_real = datetime.timedelta(hours=saida_real.hour, minutes=saida_real.minute, seconds=saida_real.second)
    dt_entrada_turno = datetime.timedelta(hours=entrada_turno.hour, minutes=entrada_turno.minute, seconds=entrada_turno.second)
    dt_saida_turno = datetime.timedelta(hours=saida_turno.hour, minutes=saida_turno.minute, seconds=saida_turno.second)
    minutos_trabalhados = (dt_saida_real - dt_entrada_real).total_seconds() / 60
    minutos_turno = (dt_saida_turno - dt_entrada_turno).total_seconds() / 60
    extra = minutos_trabalhados - minutos_turno
    return extra if extra > 15 else 0  # só conta hora extra se > 15 minutos

def analisar_ponto(df):
    df['Fora_do_turno'] = df.apply(lambda r: fora_do_turno(r['Entrada 1'], r['Turnos.ENTRADA']), axis=1)
    df['Hora_extra'] = df.apply(lambda r: calc_hora_extra(r['Entrada 1'], r['Saída 1'], r['Turnos.ENTRADA'], r['Turnos.SAIDA']), axis=1)

    df['fora_do_turno_int'] = df['Fora_do_turno'].astype(int)
    df['hora_extra_int'] = df['Hora_extra'].apply(lambda x: 1 if x > 0 else 0)

    reincidentes = df.groupby('Funcionario').agg(
        fora_do_turno_total=('fora_do_turno_int', 'sum'),
        hora_extra_total=('hora_extra_int', 'sum'),
        horas_extras_sum=('Hora_extra', 'sum')
    ).reset_index()

    reincidentes['total_erros'] = reincidentes['fora_do_turno_total'] + reincidentes['hora_extra_total']

    reincidentes = reincidentes.sort_values(by='total_erros', ascending=False).reset_index(drop=True)

    def medalha(i):
        return ['🥇', '🥈', '🥉'][i] if i < 3 else ''

    reincidentes['Medalha'] = [medalha(i) for i in range(len(reincidentes))]

    return df, reincidentes

def filtrar_por_periodo(df, periodo):
    hoje = pd.Timestamp.today().normalize()
    if periodo == 'Últimos 30 dias':
        data_inicio = hoje - pd.Timedelta(days=30)
    elif periodo == 'Mês atual':
        data_inicio = hoje.replace(day=1)
    elif periodo == 'Ano atual':
        data_inicio = hoje.replace(month=1, day=1)
    else:
        data_inicio = None
    if data_inicio:
        return df[df['Data'] >= data_inicio]
    return df

def exportar_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatório')
    processed_data = output.getvalue()
    return processed_data

# --- Início do app Streamlit ---

st.set_page_config(page_title="Análise de Ponto", layout="wide")

df = carregar_dados()

st.title("📊 Análise de Ponto")

periodo = st.selectbox("Selecione o período:", ['Últimos 30 dias', 'Mês atual', 'Ano atual', 'Todos os dados'])

if periodo != 'Todos os dados':
    df_filtrado = filtrar_por_periodo(df, periodo)
else:
    df_filtrado = df.copy()

df_analisado, reincidentes = analisar_ponto(df_filtrado)

st.subheader("🏆 Ranking de Reincidentes")
reincidentes_display = reincidentes[['Medalha', 'Funcionario', 'fora_do_turno_total', 'hora_extra_total', 'horas_extras_sum']]
reincidentes_display.columns = ['🏅', 'Funcionário', 'Fora do Turno', 'Hora Extra (ocorrências)', 'Total Horas Extras']

def color_ranking(row):
    if row['Fora do Turno'] > 0 or row['Hora Extra (ocorrências)'] > 0:
        return ['background-color: #ffcccc']*5
    return ['']*5

st.dataframe(reincidentes_display.style.apply(color_ranking, axis=1), use_container_width=True)

func_selecionado = st.selectbox("Ver detalhes do funcionário:", reincidentes['Funcionario'])

if func_selecionado:
    detalhes = df_analisado[(df_analisado['Funcionario'] == func_selecionado) & ((df_analisado['Fora_do_turno']) | (df_analisado['Hora_extra'] > 0))]
    detalhes = detalhes[['Data', 'Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Fora_do_turno', 'Hora_extra']]

    detalhes['Data'] = detalhes['Data'].dt.strftime('%d/%m/%Y')
    for col in ['Entrada 1', 'Saída 1', 'Turnos.ENTRADA', 'Turnos.SAIDA']:
        detalhes[col] = detalhes[col].apply(lambda x: x.strftime('%H:%M') if pd.notna(x) else '')

    st.subheader(f"📅 Detalhes para {func_selecionado}")
    st.dataframe(detalhes, use_container_width=True)

st.subheader("📈 Ocorrências por funcionário")

fig = px.bar(
    reincidentes,
    x='Funcionario',
    y=['fora_do_turno_total', 'hora_extra_total'],
    labels={'value': 'Ocorrências', 'Funcionario': 'Funcionário', 'variable': 'Tipo de Ocorrência'},
    title='Fora do turno vs Hora extra',
    color_discrete_map=COLOR_MAP
)

fig.update_layout(barmode='stack', xaxis_tickangle=-45, height=450)
st.plotly_chart(fig, use_container_width=True)

st.download_button(
    label="📥 Baixar relatório Excel filtrado",
    data=exportar_excel(df_analisado),
    file_name='relatorio_ponto.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

