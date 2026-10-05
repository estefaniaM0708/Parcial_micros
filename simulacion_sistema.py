"""
simulacion_sistema.py  -  Sistema de Logística de Monedas Inteligentes (Grupo 5)

Simulación en PyBullet de todo el flujo del grupo:

  1. BANDA TRANSPORTADORA: las monedas entran por la tolva y avanzan sobre una
     banda negra hasta la zona de inspección, donde una compuerta las detiene.
  2. VISIÓN: una cámara virtual toma la imagen y la clasifica con el MISMO
     código que se usa con la cámara real (1_vision/vision_monedas.py).
  3. SELECTOR EN CADENA DE VASOS: la cadena gira hasta dejar bajo la caída el
     vaso de esa denominación; la compuerta suelta la moneda y cae en su vaso.
  4. CARRO + APARCAMIENTO POR VOZ: con la orden "estacionar" el carro se
     ubica y retrocede hasta la estación usando su sensor ultrasónico trasero;
     con "cargar" el empujador le pasa el vaso; con "meta" recorre la pista y
     esquiva los tres obstáculos hasta la bandera.

Las órdenes llegan del teclado o por UDP (puerto 5005) desde la app de
Streamlit, que las genera con reconocimiento de voz. El estado se guarda en
estado_sim.json para el dashboard.

Uso:
  python simulacion_sistema.py              (interactiva)
  python simulacion_sistema.py --demo       (todo automático: monedas, estacionar, cargar y meta)

Teclas (ventana de PyBullet activa):
  n = nueva moneda   e = estacionar   c = cargar   m = ir a la meta   b = volver a la base
  flechas = mover el carro   espacio = alto
"""

import argparse
import json
import math
import os
import random
import socket
import sys
import time

import cv2
import numpy as np
import pybullet as p
import pybullet_data

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "1_vision"))
import vision_monedas as vm  # noqa: E402

S = 4.0                              # escala de la maqueta (1 mm real = 4 mm simulados)
URDF_CARRO = os.path.join(AQUI, "..", "6_cad", "carro.urdf")
ARCHIVO_ESTADO = os.path.join(AQUI, "estado_sim.json")
PUERTO_UDP = 5005

# ---------------- banda transportadora ----------------
Z_BANDA = 0.90                       # altura de la superficie de la banda
X_TOLVA, X_INSPECCION, X_FIN = -1.75, -0.10, 0.20     # inspección a 75 mm reales del final
V_BANDA = 0.25                       # m/s simulados
ANCHO_BANDA = 0.16
GROSOR_MONEDA = 0.010

# ---------------- cadena de vasos ----------------
Z_MESA = 0.40
R_VASO, H_VASO, PARED = 0.14, 0.30, 0.012
CADENA_X0, CADENA_X1, CADENA_Y0, CADENA_Y1 = 0.30, 0.90, 0.0, -1.40
R_CURVA = (CADENA_X1 - CADENA_X0) / 2
LARGO_CADENA = 2 * (CADENA_Y0 - CADENA_Y1) + 2 * math.pi * R_CURVA
PUESTOS = [50, 100, 200, 500, 1000, "rechazo"]
PASO = LARGO_CADENA / len(PUESTOS)
S_CAIDA, S_ENTREGA = 0.0, LARGO_CADENA / 2
V_CADENA = 0.80                      # m/s
COLOR_VASO = {50: [0.6, 0.6, 0.65, 1], 100: [0.85, 0.65, 0.15, 1], 200: [0.75, 0.85, 0.95, 1],
              500: [0.2, 0.7, 0.3, 1], 1000: [0.95, 0.45, 0.1, 1], "rechazo": [0.85, 0.1, 0.1, 1]}
MESA_X_MAX = 1.15                    # borde de la mesa del lado del carro

# ---------------- carro y pista ----------------
R_RUEDA = 32.5 * S / 1000
VIA = 2 * (140 / 2 + 3 + 26 / 2) * S / 1000
X_DESDE_SENSOR = (220 / 2 + 14) * S / 1000     # centro del carro -> sensor trasero
POS_BASE = (3.2, -2.8, math.pi / 2)            # garaje del carro
PREPARQUEO = (2.7, -1.40)
META = (8.2, 2.6)
CAMINO_META = [(2.3, -1.40), (2.9, -1.60), (3.3, -1.78), (4.0, -1.78), (4.4, -1.45), (4.8, -0.90),
               (4.95, -0.20), (5.30, 0.35), (5.30, 0.95), (5.05, 1.55), (5.45, 2.25),
               (6.20, 2.40), (6.65, 2.20), (7.45, 2.25), (8.20, 2.60)]
CARRETERA = [(1.7, -1.4), (4.0, -1.4), (5.0, -0.4), (5.0, 1.6), (6.0, 2.6), (8.6, 2.6)]
OBSTACULOS = [(3.65, -1.00), (4.55, 0.70), (7.05, 3.05)]        # muros de ladrillo


# ===========================================================================
# Utilidades de geometría
# ===========================================================================
def punto_cadena(s):
    """Posición (x, y) y tangente sobre el óvalo de la cadena para la distancia s."""
    s %= LARGO_CADENA
    recta = CADENA_Y0 - CADENA_Y1
    if s < recta:                                         # recta izquierda (bajando)
        return CADENA_X0, CADENA_Y0 - s
    s -= recta
    curva = math.pi * R_CURVA
    if s < curva:                                         # curva inferior
        a = math.pi + s / R_CURVA
        return (CADENA_X0 + R_CURVA) + R_CURVA * math.cos(a), CADENA_Y1 + R_CURVA * math.sin(a)
    s -= curva
    if s < recta:                                         # recta derecha (subiendo)
        return CADENA_X1, CADENA_Y1 + s
    s -= recta                                            # curva superior
    a = s / R_CURVA
    return (CADENA_X0 + R_CURVA) + R_CURVA * math.cos(a), CADENA_Y0 + R_CURVA * math.sin(a)


def angulo_normal(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def caja(pos, medidas, color, masa=0.0, yaw=0.0, colision=True):
    he = [m / 2 for m in medidas]
    col = p.createCollisionShape(p.GEOM_BOX, halfExtents=he) if colision else -1
    vis = p.createVisualShape(p.GEOM_BOX, halfExtents=he, rgbaColor=color)
    return p.createMultiBody(masa, col, vis, pos, p.getQuaternionFromEuler([0, 0, yaw]))


# ===========================================================================
# Escenario
# ===========================================================================
def construir_estacion():
    largo = X_FIN - X_TOLVA + 0.05          # la banda termina justo en X_FIN
    cx = X_FIN - largo / 2
    # banda (negra) y estructura
    caja([cx, 0, Z_BANDA - 0.01], [largo, ANCHO_BANDA, 0.02], [0.06, 0.06, 0.07, 1])
    for y in (-1, 1):
        caja([cx, y * (ANCHO_BANDA / 2 + 0.02), Z_BANDA - 0.01], [largo, 0.04, 0.08], [0.03, 0.05, 0.16, 1])
    for x in (X_TOLVA + 0.05, cx, X_FIN - 0.05):
        for y in (-1, 1):
            caja([x, y * 0.1, (Z_BANDA - 0.05) / 2], [0.05, 0.05, Z_BANDA - 0.05], [0.4, 0.4, 0.45, 1])
    # rodillos de los extremos
    for x in (X_TOLVA - 0.05, X_FIN + 0.05):
        v = p.createVisualShape(p.GEOM_CYLINDER, radius=0.04, length=ANCHO_BANDA + 0.04,
                                rgbaColor=[0.2, 0.2, 0.2, 1])
        p.createMultiBody(0, -1, v, [x, 0, Z_BANDA - 0.04], p.getQuaternionFromEuler([math.pi / 2, 0, 0]))
    # tolva de entrada
    caja([X_TOLVA, 0, Z_BANDA + 0.12], [0.18, 0.22, 0.04], [0.8, 0.8, 0.85, 1], colision=False)
    # soporte y cámara de inspección
    caja([X_INSPECCION, 0.18, Z_BANDA + 0.25], [0.03, 0.03, 0.5], [0.3, 0.3, 0.3, 1], colision=False)
    caja([X_INSPECCION, 0.09, Z_BANDA + 0.5], [0.03, 0.2, 0.03], [0.3, 0.3, 0.3, 1], colision=False)
    caja([X_INSPECCION, 0, Z_BANDA + 0.5], [0.07, 0.07, 0.05], [0.05, 0.05, 0.05, 1], colision=False)
    # mesa de la cadena de vasos y la guía de la cadena
    caja([(CADENA_X0 + CADENA_X1) / 2, -0.7, Z_MESA / 2],
         [MESA_X_MAX - (CADENA_X0 - 0.45), 2.4, Z_MESA], [0.75, 0.6, 0.45, 1])
    puntos = [punto_cadena(LARGO_CADENA * i / 120) for i in range(121)]
    for a, b in zip(puntos[:-1], puntos[1:]):
        p.addUserDebugLine([a[0], a[1], Z_MESA + 0.005], [b[0], b[1], Z_MESA + 0.005], [0.1, 0.1, 0.1], 4)
    # empujador (servo) en el puesto de entrega
    xe, ye = punto_cadena(S_ENTREGA)
    empujador = caja([xe - 0.25, ye, Z_MESA + 0.08], [0.06, 0.24, 0.12], [0.9, 0.9, 0.2, 1], colision=False)
    p.addUserDebugText("ESTACION: banda + vision + cadena de vasos", [-0.9, 0.35, Z_BANDA + 0.65],
                       [0.1, 0.1, 0.4], 1.2)
    return empujador


def construir_pista():
    for a, b in zip(CARRETERA[:-1], CARRETERA[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        largo = math.hypot(dx, dy)
        caja([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, 0.003], [largo, 1.3, 0.006],
             [0.18, 0.18, 0.2, 1], yaw=math.atan2(dy, dx), colision=False)
        p.addUserDebugLine([a[0], a[1], 0.01], [b[0], b[1], 0.01], [1, 1, 1], 2)
    for x, y in CARRETERA[1:-1]:                     # curvas redondeadas
        v = p.createVisualShape(p.GEOM_CYLINDER, radius=0.65, length=0.006, rgbaColor=[0.18, 0.18, 0.2, 1])
        p.createMultiBody(0, -1, v, [x, y, 0.003])
    # zona de carga (estacionamiento)
    caja([1.75, -1.40, 0.004], [1.0, 0.9, 0.008], [0.95, 0.85, 0.1, 1], colision=False)
    p.addUserDebugText("ZONA DE CARGA", [1.45, -0.85, 0.05], [0.6, 0.5, 0], 1.3)
    # garaje
    caja([POS_BASE[0], POS_BASE[1], 0.004], [1.0, 1.0, 0.008], [0.3, 0.5, 0.9, 1], colision=False)
    p.addUserDebugText("BASE", [POS_BASE[0] - 0.2, POS_BASE[1] - 0.6, 0.05], [0.1, 0.2, 0.7], 1.3)
    # obstáculos: muros de ladrillo
    for x, y in OBSTACULOS:
        caja([x, y, 0.2], [0.35, 0.55, 0.4], [0.72, 0.25, 0.15, 1])
        for k in range(4):
            p.addUserDebugLine([x - 0.176, y - 0.28, 0.1 * k], [x - 0.176, y + 0.28, 0.1 * k], [0.9, 0.85, 0.8], 1)
    # meta: bandera a cuadros
    caja([META[0] + 0.4, META[1] + 0.55, 0.6], [0.04, 0.04, 1.2], [0.2, 0.2, 0.2, 1])
    for i in range(4):
        for j in range(3):
            color = [0.05, 0.05, 0.05, 1] if (i + j) % 2 == 0 else [1, 1, 1, 1]
            caja([META[0] + 0.4, META[1] + 0.6 + 0.08 * i, 1.1 + 0.08 * j], [0.01, 0.08, 0.08], color, colision=False)
    caja([META[0], META[1], 0.005], [0.12, 1.3, 0.01], [1, 1, 1, 1], colision=False)
    p.addUserDebugText("META", [META[0] - 0.2, META[1] - 0.8, 0.05], [0, 0, 0], 1.5)


# ===========================================================================
# Monedas
# ===========================================================================
ORO = [0.86, 0.66, 0.22, 1]
PLATA = [0.78, 0.78, 0.80, 1]


def crear_moneda(valor, pos):
    m = vm.MONEDAS[valor]
    r = m["diametro"] / 2000 * S
    c_anillo = ORO if m["anillo"] == "oro" else PLATA
    c_centro = ORO if m["centro"] == "oro" else PLATA
    col = p.createCollisionShape(p.GEOM_CYLINDER, radius=r, height=GROSOR_MONEDA)
    vis = p.createVisualShape(p.GEOM_CYLINDER, radius=r, length=GROSOR_MONEDA, rgbaColor=c_anillo)
    vc = p.createVisualShape(p.GEOM_CYLINDER, radius=r * 0.62, length=GROSOR_MONEDA * 1.2, rgbaColor=c_centro)
    cuerpo = p.createMultiBody(0.02, col, vis, pos, linkMasses=[0.001], linkCollisionShapeIndices=[-1],
                               linkVisualShapeIndices=[vc], linkPositions=[[0, 0, 0.0005]],
                               linkOrientations=[[0, 0, 0, 1]], linkInertialFramePositions=[[0, 0, 0]],
                               linkInertialFrameOrientations=[[0, 0, 0, 1]], linkParentIndices=[0],
                               linkJointTypes=[p.JOINT_FIXED], linkJointAxis=[[0, 0, 1]])
    p.changeDynamics(cuerpo, -1, ccdSweptSphereRadius=0.004, lateralFriction=0.6)
    return {"id": cuerpo, "valor": valor, "r": r, "estado": "banda", "x": pos[0], "t": 0.0,
            "detectado": None, "vaso": None, "local": None}


# ===========================================================================
# Vasos
# ===========================================================================
def crear_vaso(etiqueta, masa=0.0, relleno=0):
    n = 14
    tipos, medidas, posiciones, orient = [p.GEOM_CYLINDER], [[R_VASO + PARED, 0, 0]], [[0, 0, 0.02]], [[0, 0, 0, 1]]
    largos = [0.04]
    for i in range(n):
        a = 2 * math.pi * i / n
        rm = R_VASO + PARED / 2
        tipos.append(p.GEOM_BOX)
        medidas.append([PARED / 2, rm * math.pi / n * 1.1, H_VASO / 2])
        posiciones.append([rm * math.cos(a), rm * math.sin(a), H_VASO / 2])
        orient.append(p.getQuaternionFromEuler([0, 0, a]))
        largos.append(0)
    radios = [m[0] for m in medidas]
    col = p.createCollisionShapeArray(tipos, radii=radios, halfExtents=medidas, lengths=largos,
                                      collisionFramePositions=posiciones, collisionFrameOrientations=orient)
    vidrio = [0.85, 0.92, 1.0, 0.45]
    colores = [vidrio] * len(tipos)
    vis = p.createVisualShapeArray(tipos, radii=radios, halfExtents=medidas, lengths=largos,
                                   rgbaColors=colores, visualFramePositions=posiciones,
                                   visualFrameOrientations=orient)
    # franja de color que identifica la denominación (+ relleno de monedas si va cargado)
    t2, m2, p2, o2, c2 = [], [], [], [], []
    for i in range(n):
        a = 2 * math.pi * i / n
        rm = R_VASO + PARED * 1.2
        t2.append(p.GEOM_BOX)
        m2.append([PARED / 2, rm * math.pi / n * 1.15, 0.03])
        p2.append([rm * math.cos(a), rm * math.sin(a), H_VASO - 0.05])
        o2.append(p.getQuaternionFromEuler([0, 0, a]))
        c2.append(COLOR_VASO[etiqueta])
    if relleno:
        h = min(H_VASO - 0.06, 0.012 * relleno + 0.02)
        t2.append(p.GEOM_CYLINDER)
        m2.append([R_VASO - 0.01, 0, 0])
        p2.append([0, 0, 0.04 + h / 2])
        o2.append([0, 0, 0, 1])
        c2.append(ORO)
    franja = p.createVisualShapeArray(t2, radii=[m[0] for m in m2], halfExtents=m2,
                                      lengths=[0.0] * (len(t2) - (1 if relleno else 0)) + ([h] if relleno else []),
                                      rgbaColors=c2, visualFramePositions=p2, visualFrameOrientations=o2)
    return p.createMultiBody(masa, col, vis, [0, 0, -5], linkMasses=[0.001], linkCollisionShapeIndices=[-1],
                             linkVisualShapeIndices=[franja], linkPositions=[[0, 0, 0]],
                             linkOrientations=[[0, 0, 0, 1]], linkInertialFramePositions=[[0, 0, 0]],
                             linkInertialFrameOrientations=[[0, 0, 0, 1]], linkParentIndices=[0],
                             linkJointTypes=[p.JOINT_FIXED], linkJointAxis=[[0, 0, 1]])


# ===========================================================================
# Sistema completo
# ===========================================================================
class Sistema:
    def __init__(self, gui, demo):
        self.gui = gui
        self.demo = demo
        self.t = 0.0
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        p.setPhysicsEngineParameter(numSolverIterations=80)
        p.loadURDF("plane.urdf")
        self.empujador = construir_estacion()
        construir_pista()

        # cadena de vasos
        self.fase = 0.0              # desplazamiento de la cadena (m)
        self.fase_obj = 0.0
        self.vasos = []
        for i, etiqueta in enumerate(PUESTOS):
            self.vasos.append({"id": crear_vaso(etiqueta), "etiqueta": etiqueta, "idx": i, "monedas": []})
        self.textos_vasos = [-1] * len(PUESTOS)
        self.mover_vasos()

        # camara de inspección (misma lógica que la camara real)
        self.cam_w, self.cam_h, self.cam_fov, self.cam_alt = 320, 240, 30.0, 0.42
        px_por_m = (self.cam_h / 2) / ((self.cam_alt - GROSOR_MONEDA) * math.tan(math.radians(self.cam_fov / 2)))
        self.px_por_mm = px_por_m * S / 1000.0
        self.vista = p.computeViewMatrix([X_INSPECCION, 0, Z_BANDA + self.cam_alt],
                                         [X_INSPECCION, 0, Z_BANDA], [1, 0, 0])
        self.proy = p.computeProjectionMatrixFOV(self.cam_fov, self.cam_w / self.cam_h, 0.05, 3)

        # compuerta (servo) en la zona de inspección
        self.compuerta = caja([X_INSPECCION + 0.07, 0, Z_BANDA + 0.03], [0.012, ANCHO_BANDA, 0.05],
                              [0.22, 0.22, 0.25, 1], colision=False)

        self.monedas = []
        self.estado_estacion = "BANDA"
        self.moneda_actual = None
        self.t_estado = 0.0
        self.ultima = None
        self.conteo = {v: 0 for v in vm.MONEDAS}
        self.rechazadas = 0
        self.t_proxima_moneda = 1.0
        self.pedido_carga = None
        self.vaso_en_carro = None
        self.entregas = []

        # carro
        self.carro = p.loadURDF(URDF_CARRO, [POS_BASE[0], POS_BASE[1], 0.18],
                                p.getQuaternionFromEuler([0, 0, POS_BASE[2]]))
        self.juntas = {p.getJointInfo(self.carro, i)[1].decode(): i for i in range(p.getNumJoints(self.carro))}
        p.changeDynamics(self.carro, self.juntas["loca"], lateralFriction=0.0, rollingFriction=0.0,
                         spinningFriction=0.0)
        for j in ("motor_izq", "motor_der"):
            p.changeDynamics(self.carro, self.juntas[j], lateralFriction=1.5)
        self.modo_carro = "LIBRE"
        self.camino = []
        self.i_camino = 0
        self.manual = None
        self.v_cmd = 0.0
        self.w_cmd = 0.0
        self.mensaje = "Listo. Ordenes: estacionar, cargar, meta"
        self.hud = -1
        self.hud_estacion = -1

        # entrada por UDP (desde la app de Streamlit / voz)
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("127.0.0.1", PUERTO_UDP))
        self.udp.setblocking(False)

        if gui:
            p.resetDebugVisualizerCamera(6.5, -40, -42, [2.6, -0.4, 0])

    # ----------------------------------------------------------------- cadena
    def posicion_vaso(self, vaso):
        s = vaso["idx"] * PASO + self.fase
        x, y = punto_cadena(s)
        return [x, y, Z_MESA]

    def mover_vasos(self):
        for k, vaso in enumerate(self.vasos):
            if vaso.get("en_carro"):
                continue
            pos = self.posicion_vaso(vaso)
            anterior = p.getBasePositionAndOrientation(vaso["id"])[0]
            p.resetBasePositionAndOrientation(vaso["id"], pos, [0, 0, 0, 1])
            d = [pos[i] - anterior[i] for i in range(3)]
            for mon in vaso["monedas"]:          # las monedas viajan con su vaso
                if mon["local"] is not None:
                    q = [pos[i] + mon["local"][i] for i in range(3)]
                    p.resetBasePositionAndOrientation(mon["id"], q, [0, 0, 0, 1])
                    p.resetBaseVelocity(mon["id"], [0, 0, 0], [0, 0, 0])
            if self.gui:
                texto = ("$%d" % vaso["etiqueta"]) if vaso["etiqueta"] != "rechazo" else "RECHAZO"
                texto += " (%d)" % len(vaso["monedas"])
                self.textos_vasos[k] = p.addUserDebugText(
                    texto, [pos[0] - 0.12, pos[1], Z_MESA + H_VASO + 0.08], COLOR_VASO[vaso["etiqueta"]][:3],
                    1.1, replaceItemUniqueId=self.textos_vasos[k])

    def ir_a_puesto(self, vaso, s_puesto):
        """Fija la fase de la cadena para que 'vaso' quede en el puesto s_puesto (camino más corto)."""
        objetivo = (s_puesto - vaso["idx"] * PASO) % LARGO_CADENA
        actual = self.fase % LARGO_CADENA
        delta = (objetivo - actual + LARGO_CADENA / 2) % LARGO_CADENA - LARGO_CADENA / 2
        self.fase_obj = self.fase + delta

    def cadena_quieta(self):
        return abs(self.fase_obj - self.fase) < 1e-4

    def vaso_de(self, etiqueta):
        for v in self.vasos:
            if v["etiqueta"] == etiqueta and not v.get("en_carro"):
                return v
        return None

    # --------------------------------------------------------------- estación
    def nueva_moneda(self, valor=None):
        if valor is None:
            valor = random.choice(list(vm.MONEDAS))
        libre = all(m["x"] > X_TOLVA + 0.2 for m in self.monedas if m["estado"] == "banda")
        if libre:
            self.monedas.append(crear_moneda(valor, [X_TOLVA, 0, Z_BANDA + GROSOR_MONEDA / 2]))

    def inspeccionar(self, moneda):
        _, _, rgb, _, _ = p.getCameraImage(
            self.cam_w, self.cam_h, self.vista, self.proy,
            renderer=p.ER_BULLET_HARDWARE_OPENGL if self.gui else p.ER_TINY_RENDERER,
            lightDirection=[0.3, 0.3, 1])
        img = np.reshape(np.array(rgb, dtype=np.uint8), (self.cam_h, self.cam_w, 4))[:, :, :3]
        frame = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        resultados = vm.analizar(frame, self.px_por_mm)
        if not resultados:
            return None, None
        # la moneda más cercana al centro de la imagen
        r = min(resultados, key=lambda m: (m["x"] - self.cam_w / 2) ** 2 + (m["y"] - self.cam_h / 2) ** 2)
        return r["valor"], r

    def actualizar_estacion(self, dt):
        # monedas sobre la banda
        delante = None
        compuerta_abierta = self.estado_estacion == "SOLTANDO"
        for m in sorted([m for m in self.monedas if m["estado"] == "banda"], key=lambda m: -m["x"]):
            limite = X_FIN + 1.0
            if delante is not None:
                limite = delante - 0.14                     # no chocar con la moneda de adelante
            pasa = compuerta_abierta and m is self.moneda_actual
            if not pasa and m["x"] <= X_INSPECCION + 1e-9:
                limite = min(limite, X_INSPECCION)          # la compuerta la detiene
            m["x"] = min(m["x"] + V_BANDA * dt, limite)
            p.resetBasePositionAndOrientation(m["id"], [m["x"], 0, Z_BANDA + GROSOR_MONEDA / 2], [0, 0, 0, 1])
            p.resetBaseVelocity(m["id"], [0, 0, 0], [0, 0, 0])
            if m["x"] >= X_FIN + m["r"]:                     # su centro pasó el borde: cae
                m["estado"] = "cayendo"
                m["t"] = 0.0
                p.resetBaseVelocity(m["id"], [V_BANDA, 0, 0], [0, 0, 0])
            delante = m["x"]

        # monedas cayendo: ¿entraron a un vaso?
        for m in self.monedas:
            if m["estado"] != "cayendo":
                continue
            m["t"] += dt
            pos = p.getBasePositionAndOrientation(m["id"])[0]
            vel = p.getBaseVelocity(m["id"])[0]
            vaso = m["vaso"]
            if vaso is not None:
                pv = p.getBasePositionAndOrientation(vaso["id"])[0]
                dentro = math.hypot(pos[0] - pv[0], pos[1] - pv[1]) < R_VASO and pos[2] < Z_MESA + H_VASO
                if dentro and math.hypot(*vel) < 0.05 and m["t"] > 0.4:
                    m["estado"] = "en_vaso"
                    m["local"] = [pos[0] - pv[0], pos[1] - pv[1], pos[2] - pv[2]]
                    vaso["monedas"].append(m)
                    if vaso["etiqueta"] == "rechazo":
                        self.rechazadas += 1
                    else:
                        self.conteo[vaso["etiqueta"]] += 1
            if m["t"] > 3.0 and m["estado"] == "cayendo":     # se salió del vaso
                m["estado"] = "perdida"
                p.removeBody(m["id"])

        # máquina de estados de la estación
        self.t_estado += dt
        e = self.estado_estacion
        if e == "BANDA":
            if self.pedido_carga is not None:
                self.estado_estacion, self.t_estado = "ENTREGANDO_CADENA", 0.0
                return
            for m in self.monedas:
                if m["estado"] == "banda" and abs(m["x"] - X_INSPECCION) < 1e-6:
                    self.moneda_actual = m
                    self.estado_estacion, self.t_estado = "INSPECCION", 0.0
                    break
        elif e == "INSPECCION" and self.t_estado > 0.3:
            valor, detalle = self.inspeccionar(self.moneda_actual)
            self.moneda_actual["detectado"] = valor
            self.ultima = {"real": self.moneda_actual["valor"], "detectado": valor,
                           "diametro_mm": detalle["diametro"] if detalle else None,
                           "centro": detalle["centro"] if detalle else None,
                           "anillo": detalle["anillo"] if detalle else None}
            vaso = self.vaso_de(valor if valor else "rechazo")
            self.moneda_actual["vaso"] = vaso
            self.ir_a_puesto(vaso, S_CAIDA)
            print("[VISION] moneda real $%s -> detectada %s (%.1f mm, %s/%s)" % (
                self.moneda_actual["valor"], ("$%d" % valor) if valor else "DESCONOCIDA",
                detalle["diametro"] if detalle else 0, self.ultima["centro"], self.ultima["anillo"]))
            self.estado_estacion, self.t_estado = "INDEXANDO", 0.0
        elif e == "INDEXANDO" and self.cadena_quieta():
            self.estado_estacion, self.t_estado = "SOLTANDO", 0.0
        elif e == "SOLTANDO":
            ang = -1.2 if self.t_estado < 0.6 else 0.0          # la compuerta se levanta
            p.resetBasePositionAndOrientation(self.compuerta, [X_INSPECCION + 0.07, 0, Z_BANDA + 0.03 + (0.06 if ang else 0)],
                                              p.getQuaternionFromEuler([0, ang, 0]))
            if self.moneda_actual["estado"] in ("en_vaso", "perdida"):
                self.moneda_actual = None
                self.estado_estacion, self.t_estado = "BANDA", 0.0
        elif e == "ENTREGANDO_CADENA":
            vaso = self.pedido_carga
            if self.t_estado < dt * 1.5:
                self.ir_a_puesto(vaso, S_ENTREGA)
            elif self.cadena_quieta():
                self.estado_estacion, self.t_estado = "EMPUJANDO", 0.0
                self.inicio_empuje = self.posicion_vaso(vaso)
        elif e == "EMPUJANDO":
            vaso = self.pedido_carga
            destino = self.posicion_porta_vaso()
            k = min(1.0, self.t_estado / 1.8)
            k = k * k * (3 - 2 * k)
            a = self.inicio_empuje
            pos = [a[0] + (destino[0] - a[0]) * k, a[1] + (destino[1] - a[1]) * k,
                   a[2] + (destino[2] - a[2]) * k + 0.05 * math.sin(math.pi * k)]
            p.resetBasePositionAndOrientation(vaso["id"], pos, [0, 0, 0, 1])
            for mon in vaso["monedas"]:
                p.resetBasePositionAndOrientation(mon["id"], [pos[i] + mon["local"][i] for i in range(3)], [0, 0, 0, 1])
            xe, ye = punto_cadena(S_ENTREGA)
            p.resetBasePositionAndOrientation(self.empujador, [xe - 0.25 + 0.3 * math.sin(math.pi * min(1, self.t_estado / 1.8)),
                                                               ye, Z_MESA + 0.08], [0, 0, 0, 1])
            if self.t_estado >= 1.8:
                self.cargar_en_carro(vaso)
                self.pedido_carga = None
                self.estado_estacion, self.t_estado = "BANDA", 0.0

        # la cadena se mueve hacia su fase objetivo
        if not self.cadena_quieta():
            paso = max(-V_CADENA * dt, min(V_CADENA * dt, self.fase_obj - self.fase))
            self.fase += paso
            self.mover_vasos()
        elif self.gui and int(self.t * 60) % 30 == 0:
            self.mover_vasos()

    def posicion_porta_vaso(self):
        estado = p.getLinkState(self.carro, self.juntas["porta_vaso"])
        return [estado[4][0], estado[4][1], estado[4][2] + 0.005]

    def cargar_en_carro(self, vaso):
        n = len(vaso["monedas"])
        valor = sum(m["valor"] for m in vaso["monedas"])
        peso = round(sum(vm.MONEDAS[m["valor"]]["peso"] for m in vaso["monedas"]), 2)
        for m in vaso["monedas"]:
            p.removeBody(m["id"])
        p.removeBody(vaso["id"])
        # el vaso cargado se vuelve un cuerpo dinámico unido al porta-vaso del carro
        nuevo = crear_vaso(vaso["etiqueta"], masa=0.3, relleno=n)
        destino = self.posicion_porta_vaso()
        p.resetBasePositionAndOrientation(nuevo, destino, [0, 0, 0, 1])
        c = p.createConstraint(self.carro, self.juntas["porta_vaso"], nuevo, -1, p.JOINT_FIXED,
                               [0, 0, 0], [0, 0, 0], [0, 0, -0.005])
        p.changeConstraint(c, maxForce=200)
        self.vaso_en_carro = {"id": nuevo, "restriccion": c, "etiqueta": vaso["etiqueta"],
                              "monedas": n, "valor": valor, "peso": peso}
        self.mensaje = "Vaso de %s cargado: %d monedas, $%d" % (vaso["etiqueta"], n, valor)
        print("[ESTACION]", self.mensaje)
        # reposición: un vaso vacío nuevo ocupa el puesto en la cadena
        vaso["id"] = crear_vaso(vaso["etiqueta"])
        vaso["monedas"] = []
        self.mover_vasos()

    # ------------------------------------------------------------------ carro
    def pose_carro(self):
        pos, orn = p.getBasePositionAndOrientation(self.carro)
        return pos[0], pos[1], p.getEulerFromQuaternion(orn)[2]

    def distancia_sensor(self, nombre):
        """Ultrasonido simulado con un rayo (como el HC-SR04, alcance 4 m reales)."""
        st = p.getLinkState(self.carro, self.juntas[nombre], computeForwardKinematics=True)
        o = st[4]
        m = p.getMatrixFromQuaternion(st[5])
        d = [m[0], m[3], m[6]]
        alcance = 4.0 * S / 4
        fin = [o[i] + alcance * d[i] for i in range(3)]
        r = p.rayTest(o, fin)[0]
        if r[0] < 0 or r[0] == self.carro:
            return alcance
        return r[2] * alcance

    def ordenar(self, texto):
        """Interpreta una orden (de teclado, voz o UDP)."""
        t = texto.lower().strip()
        if not t:
            return
        print("[ORDEN]", t)
        if "estacion" in t or "parque" in t or "aparca" in t:
            self.modo_carro = "IR_PREPARQUEO"
            self.camino = self.camino_hacia(PREPARQUEO)
            self.i_camino = 0
            self.mensaje = "Aparcamiento automatico en la zona de carga"
        elif "carga" in t:
            if self.modo_carro != "ESTACIONADO":
                self.mensaje = "Primero estaciona el carro en la zona de carga"
            elif self.vaso_en_carro:
                self.mensaje = "El carro ya lleva un vaso"
            else:
                elegido = None
                for v in vm.MONEDAS:
                    if str(v) in t.replace("$", "").split():
                        elegido = self.vaso_de(v)
                if elegido is None:      # el vaso con más dinero
                    elegido = max((v for v in self.vasos if v["etiqueta"] != "rechazo"),
                                  key=lambda v: sum(m["valor"] for m in v["monedas"]))
                if not elegido["monedas"]:
                    self.mensaje = "Los vasos estan vacios todavia"
                else:
                    self.pedido_carga = elegido
                    self.mensaje = "Cargando vaso de $%s" % elegido["etiqueta"]
        elif "meta" in t or "entrega" in t:
            self.modo_carro = "A_META"
            x, y, _ = self.pose_carro()
            self.camino = CAMINO_META[:] if x < 3.0 else self.camino_hacia(META)
            self.i_camino = 0
            self.mensaje = "Rumbo a la meta (esquivando obstaculos)"
        elif "base" in t or "casa" in t:
            self.modo_carro = "A_BASE"
            self.camino = self.camino_hacia(POS_BASE[:2])
            self.i_camino = 0
            self.mensaje = "Volviendo a la base"
        elif "alto" in t or "para" in t or "deten" in t:
            self.modo_carro = "LIBRE"
            self.manual = None
            self.mensaje = "Alto"
        elif "adelante" in t or "avanza" in t:
            self.iniciar_manual("recto", 0.6)
        elif "atras" in t or "atrás" in t or "retrocede" in t:
            self.iniciar_manual("recto", -0.6)
        elif "izquierda" in t:
            self.iniciar_manual("giro", math.radians(45))
        elif "derecha" in t:
            self.iniciar_manual("giro", -math.radians(45))
        elif "moneda" in t:
            self.nueva_moneda()
        else:
            self.mensaje = "No entendi: '%s'" % t

    def camino_hacia(self, destino):
        x, y, _ = self.pose_carro()
        return [(x + (destino[0] - x) * 0.5, y + (destino[1] - y) * 0.5), destino]

    def iniciar_manual(self, tipo, cantidad):
        x, y, yaw = self.pose_carro()
        self.modo_carro = "MANUAL"
        self.manual = {"tipo": tipo, "cantidad": cantidad, "x0": x, "y0": y, "yaw0": yaw}
        self.mensaje = "Movimiento manual: %s" % tipo

    def seguir_camino(self, v_max):
        x, y, yaw = self.pose_carro()
        while self.i_camino < len(self.camino) - 1 and \
                math.hypot(self.camino[self.i_camino][0] - x, self.camino[self.i_camino][1] - y) < 0.45:
            self.i_camino += 1
        tx, ty = self.camino[self.i_camino]
        dist = math.hypot(tx - x, ty - y)
        err = angulo_normal(math.atan2(ty - y, tx - x) - yaw)
        w = max(-1.6, min(1.6, 2.5 * err))
        v = v_max * max(0.0, math.cos(err)) * min(1.0, dist / 0.4 + 0.3)
        # llegada: cerca del último punto (o justo a un lado, para no orbitar alrededor)
        llegado = self.i_camino == len(self.camino) - 1 and (dist < 0.12 or (dist < 0.3 and abs(err) > 1.0))
        return v, w, llegado

    def actualizar_carro(self, dt):
        x, y, yaw = self.pose_carro()
        modo = self.modo_carro
        v = w = 0.0
        d_frente = self.distancia_sensor("sensor_frontal")
        if modo in ("IR_PREPARQUEO", "A_META", "A_BASE"):
            v, w, llego = self.seguir_camino(0.7 if modo == "A_META" else 0.6)
            if d_frente < 0.15 and v > 0:                       # seguridad: obstáculo inesperado
                v = 0.0
                self.mensaje = "Obstaculo al frente: esperando"
            if llego:
                if modo == "IR_PREPARQUEO":
                    self.modo_carro = "ALINEANDO"
                elif modo == "A_META":
                    self.modo_carro = "EN_META"
                    if self.vaso_en_carro:
                        self.entregas.append({k: self.vaso_en_carro[k] for k in ("etiqueta", "monedas", "valor", "peso")})
                        self.mensaje = "ENTREGADO en la meta: $%d" % self.vaso_en_carro["valor"]
                    else:
                        self.mensaje = "Llego a la meta"
                    print("[CARRO]", self.mensaje)
                else:
                    self.modo_carro = "LIBRE"
                    self.mensaje = "En la base"
        elif modo == "ALINEANDO":                              # girar hasta mirar a +x
            err = angulo_normal(0.0 - yaw)
            w = max(-1.2, min(1.2, 3.0 * err))
            if abs(err) < 0.03:
                self.modo_carro = "REVERSA"
        elif modo == "REVERSA":                                # retroceder hasta la estación
            d_atras = self.distancia_sensor("sensor_trasero")
            err_y = PREPARQUEO[1] - y
            err = angulo_normal(0.0 - yaw)
            v = -0.25 if d_atras > 0.20 else -0.10
            w = 3.0 * err - 2.0 * err_y          # en reversa, corregir la desviación lateral
            if d_atras <= 0.06:
                self.modo_carro = "ESTACIONADO"
                self.mensaje = "ESTACIONADO (sensor trasero %.1f cm reales)" % (d_atras / S * 100)
                print("[CARRO]", self.mensaje)
        elif modo == "MANUAL" and self.manual:
            mnl = self.manual
            if mnl["tipo"] == "recto":
                hecho = math.hypot(x - mnl["x0"], y - mnl["y0"])
                v = 0.4 * (1 if mnl["cantidad"] > 0 else -1)
                if (v > 0 and d_frente < 0.15) or hecho >= abs(mnl["cantidad"]):
                    v = 0.0
                    self.modo_carro, self.manual = "LIBRE", None
            else:
                girado = angulo_normal(yaw - mnl["yaw0"])
                w = 1.0 * (1 if mnl["cantidad"] > 0 else -1)
                if abs(girado) >= abs(mnl["cantidad"]):
                    w = 0.0
                    self.modo_carro, self.manual = "LIBRE", None

        # aceleración suave (como el PWM con rampa del firmware)
        k = min(1.0, 6.0 * dt)
        self.v_cmd += (v - self.v_cmd) * k
        self.w_cmd += (w - self.w_cmd) * k
        w_izq = (self.v_cmd - self.w_cmd * VIA / 2) / R_RUEDA
        w_der = (self.v_cmd + self.w_cmd * VIA / 2) / R_RUEDA
        p.setJointMotorControl2(self.carro, self.juntas["motor_izq"], p.VELOCITY_CONTROL, targetVelocity=w_izq, force=40)
        p.setJointMotorControl2(self.carro, self.juntas["motor_der"], p.VELOCITY_CONTROL, targetVelocity=w_der, force=40)

    # ------------------------------------------------------------- entradas
    def leer_entradas(self):
        while True:
            try:
                datos, _ = self.udp.recvfrom(1024)
            except (BlockingIOError, OSError):
                break
            self.ordenar(datos.decode("utf-8", errors="ignore"))
        if not self.gui:
            return
        teclas = p.getKeyboardEvents()
        disparo = lambda k: teclas.get(k, 0) & p.KEY_WAS_TRIGGERED
        if disparo(ord("n")):
            self.nueva_moneda()
        if disparo(ord("e")):
            self.ordenar("estacionar")
        if disparo(ord("c")):
            self.ordenar("cargar")
        if disparo(ord("m")):
            self.ordenar("meta")
        if disparo(ord("b")):
            self.ordenar("base")
        if disparo(ord(" ")):
            self.ordenar("alto")
        if disparo(p.B3G_UP_ARROW):
            self.ordenar("adelante")
        if disparo(p.B3G_DOWN_ARROW):
            self.ordenar("atras")
        if disparo(p.B3G_LEFT_ARROW):
            self.ordenar("izquierda")
        if disparo(p.B3G_RIGHT_ARROW):
            self.ordenar("derecha")

    # --------------------------------------------------------------- estado
    def estado(self):
        x, y, yaw = self.pose_carro()
        vasos = []
        for v in self.vasos:
            vasos.append({"etiqueta": v["etiqueta"], "monedas": len(v["monedas"]),
                          "valor": sum(m["valor"] for m in v["monedas"]),
                          "peso": round(sum(vm.MONEDAS[m["valor"]]["peso"] for m in v["monedas"]), 2)})
        total = sum(k * n for k, n in self.conteo.items())
        peso = sum(vm.MONEDAS[k]["peso"] * n for k, n in self.conteo.items())
        return {
            "t": round(self.t, 1),
            "conteo": {str(k): n for k, n in self.conteo.items()},
            "rechazadas": self.rechazadas,
            "valor_total": total,
            "peso_total_g": round(peso, 2),
            "monedas_total": sum(self.conteo.values()),
            "estacion": self.estado_estacion,
            "ultima_moneda": self.ultima,
            "vasos": vasos,
            "carro": {"x": round(x, 2), "y": round(y, 2), "rumbo": round(math.degrees(yaw)),
                      "modo": self.modo_carro, "mensaje": self.mensaje,
                      "dist_frontal_cm": round(self.distancia_sensor("sensor_frontal") / S * 100, 1),
                      "dist_trasera_cm": round(self.distancia_sensor("sensor_trasero") / S * 100, 1),
                      "carga": self.vaso_en_carro and {k: self.vaso_en_carro[k]
                                                        for k in ("etiqueta", "monedas", "valor", "peso")}},
            "entregas": self.entregas,
        }

    def guardar_estado(self):
        tmp = ARCHIVO_ESTADO + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.estado(), f, indent=1)
        os.replace(tmp, ARCHIVO_ESTADO)

    def mostrar(self):
        if not self.gui:
            return
        x, y, _ = self.pose_carro()
        self.hud = p.addUserDebugText("%s | %s" % (self.modo_carro, self.mensaje), [x - 0.6, y, 0.75],
                                      [0.05, 0.05, 0.4], 1.1, replaceItemUniqueId=self.hud)
        u = self.ultima
        txt = "Estacion: %s | monedas %d | $%d" % (self.estado_estacion, sum(self.conteo.values()),
                                                   sum(k * n for k, n in self.conteo.items()))
        if u:
            txt += " | ultima: %s" % (("$%d" % u["detectado"]) if u["detectado"] else "?")
        self.hud_estacion = p.addUserDebugText(txt, [-1.6, -0.45, Z_BANDA + 0.45], [0.4, 0.05, 0.05], 1.1,
                                               replaceItemUniqueId=self.hud_estacion)


# ===========================================================================
def main():
    ap = argparse.ArgumentParser(description="Simulación del sistema de logística de monedas (Grupo 5)")
    ap.add_argument("--demo", action="store_true", help="secuencia automática completa")
    ap.add_argument("--monedas", type=int, default=12, help="monedas que entran en modo demo")
    ap.add_argument("--sin-gui", action="store_true")
    ap.add_argument("--duracion", type=float, default=0, help="segundos (0 = sin límite)")
    ap.add_argument("--semilla", type=int, default=7)
    args = ap.parse_args()
    random.seed(args.semilla)

    gui = not args.sin_gui
    p.connect(p.GUI if gui else p.DIRECT)
    if gui:
        p.configureDebugVisualizer(p.COV_ENABLE_GUI, 1)
    sis = Sistema(gui, args.demo)

    DT = 1.0 / 240.0
    SUB = 4                                   # control a 60 Hz
    pasos = int(args.duracion / DT) if args.duracion > 0 else 10 ** 12
    t0 = time.time()
    entradas = 0
    guion = [(0.0, None)]
    if args.demo:
        guion = []
    print("Ordenes por UDP en 127.0.0.1:%d  |  teclas: n e c m b flechas espacio" % PUERTO_UDP)
    try:
        for i in range(pasos):
            if i % SUB == 0:
                dt = DT * SUB
                sis.t += dt
                sis.leer_entradas()
                if args.demo:
                    # monedas cada 2,2 s y luego la secuencia del carro
                    if entradas < args.monedas and sis.t >= sis.t_proxima_moneda:
                        sis.nueva_moneda()
                        entradas += 1
                        sis.t_proxima_moneda = sis.t + 2.2
                    if sis.t > 4.0 and sis.modo_carro == "LIBRE" and not sis.vaso_en_carro and "estacionar" not in guion:
                        sis.ordenar("estacionar")
                        guion.append("estacionar")
                    fin_monedas = entradas >= args.monedas and sis.estado_estacion == "BANDA" and \
                        not any(m["estado"] in ("banda", "cayendo") for m in sis.monedas)
                    if sis.modo_carro == "ESTACIONADO" and fin_monedas and "cargar" not in guion:
                        sis.ordenar("cargar")
                        guion.append("cargar")
                    if sis.vaso_en_carro and "meta" not in guion and sis.estado_estacion == "BANDA":
                        guion.append("meta")
                        sis.t_meta = sis.t + 1.0
                    if "meta" in guion and "meta_ok" not in guion and sis.t >= sis.t_meta:
                        sis.ordenar("meta")
                        guion.append("meta_ok")
                sis.actualizar_estacion(dt)
                sis.actualizar_carro(dt)
                if i % (SUB * 15) == 0:
                    sis.mostrar()
                    sis.guardar_estado()
                if not gui and i % (SUB * 60) == 0:
                    e = sis.estado()
                    print("t=%5.1f est=%-17s monedas=%2d $%-6d carro=%s (%.2f,%.2f) %s" % (
                        e["t"], e["estacion"], e["monedas_total"], e["valor_total"], e["carro"]["modo"],
                        e["carro"]["x"], e["carro"]["y"], e["carro"]["mensaje"]))
            p.stepSimulation()
            atraso = (i + 1) * DT - (time.time() - t0)
            if gui and atraso > 0:
                time.sleep(atraso)
    except KeyboardInterrupt:
        pass
    finally:
        sis.guardar_estado()
        p.disconnect()


if __name__ == "__main__":
    main()
