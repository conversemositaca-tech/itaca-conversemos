"""Carga el directorio de profesionales de Itaca Conversemos (datos del PDF).

    python manage.py seed_profesionales
    python manage.py seed_profesionales --reset
"""
from django.core.management.base import BaseCommand

from core.models import Clinica
from usuarios.models import Profesional

P, L = "piura", "lima"

PROFESIONALES = [
    {
        "nombre": "Emma Curipuma", "colegiatura": "25662", "sede": P,
        "enfoque": "Psicoterapeuta clínica con enfoque Conductual Contextual con especialidad en adultos, parejas, adolescentes y adulto mayor.",
        "poblaciones": "Adultos, parejas, adolescentes, adulto mayor",
        "problematicas": "Conducta disfuncional, alteraciones del estado de ánimo, ansiedad, depresión, adicciones, trastornos de la conducta alimentaria, miedos y fobias, estrés postraumático, somatización, control de impulsos, autoestima e inseguridad, violencia física y psicológica, sexualidad, trastornos de personalidad, problemas de pareja y familia, duelo, acompañamiento en enfermedades crónicas y discapacidad.",
        "formacion": "Especialista en terapia conductual contextual.\nPsicodiagnóstico y prevención para la conservación de la salud mental.\nProtocolo de ACT para desmantelar patrones de pensamiento negativo repetitivo.\nAnálisis de conducta y modelos de tratamiento conductuales contextuales.\nUso de sustancias psicoactivas y la enfermedad adictiva.\nIntervención breve para familiares de usuarios de alcohol y/o drogas.\nAtención integral de NNA sin cuidados parentales o en riesgo de desprotección familiar.\nIntervención en suicidio y conducta suicida.",
        "trayectoria": "Hospital de apoyo Chulucanas; Save the Children International; Unicef; Poder Judicial del Perú; Centro de salud E.S. Tacalá en Castilla – Minsa, entre otros.",
        "frase": "Si estás pasando por momentos difíciles y necesitas ayuda, permíteme acompañarte.",
    },
    {
        "nombre": "Angi Requena", "colegiatura": "32695", "sede": P,
        "enfoque": "Psicoterapeuta clínica con enfoque en Terapia Sistémica y terapias de tercera generación con especialidad en adolescentes, adultos y parejas.",
        "poblaciones": "Adolescentes, adultos, parejas",
        "problematicas": "Conducta disfuncional, alteraciones del estado de ánimo, ansiedad, depresión, adicciones, trastornos de la conducta alimentaria, miedos y fobias, estrés postraumático, somatización, control de impulsos, autoestima e inseguridad, violencia física y psicológica, sexualidad, trastornos de personalidad, problemas de pareja y familia, duelo, acompañamiento en enfermedades crónicas y discapacidad.",
        "formacion": "Maestría en psicoterapias de tercera generación (conductual contextual, dialéctica conductual, funcional analítica, aceptación y compromiso).\nTerapia familiar sistémica.\nIntervención en terapia de parejas.\nIntervención en violencia y adicciones.\nGestión de relaciones comunitarias (RSE y prevención de conflictos).\nCoaching neurolingüístico (internacional).\nCertificación en liderazgo.",
        "trayectoria": "Comité Internacional de Rescate; OPS-OMS; OIM (Naciones Unidas); Encuentros: Servicio Jesuita a Migrantes; ASPOV; Colegio Talentitos; Consultorio ILLAREK, entre otros.",
        "frase": "Si estás pasando por momentos difíciles y necesitas ayuda, permíteme acompañarte.",
    },
    {
        "nombre": "Sofía Ferreyra", "colegiatura": "32381", "sede": P,
        "enfoque": "Psicóloga clínica con enfoque Conductual Contextual con especialidad en adolescentes y adultos.",
        "poblaciones": "Adolescentes, adultos",
        "problematicas": "Ansiedad, ataques de pánico, fobias, depresión, problemas de ira, control de impulsos, desregulación emocional, TLP y otros trastornos de personalidad, trastornos de la conducta alimentaria, duelo, rumia, autolesiones, riesgo suicida, relaciones interpersonales, autoestima, sentido de vida y desarrollo personal.",
        "formacion": "Especialización en psicología clínica (terapias contextuales).\nACT, DBT y TCC.\nAnálisis funcional de la conducta.\nActivación conductual para la depresión.\nSuicidio y conducta suicida (Protocolo L-RAMP).\nRO DBT (sobrecontrol emocional).\nIntervención clínica del dolor crónico.\nDesmantelar patrones de pensamiento negativo repetitivo (PNR).",
        "trayectoria": "Centro psicológico Vivir en Balance; Centro psicológico Bienestar (Tacna); C.S. La Nativa (Tacna); Centro Médico Ocupacional San Pedro Apóstol (Tacna); Colegio Anglo Americano (Arequipa); Hospital EsSalud C. A. Seguín Escobedo (Arequipa), entre otros.",
        "frase": "Buscar ayuda no es fácil. Si decidiste empezar, estoy aquí para ofrecerte un espacio seguro. No estás solo.",
    },
    {
        "nombre": "Alejandro Chung", "colegiatura": "56917", "sede": P,
        "enfoque": "Psicólogo clínico con enfoque Cognitivo Conductual y Racional Emotivo Conductual con especialidad en adolescentes y adultos.",
        "poblaciones": "Adolescentes, adultos",
        "problematicas": "Conducta disfuncional, alteraciones del estado de ánimo, ansiedad, depresión, riesgo suicida, adicciones, trastornos de la conducta alimentaria, miedos y fobias, somatización, control de impulsos, autoestima e inseguridad, trastornos de personalidad.",
        "formacion": "Especialista en depresión y riesgo suicida.\nTrastorno de ansiedad.\nConsejería/counseling y orientación.\nTrastornos de personalidad.\nDiplomado en Psicología Clínica y de la Salud.\nTerapia Racional Emotiva Conductual.",
        "trayectoria": "Equipo psicopedagógico del Colegio 14646 'El Azul' (Morropón); I.E.P. El Triunfo (Piura); Mental Health (Piura); voluntario de 'Hombres por la Igualdad – HPI' (programa Aurora, MIMP).",
        "frase": "No me resigno a que cuando yo muera, siga el mundo como si yo no hubiera vivido. Estoy aquí para ti.",
    },
    {
        "nombre": "Grecia Palacios", "colegiatura": "18328", "sede": P,
        "enfoque": "Psicoterapeuta clínica con enfoque Cognitivo Conductual con especialidad en niños, adolescentes y adultos.",
        "poblaciones": "Niños, adolescentes, adultos",
        "problematicas": "Alteraciones del estado de ánimo, intervención en TEA y TDAH, problemas de aprendizaje y conducta en niños, dificultades de lenguaje, ansiedad, estrés, autoestima e inseguridad, trastornos de personalidad y alteraciones mentales.",
        "formacion": "Especialización en psicología clínica y de la salud.\nTREC.\nIntervención con niños con TEA, TDAH y dificultades de aprendizaje.\nTerapia de lenguaje.\nTerapia Narrativa en niños.\nDesarrollo de habilidades sociales.\nIntervención clínica en población infantojuvenil.",
        "trayectoria": "Inclusión 360; Control Medic; Medcorp (Lima); I.E.P. Exitus; IFODEP; ONG ARPETSIDA, entre otros.",
        "frase": "Cambiar puede dar miedo, pero es una aventura que puede llevarte muy lejos. Te acompañaré durante este proceso.",
    },
    {
        "nombre": "Máximo Jr. Aldana", "colegiatura": "54428", "sede": P,
        "enfoque": "Psicólogo clínico con enfoque en terapia de Esquemas e Integrativo con especialidad en adolescentes y adultos.",
        "poblaciones": "Adolescentes, adultos",
        "problematicas": "Duelo, desafíos en la expresión emocional, alteraciones del estado de ánimo, ansiedad, depresión, estrés, autoestima e inseguridad, miedo al abandono, sentimiento de fracaso, problemas con la disciplina y hábitos saludables, conflictos familiares y relaciones interpersonales, autolesiones, conducta suicida, dificultades de pareja y procesos de separación.",
        "formacion": "Especialización en terapia de esquemas.\nArteterapia integral.\nPsicología clínica y de la salud.\nEstrategias de intervención en terapias contextuales.\nDesarrollo de habilidades sociales.\nIntervención clínica en población juvenil.\nDiagnóstico e informe psicológico.",
        "trayectoria": "Centro de psicoterapia integral Crecer; Centro de bienestar integral Ki House, entre otros.",
        "frase": "Toda emoción tiene un mensaje. Permíteme ayudarte a comprender lo que estás sintiendo.",
    },
    {
        "nombre": "Mayra Dávalos", "colegiatura": "30818", "sede": L,
        "enfoque": "Psicoterapeuta clínica con enfoque conductual e integrativo con especialidad en niños, adolescentes y adultos.",
        "poblaciones": "Niños, adolescentes, adultos",
        "problematicas": "Alteraciones del estado de ánimo, ansiedad, depresión, adicciones, trastornos de la conducta alimentaria, miedos y fobias, somatización, control de impulsos, autoestima e inseguridad, violencia física y psicológica, sexualidad, trastornos de personalidad, problemas de pareja y familia, duelo.",
        "formacion": "Especialización en Psicoterapia Cognitiva Conductual.\nFormación en Gestalt.\nVíctimas de abuso sexual.\nIntervención en feminicidio y violencia de género.\nActivación Conductual para la Depresión.\nDetección temprana de alteraciones mentales.\nTerapia psicológica en población infantojuvenil.",
        "trayectoria": "Hospital del Niño (HNSN); Centro de Terapias SUELBEM; Consultorio Psicológico CONTIGO; Serum en Huancabamba; Colegio Peruano Chino.",
        "frase": "Cada paso es importante; permíteme acompañarte en el proceso hacia tu bienestar emocional.",
    },
    {
        "nombre": "Karol García", "colegiatura": "64256", "sede": L,
        "enfoque": "Psicoterapeuta clínica con enfoque Cognitivo Conductual con especialidad en niños, adolescentes y adultos.",
        "poblaciones": "Niños, adolescentes, adultos",
        "problematicas": "Alteraciones del estado de ánimo, ansiedad, depresión, duelo, miedos y fobias, desregulación emocional, control de impulsos, baja autoestima e inseguridades, dependencia emocional, estrés, habilidades sociales, problemas de conducta en niños y adolescentes, asesoría en crianza respetuosa, desarrollo personal, relaciones interpersonales, acompañamiento en enfermedades crónicas.",
        "formacion": "TCC.\nConsejería emocional en niños y adolescentes.\nTREC.\nPsicodiagnóstico y prevención.\nAbordaje psicoterapéutico en pacientes oncológicos.\nIntervención en adicciones conductuales.\nTerapia psicológica en población infantojuvenil.",
        "trayectoria": "Centro psicológico KIMI; Psicólogas Asociadas; Centro de estimulación temprana 'Creciendo Juntos', entre otros.",
        "frase": "Acompaño procesos humanos con escucha, respeto y la convicción de que cada persona tiene dentro los recursos para sanar y crecer.",
    },
    {
        "nombre": "Paolo Ronceros", "colegiatura": "100625", "sede": L,
        "enfoque": "Psicoterapeuta clínico con enfoque Conductual Contextual con especialidad en adolescentes, adultos y parejas.",
        "poblaciones": "Adolescentes, adultos, parejas",
        "problematicas": "Autoestima y autoconcepto, gestión de emociones, alteraciones del estado de ánimo, ansiedad, depresión, duelo, riesgo suicida, relaciones interpersonales, conflictos familiares, problemas de pareja, incertidumbre al futuro, identidad sexual y género.",
        "formacion": "Terapias Conductuales Contextuales.\nDBT, TCC y ACT.\nExposición y prevención de respuesta.\nViolencia doméstica de pareja y masculinidades.\nParejas, sexología y disfunciones sexuales.\nAcompañamiento ético a personas trans y sus familias.\nTrastornos de personalidad.\nRegulación emocional desde terapias contextuales.",
        "trayectoria": "Centro Perspectiva; Centro Mente Efectiva; Voluntarios de Empatía LGBT+; Clínica Psicohablemos; CSMC 12 de Noviembre; Consultorio Psicopride; Psicólogo Monterrico; Orientación psicopedagógica UPC; Colegio Talentus Villa, entre otros.",
        "frase": "Pedir ayuda no es fácil. Si decides hacerlo, aquí estoy, con respeto y corazón.",
    },
    {
        "nombre": "Angelo Villa", "colegiatura": "72257", "sede": L,
        "enfoque": "Psicoterapeuta clínico con enfoque en psicoterapia de Aceptación y Compromiso (ACT) en adolescentes, jóvenes y adultos.",
        "poblaciones": "Adolescentes, jóvenes, adultos",
        "problematicas": "Alteraciones del estado de ánimo, ansiedad, depresión, duelo, miedos y fobias, desregulación emocional, control de impulsos, baja autoestima e inseguridades, dependencia emocional, estrés, habilidades sociales, asesoría para padres de familia, desarrollo personal, relaciones interpersonales, proyecto de vida.",
        "formacion": "ACT.\nFAP (Analítico Funcional).\nConsejería emocional.\nPsicodiagnóstico y prevención.\nAbordaje del duelo desde ACT.\nAcompañamiento a padres desde ACT.\nMiembro activo de la ACBS.",
        "trayectoria": "Centro Psicovive; Clínica Universidad Digital; Consultorio Universitario; Clínica Altoc, entre otros.",
        "frase": "Buscar ayuda es un acto de amor y responsabilidad contigo mismo.",
    },
    {
        "nombre": "Cristel Ríos", "colegiatura": "37246", "sede": L,
        "enfoque": "Psicoterapeuta clínica con enfoque Dialéctico Conductual (DBT) con especialidad en adolescentes y adultos.",
        "poblaciones": "Adolescentes, adultos",
        "problematicas": "Alteraciones del estado de ánimo, ansiedad, depresión, baja autoestima e inseguridades, dependencia emocional, duelo por ruptura de pareja, estrés, habilidades sociales, desarrollo personal, relaciones interpersonales, trastorno de la conducta alimentaria, desafíos de la crianza, procesos emocionales de adolescentes y adultos.",
        "formacion": "DBT y habilidades DBT.\nDisciplina positiva y convivencia escolar.\nPsicología educativa.\nPsicodiagnóstico y prevención.\nTerapia psicológica en población infantojuvenil.",
        "trayectoria": "Policlínico Inkamay Salud; Innova Schools; Asociación Civil Educativa Avante; I.E. Melgar Millenium; Saco Oliveros; Presencia de María, entre otros.",
        "frase": "Es momento de priorizarte y cuidar tu bienestar emocional. Estoy aquí para acompañarte.",
    },
    {
        "nombre": "Sabrina Sardón", "colegiatura": "72194", "sede": L,
        "enfoque": "Psicoterapeuta clínica con enfoque Conductual Contextual e integral con especialidad en adolescentes, jóvenes y adultos.",
        "poblaciones": "Adolescentes, jóvenes, adultos",
        "problematicas": "Alteraciones del estado de ánimo, ansiedad, depresión, imagen corporal y autoestima, trastornos de la conducta alimentaria, duelo, regulación emocional, relación con la comida, relación con el cuerpo y dolor crónico, estrés, desarrollo personal, relaciones interpersonales.",
        "formacion": "ACT.\nMaestría en Trastorno del Comportamiento Alimentario y Obesidad.\nTerapias contextuales para trastornos alimentarios.\nActivación conductual para la depresión.\nPsicodiagnóstico y prevención.",
        "trayectoria": "Centro Fluir; Psicosalud Emocional; GABA Perú, entre otros.",
        "frase": "Te acompaño a habitar la vida con más calma, sentido y autenticidad.",
    },
    {
        "nombre": "Bruno Gárate", "colegiatura": "53183", "sede": L,
        "enfoque": "Psicoterapeuta clínico con enfoque Conductual Contextual con especialidad en adolescentes, adultos y adultos mayores.",
        "poblaciones": "Adolescentes, adultos, adultos mayores",
        "problematicas": "Alteraciones del estado de ánimo, depresión, ansiedad, ansiedad social, gestión de emociones, control de impulsos, autoestima, inseguridades, habilidades sociales y blandas, preocupación y rumia, trastornos de la conducta alimentaria, entre otros.",
        "formacion": "Psicoterapia Conductual Contextual.\nACT.\nAnálisis y modificación de conducta.\nProtocolo de ACT para PNR.\nActivación conductual para la depresión.\nIntervención en rumia–preocupación.",
        "trayectoria": "Proyecto 'El Jardín' – ONG Cespeju; Psiconet; I.E. Virgen Purísima, entre otros.",
        "frase": "Te acompañaré en tu camino hacia la vida que deseas construir.",
    },
    {
        "nombre": "Meriveth Rojas", "colegiatura": "27939", "sede": L,
        "enfoque": "Psicoterapeuta clínica con enfoque Contextual, Cognitivo Conductual y Gestalt con especialidad en niños, adolescentes, adultos y parejas.",
        "poblaciones": "Niños, adolescentes, adultos, parejas",
        "problematicas": "Conducta disfuncional, trastornos de la personalidad, alteraciones del estado de ánimo, ansiedad, depresión, adicciones, trastornos de la conducta alimentaria, miedos y fobias, estrés postraumático, somatización, control de impulsos, autoestima e inseguridad, violencia física y psicológica, sexualidad, duelo, problemas de pareja y familia, psicología perinatal.",
        "formacion": "Terapia cognitiva conductual.\nTerapia humanista (niños, adolescentes y familia).\nGestalt.\nIntervención para parejas y familia.\nTerapias contextuales (DBT y ACT).\nTrastornos de la personalidad.\nPrevención y tratamiento de adicciones.\nTerapia de lenguaje y aprendizaje.\nIntervención en abuso infantil.\nPsicología perinatal.",
        "trayectoria": "Clínica Centro Ser; Lebar Consulting; Clínica Red Dafi Salud; Psicandal; Mavimedic; Policlínico municipal de SJL; Saco Oliveros; San Mateo, entre otros.",
        "frase": "Si estás pasando por momentos difíciles y necesitas ayuda, permíteme acompañarte.",
    },
]


class Command(BaseCommand):
    help = "Carga el directorio de profesionales de Itaca Conversemos (datos del PDF)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra y recrea el directorio.")

    def handle(self, *args, **options):
        clinica = Clinica.objects.filter(slug="itaca").first() or Clinica.objects.first()
        if clinica is None:
            self.stderr.write("No hay clinica. Corre primero: python manage.py seed_demo")
            return

        if options["reset"]:
            Profesional.objects.filter(clinica=clinica).delete()
            self.stdout.write("Profesionales anteriores borrados.")

        if Profesional.objects.filter(clinica=clinica).exists():
            self.stdout.write(self.style.WARNING("Ya hay profesionales. Usa --reset para recrearlos."))
            return

        for i, p in enumerate(PROFESIONALES, start=1):
            Profesional.objects.create(clinica=clinica, orden=i, modalidad="ambas", **p)

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {len(PROFESIONALES)} profesionales cargados en '{clinica.nombre}'."
        ))
