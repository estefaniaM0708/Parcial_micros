// carro.scad - Carro recolector de vasos (Grupo 5) - cotas en mm
// Generado por generar_cad.py. Abrir en OpenSCAD: F5 vista previa, F6 render, F7 exportar STL.
// Cambia "pieza" para exportar cada parte imprimible por separado.

pieza = "ensamble";   // "ensamble", "chasis", "piso2", "portavaso", "soporte_sensor"
$fn = 64;

L = 220.0; W = 140.0;
t_chasis = 4.0; z_chasis = 42.0;
r_rueda = 32.5; a_rueda = 26.0;
x_eje = -30.0; y_rueda = 86.0;
x_loca = 85.0; r_bola = 10.0;
h_sep = 40.0; t_piso2 = 3.0;
z_piso2 = z_chasis + t_chasis + h_sep;
x_vaso = -55.0; r_ext_vaso = 43.0; r_int_vaso = 39.0; h_portavaso = 30.0;
r_esquina = 10;

module placa_redondeada(l, w, t, r) {
    hull() for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * (l / 2 - r), sy * (w / 2 - r), 0]) cylinder(r = r, h = t);
}

// Chasis inferior: agujeros para separadores, rueda loca, motores y paso de cables
module chasis() {
    difference() {
        placa_redondeada(L, W, t_chasis, r_esquina);
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * (L / 2 - 15), sy * (W / 2 - 10), -1]) cylinder(d = 3.4, h = t_chasis + 2);
        for (dx = [-10, 10], dy = [-10, 10])                 // rueda loca
            translate([x_loca + dx, dy, -1]) cylinder(d = 3.4, h = t_chasis + 2);
        for (s = [-1, 1], dx = [-8, 8])                      // soportes de motor
            translate([x_eje + dx, s * 40, -1]) cylinder(d = 3.4, h = t_chasis + 2);
        translate([0, 0, -1]) linear_extrude(t_chasis + 2)   // paso de cables
            hull() { translate([-10, 0]) circle(d = 14); translate([10, 0]) circle(d = 14); }
        for (y = [-20, 0, 20])                                // sensores IR de linea
            translate([L / 2 - 12, y, -1]) cylinder(d = 3.4, h = t_chasis + 2);
    }
}

// Chasis superior con agujero para el porta-vaso y ventilacion
module piso2() {
    difference() {
        placa_redondeada(L, W, t_piso2, r_esquina);
        for (sx = [-1, 1], sy = [-1, 1])
            translate([sx * (L / 2 - 15), sy * (W / 2 - 10), -1]) cylinder(d = 3.4, h = t_piso2 + 2);
        for (i = [0 : 3])
            translate([20 + i * 18, -25, -1]) cube([10, 50, t_piso2 + 2]);
    }
}

// Porta-vaso: tubo con base, recibe un vaso de 70 mm
module portavaso() {
    difference() {
        union() {
            cylinder(r = r_ext_vaso, h = h_portavaso);
            cylinder(r = r_ext_vaso + 6, h = 2);             // pestaña de apoyo
        }
        translate([0, 0, 2]) cylinder(r = r_int_vaso, h = h_portavaso);
        translate([0, 0, -1]) cylinder(r = r_int_vaso - 8, h = 4);
        translate([-r_ext_vaso - 1, -8, 12]) cube([10, 16, h_portavaso]);   // ranura sensor
    }
}

// Soporte en L para el HC-SR04
module soporte_sensor() {
    difference() {
        union() {
            translate([-2, -25, 0]) cube([2, 50, 26]);
            translate([-14, -25, 0]) cube([14, 50, 2]);
        }
        for (y = [-13, 13]) translate([-3, y, 16]) rotate([0, 90, 0]) cylinder(d = 16.5, h = 4);
        for (y = [-18, 18]) translate([-7, y, -1]) cylinder(d = 3.4, h = 4);
    }
}

module rueda() { rotate([90, 0, 0]) cylinder(r = r_rueda, h = a_rueda, center = true); }
module motor_tt() { cube([22.5, 65, 18.8], center = true); }

module ensamble() {
    color("orange") translate([0, 0, z_chasis]) chasis();
    color("gainsboro") translate([0, 0, z_piso2]) piso2();
    color("goldenrod") for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * (L / 2 - 15), sy * (W / 2 - 10), z_chasis + t_chasis]) cylinder(r = 3, h = h_sep);
    for (s = [-1, 1]) {
        color("gold") translate([x_eje, s * (5 + 65 / 2), z_chasis - 18.8 / 2]) motor_tt();
        color("black") translate([x_eje, s * y_rueda, r_rueda]) rueda();
    }
    color("silver") translate([x_loca, 0, r_bola]) sphere(r = r_bola);
    color("silver") translate([x_loca - 15, -15, 2 * r_bola - 2]) cube([30, 30, z_chasis - 2 * r_bola + 2]);
    color("dodgerblue") translate([x_vaso, 0, z_piso2 + t_piso2]) portavaso();
    color("steelblue") translate([L / 2, 0, z_chasis + t_chasis]) soporte_sensor();
    color("steelblue") translate([-L / 2, 0, z_chasis + t_chasis]) mirror([1, 0, 0]) soporte_sensor();
    color([0.1, 0.1, 0.12]) translate([0.5, 19.0, 46.0]) cube([69.0, 26.0, 10.0]);  // esp32_s3
    color([0.75, 0.1, 0.1]) translate([24.5, -38.0, 46.0]) cube([21.0, 20.0, 8.0]);  // tb6612
    color([0.15, 0.15, 0.55]) translate([-68.5, -20.5, 46.0]) cube([77.0, 41.0, 21.0]);  // bateria
    color([0.1, 0.35, 0.65]) translate([50.5, -48.5, 46.0]) cube([43.0, 21.0, 14.0]);  // buck_5v
}

if (pieza == "ensamble") ensamble();
if (pieza == "chasis") chasis();
if (pieza == "piso2") piso2();
if (pieza == "portavaso") portavaso();
if (pieza == "soporte_sensor") soporte_sensor();
