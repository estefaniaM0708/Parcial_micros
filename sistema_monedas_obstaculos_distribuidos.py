import pybullet as p
import pybullet_data
import time
import math
import heapq

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
    cameraDistance=13.0,
    cameraYaw=45,
    cameraPitch=-35,
    cameraTargetPosition=[2.0, -1.8, 0.35]
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
piezas_vasos = []

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
    piezas = []

    piezas.append(crear_caja(
        f"Base vaso {valor}",
        [x_vaso, y_vaso, 0.09],
        [0.36, 0.32, 0.07],
        COLOR_VASO
    ))

    altura_pared = 0.12
    z_pared = 0.21

    piezas.append(crear_caja(
        f"Pared trasera {valor}",
        [x_vaso + 0.33, y_vaso, z_pared],
        [0.035, 0.32, altura_pared],
        COLOR_VASO
    ))

    piezas.append(crear_caja(
        f"Pared frontal {valor}",
        [x_vaso - 0.33, y_vaso, z_pared],
        [0.035, 0.32, altura_pared],
        COLOR_VASO
    ))

    for lado in [-1, 1]:

        piezas.append(crear_caja(
            f"Pared lateral {valor}",
            [x_vaso, y_vaso + lado * 0.29, z_pared],
            [0.36, 0.035, altura_pared],
            COLOR_VASO
        ))

    piezas_vasos.append(piezas)

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
# 12. CARRO AUTONOMO PARA RECOGER LOS VASITOS
# ============================================================

# Tres obstaculos ubicados en el corredor entre la clasificacion y la zona de entrega.
# Forman una barrera que obliga al planificador A* a rodearlos por un extremo.
obstaculos_carro = [(4.1, -2.2), (3.9, 0.5), (6.0, -4.2)]
for i, (ox, oy) in enumerate(obstaculos_carro, start=1):
    crear_caja(f"Obstaculo {i}", [ox, oy, 0.35], [0.32, 0.32, 0.35], [0.85, 0.18, 0.12, 1])
    crear_texto(f"OBSTACULO {i}", [ox - 0.55, oy, 0.78], [0.65, 0.05, 0.02], 0.9)

# La zona de entrega y la meta quedan alejadas para que el trayecto sea mas largo.
zona_entrega = (7.0, -5.5)
meta_final = (10.0, -8.0)
crear_caja("Zona de entrega", [zona_entrega[0], zona_entrega[1], 0.04], [0.55, 0.55, 0.04], [0.95, 0.72, 0.08, 1])
crear_caja("Meta carro", [meta_final[0], meta_final[1], 0.04], [0.48, 0.48, 0.04], [0.1, 0.8, 0.2, 1])
crear_texto("ZONA DE ENTREGA", [6.1, -4.75, 0.65], [0.55, 0.35, 0.0])
crear_texto("META FINAL", [9.3, -7.9, 0.65], [0.0, 0.55, 0.0])

carro_pos = [5.7, -3.8]
carro_z = 0.22
chasis = crear_caja("Chasis carro", [carro_pos[0], carro_pos[1], carro_z], [0.48, 0.38, 0.12], [0.08, 0.25, 0.78, 1])
canasta = crear_caja("Canastilla carro", [carro_pos[0], carro_pos[1], 0.52], [0.43, 0.34, 0.08], [0.12, 0.45, 0.9, 1])
ruedas_carro=[]
for dx,dy in [(0.34,0.28),(0.34,-0.28),(-0.34,0.28),(-0.34,-0.28)]:
    v=p.createVisualShape(p.GEOM_CYLINDER,radius=0.14,length=0.10,rgbaColor=[0.07,0.07,0.07,1])
    r=p.createMultiBody(baseMass=0,baseVisualShapeIndex=v,basePosition=[carro_pos[0]+dx,carro_pos[1]+dy,0.12],baseOrientation=p.getQuaternionFromEuler([math.pi/2,0,0]))
    ruedas_carro.append((r,dx,dy))

# Cada vasito se recoge por turnos; los componentes y sus monedas viajan juntos.
indice_vaso_carro = 0
vaso_en_transporte = False
carro_finalizado = False
velocidad_carro = 0.85
ruta_carro = []
objetivo_carro = None
objetivo_calculado = None
indice_punto_ruta = 0
# Guarda la geometría inicial del vasito y sus monedas para evitar que
# el desplazamiento vertical se acumule en cada actualización.
offsets_vasos = {}


def actualizar_carro_autonomo(x, y, yaw=0):
    p.resetBasePositionAndOrientation(chasis,[x,y,carro_z],p.getQuaternionFromEuler([0,0,yaw]))
    p.resetBasePositionAndOrientation(canasta,[x,y,0.52],p.getQuaternionFromEuler([0,0,yaw]))
    for rueda,dx,dy in ruedas_carro:
        wx=x+dx*math.cos(yaw)-dy*math.sin(yaw)
        wy=y+dx*math.sin(yaw)+dy*math.cos(yaw)
        p.resetBasePositionAndOrientation(rueda,[wx,wy,0.12],p.getQuaternionFromEuler([math.pi/2,0,yaw]))


def mover_piezas_vaso(indice, x, y):
    """Mueve el vasito y sus monedas manteniendo sus posiciones relativas."""
    comp = compartimentos[indice]
    origen_x, origen_y = x_vaso, comp["y"]

    # Capturar una sola vez la posición original de cada pieza y moneda.
    if indice not in offsets_vasos:
        offsets = []
        cuerpos = piezas_vasos[indice] + comp["monedas"]
        for cuerpo in cuerpos:
            pos, orn = p.getBasePositionAndOrientation(cuerpo)
            offsets.append((
                cuerpo,
                pos[0] - origen_x,
                pos[1] - origen_y,
                pos[2] + 0.30,
                orn
            ))
        offsets_vasos[indice] = offsets

    # Reubicar siempre desde la posición original; no sumar desplazamientos.
    for cuerpo, dx, dy, z_destino, orn in offsets_vasos[indice]:
        p.resetBasePositionAndOrientation(
            cuerpo, [x + dx, y + dy, z_destino], orn
        )


def calcular_ruta_evadiendo_obstaculos(inicio, fin):
    """Calcula una ruta A* en una cuadrícula que rodea los obstáculos."""
    paso = 0.25
    margen = 0.78
    xmin, xmax = -4.0, 11.0
    ymin, ymax = -9.0, 4.0

    def nodo(punto):
        return (round(punto[0] / paso), round(punto[1] / paso))

    def xy(n):
        return (n[0] * paso, n[1] * paso)

    inicio_n, fin_n = nodo(inicio), nodo(fin)

    def dentro(n):
        x, y = xy(n)
        return xmin <= x <= xmax and ymin <= y <= ymax

    def bloqueado(n):
        x, y = xy(n)
        for ox, oy in obstaculos_carro:
            if math.hypot(x - ox, y - oy) < margen:
                return True
        return False

    vecinos = [(-1, 0), (1, 0), (0, -1), (0, 1),
               (-1, -1), (-1, 1), (1, -1), (1, 1)]
    cola = [(0.0, inicio_n)]
    anterior = {}
    costo = {inicio_n: 0.0}
    visitados = set()

    while cola:
        _, actual = heapq.heappop(cola)
        if actual in visitados:
            continue
        visitados.add(actual)
        if actual == fin_n:
            break

        for dx, dy in vecinos:
            sig = (actual[0] + dx, actual[1] + dy)
            if not dentro(sig):
                continue
            # Se permite el nodo inicial/final para que el carro pueda
            # acercarse al punto de recogida o entrega.
            if sig not in (inicio_n, fin_n) and bloqueado(sig):
                continue
            nuevo = costo[actual] + (math.sqrt(2) if dx and dy else 1.0)
            if nuevo < costo.get(sig, float("inf")):
                costo[sig] = nuevo
                anterior[sig] = actual
                fx, fy = xy(fin_n)
                sx, sy = xy(sig)
                heuristica = math.hypot(fx - sx, fy - sy) / paso
                heapq.heappush(cola, (nuevo + heuristica, sig))

    if fin_n not in costo:
        # Respaldo: ruta directa si no se encuentra camino.
        return [fin]

    camino = [fin_n]
    while camino[-1] != inicio_n:
        camino.append(anterior[camino[-1]])
    camino.reverse()
    return [xy(n) for n in camino[1:]]

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

        # ------------------------------------------------
        # CARRO AUTONOMO: ruta calculada para rodear obstáculos
        # ------------------------------------------------
        if not carro_finalizado and all(m["estado"] == "clasificada" for m in monedas):
            if objetivo_carro is None:
                if indice_vaso_carro < len(compartimentos):
                    objetivo_carro = (3.25, compartimentos[indice_vaso_carro]["y"])
                else:
                    objetivo_carro = meta_final

            # Recalcular ruta cuando cambia el objetivo (vasito/entrega/meta).
            if objetivo_calculado != objetivo_carro:
                ruta_carro = calcular_ruta_evadiendo_obstaculos(carro_pos, objetivo_carro)
                indice_punto_ruta = 0
                objetivo_calculado = objetivo_carro

            if indice_punto_ruta >= len(ruta_carro):
                carro_pos[:] = objetivo_carro
                if indice_vaso_carro < len(compartimentos) and not vaso_en_transporte:
                    vaso_en_transporte = True
                    mover_piezas_vaso(indice_vaso_carro, carro_pos[0], carro_pos[1])
                    print(f"Carro recogió el vasito de ${compartimentos[indice_vaso_carro]['valor']}.")
                    objetivo_carro = zona_entrega
                elif vaso_en_transporte:
                    vaso_en_transporte = False
                    print(f"Vasito de ${compartimentos[indice_vaso_carro]['valor']} entregado.")
                    indice_vaso_carro += 1
                    objetivo_carro = None
                else:
                    carro_finalizado = True
                    print("¡Carro llegó a la meta con los vasitos recolectados!")
            else:
                punto = ruta_carro[indice_punto_ruta]
                dx = punto[0] - carro_pos[0]
                dy = punto[1] - carro_pos[1]
                dist = math.hypot(dx, dy)
                if dist < 0.07:
                    carro_pos[:] = punto
                    indice_punto_ruta += 1
                elif dist > 0:
                    yaw = math.atan2(dy, dx)
                    paso_carro = min(velocidad_carro * DT, dist)
                    carro_pos[0] += paso_carro * dx / dist
                    carro_pos[1] += paso_carro * dy / dist
                    actualizar_carro_autonomo(carro_pos[0], carro_pos[1], yaw)
                    if vaso_en_transporte:
                        mover_piezas_vaso(indice_vaso_carro, carro_pos[0], carro_pos[1])

        p.stepSimulation()
        time.sleep(DT)

except KeyboardInterrupt:

    print("Simulación detenida.")

finally:

    if p.isConnected():
        p.disconnect()
