"""
vision_monedas.py  -  Identificación visual de monedas colombianas (PC)

Una cámara cenital mira la "zona de inspección" de la banda transportadora
(banda NEGRA para dar contraste). Cuando una moneda se detiene bajo la cámara:
  1. Se segmenta por brillo (moneda clara sobre banda oscura) y contornos.
  2. Se mide su diámetro en mm (con la calibración px/mm).
  3. Se mide el color del centro y del anillo (dorado o plateado) en HSV.
  4. Se elige la denominación que mejor coincide (diámetro + colores).
  5. Se envía el resultado a la ESP32 de la estación por Wi-Fi (HTTP).

Las mismas funciones las usa la simulación de PyBullet con su cámara virtual.

Uso:
  python vision_monedas.py --ip 192.168.1.50          (sistema real)
  python vision_monedas.py --sin-esp                   (solo ver la clasificación)
  python vision_monedas.py --calibrar 1000             (poner una moneda de $1000 y calibrar)
"""

import argparse
import json
import os
import time
import urllib.request

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
ARCHIVO_CALIBRACION = os.path.join(AQUI, "calibracion.json")

# Monedas en circulación (Banco de la República, familia 2012)
MONEDAS = {
    50:   {"diametro": 17.0, "peso": 2.00, "anillo": "plata", "centro": "plata"},
    100:  {"diametro": 20.3, "peso": 3.34, "anillo": "oro",   "centro": "oro"},
    200:  {"diametro": 22.4, "peso": 4.61, "anillo": "plata", "centro": "plata"},
    500:  {"diametro": 23.7, "peso": 7.14, "anillo": "plata", "centro": "oro"},
    1000: {"diametro": 26.7, "peso": 9.95, "anillo": "oro",   "centro": "plata"},
}

TOLERANCIA_MM = 0.6      # error de diámetro que vale "1 punto" en el costo
UMBRAL_SATURACION = 70   # S (0-255) a partir de la cual un tono amarillo es "oro"
UMBRAL_BRILLO = 80       # V (0-255): lo más claro que esto es moneda (banda negra). None = Otsu
COSTO_MAXIMO = 3.0       # por encima de esto la moneda se marca como desconocida


# ---------------------------------------------------------------------------
# Funciones de visión (las usa también la simulación)
# ---------------------------------------------------------------------------
def segmentar(frame_bgr, px_por_mm):
    """Devuelve una lista de monedas candidatas: (cx, cy, radio_px, contorno)."""
    # Brillo (canal V): las monedas, doradas o plateadas, son mucho más claras que la banda negra
    brillo = cv2.GaussianBlur(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)[..., 2], (5, 5), 0)
    if UMBRAL_BRILLO is None:
        _, binaria = cv2.threshold(brillo, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        _, binaria = cv2.threshold(brillo, UMBRAL_BRILLO, 255, cv2.THRESH_BINARY)
    nucleo = np.ones((5, 5), np.uint8)
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_OPEN, nucleo)
    binaria = cv2.morphologyEx(binaria, cv2.MORPH_CLOSE, nucleo)   # tapa reflejos dentro de la moneda
    contornos, _ = cv2.findContours(binaria, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    r_min = 7.0 * px_por_mm       # una moneda de $50 tiene radio 8,5 mm
    r_max = 16.0 * px_por_mm      # una de $1000 tiene radio 13,35 mm
    monedas = []
    for c in contornos:
        area = cv2.contourArea(c)
        if area < np.pi * r_min ** 2 or area > np.pi * r_max ** 2:
            continue
        perimetro = cv2.arcLength(c, True)
        circularidad = 4 * np.pi * area / (perimetro ** 2 + 1e-9)
        if circularidad < 0.75:
            continue
        (cx, cy), _ = cv2.minEnclosingCircle(c)
        radio = np.sqrt(area / np.pi)          # radio equivalente por área (más estable)
        monedas.append((cx, cy, radio, c))
    return monedas


def color_zona(hsv, cx, cy, r_in, r_out):
    """'oro' o 'plata' según la mediana de tono y saturación en un anillo."""
    h, w = hsv.shape[:2]
    yy, xx = np.ogrid[:h, :w]
    d2 = (xx - cx) ** 2 + (yy - cy) ** 2
    mascara = (d2 >= r_in ** 2) & (d2 <= r_out ** 2)
    if not mascara.any():
        return "plata", 0, 0
    tono = float(np.median(hsv[..., 0][mascara]))
    sat = float(np.median(hsv[..., 1][mascara]))
    es_oro = sat >= UMBRAL_SATURACION and 8 <= tono <= 40
    return ("oro" if es_oro else "plata"), tono, sat


def clasificar(diametro_mm, color_centro, color_anillo):
    """Denominación más probable y su costo (menor = mejor)."""
    mejor, costo_min = None, 1e9
    for valor, m in MONEDAS.items():
        costo = abs(diametro_mm - m["diametro"]) / TOLERANCIA_MM
        costo += 2.0 * (color_centro != m["centro"]) + 2.0 * (color_anillo != m["anillo"])
        if costo < costo_min:
            mejor, costo_min = valor, costo
    if costo_min > COSTO_MAXIMO:
        return None, costo_min
    return mejor, costo_min


def analizar(frame_bgr, px_por_mm):
    """Detecta y clasifica todas las monedas de la imagen.
    Devuelve una lista de diccionarios con valor, diámetro, colores y posición."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    resultados = []
    for cx, cy, r, contorno in segmentar(frame_bgr, px_por_mm):
        diametro = float(2 * r / px_por_mm)
        c_centro, h1, s1 = color_zona(hsv, cx, cy, 0, 0.35 * r)
        c_anillo, h2, s2 = color_zona(hsv, cx, cy, 0.78 * r, 0.92 * r)
        valor, costo = clasificar(diametro, c_centro, c_anillo)
        resultados.append({"valor": valor, "diametro": round(diametro, 2), "centro": c_centro,
                           "anillo": c_anillo, "costo": round(costo, 2), "x": cx, "y": cy, "r": r,
                           "peso": MONEDAS[valor]["peso"] if valor else 0.0})
    return resultados


def dibujar(frame, resultados):
    for m in resultados:
        color = (0, 200, 0) if m["valor"] else (0, 0, 255)
        cv2.circle(frame, (int(m["x"]), int(m["y"])), int(m["r"]), color, 2)
        texto = ("$%d" % m["valor"]) if m["valor"] else "?"
        cv2.putText(frame, "%s  %.1f mm  %s/%s" % (texto, m["diametro"], m["centro"], m["anillo"]),
                    (int(m["x"] - m["r"]), int(m["y"] - m["r"] - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    return frame


# ---------------------------------------------------------------------------
# Programa principal (cámara real)
# ---------------------------------------------------------------------------
def cargar_calibracion():
    if os.path.isfile(ARCHIVO_CALIBRACION):
        with open(ARCHIVO_CALIBRACION) as f:
            return json.load(f)["px_por_mm"]
    return 10.0


def enviar_estacion(ip, resultado):
    url = "http://%s/moneda?valor=%d&diametro=%.2f" % (ip, resultado["valor"], resultado["diametro"])
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.read().decode()
    except Exception as e:
        return "ERROR: %s" % e


def main():
    ap = argparse.ArgumentParser(description="Identificación de monedas con OpenCV")
    ap.add_argument("--camara", type=int, default=0)
    ap.add_argument("--ip", default="192.168.1.50", help="IP de la ESP32 de la estación")
    ap.add_argument("--sin-esp", action="store_true")
    ap.add_argument("--calibrar", type=int, choices=list(MONEDAS), help="moneda de referencia")
    args = ap.parse_args()

    px_por_mm = cargar_calibracion()
    cap = cv2.VideoCapture(args.camara)
    estable, ultimo, enviado, vacio = 0, None, False, 0
    print("px/mm = %.2f  (q = salir, c = calibrar con --calibrar)" % px_por_mm)

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        # Zona de inspección: el tercio central de la imagen
        x0, x1 = w // 3, 2 * w // 3
        roi = frame[:, x0:x1]
        resultados = analizar(roi, px_por_mm)
        for m in resultados:
            m["x"] += x0
        cv2.rectangle(frame, (x0, 0), (x1, h - 1), (255, 200, 0), 1)
        dibujar(frame, resultados)

        if args.calibrar and len(resultados) == 1:
            cv2.putText(frame, "c = calibrar con moneda de $%d" % args.calibrar, (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # Una sola moneda, estable durante 5 cuadros -> se envía una vez
        if len(resultados) == 1 and resultados[0]["valor"]:
            vacio = 0
            v = resultados[0]["valor"]
            estable = estable + 1 if v == ultimo else 1
            ultimo = v
            if estable >= 5 and not enviado and not args.calibrar:
                respuesta = "sin ESP" if args.sin_esp else enviar_estacion(args.ip, resultados[0])
                print("Moneda $%d (%.1f mm) -> %s" % (v, resultados[0]["diametro"], respuesta))
                enviado = True
        elif not resultados:
            vacio += 1
            if vacio > 10:            # la moneda ya salió de la zona
                enviado, estable, ultimo = False, 0, None

        cv2.imshow("Monedas - zona de inspeccion", frame)
        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord("q"):
            break
        if tecla == ord("c") and args.calibrar and len(resultados) == 1:
            d_px = 2 * resultados[0]["r"]
            px_por_mm = d_px / MONEDAS[args.calibrar]["diametro"]
            with open(ARCHIVO_CALIBRACION, "w") as f:
                json.dump({"px_por_mm": px_por_mm}, f)
            print("Calibrado: %.3f px/mm guardado en calibracion.json" % px_por_mm)

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
