"""
generar_cad.py  -  CAD del carro recolector de vasos (Grupo 5)

Una sola fuente de verdad para el diseño mecánico del carro. A partir de las
cotas reales (en mm) este script genera:

  carro.scad           modelo paramétrico para OpenSCAD (editable; F6 + F7 exporta STL)
  carro_ensamble.stl   ensamble 3D en mm (para ver en cualquier visor/slicer)
  carro.urdf           modelo para PyBullet (escala configurable)
  plano_carro.png      plano con vistas superior y lateral acotadas

Uso:  python generar_cad.py            (escala del URDF = 4, la de la simulación)
      python generar_cad.py --escala 1 (URDF a tamaño real)
"""

import argparse
import math
import os
import struct

AQUI = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# COTAS DEL CARRO (mm). Ejes: X adelante, Y izquierda, Z arriba. Origen: centro
# del chasis inferior a nivel del piso.
# ---------------------------------------------------------------------------
L, W = 220.0, 140.0            # chasis inferior (acrilico / PLA 4 mm)
T_CHASIS = 4.0
Z_CHASIS = 42.0                # cara inferior del chasis
R_RUEDA, A_RUEDA = 32.5, 26.0  # rueda TT de 65 mm
X_EJE = -30.0                  # eje de las ruedas motrices
Y_RUEDA = W / 2 + 3 + A_RUEDA / 2
MOTOR = (65.0, 22.5, 18.8)     # motorreductor TT (largo en Y)
X_LOCA, R_BOLA = 85.0, 10.0    # rueda loca (ball caster)
H_SEPARADOR, R_SEPARADOR = 40.0, 3.0
T_PISO2 = 3.0                  # chasis superior
Z_PISO2 = Z_CHASIS + T_CHASIS + H_SEPARADOR
X_VASO = -55.0                 # porta-vaso sobre el piso superior
R_EXT_VASO, R_INT_VASO, H_PORTAVASO = 43.0, 39.0, 30.0

# Componentes (centro x, centro y, tamaño x, tamaño y, tamaño z, z inferior, color)
Z_SUP = Z_CHASIS + T_CHASIS
COMPONENTES = {
    "esp32_s3":  (35.0, 32.0, 69.0, 26.0, 10.0, Z_SUP, (0.10, 0.10, 0.12)),
    "tb6612":    (35.0, -28.0, 21.0, 20.0, 8.0, Z_SUP, (0.75, 0.10, 0.10)),
    "bateria":   (-30.0, 0.0, 77.0, 41.0, 21.0, Z_SUP, (0.15, 0.15, 0.55)),
    "buck_5v":   (72.0, -38.0, 43.0, 21.0, 14.0, Z_SUP, (0.10, 0.35, 0.65)),
}
HCSR04 = [(+1, L / 2 + 2.0), (-1, -L / 2 - 2.0)]   # (sentido, x de la placa)
Z_HCSR04 = Z_SUP + 16.0
IR_LINEA = [(L / 2 - 12.0, y) for y in (-20.0, 0.0, 20.0)]

COLORES = {
    "chasis": (0.95, 0.55, 0.10), "piso2": (0.85, 0.85, 0.90), "rueda": (0.08, 0.08, 0.08),
    "rin": (0.95, 0.80, 0.10), "motor": (0.95, 0.80, 0.10), "loca": (0.6, 0.6, 0.6),
    "separador": (0.80, 0.70, 0.30), "portavaso": (0.20, 0.55, 0.90), "sensor": (0.10, 0.45, 0.80),
    "transductor": (0.80, 0.80, 0.82), "ir": (0.05, 0.05, 0.05),
}


# ---------------------------------------------------------------------------
# Lista de piezas como primitivas (sirve para STL, URDF y plano)
# ---------------------------------------------------------------------------
def piezas():
    """Devuelve (nombre, tipo, parametros, color). Tipos: caja / cilindro / esfera.
    caja: (cx, cy, cz, sx, sy, sz); cilindro: (cx, cy, cz, r, h, eje); esfera: (cx, cy, cz, r)"""
    p = []
    p.append(("chasis", "caja", (0, 0, Z_CHASIS + T_CHASIS / 2, L, W, T_CHASIS), COLORES["chasis"]))
    p.append(("piso2", "caja", (0, 0, Z_PISO2 + T_PISO2 / 2, L, W, T_PISO2), COLORES["piso2"]))
    for sx in (-1, 1):
        for sy in (-1, 1):
            p.append(("separador", "cilindro",
                      (sx * (L / 2 - 15), sy * (W / 2 - 10), Z_SUP + H_SEPARADOR / 2,
                       R_SEPARADOR, H_SEPARADOR, "z"), COLORES["separador"]))
    for s in (-1, 1):
        p.append(("motor", "caja", (X_EJE, s * (5 + MOTOR[0] / 2), Z_CHASIS - MOTOR[2] / 2,
                                    MOTOR[1], MOTOR[0], MOTOR[2]), COLORES["motor"]))
        p.append(("rueda", "cilindro", (X_EJE, s * Y_RUEDA, R_RUEDA, R_RUEDA, A_RUEDA, "y"), COLORES["rueda"]))
        p.append(("rin", "cilindro", (X_EJE, s * (Y_RUEDA + A_RUEDA / 2), R_RUEDA,
                                      R_RUEDA * 0.55, 2.0, "y"), COLORES["rin"]))
    p.append(("soporte_loca", "caja", (X_LOCA, 0, (2 * R_BOLA + Z_CHASIS) / 2 + R_BOLA / 2,
                                       30, 30, Z_CHASIS - 1.5 * R_BOLA), COLORES["loca"]))
    p.append(("bola_loca", "esfera", (X_LOCA, 0, R_BOLA, R_BOLA), COLORES["loca"]))
    for nombre, (cx, cy, sx, sy, sz, z0, color) in COMPONENTES.items():
        p.append((nombre, "caja", (cx, cy, z0 + sz / 2, sx, sy, sz), color))
    for sentido, x in HCSR04:
        p.append(("hcsr04", "caja", (x, 0, Z_HCSR04, 1.6, 45.0, 20.0), COLORES["sensor"]))
        for y in (-13.0, 13.0):
            p.append(("transductor", "cilindro", (x + sentido * 6.8, y, Z_HCSR04, 8.0, 12.0, "x"),
                      COLORES["transductor"]))
    for x, y in IR_LINEA:
        p.append(("ir_linea", "caja", (x, y, Z_CHASIS - 6, 10, 10, 12), COLORES["ir"]))
    # porta-vaso: anillo formado por 24 segmentos (para STL/URDF) / tubo en OpenSCAD
    n = 24
    r_med = (R_EXT_VASO + R_INT_VASO) / 2
    ancho = 2 * math.pi * r_med / n * 1.05
    for i in range(n):
        a = 2 * math.pi * i / n
        p.append(("portavaso", "caja_rot",
                  (X_VASO + r_med * math.cos(a), r_med * math.sin(a), Z_PISO2 + T_PISO2 + H_PORTAVASO / 2,
                   R_EXT_VASO - R_INT_VASO, ancho, H_PORTAVASO, a), COLORES["portavaso"]))
    return p


# ---------------------------------------------------------------------------
# 1) OpenSCAD
# ---------------------------------------------------------------------------
def generar_scad(ruta):
    s = f"""// carro.scad - Carro recolector de vasos (Grupo 5) - cotas en mm
// Generado por generar_cad.py. Abrir en OpenSCAD: F5 vista previa, F6 render, F7 exportar STL.
// Cambia "pieza" para exportar cada parte imprimible por separado.

pieza = "ensamble";   // "ensamble", "chasis", "piso2", "portavaso", "soporte_sensor"
$fn = 64;

L = {L}; W = {W};
t_chasis = {T_CHASIS}; z_chasis = {Z_CHASIS};
r_rueda = {R_RUEDA}; a_rueda = {A_RUEDA};
x_eje = {X_EJE}; y_rueda = {Y_RUEDA};
x_loca = {X_LOCA}; r_bola = {R_BOLA};
h_sep = {H_SEPARADOR}; t_piso2 = {T_PISO2};
z_piso2 = z_chasis + t_chasis + h_sep;
x_vaso = {X_VASO}; r_ext_vaso = {R_EXT_VASO}; r_int_vaso = {R_INT_VASO}; h_portavaso = {H_PORTAVASO};
r_esquina = 10;

module placa_redondeada(l, w, t, r) {{
    hull() for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * (l / 2 - r), sy * (w / 2 - r), 0]) cylinder(r = r, h = t);
}}

// Chasis inferior: agujeros para separadores, rueda loca, motores y paso de cables
module chasis() {{
    difference() {{
        placa_redondeada(L, W, t_chasis, r_esquina);
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * (L / 2 - 15), sy * (W / 2 - 10), -1]) cylinder(d = 3.4, h = t_chasis + 2);
        for (dx = [-10, 10], dy = [-10, 10])                 // rueda loca
            translate([x_loca + dx, dy, -1]) cylinder(d = 3.4, h = t_chasis + 2);
        for (s = [-1, 1], dx = [-8, 8])                      // soportes de motor
            translate([x_eje + dx, s * 40, -1]) cylinder(d = 3.4, h = t_chasis + 2);
        translate([0, 0, -1]) linear_extrude(t_chasis + 2)   // paso de cables
            hull() {{ translate([-10, 0]) circle(d = 14); translate([10, 0]) circle(d = 14); }}
        for (y = [-20, 0, 20])                                // sensores IR de linea
            translate([L / 2 - 12, y, -1]) cylinder(d = 3.4, h = t_chasis + 2);
    }}
}}

// Chasis superior con agujero para el porta-vaso y ventilacion
module piso2() {{
    difference() {{
        placa_redondeada(L, W, t_piso2, r_esquina);
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * (L / 2 - 15), sy * (W / 2 - 10), -1]) cylinder(d = 3.4, h = t_piso2 + 2);
        for (i = [0 : 3])
            translate([20 + i * 18, -25, -1]) cube([10, 50, t_piso2 + 2]);
    }}
}}

// Porta-vaso: tubo con base, recibe un vaso de 70 mm
module portavaso() {{
    difference() {{
        union() {{
            cylinder(r = r_ext_vaso, h = h_portavaso);
            cylinder(r = r_ext_vaso + 6, h = 2);             // pestaña de apoyo
        }}
        translate([0, 0, 2]) cylinder(r = r_int_vaso, h = h_portavaso);
        translate([0, 0, -1]) cylinder(r = r_int_vaso - 8, h = 4);
        translate([-r_ext_vaso - 1, -8, 12]) cube([10, 16, h_portavaso]);   // ranura sensor
    }}
}}

// Soporte en L para el HC-SR04
module soporte_sensor() {{
    difference() {{
        union() {{
            translate([-2, -25, 0]) cube([2, 50, 26]);
            translate([-14, -25, 0]) cube([14, 50, 2]);
        }}
        for (y = [-13, 13]) translate([-3, y, 16]) rotate([0, 90, 0]) cylinder(d = 16.5, h = 4);
        for (y = [-18, 18]) translate([-7, y, -1]) cylinder(d = 3.4, h = 4);
    }}
}}

module rueda() {{ rotate([90, 0, 0]) cylinder(r = r_rueda, h = a_rueda, center = true); }}
module motor_tt() {{ cube([22.5, 65, 18.8], center = true); }}

module ensamble() {{
    color("orange") translate([0, 0, z_chasis]) chasis();
    color("gainsboro") translate([0, 0, z_piso2]) piso2();
    color("goldenrod") for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * (L / 2 - 15), sy * (W / 2 - 10), z_chasis + t_chasis]) cylinder(r = 3, h = h_sep);
    for (s = [-1, 1]) {{
        color("gold") translate([x_eje, s * (5 + 65 / 2), z_chasis - 18.8 / 2]) motor_tt();
        color("black") translate([x_eje, s * y_rueda, r_rueda]) rueda();
    }}
    color("silver") translate([x_loca, 0, r_bola]) sphere(r = r_bola);
    color("silver") translate([x_loca - 15, -15, 2 * r_bola - 2]) cube([30, 30, z_chasis - 2 * r_bola + 2]);
    color("dodgerblue") translate([x_vaso, 0, z_piso2 + t_piso2]) portavaso();
    color("steelblue") translate([L / 2, 0, z_chasis + t_chasis]) soporte_sensor();
    color("steelblue") translate([-L / 2, 0, z_chasis + t_chasis]) mirror([1, 0, 0]) soporte_sensor();
"""
    for nombre, (cx, cy, sx, sy, sz, z0, color) in COMPONENTES.items():
        s += (f"    color([{color[0]}, {color[1]}, {color[2]}]) "
              f"translate([{cx - sx / 2}, {cy - sy / 2}, {z0}]) cube([{sx}, {sy}, {sz}]);  // {nombre}\n")
    s += """}

if (pieza == "ensamble") ensamble();
if (pieza == "chasis") chasis();
if (pieza == "piso2") piso2();
if (pieza == "portavaso") portavaso();
if (pieza == "soporte_sensor") soporte_sensor();
"""
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(s)


# ---------------------------------------------------------------------------
# 2) STL (ensamble de primitivas)
# ---------------------------------------------------------------------------
def _caja(c, s, ang=0.0):
    cx, cy, cz = c
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    ca, sa = math.cos(ang), math.sin(ang)
    v = []
    for dx, dy, dz in [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                       (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]:
        x, y = dx * hx, dy * hy
        v.append((cx + ca * x - sa * y, cy + sa * x + ca * y, cz + dz * hz))
    caras = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
             (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return [(v[a], v[b], v[c]) for a, b, c in caras]


def _cilindro(c, r, h, eje, n=40):
    def punto(a, t):
        u, w = r * math.cos(a), r * math.sin(a)
        if eje == "z":
            return (c[0] + u, c[1] + w, c[2] + t)
        if eje == "y":
            return (c[0] + u, c[1] + t, c[2] + w)
        return (c[0] + t, c[1] + u, c[2] + w)
    tri = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        p0, p1 = punto(a0, -h / 2), punto(a1, -h / 2)
        q0, q1 = punto(a0, h / 2), punto(a1, h / 2)
        cb = {"z": (c[0], c[1], c[2] - h / 2), "y": (c[0], c[1] - h / 2, c[2]), "x": (c[0] - h / 2, c[1], c[2])}[eje]
        ct = {"z": (c[0], c[1], c[2] + h / 2), "y": (c[0], c[1] + h / 2, c[2]), "x": (c[0] + h / 2, c[1], c[2])}[eje]
        tri += [(p0, p1, q1), (p0, q1, q0), (cb, p1, p0), (ct, q0, q1)]
    if eje == "y":   # el eje y invierte la orientacion de las caras
        tri = [(a, c_, b) for a, b, c_ in tri]
    return tri


def _esfera(c, r, n=20):
    tri = []
    for i in range(n):
        t0, t1 = math.pi * i / n, math.pi * (i + 1) / n
        for j in range(2 * n):
            f0, f1 = 2 * math.pi * j / (2 * n), 2 * math.pi * (j + 1) / (2 * n)
            def pt(t, f):
                return (c[0] + r * math.sin(t) * math.cos(f), c[1] + r * math.sin(t) * math.sin(f), c[2] + r * math.cos(t))
            a, b, cc, d = pt(t0, f0), pt(t1, f0), pt(t1, f1), pt(t0, f1)
            tri += [(a, b, cc), (a, cc, d)]
    return tri


def triangulos():
    tri = []
    for nombre, tipo, prm, _ in piezas():
        if tipo == "caja":
            tri += _caja(prm[:3], prm[3:6])
        elif tipo == "caja_rot":
            tri += _caja(prm[:3], prm[3:6], prm[6])
        elif tipo == "cilindro":
            tri += _cilindro(prm[:3], prm[3], prm[4], prm[5])
        else:
            tri += _esfera(prm[:3], prm[3])
    return tri


def generar_stl(ruta):
    tri = triangulos()
    with open(ruta, "wb") as f:
        f.write(b"carro recolector grupo 5 (mm)".ljust(80, b" "))
        f.write(struct.pack("<I", len(tri)))
        for a, b, c in tri:
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            m = math.sqrt(sum(x * x for x in n)) or 1.0
            f.write(struct.pack("<12fH", n[0] / m, n[1] / m, n[2] / m, *a, *b, *c, 0))
    return len(tri)


# ---------------------------------------------------------------------------
# 3) URDF para PyBullet
# ---------------------------------------------------------------------------
def generar_urdf(ruta, escala):
    k = escala / 1000.0                     # mm -> m, multiplicado por la escala
    z_base = Z_CHASIS + T_CHASIS / 2        # el marco del chasis esta en su centro

    def f(v):
        return " ".join("%.5f" % x for x in v)

    visuales = []
    for nombre, tipo, prm, color in piezas():
        if nombre in ("rueda", "rin", "bola_loca"):
            continue
        mat = '<material name="m_%s"><color rgba="%.2f %.2f %.2f 1"/></material>' % (nombre, *color)
        if tipo in ("caja", "caja_rot"):
            cx, cy, cz, sx, sy, sz = prm[:6]
            yaw = prm[6] if tipo == "caja_rot" else 0.0
            visuales.append(
                f'    <visual name="{nombre}"><origin xyz="{f((cx * k, cy * k, (cz - z_base) * k))}" rpy="0 0 {yaw:.5f}"/>'
                f'<geometry><box size="{f((sx * k, sy * k, sz * k))}"/></geometry>{mat}</visual>')
        elif tipo == "cilindro":
            cx, cy, cz, r, h, eje = prm
            rpy = {"z": "0 0 0", "y": "1.5708 0 0", "x": "0 1.5708 0"}[eje]
            visuales.append(
                f'    <visual name="{nombre}"><origin xyz="{f((cx * k, cy * k, (cz - z_base) * k))}" rpy="{rpy}"/>'
                f'<geometry><cylinder radius="{r * k:.5f}" length="{h * k:.5f}"/></geometry>{mat}</visual>')

    masa_chasis = 0.9 * escala                     # kg (0,9 kg reales; se escala para la simulacion)
    Lm, Wm, Hm = L * k, W * k, (Z_PISO2 + T_PISO2 - Z_CHASIS) * k
    Ixx = masa_chasis * (Wm ** 2 + Hm ** 2) / 12
    Iyy = masa_chasis * (Lm ** 2 + Hm ** 2) / 12
    Izz = masa_chasis * (Lm ** 2 + Wm ** 2) / 12
    m_rueda = 0.05 * escala
    Ir_eje = m_rueda * (R_RUEDA * k) ** 2 / 2
    Ir_rad = m_rueda * (3 * (R_RUEDA * k) ** 2 + (A_RUEDA * k) ** 2) / 12
    colisiones = (
        f'    <collision><origin xyz="0 0 0"/><geometry><box size="{f((L * k, W * k, T_CHASIS * k))}"/></geometry></collision>\n'
        f'    <collision><origin xyz="0 0 {(Z_PISO2 + T_PISO2 / 2 - z_base) * k:.5f}"/>'
        f'<geometry><box size="{f((L * k, W * k, T_PISO2 * k))}"/></geometry></collision>\n'
        f'    <collision><origin xyz="{f((-30 * k, 0, (Z_SUP + 10 - z_base) * k))}"/>'
        f'<geometry><box size="{f((90 * k, 50 * k, 20 * k))}"/></geometry></collision>')

    rueda = lambda lado, s: f"""
  <link name="rueda_{lado}">
    <visual><origin rpy="1.5708 0 0"/><geometry><cylinder radius="{R_RUEDA * k:.5f}" length="{A_RUEDA * k:.5f}"/></geometry>
      <material name="m_rueda"><color rgba="0.08 0.08 0.08 1"/></material></visual>
    <visual><origin xyz="0 {s * A_RUEDA / 2 * k:.5f} 0" rpy="1.5708 0 0"/><geometry><cylinder radius="{R_RUEDA * 0.55 * k:.5f}" length="{2 * k:.5f}"/></geometry>
      <material name="m_rin"><color rgba="0.95 0.8 0.1 1"/></material></visual>
    <collision><origin rpy="1.5708 0 0"/><geometry><cylinder radius="{R_RUEDA * k:.5f}" length="{A_RUEDA * k:.5f}"/></geometry></collision>
    <inertial><mass value="{m_rueda:.3f}"/><inertia ixx="{Ir_rad:.6f}" iyy="{Ir_eje:.6f}" izz="{Ir_rad:.6f}" ixy="0" ixz="0" iyz="0"/></inertial>
  </link>
  <joint name="motor_{lado}" type="continuous">
    <parent link="chasis"/><child link="rueda_{lado}"/>
    <origin xyz="{f((X_EJE * k, s * Y_RUEDA * k, (R_RUEDA - z_base) * k))}"/><axis xyz="0 1 0"/>
  </joint>"""

    urdf = f"""<?xml version="1.0"?>
<!-- carro.urdf - Carro recolector de vasos (Grupo 5). Generado por generar_cad.py, escala {escala}:1 -->
<robot name="carro_recolector">
  <link name="chasis">
{chr(10).join(visuales)}
{colisiones}
    <inertial><origin xyz="{-15 * k:.5f} 0 0"/><mass value="{masa_chasis:.3f}"/>
      <inertia ixx="{Ixx:.6f}" iyy="{Iyy:.6f}" izz="{Izz:.6f}" ixy="0" ixz="0" iyz="0"/></inertial>
  </link>
{rueda("izq", 1)}
{rueda("der", -1)}
  <link name="rueda_loca">
    <visual><geometry><sphere radius="{R_BOLA * k:.5f}"/></geometry>
      <material name="m_loca"><color rgba="0.6 0.6 0.6 1"/></material></visual>
    <collision><geometry><sphere radius="{R_BOLA * k:.5f}"/></geometry></collision>
    <inertial><mass value="{0.01 * escala:.3f}"/><inertia ixx="{Ir_rad / 5:.6f}" iyy="{Ir_rad / 5:.6f}" izz="{Ir_rad / 5:.6f}" ixy="0" ixz="0" iyz="0"/></inertial>
  </link>
  <joint name="loca" type="fixed">
    <parent link="chasis"/><child link="rueda_loca"/>
    <origin xyz="{f((X_LOCA * k, 0, (R_BOLA - z_base) * k))}"/>
  </joint>
  <link name="porta_vaso"><inertial><mass value="0.001"/><inertia ixx="1e-6" iyy="1e-6" izz="1e-6" ixy="0" ixz="0" iyz="0"/></inertial></link>
  <joint name="porta_vaso" type="fixed">
    <parent link="chasis"/><child link="porta_vaso"/>
    <origin xyz="{f((X_VASO * k, 0, (Z_PISO2 + T_PISO2 - z_base) * k))}"/>
  </joint>
  <link name="sensor_frontal"><inertial><mass value="0.001"/><inertia ixx="1e-6" iyy="1e-6" izz="1e-6" ixy="0" ixz="0" iyz="0"/></inertial></link>
  <joint name="sensor_frontal" type="fixed">
    <parent link="chasis"/><child link="sensor_frontal"/>
    <origin xyz="{f(((L / 2 + 14) * k, 0, (Z_HCSR04 - z_base) * k))}"/>
  </joint>
  <link name="sensor_trasero"><inertial><mass value="0.001"/><inertia ixx="1e-6" iyy="1e-6" izz="1e-6" ixy="0" ixz="0" iyz="0"/></inertial></link>
  <joint name="sensor_trasero" type="fixed">
    <parent link="chasis"/><child link="sensor_trasero"/>
    <origin xyz="{f((-(L / 2 + 14) * k, 0, (Z_HCSR04 - z_base) * k))}" rpy="0 0 3.14159"/>
  </joint>
</robot>
"""
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(urdf)


# ---------------------------------------------------------------------------
# 4) Plano acotado
# ---------------------------------------------------------------------------
def generar_plano(ruta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle, Circle

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 6.2))
    fig.suptitle("Carro recolector de vasos — Grupo 5 (cotas en mm)", fontsize=14, weight="bold")

    def cota(ax, p0, p1, texto, off=(0, 0)):
        ax.annotate("", p0, p1, arrowprops=dict(arrowstyle="<->", lw=1))
        ax.text((p0[0] + p1[0]) / 2 + off[0], (p0[1] + p1[1]) / 2 + off[1], texto,
                ha="center", va="center", fontsize=9, backgroundcolor="white")

    # --- vista superior ---
    a1.set_title("Vista superior")
    a1.add_patch(Rectangle((-L / 2, -W / 2), L, W, fc=COLORES["chasis"], ec="k", alpha=0.35))
    for s in (-1, 1):
        a1.add_patch(Rectangle((X_EJE - R_RUEDA, s * Y_RUEDA - A_RUEDA / 2), 2 * R_RUEDA, A_RUEDA, fc="0.15", ec="k"))
        a1.add_patch(Rectangle((X_EJE - MOTOR[1] / 2, s * (5 + MOTOR[0] / 2) - MOTOR[0] / 2),
                               MOTOR[1], MOTOR[0], fc=COLORES["motor"], ec="k", alpha=0.6))
    a1.add_patch(Circle((X_LOCA, 0), R_BOLA, fc="0.6", ec="k"))
    a1.add_patch(Circle((X_VASO, 0), R_EXT_VASO, fc="none", ec=COLORES["portavaso"], lw=3))
    a1.add_patch(Circle((X_VASO, 0), R_INT_VASO, fc="none", ec=COLORES["portavaso"], lw=1, ls="--"))
    for nombre, (cx, cy, sx, sy, sz, z0, color) in COMPONENTES.items():
        a1.add_patch(Rectangle((cx - sx / 2, cy - sy / 2), sx, sy, fc=color, ec="k", alpha=0.55))
        a1.text(cx, cy, nombre, ha="center", va="center", fontsize=7, color="w")
    for _, x in HCSR04:
        a1.add_patch(Rectangle((x - 1, -22.5), 2, 45, fc=COLORES["sensor"], ec="k"))
    for x, y in IR_LINEA:
        a1.add_patch(Rectangle((x - 5, y - 5), 10, 10, fc="k"))
    cota(a1, (-L / 2, -Y_RUEDA - 40), (L / 2, -Y_RUEDA - 40), f"largo {L:.0f}")
    cota(a1, (L / 2 + 25, -W / 2), (L / 2 + 25, W / 2), f"ancho {W:.0f}", off=(0, 0))
    cota(a1, (-L / 2 - 25, Y_RUEDA), (-L / 2 - 25, -Y_RUEDA), f"vía {2 * Y_RUEDA:.0f}", off=(0, 0))
    cota(a1, (X_EJE, W / 2 + 40), (X_LOCA, W / 2 + 40), f"batalla {X_LOCA - X_EJE:.0f}")
    a1.text(X_VASO, R_EXT_VASO + 8, f"porta-vaso Ø{2 * R_INT_VASO:.0f} int.", ha="center", fontsize=8,
            color=COLORES["portavaso"])
    a1.set_xlim(-170, 190); a1.set_ylim(-160, 150); a1.set_aspect("equal"); a1.grid(alpha=0.2)
    a1.set_xlabel("X (adelante →)"); a1.set_ylabel("Y")

    # --- vista lateral ---
    a2.set_title("Vista lateral (izquierda)")
    a2.add_patch(Rectangle((-L / 2, Z_CHASIS), L, T_CHASIS, fc=COLORES["chasis"], ec="k"))
    a2.add_patch(Rectangle((-L / 2, Z_PISO2), L, T_PISO2, fc=COLORES["piso2"], ec="k"))
    for sx in (-1, 1):
        a2.add_patch(Rectangle((sx * (L / 2 - 15) - 3, Z_SUP), 6, H_SEPARADOR, fc=COLORES["separador"], ec="k"))
    a2.add_patch(Circle((X_EJE, R_RUEDA), R_RUEDA, fc="0.15", ec="k"))
    a2.add_patch(Circle((X_EJE, R_RUEDA), R_RUEDA * 0.55, fc=COLORES["rin"], ec="k"))
    a2.add_patch(Circle((X_LOCA, R_BOLA), R_BOLA, fc="0.6", ec="k"))
    a2.add_patch(Rectangle((X_LOCA - 15, 2 * R_BOLA - 2), 30, Z_CHASIS - 2 * R_BOLA + 2, fc="0.75", ec="k"))
    a2.add_patch(Rectangle((X_VASO - R_EXT_VASO, Z_PISO2 + T_PISO2), 2 * R_EXT_VASO, H_PORTAVASO,
                           fc=COLORES["portavaso"], ec="k", alpha=0.8))
    a2.add_patch(Rectangle((X_VASO - 35, Z_PISO2 + T_PISO2 + 2), 70, 75, fc="none", ec="0.4", ls=":"))
    a2.text(X_VASO, Z_PISO2 + 85, "vaso Ø70", ha="center", fontsize=8, color="0.3")
    for nombre, (cx, cy, sx, sy, sz, z0, color) in COMPONENTES.items():
        a2.add_patch(Rectangle((cx - sx / 2, z0), sx, sz, fc=color, ec="k", alpha=0.5))
    for s, x in HCSR04:
        a2.add_patch(Rectangle((x - 1, Z_HCSR04 - 10), 2, 20, fc=COLORES["sensor"], ec="k"))
        a2.add_patch(Rectangle((x + (0 if s > 0 else -12), Z_HCSR04 - 8), 12, 16, fc=COLORES["transductor"], ec="k"))
    a2.plot([-170, 190], [0, 0], "k-", lw=2)
    altura = Z_PISO2 + T_PISO2 + H_PORTAVASO
    cota(a2, (150, 0), (150, altura), f"{altura:.0f}", off=(14, 0))
    cota(a2, (-150, 0), (-150, Z_CHASIS), f"{Z_CHASIS:.0f}", off=(-14, 0))
    cota(a2, (X_EJE - R_RUEDA, -15), (X_EJE + R_RUEDA, -15), f"Ø{2 * R_RUEDA:.0f}")
    a2.set_xlim(-170, 190); a2.set_ylim(-35, 190); a2.set_aspect("equal"); a2.grid(alpha=0.2)
    a2.set_xlabel("X (adelante →)"); a2.set_ylabel("Z")
    plt.tight_layout()
    plt.savefig(ruta, dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--escala", type=float, default=4.0, help="escala del URDF (la simulación usa 4)")
    args = ap.parse_args()
    generar_scad(os.path.join(AQUI, "carro.scad"))
    n = generar_stl(os.path.join(AQUI, "carro_ensamble.stl"))
    generar_urdf(os.path.join(AQUI, "carro.urdf"), args.escala)
    generar_plano(os.path.join(AQUI, "plano_carro.png"))
    print("carro.scad, carro_ensamble.stl (%d triangulos), carro.urdf (escala %g) y plano_carro.png generados"
          % (n, args.escala))
