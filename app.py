"""
app.py  -  Dashboard en tiempo real + control del carro por voz (Streamlit)

Funciona con dos orígenes de datos:
  * Simulación (PyBullet): lee 5_simulacion/estado_sim.json y envía las órdenes
    al simulador por UDP (127.0.0.1:5005).
  * Sistema real (ESP32-S3): lee /estado de la estación y del carro por Wi-Fi
    (HTTP) y envía las órdenes al carro (/cmd) y a la estación (/entregar).

Ejecutar:  streamlit run app.py
"""

import json
import os
import re
import socket
import time
import unicodedata
import urllib.parse

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

try:
    from streamlit_mic_recorder import speech_to_text
except ImportError:          # la app funciona igual con botones y texto
    speech_to_text = None

AQUI = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_SIM = os.path.join(AQUI, "..", "5_simulacion", "estado_sim.json")
DENOMINACIONES = [50, 100, 200, 500, 1000]
PESOS = {50: 2.00, 100: 3.34, 200: 4.61, 500: 7.14, 1000: 9.95}

st.set_page_config(page_title="Logística de Monedas Inteligentes", page_icon="🪙", layout="wide")

# ------------------------------------------------------------------ BARRA LATERAL
st.sidebar.title("⚙️ Conexión")
origen = st.sidebar.radio("Origen de datos", ["Simulación (PyBullet)", "Sistema real (ESP32-S3)"])
SIM = origen.startswith("Simulación")
ip_estacion = st.sidebar.text_input("IP de la estación", "192.168.1.50", disabled=SIM)
ip_carro = st.sidebar.text_input("IP del carro", "192.168.1.51", disabled=SIM)
intervalo = st.sidebar.slider("Actualizar cada (s)", 0.5, 5.0, 1.0, 0.5)
st.sidebar.caption("En modo real, el PC y las dos ESP32-S3 deben estar en la misma red Wi-Fi.")

if "historial" not in st.session_state:
    st.session_state.historial = []
if "registro" not in st.session_state:
    st.session_state.registro = []


# ------------------------------------------------------------------ DATOS
def leer_estado():
    """Estado normalizado del sistema (simulado o real)."""
    if SIM:
        try:
            with open(ARCHIVO_SIM, encoding="utf-8") as f:
                e = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None, "Inicia la simulación: python simulacion_sistema.py"
        return {
            "conteo": {int(k): v for k, v in e["conteo"].items()},
            "valor_total": e["valor_total"], "peso_total_g": e["peso_total_g"],
            "monedas_total": e["monedas_total"], "rechazadas": e["rechazadas"],
            "estacion": e["estacion"], "ultima": e.get("ultima_moneda"),
            "vasos": e["vasos"], "carro": e["carro"], "entregas": e.get("entregas", []),
            "peso_medido_g": None,
        }, None
    try:
        est = requests.get("http://%s/estado" % ip_estacion, timeout=1.5).json()
    except Exception as ex:
        return None, "No responde la estación (%s): %s" % (ip_estacion, ex)
    try:
        car = requests.get("http://%s/estado" % ip_carro, timeout=1.5).json()
    except Exception:
        car = {"modo": "SIN CONEXION", "mensaje": "", "dist_frontal_cm": None, "dist_trasera_cm": None}
    vasos = [{"etiqueta": (int(k) if k.isdigit() else k), **v} for k, v in est["vasos"].items()]
    return {
        "conteo": {int(k): v for k, v in est["conteo"].items()},
        "valor_total": est["valor_total"], "peso_total_g": est["peso_total_g"],
        "monedas_total": est["monedas_total"], "rechazadas": est["rechazadas"],
        "estacion": est["estado"], "ultima": est.get("ultima"), "vasos": vasos,
        "carro": car, "entregas": [], "peso_medido_g": est.get("peso_medido_g"),
    }, None


def sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def interpretar(texto):
    """Convierte la frase dicha en una orden del sistema."""
    t = sin_tildes(texto)
    if any(p in t for p in ("estaciona", "parquea", "aparca", "zona de carga")):
        return "estacionar"
    if "carga" in t or "subir el vaso" in t:
        numeros = re.findall(r"\d+", t.replace(".", ""))
        palabras = re.findall(r"[a-z]+", t)
        nombres = {50: "cincuenta", 100: "cien", 200: "doscientos", 500: "quinientos", 1000: "mil"}
        for d in sorted(DENOMINACIONES, reverse=True):
            if str(d) in numeros or nombres[d] in palabras:
                return "cargar %d" % d
        return "cargar"
    if "meta" in t or "entrega" in t:
        return "meta"
    if any(p in t for p in ("alto", "para", "detente", "frena")):
        return "alto"
    if "base" in t or "casa" in t or "garaje" in t:
        return "base"
    if "adelante" in t or "avanza" in t:
        return "adelante"
    if "atras" in t or "retrocede" in t or "reversa" in t:
        return "atras"
    if "izquierda" in t:
        return "izquierda"
    if "derecha" in t:
        return "derecha"
    return None


def enviar(orden):
    """Envía la orden al simulador (UDP) o a las ESP32-S3 (HTTP)."""
    if SIM:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(orden.encode("utf-8"), ("127.0.0.1", 5005))
        s.close()
        return "Enviado al simulador"
    try:
        if orden.startswith("cargar"):
            partes = orden.split()
            url = "http://%s/entregar" % ip_estacion + (("?valor=" + partes[1]) if len(partes) > 1 else "")
        else:
            url = "http://%s/cmd?c=%s" % (ip_carro, urllib.parse.quote(orden))
        return requests.get(url, timeout=2).text
    except Exception as ex:
        return "Error: %s" % ex


def registrar(origen_txt, texto, orden, respuesta):
    st.session_state.registro.insert(0, {"hora": time.strftime("%H:%M:%S"), "origen": origen_txt,
                                         "dicho": texto, "orden": orden or "—", "respuesta": str(respuesta)[:80]})


# ------------------------------------------------------------------ INTERFAZ
st.title("🪙 Sistema de Logística de Monedas Inteligentes")
st.caption("Grupo 5 · Selector en cadena de vasos por visión computacional · Carro con ESP32-S3 y aparcamiento por voz")
tab_dash, tab_voz = st.tabs(["📊 Dashboard en tiempo real", "🎙️ Carro por voz"])

with tab_dash:
    @st.fragment(run_every=intervalo)
    def panel():
        e, error = leer_estado()
        if error:
            st.warning(error)
            return
        h = st.session_state.historial
        h.append({"t": time.strftime("%H:%M:%S"), "valor": e["valor_total"], "monedas": e["monedas_total"]})
        del h[:-120]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("💰 Valor procesado", "$%s" % format(e["valor_total"], ",").replace(",", "."))
        c2.metric("🪙 Monedas", e["monedas_total"])
        c3.metric("⚖️ Peso", "%.2f g" % e["peso_total_g"])
        c4.metric("🚫 Rechazadas", e["rechazadas"])
        c5.metric("🏭 Estación", e["estacion"])

        df = pd.DataFrame({"Denominación": ["$%d" % d for d in DENOMINACIONES],
                           "Cantidad": [e["conteo"].get(d, 0) for d in DENOMINACIONES],
                           "Valor": [d * e["conteo"].get(d, 0) for d in DENOMINACIONES],
                           "Peso (g)": [round(PESOS[d] * e["conteo"].get(d, 0), 2) for d in DENOMINACIONES]})
        g1, g2, g3 = st.columns(3)
        g1.plotly_chart(px.bar(df, x="Denominación", y="Cantidad", text="Cantidad", color="Denominación",
                               title="Monedas por denominación"), use_container_width=True)
        g2.plotly_chart(px.pie(df, names="Denominación", values="Valor", title="Valor por denominación",
                               hole=0.45), use_container_width=True)
        g3.plotly_chart(px.line(pd.DataFrame(h), x="t", y="valor", markers=True,
                                title="Valor acumulado en el tiempo"), use_container_width=True)

        izq, der = st.columns([3, 2])
        with izq:
            st.subheader("🥤 Cadena de vasos")
            vasos = pd.DataFrame(e["vasos"])
            if not vasos.empty:
                vasos["etiqueta"] = vasos["etiqueta"].apply(lambda v: "$%d" % v if isinstance(v, int) else str(v))
                st.dataframe(vasos.rename(columns={"etiqueta": "Vaso", "monedas": "Monedas", "valor": "Valor ($)",
                                                   "peso": "Peso (g)"}), hide_index=True, use_container_width=True)
            if e["ultima"]:
                st.info("Última moneda: %s" % json.dumps(e["ultima"], ensure_ascii=False))
            if e.get("peso_medido_g") is not None:
                st.caption("Peso medido por la celda de carga en la entrega: %.2f g" % e["peso_medido_g"])
        with der:
            st.subheader("🚗 Carro")
            car = e["carro"]
            a, b = st.columns(2)
            a.metric("Modo", car.get("modo", "—"))
            b.metric("Sensor trasero", "%s cm" % car.get("dist_trasera_cm"))
            st.write(car.get("mensaje", ""))
            if car.get("carga"):
                st.success("Carga: vaso de $%s con %d monedas ($%d)" % (
                    car["carga"]["etiqueta"], car["carga"]["monedas"], car["carga"]["valor"]))
            if e["entregas"]:
                st.write("Entregas en la meta:")
                st.dataframe(pd.DataFrame(e["entregas"]), hide_index=True, use_container_width=True)

    panel()

with tab_voz:
    st.subheader("🎙️ Aparcamiento y control por voz")
    st.write("Di por ejemplo: **«estaciona el carro»**, **«carga el vaso de quinientos»**, "
             "**«ve a la meta»**, **«alto»**, **«gira a la izquierda»**.")
    if speech_to_text is not None:
        texto = speech_to_text(language="es", start_prompt="🎤 Hablar", stop_prompt="⏹️ Enviar",
                               just_once=True, use_container_width=True, key="voz")
        if texto:
            orden = interpretar(texto)
            respuesta = enviar(orden) if orden else "No entendí la orden"
            registrar("voz", texto, orden, respuesta)
            (st.success if orden else st.error)("🗣️ «%s» → %s" % (texto, orden or "sin orden"))
    else:
        st.warning("Instala streamlit-mic-recorder para usar el micrófono (pip install streamlit-mic-recorder).")

    escrito = st.text_input("…o escribe la orden", placeholder="estaciona el carro")
    if st.button("Enviar texto") and escrito:
        orden = interpretar(escrito)
        registrar("texto", escrito, orden, enviar(orden) if orden else "No entendí la orden")

    st.write("Botones rápidos:")
    cols = st.columns(8)
    for col, orden in zip(cols, ["estacionar", "cargar", "meta", "alto", "adelante", "atras", "izquierda", "derecha"]):
        if col.button(orden.capitalize(), use_container_width=True):
            registrar("botón", orden, orden, enviar(orden))

    if st.session_state.registro:
        st.dataframe(pd.DataFrame(st.session_state.registro[:15]), hide_index=True, use_container_width=True)
