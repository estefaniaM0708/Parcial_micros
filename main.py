# main.py  -  ESP32-S3 "CARRO" (MicroPython)
# Carro recolector de vasos: aparcamiento por voz, seguidor de línea y esquive
# de obstáculos. Recibe órdenes por Wi-Fi (HTTP) desde la app de Streamlit,
# que convierte la voz en texto.
#
# Rutas HTTP:  /cmd?c=estacionar   /cmd?c=meta   /cmd?c=adelante ...   /estado
# Órdenes:     estacionar | meta | alto | adelante | atras | izquierda | derecha | base

import asyncio
import json
import time
import network
from machine import Pin, PWM, time_pulse_us

# ------------------------------------------------------------------ CONFIGURACION
WIFI_SSID = "MI_RED"
WIFI_CLAVE = "MI_CLAVE"
AP_SSID, AP_CLAVE = "Carro-Monedas", "12345678"

# TB6612FNG (A = motor izquierdo, B = motor derecho)
AIN1, AIN2, PWMA = 4, 5, 6
BIN1, BIN2, PWMB = 7, 15, 16
STBY = 17
# HC-SR04 (ECHO con divisor 1 kΩ / 2 kΩ: 5 V -> 3,3 V)
TRIG_FRONTAL, ECHO_FRONTAL = 1, 2
TRIG_TRASERO, ECHO_TRASERO = 41, 42
# Sensores de línea TCRT5000 (salida digital: 1 = negro / línea)
IR_IZQ, IR_CEN, IR_DER = 8, 9, 10
LINEA_ES = 1
PIN_BUZZER = 18

V_CRUCERO = 0.55          # fracción de PWM en la pista
V_GIRO = 0.45
DIST_PARQUEO_CM = 6.0     # se detiene a esta distancia de la estación
DIST_OBSTACULO_CM = 18.0
LADOS_ESQUIVE = ["der", "izq", "der"]    # por dónde rodear cada obstáculo de la pista
T_MANUAL_RECTO, T_MANUAL_GIRO = 1000, 450   # ms (calibrar en el piso real)
RAMPA = 0.08              # cambio máximo de PWM por ciclo de 20 ms (arranque suave)


# ------------------------------------------------------------------ HARDWARE
class Motor:
    def __init__(self, in1, in2, pwm, invertido=False):
        self.in1 = Pin(in1, Pin.OUT, value=0)
        self.in2 = Pin(in2, Pin.OUT, value=0)
        self.pwm = PWM(Pin(pwm), freq=1000, duty_u16=0)
        self.inv = invertido
        self.actual = 0.0

    def poner(self, v):
        v = max(-1.0, min(1.0, v))
        if self.inv:
            v = -v
        self.in1.value(1 if v > 0 else 0)
        self.in2.value(1 if v < 0 else 0)
        self.pwm.duty_u16(int(abs(v) * 65535))


motor_izq = Motor(AIN1, AIN2, PWMA)
motor_der = Motor(BIN1, BIN2, PWMB, invertido=True)   # montado en espejo
Pin(STBY, Pin.OUT, value=1)
trig_f, echo_f = Pin(TRIG_FRONTAL, Pin.OUT, value=0), Pin(ECHO_FRONTAL, Pin.IN)
trig_t, echo_t = Pin(TRIG_TRASERO, Pin.OUT, value=0), Pin(ECHO_TRASERO, Pin.IN)
ir = [Pin(IR_IZQ, Pin.IN), Pin(IR_CEN, Pin.IN), Pin(IR_DER, Pin.IN)]
buzzer = Pin(PIN_BUZZER, Pin.OUT, value=0)


def distancia_cm(trig, echo):
    trig.value(0)
    time.sleep_us(2)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    t = time_pulse_us(echo, 1, 15000)      # 15 ms = 2,5 m como máximo
    return 250.0 if t < 0 else t / 58.0


def linea():
    return [1 if s.value() == LINEA_ES else 0 for s in ir]


# ------------------------------------------------------------------ ESTADO
st = {"modo": "LIBRE", "mensaje": "Listo", "dist_frontal_cm": 0.0, "dist_trasera_cm": 0.0,
      "linea": [0, 0, 0], "vel": [0.0, 0.0], "esquivados": 0, "ip": ""}
objetivo = [0.0, 0.0]       # PWM deseado (izquierdo, derecho)
manual_hasta = 0
ultimo_giro = 1
pasos_esquive = []


def ordenar(texto):
    """Interpreta la orden que llega de la app (texto reconocido por voz)."""
    global manual_hasta, pasos_esquive
    t = texto.lower()
    ahora = time.ticks_ms()
    if "estacion" in t or "parque" in t or "aparca" in t:
        st["modo"], st["mensaje"] = "ESTACIONANDO", "Retrocediendo hacia la estacion"
    elif "meta" in t or "entrega" in t:
        st["modo"], st["mensaje"] = "LINEA", "Siguiendo la pista hacia la meta"
        st["esquivados"] = 0
    elif "alto" in t or "para" in t or "deten" in t:
        st["modo"], st["mensaje"] = "LIBRE", "Alto"
        pasos_esquive = []
    elif "adelante" in t or "avanza" in t:
        st["modo"], objetivo[0], objetivo[1] = "MANUAL", V_GIRO, V_GIRO
        manual_hasta = time.ticks_add(ahora, T_MANUAL_RECTO)
    elif "atras" in t or "retrocede" in t:
        st["modo"], objetivo[0], objetivo[1] = "MANUAL", -V_GIRO, -V_GIRO
        manual_hasta = time.ticks_add(ahora, T_MANUAL_RECTO)
    elif "izquierda" in t:
        st["modo"], objetivo[0], objetivo[1] = "MANUAL", -V_GIRO, V_GIRO
        manual_hasta = time.ticks_add(ahora, T_MANUAL_GIRO)
    elif "derecha" in t:
        st["modo"], objetivo[0], objetivo[1] = "MANUAL", V_GIRO, -V_GIRO
        manual_hasta = time.ticks_add(ahora, T_MANUAL_GIRO)
    else:
        return False
    return True


def plan_esquive(lado):
    """Secuencia (izq, der, ms) para rodear un obstáculo y volver a la línea."""
    s = 1 if lado == "der" else -1
    g = V_GIRO
    return [(g * s, -g * s, 420), (V_CRUCERO, V_CRUCERO, 900), (-g * s, g * s, 420),
            (V_CRUCERO, V_CRUCERO, 1000), (-g * s, g * s, 420), ("BUSCAR", s, 2500)]


async def control():
    """Bucle de control a 50 Hz."""
    global ultimo_giro, pasos_esquive
    t_paso = time.ticks_ms()
    t_pitido = 0
    while True:
        ahora = time.ticks_ms()
        modo = st["modo"]
        d_f = distancia_cm(trig_f, echo_f)
        d_t = distancia_cm(trig_t, echo_t) if modo in ("ESTACIONANDO", "LIBRE", "ESTACIONADO") else st["dist_trasera_cm"]
        l = linea()
        st["dist_frontal_cm"], st["dist_trasera_cm"], st["linea"] = round(d_f, 1), round(d_t, 1), l

        if modo == "MANUAL":
            if time.ticks_diff(ahora, manual_hasta) >= 0 or (objetivo[0] > 0 and objetivo[1] > 0 and d_f < DIST_OBSTACULO_CM):
                objetivo[0] = objetivo[1] = 0.0
                st["modo"] = "LIBRE"

        elif modo == "ESTACIONANDO":
            # Aparcamiento en reversa con el ultrasonido trasero (como un sensor de parqueo)
            if d_t <= DIST_PARQUEO_CM:
                objetivo[0] = objetivo[1] = 0.0
                st["modo"], st["mensaje"] = "ESTACIONADO", "Estacionado a %.1f cm" % d_t
                buzzer.value(1)
                await asyncio.sleep_ms(400)
                buzzer.value(0)
            else:
                v = -0.45 if d_t > 25 else -0.28
                corr = 0.0
                if l[0] and not l[2]:          # la guía quedó a la izquierda (en reversa se corrige al revés)
                    corr = 0.10
                elif l[2] and not l[0]:
                    corr = -0.10
                objetivo[0], objetivo[1] = v + corr, v - corr
                periodo = max(80, int(d_t * 20))       # pitidos más rápidos al acercarse
                if time.ticks_diff(ahora, t_pitido) > periodo:
                    t_pitido = ahora
                    buzzer.value(not buzzer.value())

        elif modo == "LINEA":
            if d_f < DIST_OBSTACULO_CM:                 # obstáculo: plan de esquive
                lado = LADOS_ESQUIVE[st["esquivados"] % len(LADOS_ESQUIVE)]
                pasos_esquive = plan_esquive(lado)
                t_paso = ahora
                st["modo"], st["mensaje"] = "ESQUIVANDO", "Esquivando obstaculo por la %s" % lado
            elif l == [1, 1, 1]:                        # franja de la meta
                objetivo[0] = objetivo[1] = 0.0
                st["modo"], st["mensaje"] = "EN_META", "Llego a la meta"
            elif l[1] and not l[0] and not l[2]:
                objetivo[0] = objetivo[1] = V_CRUCERO
            elif l[0]:
                objetivo[0], objetivo[1] = 0.1, V_CRUCERO
                ultimo_giro = -1
            elif l[2]:
                objetivo[0], objetivo[1] = V_CRUCERO, 0.1
                ultimo_giro = 1
            else:                                       # perdió la línea: girar hacia el último lado
                objetivo[0], objetivo[1] = (V_GIRO, -V_GIRO * 0.3) if ultimo_giro > 0 else (-V_GIRO * 0.3, V_GIRO)

        elif modo == "ESQUIVANDO":
            if not pasos_esquive:
                st["modo"] = "LINEA"
                st["esquivados"] += 1
            else:
                a, b, ms = pasos_esquive[0]
                if a == "BUSCAR":                       # avanzar hasta reencontrar la línea
                    objetivo[0] = objetivo[1] = V_CRUCERO * 0.7
                    if l[1] or time.ticks_diff(ahora, t_paso) > ms:
                        pasos_esquive.pop(0)
                        pasos_esquive.insert(0, (V_GIRO * b, -V_GIRO * b, 300))   # alinearse
                        t_paso = ahora
                else:
                    objetivo[0], objetivo[1] = a, b
                    if time.ticks_diff(ahora, t_paso) > ms:
                        pasos_esquive.pop(0)
                        t_paso = ahora
        else:
            objetivo[0] = objetivo[1] = 0.0
            buzzer.value(0)

        # Rampa: el PWM cambia poco a poco (movimiento suave, sin derrapes)
        for i, m in enumerate((motor_izq, motor_der)):
            d = objetivo[i] - m.actual
            m.actual += max(-RAMPA, min(RAMPA, d))
            m.poner(m.actual)
        st["vel"] = [round(motor_izq.actual, 2), round(motor_der.actual, 2)]
        await asyncio.sleep_ms(20)


# ------------------------------------------------------------------ SERVIDOR
def parsear(ruta):
    if "?" not in ruta:
        return ruta, {}
    camino, q = ruta.split("?", 1)
    args = {}
    for par in q.split("&"):
        if "=" in par:
            k, v = par.split("=", 1)
            args[k] = v.replace("+", " ").replace("%20", " ")
    return camino, args


def manejar(ruta):
    camino, args = parsear(ruta)
    if camino == "/estado":
        return "200 OK", st
    if camino == "/cmd":
        ok = ordenar(args.get("c", ""))
        return ("200 OK" if ok else "400 Bad Request"), {"ok": ok, "modo": st["modo"], "mensaje": st["mensaje"]}
    return "404 Not Found", {"rutas": ["/estado", "/cmd?c=orden"]}


async def atender(lector, escritor):
    try:
        linea_http = await lector.readline()
        partes = linea_http.decode().split(" ")
        ruta = partes[1] if len(partes) > 1 else "/"
        while True:
            h = await lector.readline()
            if not h or h == b"\r\n":
                break
        codigo, cuerpo = manejar(ruta)
        escritor.write(("HTTP/1.1 %s\r\nContent-Type: application/json\r\n"
                        "Access-Control-Allow-Origin: *\r\nConnection: close\r\n\r\n" % codigo).encode())
        escritor.write(json.dumps(cuerpo).encode())
        await escritor.drain()
    except Exception as e:
        print("HTTP error:", e)
    finally:
        escritor.close()
        await escritor.wait_closed()


def conectar_wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if WIFI_SSID != "MI_RED":
        sta.connect(WIFI_SSID, WIFI_CLAVE)
        t0 = time.ticks_ms()
        while not sta.isconnected() and time.ticks_diff(time.ticks_ms(), t0) < 10000:
            time.sleep_ms(200)
    if sta.isconnected():
        return sta.ifconfig()[0]
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=AP_SSID, password=AP_CLAVE)
    return ap.ifconfig()[0]


async def principal():
    st["ip"] = conectar_wifi()
    print("Carro listo en http://%s/estado" % st["ip"])
    await asyncio.start_server(atender, "0.0.0.0", 80)
    await control()


asyncio.run(principal())
