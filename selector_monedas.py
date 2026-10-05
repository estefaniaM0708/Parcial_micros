
import pybullet as p
import pybullet_data
import time
import math

# ============================================================
# 1. CONFIGURACION GENERAL
# ============================================================

p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.81)
p.setTimeStep(1 / 240)
p.setRealTimeSimulation(0)

p.loadURDF("plane.urdf")

DT = 1 / 240

p.resetDebugVisualizerCamera(
    cameraDistance=8.0,
    cameraYaw=45,
    cameraPitch=-35,
    cameraTargetPosition=[-0.2, 0, 0.35]
)

# ============================================================
# 2. FUNCIONES AUXILIARES
# ============================================================

def crear_caja(nombre, posicion, dimensiones, color, orientacion=None):

    visual = p.createVisualShape(
        p.GEOM_BOX,
        halfExtents=dimensiones,
        rgbaColor=color
    )

    colision = p.createCollisionShape(
        p.GEOM_BOX,
        halfExtents=dimensiones
    )

    if orientacion is None:
        orientacion = [0, 0, 0, 1]

    return p.createMultiBody(
        baseMass=0,
        baseCollisionShapeIndex=colision,
        baseVisualShapeIndex=visual,
        basePosition=posicion,
        baseOrientation=orientacion
    )


def crear_texto(mensaje, posicion, color=(0, 0, 0), tamano=1.2):

    return p.addUserDebugText(
        mensaje,
        posicion,
        textColorRGB=color,
        textSize=tamano
    )


def crear_segmento(nombre, inicio, final, ancho, grosor, color):

    dx = final[0] - inicio[0]
    dy = final[1] - inicio[1]
    dz = final[2] - inicio[2]

    largo = math.sqrt(dx**2 + dy**2 + dz**2)
    horizontal = math.sqrt(dx**2 + dy**2)

    yaw = math.atan2(dy, dx)
    pitch = -math.atan2(dz, horizontal)

    orientacion = p.getQuaternionFromEuler(
        [0, pitch, yaw]
    )

    centro = [
        (inicio[0] + final[0]) / 2,
        (inicio[1] + final[1]) / 2,
        (inicio[2] + final[2]) / 2
    ]

    return crear_caja(
        nombre,
        centro,
        [largo / 2, ancho / 2, grosor / 2],
        color,
        orientacion
    )


# ============================================================
# 3. COLORES
# ============================================================

COLORES_MONEDAS = {
    "antigua": [0.68, 0.48, 0.22, 1],
    "nueva": [0.78, 0.80, 0.83, 1]
}

COLOR_RAMPA = [0.22, 0.25, 0.29, 1]
COLOR_GUIA = [0.12, 0.32, 0.62, 1]
COLOR_VASO = [0.10, 0.35, 0.78, 1]

# ============================================================
# 4. TOLVA DE ALIMENTACION
# ============================================================

tolva_x = -3.15
tolva_y = 0.0

# Pared trasera
crear_caja(
    "Tolva trasera",
    [tolva_x - 0.42, tolva_y, 0.95],
    [0.07, 0.62, 0.75],
    [0.58, 0.59, 0.62, 1]
)

# Pared frontal
crear_caja(
    "Tolva frontal",
    [tolva_x + 0.42, tolva_y, 0.95],
    [0.07, 0.62, 0.75],
    [0.58, 0.59, 0.62, 1]
)

# Paredes laterales
for lado in [-1, 1]:

    crear_caja(
        "Pared lateral tolva",
        [tolva_x, tolva_y + lado * 0.62, 0.95],
        [0.42, 0.07, 0.75],
        [0.72, 0.72, 0.75, 1]
    )

# Fondo
crear_caja(
    "Fondo tolva",
    [tolva_x, tolva_y, 0.25],
    [0.42, 0.62, 0.07],
    [0.35, 0.37, 0.40, 1]
)

# Tapa superior abierta visualmente:
# se omite la tapa para permitir observar las monedas.

# Botones superiores decorativos
for i in range(5):

    visual = p.createVisualShape(
        p.GEOM_CYLINDER,
        radius=0.07,
        length=0.04,
        rgbaColor=[0.20, 0.20, 0.20, 1]
    )

    p.createMultiBody(
        baseMass=0,
        baseVisualShapeIndex=visual,
        basePosition=[
            tolva_x - 0.30 + i * 0.15,
            tolva_y,
            1.82
        ]
    )

crear_texto(
    "TOLVA DE ALIMENTACION",
    [tolva_x - 0.65, 0.85, 1.90],
    [0.1, 0.1, 0.1],
    1.2
)

# ============================================================
# 5. BANDA TRANSPORTADORA
# ============================================================

crear_caja(
    "Base de banda",
    [-1.65, 0, 0.08],
    [2.1, 0.65, 0.08],
    [0.15, 0.17, 0.20, 1]
)

crear_caja(
    "Superficie de banda",
    [-1.65, 0, 0.17],
    [2.05, 0.58, 0.015],
    [0.35, 0.37, 0.40, 1]
)

for lado in [-1, 1]:

    crear_caja(
        "Borde de banda",
        [-1.65, lado * 0.62, 0.25],
        [2.1, 0.035, 0.12],
        [0.12, 0.14, 0.17, 1]
    )

crear_texto(
    "BANDA TRANSPORTADORA",
    [-2.8, 0, 0.65]
)

# ============================================================
# 6. SENSOR DE IDENTIFICACION
# ============================================================

sensor_x = -0.25

crear_caja(
    "Sensor izquierdo",
    [sensor_x, -0.48, 0.45],
    [0.04, 0.04, 0.25],
    [0.1, 0.8, 0.2, 1]
)

crear_caja(
    "Sensor derecho",
    [sensor_x, 0.48, 0.45],
    [0.04, 0.04, 0.25],
    [0.1, 0.8, 0.2, 1]
)

crear_caja(
    "Sensor superior",
    [sensor_x, 0, 0.72],
    [0.04, 0.52, 0.04],
    [0.1, 0.8, 0.2, 1]
)

crear_texto(
    "SENSOR",
    [-0.8, 0.82, 0.9],
    [0.0, 0.5, 0.0]
)

# ============================================================
# 7. SELECTOR MECANICO
# ============================================================

selector_x = 0.35

crear_caja(
    "Base selector",
    [selector_x, 0, 0.23],
    [0.15, 0.15, 0.23],
    [0.30, 0.30, 0.30, 1]
)

brazo_visual = p.createVisualShape(
    p.GEOM_BOX,
    halfExtents=[0.32, 0.055, 0.04],
    rgbaColor=[1, 0.48, 0.03, 1]
)

p.createMultiBody(
    baseMass=0,
    baseVisualShapeIndex=brazo_visual,
    basePosition=[selector_x, 0, 0.50]
)

crear_texto(
    "SELECTOR",
    [selector_x - 0.4, -0.65, 0.72],
    [0.8, 0.3, 0.0]
)

# ============================================================
# 8. TOBOGANES CURVOS Y VASITOS
# ============================================================

valores = [50, 100, 200, 500, 1000]
etiquetas = ["$50", "$100", "$200", "$500", "$1.000"]

y_inicial = -1.60
separacion = 0.80

punto_inicio = [0.65, 0.0, 0.48]
x_final = 2.35
z_final = 0.20

ancho_canal = 0.30
altura_guia = 0.12

x_vaso = 2.55

compartimentos = []
rutas = []

for i, valor in enumerate(valores):

    y_destino = y_inicial + i * separacion

    # Puntos de la trayectoria curva
    puntos = [
        [punto_inicio[0], punto_inicio[1], punto_inicio[2]],
        [0.95, y_destino * 0.20, 0.40],
        [1.35, y_destino * 0.48, 0.32],
        [1.72, y_destino * 0.78, 0.25],
        [x_final, y_destino, z_final]
    ]

    rutas.append(puntos)

    # Piso del tobogan
    for j in range(len(puntos) - 1):

        crear_segmento(
            f"Canal {valor} tramo {j}",
            puntos[j],
            puntos[j + 1],
            ancho_canal,
            0.045,
            COLOR_RAMPA
        )

    # Guias laterales
    for lado in [-1, 1]:

        for j in range(len(puntos) - 1):

            a = puntos[j]
            b = puntos[j + 1]

            dx = b[0] - a[0]
            dy = b[1] - a[1]

            largo_xy = math.sqrt(dx**2 + dy**2)

            if largo_xy == 0:
                continue

            nx = -dy / largo_xy
            ny = dx / largo_xy

            desplazamiento = lado * ancho_canal / 2

            inicio_guia = [
                a[0] + nx * desplazamiento,
                a[1] + ny * desplazamiento,
                a[2] + altura_guia / 2
            ]

            final_guia = [
                b[0] + nx * desplazamiento,
                b[1] + ny * desplazamiento,
                b[2] + altura_guia / 2
            ]

            crear_segmento(
                f"Guia {valor} {lado} tramo {j}",
                inicio_guia,
                final_guia,
                0.035,
                altura_guia,
                COLOR_GUIA
            )

    # Vasito
    y_vaso = y_destino

    crear_caja(
        f"Base vaso {valor}",
        [x_vaso, y_vaso, 0.09],
        [0.36, 0.32, 0.07],
        COLOR_VASO
    )

    altura_pared = 0.12
    z_pared = 0.21

    crear_caja(
        f"Pared trasera {valor}",
        [x_vaso + 0.33, y_vaso, z_pared],
        [0.035, 0.32, altura_pared],
        COLOR_VASO
    )

    crear_caja(
        f"Pared frontal {valor}",
        [x_vaso - 0.33, y_vaso, z_pared],
        [0.035, 0.32, altura_pared],
        COLOR_VASO
    )

    for lado in [-1, 1]:

        crear_caja(
            f"Pared lateral {valor}",
            [x_vaso, y_vaso + lado * 0.29, z_pared],
            [0.36, 0.035, altura_pared],
            COLOR_VASO
        )

    crear_texto(
        f"VASO {etiquetas[i]}",
        [x_vaso - 0.48, y_vaso + 0.39, 0.48],
        [0.05, 0.1, 0.4],
        1.1
    )

    compartimentos.append({
        "valor": valor,
        "y": y_vaso,
        "cantidad": 0,
        "total": 0,
        "monedas": []
    })

# ============================================================
# 9. MONEDAS ANTIGUAS Y NUEVAS
# ============================================================

monedas_datos = [
    (50, "antigua"),
    (100, "nueva"),
    (200, "antigua"),
    (500, "nueva"),
    (1000, "antigua"),
    (50, "nueva"),
    (100, "antigua"),
    (200, "nueva"),
    (500, "antigua"),
    (1000, "nueva"),
    (200, "antigua"),
    (50, "nueva"),
    (500, "nueva"),
    (1000, "antigua")
]

monedas = []

for i, (valor, tipo) in enumerate(monedas_datos):

    radio = 0.10 if valor < 500 else 0.12

    visual = p.createVisualShape(
        p.GEOM_CYLINDER,
        radius=radio,
        length=0.035,
        rgbaColor=COLORES_MONEDAS[tipo]
    )

    colision = p.createCollisionShape(
        p.GEOM_CYLINDER,
        radius=radio,
        height=0.035
    )

    moneda = p.createMultiBody(
        baseMass=0,
        baseCollisionShapeIndex=colision,
        baseVisualShapeIndex=visual,
        basePosition=[
            tolva_x + (i % 3 - 1) * 0.15,
            ((i % 4) - 1.5) * 0.15,
            2.0 + (i // 4) * 0.25
        ]
    )

    monedas.append({
        "id": moneda,
        "valor": valor,
        "tipo": tipo,
        "estado": "cayendo",
        "x": tolva_x + (i % 3 - 1) * 0.15,
        "y": ((i % 4) - 1.5) * 0.15,
        "z": 2.0 + (i // 4) * 0.25,
        "progreso": 0.0,
        "indice": None,
        "destino_y": None,
        "ruta": None
    })

# ============================================================
# 10. CONTADORES
# ============================================================

cantidad_total = 0
valor_total = 0

texto_contador = crear_texto(
    "MONEDAS: 0 | VALOR TOTAL: $0",
    [-3.0, 1.5, 1.15]
)

# ============================================================
# 11. VELOCIDADES
# ============================================================

velocidad_caida = 0.8
velocidad_banda = 0.75
velocidad_rampa = 0.55

# ============================================================
# 12. BUCLE PRINCIPAL
# ============================================================

try:

    while p.isConnected():

        for moneda in monedas:

            # ------------------------------------------------
            # ESTADO 1: CAIDA DENTRO DE LA TOLVA
            # ------------------------------------------------

            if moneda["estado"] == "cayendo":

                moneda["z"] -= velocidad_caida * DT

                if moneda["z"] <= 0.30:

                    moneda["z"] = 0.30

                    # Salida de la tolva hacia la banda
                    moneda["x"] = -2.55
                    moneda["y"] = 0.0

                    moneda["estado"] = "banda"

            # ------------------------------------------------
            # ESTADO 2: BANDA TRANSPORTADORA
            # ------------------------------------------------

            elif moneda["estado"] == "banda":

                moneda["x"] += velocidad_banda * DT

                if moneda["x"] >= sensor_x:

                    moneda["estado"] = "clasificando"

                    valor = moneda["valor"]
                    indice = valores.index(valor)

                    moneda["indice"] = indice
                    moneda["destino_y"] = (
                        y_inicial + indice * separacion
                    )

                    moneda["ruta"] = rutas[indice]
                    moneda["progreso"] = 0.0

                    print(
                        f"Sensor: moneda {moneda['tipo']} "
                        f"de ${valor}"
                    )

            # ------------------------------------------------
            # ESTADO 3: CLASIFICACION POR TOBOGAN
            # ------------------------------------------------

            elif moneda["estado"] == "clasificando":

                ruta = moneda["ruta"]

                moneda["progreso"] += velocidad_rampa * DT

                t = min(moneda["progreso"], 1.0)

                tramos = len(ruta) - 1
                posicion_global = t * tramos

                tramo = min(
                    int(posicion_global),
                    tramos - 1
                )

                fraccion = posicion_global - tramo

                a = ruta[tramo]
                b = ruta[tramo + 1]

                moneda["x"] = (
                    a[0] + (b[0] - a[0]) * fraccion
                )

                moneda["y"] = (
                    a[1] + (b[1] - a[1]) * fraccion
                )

                moneda["z"] = (
                    a[2] + (b[2] - a[2]) * fraccion
                )

                if t >= 1.0:

                    moneda["estado"] = "clasificada"

                    indice = moneda["indice"]
                    valor = moneda["valor"]

                    compartimentos[indice]["cantidad"] += 1
                    compartimentos[indice]["total"] += valor

                    cantidad_total += 1
                    valor_total += valor

                    # Posicion dentro del vasito
                    numero = compartimentos[indice]["cantidad"]

                    moneda["x"] = x_vaso
                    moneda["y"] = moneda["destino_y"]
                    moneda["z"] = 0.18 + (numero - 1) * 0.045

                    compartimentos[indice]["monedas"].append(
                        moneda["id"]
                    )

                    p.removeUserDebugItem(texto_contador)

                    texto_contador = crear_texto(
                        f"MONEDAS: {cantidad_total} | "
                        f"VALOR TOTAL: ${valor_total}",
                        [-3.0, 1.5, 1.15]
                    )

                    print(
                        f"Clasificada: {moneda['tipo']} "
                        f"${valor} | "
                        f"Cantidad: "
                        f"{compartimentos[indice]['cantidad']} | "
                        f"Subtotal: "
                        f"${compartimentos[indice]['total']}"
                    )

            # ------------------------------------------------
            # ACTUALIZAR POSICION DE LA MONEDA
            # ------------------------------------------------

            p.resetBasePositionAndOrientation(
                moneda["id"],
                [moneda["x"], moneda["y"], moneda["z"]],
                [0, 0, 0, 1]
            )

        p.stepSimulation()
        time.sleep(DT)

except KeyboardInterrupt:

    print("Simulación detenida.")

finally:

    if p.isConnected():
        p.disconnect()
