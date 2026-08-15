"""Semilla de la demo.

Crea dos cuentas completas para probar la app de punta a punta —
`vieraschiavi@gmail.com` y `arcortito@gmail.com`, ambas con **Gold vigente**,
verificadas, con las 10 fotos cargadas— más una población sintética con la que
deslizar.

Determinismo: todo sale de `random.Random(SEMILLA)`. Dos corridas dan la misma
población, con las mismas fotos y los mismos likes previos. Sin eso no se puede
testear el orden del deck ni el ranking de "más votados".

Los perfiles generados son personas **inventadas**, van marcados con
`sintetico=True`, la interfaz muestra el cartel y las fotos son ilustraciones
vectoriales sin caras. No se generan datos de contacto de nadie.
"""

from __future__ import annotations

import os
import random
import uuid
from datetime import date, datetime, timedelta

from . import fotos, geo, medios
from .almacen import Almacen
from .modelos import INTENCIONES, Perfil, Preferencias

SEMILLA = 20260814

# La clave de las cuentas demo. Se puede pisar con MATCHER_DEMO_CLAVE; el
# default está documentado en el README porque es una demo, no un secreto.
CLAVE_DEMO = os.getenv("MATCHER_DEMO_CLAVE", "matcher2026")

CUENTAS_DEMO = ("vieraschiavi@gmail.com", "arcortito@gmail.com")

# Listas largas a propósito: con 20 nombres para 60 perfiles el ranking
# mostraba tres "Paula" y dos "Federico" seguidos y la demo parecía rota.
NOMBRES_F = [
    "Sofía", "Valentina", "Camila", "Lucía", "Martina", "Julieta", "Agustina",
    "Florencia", "Micaela", "Renata", "Paula", "Carolina", "Bruna", "Manuela",
    "Ana", "Emilia", "Rocío", "Delfina", "Antonella", "Guadalupe", "Malena",
    "Josefina", "Pilar", "Victoria", "Constanza", "Belén", "Clara", "Elena",
    "Natalia", "Andrea", "Verónica", "Silvina", "Mariana", "Gabriela", "Laura",
    "Inés", "Julia", "Cecilia", "Fernanda", "Romina", "Daniela", "Luciana",
    "Milagros", "Aitana", "Isabella", "Catalina", "Amparo", "Regina",
]
NOMBRES_M = [
    "Mateo", "Santiago", "Joaquín", "Facundo", "Nicolás", "Bruno", "Tomás",
    "Ignacio", "Federico", "Rodrigo", "Diego", "Andrés", "Gonzalo", "Lucas",
    "Emiliano", "Rafael", "Sebastián", "Marcos", "Julián", "Álvaro", "Martín",
    "Pablo", "Javier", "Leandro", "Maximiliano", "Agustín", "Franco", "Nahuel",
    "Ramiro", "Esteban", "Hernán", "Guillermo", "Matías", "Damián", "Ezequiel",
    "Alejandro", "Cristian", "Iván", "Benicio", "Thiago", "Lautaro", "Simón",
]
# "trans" no distingue mujer/hombre trans en el modelo (es una sola categoría,
# como pidió el producto), así que toma nombre del pool combinado. "otro" tiene
# el suyo.
NOMBRES_TRANS = NOMBRES_F + NOMBRES_M
NOMBRES_OTRO = ["Alex", "Sasha", "Renzo", "Noa", "Ariel", "Cris", "Val", "Andy", "Tai", "Robin"]

INTERESES = [
    "asado", "fútbol", "básquetbol", "running", "yoga", "escalada", "surf",
    "cine", "series", "teatro", "conciertos", "rock", "cumbia", "jazz",
    "electrónica", "leer", "escribir", "fotografía", "cocinar", "vino",
    "cerveza artesanal", "café de especialidad", "viajar", "camping", "playa",
    "montaña", "perros", "gatos", "videojuegos", "ajedrez", "política",
    "historia", "ciencia", "programar", "emprender", "bailar", "pintar",
    "voluntariado", "meditación", "mate",
]

BIOS = [
    "Si llegaste hasta acá, contame cuál fue la última cosa que te hizo reír.",
    "Vengo por el café y me quedo por la charla.",
    "Domingo de asado > sábado de boliche. Discutamos.",
    "Buscando a alguien que me explique por qué su equipo es el mejor.",
    "Me gustan los planes simples y la gente que dice lo que piensa.",
    "Trabajo mucho, cocino bien, duermo poco. Dos de tres son verdad.",
    "Cero paciencia para los que no responden. Mucha para todo lo demás.",
    "Sí, la foto del perro es a propósito.",
    "Hablemos de música, de política o de nada. Todo menos el clima.",
    "Vine a conocer gente, no a coleccionar matches.",
]

# Mezcla de países. Cargada hacia el Río de la Plata porque es el mercado de
# arranque; el catálogo geo cubre el resto y basta cambiar estos pesos.
PESOS_PAIS = {
    "UY": 34, "AR": 22, "BR": 10, "ES": 8, "CL": 5, "MX": 5,
    "CO": 4, "PE": 3, "US": 3, "IT": 2, "PY": 2, "PT": 2,
}


def _fecha_nacimiento(rnd: random.Random, edad: int) -> date:
    hoy = date.today()
    # −20 días para no dejar a nadie justo en el borde del cumpleaños, que
    # hacía fallar los tests de rango de edad un día al año.
    return hoy - timedelta(days=edad * 365 + rnd.randint(20, 340))


def _perfil_sintetico(rnd: random.Random, i: int, fuente: fotos.Fuente) -> Perfil:
    pais = rnd.choices(list(PESOS_PAIS), weights=list(PESOS_PAIS.values()))[0]
    ciudades = geo.ciudades_de(pais)
    # Ponderado por tamaño de la ciudad: sorteando parejo, Canelones terminaba
    # con más gente que Montevideo y el radar quedaba vacío en la capital.
    ciudad = (
        rnd.choices(ciudades, weights=[geo.peso_ciudad(c["id"]) for c in ciudades])[0]["id"]
        if ciudades
        else ""
    )
    genero = rnd.choices(["mujer", "hombre", "trans", "otro"], weights=[44, 44, 6, 6])[0]
    nombre = rnd.choice(
        {"mujer": NOMBRES_F, "hombre": NOMBRES_M, "trans": NOMBRES_TRANS, "otro": NOMBRES_OTRO}[
            genero
        ]
    )
    edad = rnd.randint(19, 55)
    altura = {
        "mujer": rnd.randint(150, 182),
        "hombre": rnd.randint(162, 197),
        "trans": rnd.randint(152, 192),
        "otro": rnd.randint(155, 190),
    }[genero]
    equipos = geo.equipos_de(pais)
    equipo = rnd.choice(equipos) if equipos and rnd.random() < 0.72 else ""
    politica = rnd.choices(["izquierda", "derecha", "neutro"], weights=[36, 30, 34])[0]

    p = Perfil(
        id=f"demo{i:03d}",
        email=f"sintetico{i:03d}@matcher.demo",
        nombre=nombre,
        nacimiento=_fecha_nacimiento(rnd, edad),
        genero=genero,
        altura_cm=altura,
        pais=pais,
        ciudad=ciudad,
        politica=politica,
        equipo=equipo,
        bio=rnd.choice(BIOS),
        intereses=rnd.sample(INTERESES, rnd.randint(4, 8)),
        # Lo que busca esta persona (distinto de lo que filtra en los demás).
        intenciones=rnd.sample(
            [i for i in INTENCIONES if i != "disponible_hoy"], rnd.randint(1, 3)
        ),
        preferencias=Preferencias(
            generos=rnd.choices(
                [["mujer"], ["hombre"], [], ["mujer", "trans", "otro"], ["hombre", "trans", "otro"]],
                weights=[34, 34, 20, 6, 6],
            )[0],
            intenciones=rnd.sample(
                [i for i in INTENCIONES if i != "disponible_hoy"], rnd.randint(1, 3)
            ),
            edad_min=max(18, edad - rnd.randint(4, 12)),
            edad_max=min(99, edad + rnd.randint(4, 14)),
            solo_mi_pais=rnd.random() < 0.35,
        ),
        plan=rnd.choices(["gratis", "plus", "gold"], weights=[74, 18, 8])[0],
        verificado=rnd.random() < 0.42,
        sintetico=True,
        ultima_actividad=datetime.utcnow() - timedelta(hours=rnd.randint(0, 24 * 20)),
        # Las vistas se derivan de los likes y no se sortean aparte: si se
        # sortean, aparecen perfiles con 260 likes en 60 vistas (tasa 4.3) y el
        # ranking de "más votados" queda saturado en 100 para media población.
        likes_recibidos=0,
        superfans_recibidos=0,
        vistas_recibidas=0,
    )
    p.vistas_recibidas = rnd.randint(150, 2200)
    tasa = rnd.triangular(0.02, 0.45, 0.11)
    p.likes_recibidos = int(p.vistas_recibidas * tasa)
    p.superfans_recibidos = int(p.likes_recibidos * rnd.uniform(0.0, 0.06))
    # Un tercio marcado como disponible hoy, para que el filtro tenga a quién
    # devolver en la demo.
    if rnd.random() < 0.33:
        p.marcar_disponible(rnd.randint(2, 20))
    if p.plan != "gratis":
        p.plan_vence = datetime.utcnow() + timedelta(days=rnd.randint(3, 300))
    # La cara tiene que coincidir con la presentación del nombre. Un perfil
    # trans toma nombre de la lista mixta, pero su foto salía del pool
    # completo: quedaba "Julián" con cara de mujer y se leía como un bug de
    # la demo, no como una persona. Se elige el pool según el origen del
    # nombre; el género del PERFIL sigue siendo trans.
    genero_foto = genero
    if genero == "trans":
        genero_foto = "mujer" if nombre in NOMBRES_F else "hombre"
    for url in fuente.para(p.id, nombre, genero_foto, rnd.randint(2, 5)):
        medios.agregar_foto(p, url)
    return p


def _cuenta_demo(
    email: str,
    nombre: str,
    genero: str,
    generos: list[str],
    edad: int,
    altura: int,
    equipo: str,
    politica: str,
    intereses: list[str],
    bio: str,
    rnd: random.Random,
    fuente: fotos.Fuente,
) -> Perfil:
    """Cuenta con TODO habilitado: Gold vigente un año, verificada, 10 fotos.
    Es lo que se pidió para probar la app sin límites."""
    p = Perfil(
        id=uuid.uuid5(uuid.NAMESPACE_DNS, f"matcher:{email}").hex[:12],
        email=email,
        nombre=nombre,
        nacimiento=_fecha_nacimiento(rnd, edad),
        genero=genero,
        altura_cm=altura,
        pais="UY",
        ciudad="UY-MVD",
        politica=politica,
        equipo=equipo,
        bio=bio,
        intereses=intereses,
        preferencias=Preferencias(
            generos=generos,
            edad_min=18,
            edad_max=99,
            solo_mi_pais=False,
        ),
        plan="gold",
        plan_vence=datetime.utcnow() + timedelta(days=365),
        verificado=True,
        sintetico=False,
        ultima_actividad=datetime.utcnow(),
        likes_recibidos=rnd.randint(40, 90),
        superfans_recibidos=rnd.randint(4, 12),
        vistas_recibidas=rnd.randint(300, 600),
    )

    for url in fuente.para(p.id, nombre, genero, medios.MAX_FOTOS):
        medios.agregar_foto(p, url)
    # Los slots de video quedan vacíos a propósito: la demo no trae videos de
    # ejemplo. La subida de hasta 2 videos por perfil funciona desde "Mi
    # perfil" y está cubierta por tests.
    return p


def _sembrar_ubicaciones_y_cruces(almacen: Almacen, rnd: random.Random) -> None:
    """Reparte a la gente alrededor del centro de su ciudad y arma cruces con
    las cuentas demo.

    La dispersión es de hasta ~12 km: con todos en el centro exacto, el radar
    muestra 40 puntos apilados y no se entiende nada. Todo lo que se guarda ya
    pasa por `geo.aproximar`, igual que en el flujo real.
    """
    ahora = datetime.utcnow()
    perfiles = almacen.todos()
    for p in perfiles:
        centro = geo.coordenadas(p.ciudad)
        if not centro:
            continue
        # Desplazamiento de hasta ~5 km alrededor del centro. Con los ~12 km de
        # antes, la mayoría de la gente de Montevideo caía fuera del radio de
        # 15 km por diagonal y el radar mostraba una sola persona.
        d_lat = rnd.uniform(-0.045, 0.045)
        d_lon = rnd.uniform(-0.045, 0.045)
        lat, lon = geo.aproximar(centro[0] + d_lat, centro[1] + d_lon)
        almacen.guardar_ubicacion(
            p.id, lat, lon, ahora - timedelta(minutes=rnd.randint(0, 60 * 20))
        )

    cercanos = [
        p for p in perfiles if p.sintetico and p.ciudad == "UY-MVD" and p.activo and p.completo
    ]
    for email in CUENTAS_DEMO:
        cuenta = almacen.buscar_por_email(email)
        if not cuenta or not cercanos:
            continue
        for otro in rnd.sample(cercanos, min(9, len(cercanos))):
            if otro.id == cuenta.id:
                continue
            veces = rnd.choices([1, 2, 3, 5, 8], weights=[40, 26, 18, 10, 6])[0]
            ultima = ahora - timedelta(hours=rnd.randint(1, 24 * 9))
            primera = ultima - timedelta(days=rnd.randint(1, 40))
            pos = almacen.ubicacion_de(otro.id)
            celda = geo.clave_celda(pos["lat"], pos["lon"]) if pos else ""
            almacen.sumar_cruce(cuenta.id, otro.id, veces, primera, ultima, celda)


def poblar(almacen: Almacen, *, cantidad: int = 60, clave: str | None = None) -> dict:
    """Deja la base lista para la demo. Idempotente: si las cuentas ya existen,
    no las duplica ni les pisa el plan."""
    rnd = random.Random(SEMILLA)
    clave = clave or CLAVE_DEMO
    fuente = fotos.Fuente()
    creados, existentes = [], []

    cuentas = [
        {
            "email": "vieraschiavi@gmail.com",
            "nombre": "Martín",
            "genero": "hombre",
            "generos": [],
            "edad": 38,
            "altura": 180,
            "equipo": "Peñarol",
            "politica": "neutro",
            "intereses": ["asado", "fútbol", "programar", "emprender", "ciencia", "mate", "vino"],
            "bio": "Data y cobranzas de día, asado y fútbol el resto. Cuenta demo con todo activado.",
        },
        {
            "email": "arcortito@gmail.com",
            "nombre": "Ariel",
            "genero": "otro",
            "generos": [],
            "edad": 34,
            "altura": 172,
            "equipo": "Nacional",
            "politica": "neutro",
            "intereses": ["cine", "música", "viajar", "café de especialidad", "leer", "perros"],
            "bio": "Cine, café y planes sin agenda. Cuenta demo con todo activado.",
        },
    ]
    for datos in cuentas:
        if almacen.buscar_por_email(datos["email"]):
            existentes.append(datos["email"])
            continue
        perfil = _cuenta_demo(rnd=rnd, fuente=fuente, **datos)
        almacen.crear_perfil(perfil, clave)
        creados.append(datos["email"])

    # Población sintética
    if len(almacen.todos(incluir_inactivos=True)) < cantidad:
        i = 0
        while len(almacen.todos(incluir_inactivos=True)) < cantidad:
            p = _perfil_sintetico(rnd, i, fuente)
            i += 1
            if almacen.buscar_por_email(p.email) or almacen.perfil(p.id):
                continue
            almacen.crear_perfil(p, f"demo-{p.id}")

    # Algunos likes previos hacia las cuentas demo: así "quién me dio like" y
    # el ranking de más votados tienen algo que mostrar desde el primer minuto.
    sinteticos = [p for p in almacen.todos() if p.sintetico]
    for email in CUENTAS_DEMO:
        cuenta = almacen.buscar_por_email(email)
        if not cuenta:
            continue
        for otro in rnd.sample(sinteticos, min(8, len(sinteticos))):
            try:
                almacen.interactuar(otro, cuenta.id, rnd.choices(
                    ["like", "superfan"], weights=[80, 20])[0])
            except Exception:  # noqa: BLE001 — cupo agotado o ya existía; es demo
                continue

    # Ubicaciones y cruces. Sin esto el radar arranca vacío y el contador de
    # cruces en cero, que es justo lo que hay que poder mostrar en la demo.
    _sembrar_ubicaciones_y_cruces(almacen, rnd)

    return {
        "creados": creados,
        "ya_existian": existentes,
        "total_perfiles": len(almacen.todos()),
        "clave_demo": clave,
        "cuentas_demo": list(CUENTAS_DEMO),
        "fuente_de_fotos": fuente.descripcion(),
    }


if __name__ == "__main__":  # pragma: no cover
    import sys

    ruta = sys.argv[1] if len(sys.argv) > 1 else "datos/matcher.db"
    resultado = poblar(Almacen(ruta))
    print(f"Base: {ruta}")
    for k, v in resultado.items():
        print(f"  {k}: {v}")
