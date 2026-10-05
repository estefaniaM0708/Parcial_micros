
import time
import math
import pybullet as p
import pybullet_data

# ==========================================================
# 1. CONFIGURACION GENERAL
# ==========================================================

p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.81)
p.setTimeStep(1 / 240)
p.setRealTimeSimulation(0)

p.loadURDF("plane.urdf")

DT = 1 / 240

# ==========================================================
# 2. FUNCIONES AUXILIARES
# ==========================================================

def crear_caja(nombre, posicion, dimensiones, color, masa=0):
    visual = p.createVisualShape(
        p.GEOM_BOX,
        halfExtents=dimensiones,
        rgbaColor=color
    )

    colision = p.createCollisionShape(
        p.GEOM_BOX,
        halfExtents=dimensiones
    )

    cuerpo = p.createMultiBody(
        baseMass=masa,
        baseCollisionShapeIndex=colision,
        baseVisualShapeIndex=visual,
        basePosition=posicion
    )

    return cuerpo


def crear_texto(texto, posicion, color=(0, 0, 0), tamano=1.5):
    return p.addUserDebugText(
        texto,
        posicion,
        textColorRGB=color,
        textSize=tamano
    )


def mover_objeto(objeto, posicion, yaw=0):
    orientacion = p.getQuaternionFromEuler([0, 0, yaw])

    p.resetBasePositionAndOrientation(
        objeto,
        posicion,
        orientacion
    )


# ==========================================================
# 3. BANDA TRANSPORTADORA
# ==========================================================

crear_caja(
    "Banda",
    [0, 3.2, 0.08],
    [2.7, 0.45, 0.08],
    [0.12, 0.15, 0.20, 1]
)

# Superficie de la banda
crear_caja(
    "Superficie",
    [0, 3.2, 0.17],
    [2.6, 0.38, 0.015],
    [0.25, 0.28, 0.30, 1]
)

# Rodillos
for x in [-2.5, 2.5]:
    rodillo_visual = p.createVisualShape(
        p.GEOM_CYLINDER,
        radius=0.12,
        length=0.9,
        rgbaColor=[0.4, 0.4, 0.4, 1]
    )

    p.createMultiBody(
        baseMass=0,
        baseVisualShapeIndex=rodillo_visual,
        basePosition=[x, 3.2, 0.08],
        baseOrientation=p.getQuaternionFromEuler(
            [math.pi / 2, 0, 0]
        )
    )

# ==========================================================
# 4. SENSOR VIRTUAL DE CONTEO
# ==========================================================

sensor_x = 0.8

crear_caja(
    "Sensor izquierdo",
    [sensor_x, 2.82, 0.62],
    [0.045, 0.045, 0.45],
    [0.1, 0.8, 0.2, 1]
)

crear_caja(
    "Sensor derecho",
    [sensor_x, 3.58, 0.62],
    [0.045, 0.045, 0.45],
    [0.1, 0.8, 0.2, 1]
)

crear_caja(
    "Sensor superior",
    [sensor_x, 3.2, 1.08],
    [0.045, 0.42, 0.045],
    [0.1, 0.8, 0.2, 1]
)

crear_texto(
    "SENSOR DE CONTEO",
    [sensor_x - 0.8, 3.2, 1.35],
    [0, 0.5, 0]
)

# ==========================================================
# 5. MONEDAS
# ==========================================================

# Denominaciones de ejemplo en pesos colombianos
valores = [50, 100, 200, 500, 1000]

# Posiciones iniciales sobre la banda
posiciones_iniciales = [-2.2, -1.55, -0.9, -0.25, 0.4]

monedas = []

for i, valor in enumerate(valores):

    radio = 0.10 if valor < 500 else 0.12

    visual = p.createVisualShape(
        p.GEOM_CYLINDER,
        radius=radio,
        length=0.035,
        rgbaColor=[0.85, 0.65, 0.15, 1]
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
            posiciones_iniciales[i],
            3.2,
            0.22
        ]
    )

    monedas.append({
        "id": moneda,
        "valor": valor,
        "contada": False,
        "recolectada": False,
        "slot": i
    })

# ==========================================================
# 6. CONTADOR
# ==========================================================

cantidad_monedas = 0
valor_total = 0

texto_id = crear_texto(
    "MONEDAS: 0 | VALOR: $0 | RECOLECTADAS: 0",
    [-2.5, 4.1, 1.0],
    [0, 0, 0]
)

# ==========================================================
# 7. RAMPA Y ZONA DE DESCARGA
# ==========================================================

# Rampa visual de descarga
crear_caja(
    "Rampa de descarga",
    [2.85, 3.0, 0.18],
    [0.45, 0.25, 0.04],
    [0.5, 0.5, 0.5, 1]
)

crear_texto(
    "ZONA DE DESCARGA",
    [2.1, 3.65, 0.65],
    [0.2, 0.2, 0.2]
)

# ==========================================================
# 8. CARRO RECOLECTOR
# ==========================================================

carro_x = 3.5
carro_y = 2.2
carro_z = 0.22

# Chasis
carro = crear_caja(
    "Chasis del carro",
    [carro_x, carro_y, carro_z],
    [0.45, 0.32, 0.12],
    [0.1, 0.3, 0.8, 1]
)

# Canastilla
canastilla = crear_caja(
    "Canastilla recolectora",
    [carro_x, carro_y, 0.52],
    [0.40, 0.35, 0.08],
    [0.1, 0.4, 0.85, 1]
)

# Paredes de la canastilla
paredes = []

paredes.append(crear_caja(
    "Pared trasera",
    [carro_x, carro_y + 0.32, 0.72],
    [0.40, 0.035, 0.15],
    [0.1, 0.4, 0.85, 1]
))

paredes.append(crear_caja(
    "Pared izquierda",
    [carro_x - 0.37, carro_y, 0.72],
    [0.035, 0.32, 0.15],
    [0.1, 0.4, 0.85, 1]
))

paredes.append(crear_caja(
    "Pared derecha",
    [carro_x + 0.37, carro_y, 0.72],
    [0.035, 0.32, 0.15],
    [0.1, 0.4, 0.85, 1]
))

# Cuatro ruedas
ruedas = []

for dx, dy in [
    (0.32, 0.28),
    (0.32, -0.28),
    (-0.32, 0.28),
    (-0.32, -0.28)
]:

    visual_rueda = p.createVisualShape(
        p.GEOM_CYLINDER,
        radius=0.15,
        length=0.10,
        rgbaColor=[0.08, 0.08, 0.08, 1]
    )

    rueda = p.createMultiBody(
        baseMass=0,
        baseVisualShapeIndex=visual_rueda,
        basePosition=[
            carro_x + dx,
            carro_y + dy,
            0.11
        ],
        baseOrientation=p.getQuaternionFromEuler(
            [math.pi / 2, 0, 0]
        )
    )

    ruedas.append((rueda, dx, dy))

# ==========================================================
# 9. OBSTACULOS Y META
# ==========================================================

obstaculos = [
    (-1.0, 0.0),
    (1.0, -1.5),
    (-1.5, -3.0)
]

for x, y in obstaculos:
    crear_caja(
        "Obstaculo",
        [x, y, 0.35],
        [0.30, 0.30, 0.35],
        [0.8, 0.2, 0.15, 1]
    )

crear_caja(
    "Meta",
    [3.0, -3.5, 0.03],
    [0.5, 0.5, 0.03],
    [0.1, 0.8, 0.2, 1]
)

crear_texto(
    "META",
    [2.7, -3.5, 0.8],
    [0, 0.6, 0]
)

# ==========================================================
# 10. RUTA DEL CARRO
# ==========================================================

ruta = [
    (carro_x, carro_y),
    (3.5, 0.5),
    (2.5, 0.5),
    (0.0, 0.5),
    (0.0, -1.0),
    (-2.5, -1.0),
    (-2.5, -3.5),
    (0.0, -3.5),
    (3.0, -3.5)
]

# Dibujar ruta
for i in range(len(ruta) - 1):
    p.addUserDebugLine(
        [ruta[i][0], ruta[i][1], 0.03],
        [ruta[i + 1][0], ruta[i + 1][1], 0.03],
        [0.1, 0.4, 1],
        lineWidth=3
    )

# ==========================================================
# 11. ACTUALIZAR CARRO Y CANASTILLA
# ==========================================================

def actualizar_carro(x, y, yaw):

    mover_objeto(carro, [x, y, carro_z], yaw)

    mover_objeto(canastilla, [x, y, 0.52], yaw)

    # Pared trasera
    mover_objeto(
        paredes[0],
        [x, y + 0.32, 0.72],
        yaw
    )

    # Pared izquierda
    mover_objeto(
        paredes[1],
        [x - 0.37, y, 0.72],
        yaw
    )

    # Pared derecha
    mover_objeto(
        paredes[2],
        [x + 0.37, y, 0.72],
        yaw
    )

    # Ruedas
    for rueda, dx, dy in ruedas:

        wx = x + dx * math.cos(yaw) - dy * math.sin(yaw)
        wy = y + dx * math.sin(yaw) + dy * math.cos(yaw)

        mover_objeto(
            rueda,
            [wx, wy, 0.11],
            yaw
        )

# ==========================================================
# 12. VARIABLES DE MOVIMIENTO
# ==========================================================

velocidad_banda = 0.65
velocidad_carro = 0.6

indice_ruta = 0
posicion_carro = [carro_x, carro_y]

carro_en_movimiento = False
carro_terminado = False

# ==========================================================
# 13. BUCLE PRINCIPAL
# ==========================================================

try:

    while p.isConnected():

        # ----------------------------------------------
        # A. MOVIMIENTO DE LAS MONEDAS
        # ----------------------------------------------

        for moneda in monedas:

            if moneda["recolectada"]:
                continue

            posicion, orientacion = p.getBasePositionAndOrientation(
                moneda["id"]
            )

            x, y, z = posicion

            # Avance de la moneda por la banda
            x += velocidad_banda * DT

            # Detección del sensor
            if x >= sensor_x and not moneda["contada"]:

                moneda["contada"] = True

                cantidad_monedas += 1
                valor_total += moneda["valor"]

                print(
                    f"Moneda: ${moneda['valor']} | "
                    f"Cantidad: {cantidad_monedas} | "
                    f"Total: ${valor_total}"
                )

                p.removeUserDebugItem(texto_id)

                texto_id = crear_texto(
                    f"MONEDAS: {cantidad_monedas} | "
                    f"VALOR: ${valor_total} | "
                    f"RECOLECTADAS: "
                    f"{sum(m['recolectada'] for m in monedas)}",
                    [-2.5, 4.1, 1.0],
                    [0, 0, 0]
                )

            # Llegada a la zona de descarga
            if x >= 2.45:

                moneda["recolectada"] = True

                slot = moneda["slot"]

                # Posición de la moneda dentro de la canastilla
                fila = slot // 3
                columna = slot % 3

                destino_x = carro_x + (columna - 1) * 0.18
                destino_y = carro_y + (fila - 0.5) * 0.18
                destino_z = 0.68 + fila * 0.05

                mover_objeto(
                    moneda["id"],
                    [destino_x, destino_y, destino_z]
                )

                print(
                    f"Moneda de ${moneda['valor']} "
                    "depositada en la canastilla."
                )

            else:

                mover_objeto(
                    moneda["id"],
                    [x, y, z]
                )

        # ----------------------------------------------
        # B. INICIO DEL CARRO TRAS LA RECOLECCION
        # ----------------------------------------------

        todas_recolectadas = all(
            moneda["recolectada"] for moneda in monedas
        )

        if todas_recolectadas and not carro_en_movimiento:
            carro_en_movimiento = True
            print("Todas las monedas fueron recolectadas.")
            print("El carro inicia su recorrido hacia la meta.")

        # ----------------------------------------------
        # C. MOVIMIENTO DEL CARRO
        # ----------------------------------------------

        if carro_en_movimiento and not carro_terminado:

            if indice_ruta < len(ruta) - 1:

                objetivo = ruta[indice_ruta + 1]

                dx = objetivo[0] - posicion_carro[0]
                dy = objetivo[1] - posicion_carro[1]

                distancia = math.sqrt(dx * dx + dy * dy)

                if distancia < 0.04:

                    posicion_carro = list(objetivo)
                    indice_ruta += 1

                else:

                    yaw = math.atan2(dy, dx)

                    avance = min(
                        velocidad_carro * DT,
                        distancia
                    )

                    posicion_carro[0] += avance * dx / distancia
                    posicion_carro[1] += avance * dy / distancia

                    actualizar_carro(
                        posicion_carro[0],
                        posicion_carro[1],
                        yaw
                    )

            else:

                carro_terminado = True
                print("El carro llegó a la meta.")

        # ----------------------------------------------
        # D. MANTENER LAS MONEDAS DENTRO DEL CARRO
        # ----------------------------------------------

        for moneda in monedas:

            if moneda["recolectada"]:

                slot = moneda["slot"]

                fila = slot // 3
                columna = slot % 3

                dx = (columna - 1) * 0.18
                dy = (fila - 0.5) * 0.18

                yaw = 0

                destino_x = (
                    posicion_carro[0]
                    + dx * math.cos(yaw)
                    - dy * math.sin(yaw)
                )

                destino_y = (
                    posicion_carro[1]
                    + dx * math.sin(yaw)
                    + dy * math.cos(yaw)
                )

                mover_objeto(
                    moneda["id"],
                    [
                        destino_x,
                        destino_y,
                        0.68 + fila * 0.05
                    ]
                )

        # ----------------------------------------------
        # E. ACTUALIZAR SIMULACION
        # ----------------------------------------------

        p.stepSimulation()
        time.sleep(DT)

except KeyboardInterrupt:
    print("Simulacion detenida.")

finally:
    if p.isConnected():
        p.disconnect()
