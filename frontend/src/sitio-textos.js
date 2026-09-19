// Textos del sitio de Ítaca Conversemos, tomados del WordPress tal como los
// escribió el equipo (se corrigieron solo tildes y erratas evidentes; el sentido
// no se tocó). Nada de esto es relleno: si un dato no estaba, aquí no está.
//
// Lo que NO se copió, a propósito:
//  - Las cifras de la portada ("300+ vidas cambiadas", "2,000+ personas",
//    "21,600+ horas conversando"): el sistema registra hoy 2.833 atenciones, así
//    que esas cifras no se pueden sostener con la base. Quedan las frases que
//    las acompañaban, que sí son del equipo.
//  - La lista de psicólogos: sale de la base del sistema (15 activos), no de la
//    web (7, tres de ellos ya inactivos).

export const INICIO = {
  rotulo: "Bienvenidos",
  titulo: "Este espacio es para ti.",
  entrada:
    "Conversemos es un espacio dedicado a cuidar de nuestra salud mental y para todos los que buscan un espacio para mirar dentro y sanar: un lugar donde podemos cuestionarnos, informarnos y conversar sin miedo a ser juzgados, con un acompañamiento seguro y real.",
  procesoTitulo: "¿Cómo llevamos el proceso?",
  procesoRotulo: "Sesiones personalizadas",
  procesoFrase:
    "Estás a solo un paso para empezar tu viaje para lograr eso que tanto quieres, para poder sanar, para poder permitirte vivir en paz.",
  equipoTitulo: "Algunos de nuestros psicólogos",
  equipoRotulo: "Profesionales de primera",
  testimoniosTitulo: "¿Será que esto me pasa sólo a mí?",
  testimoniosRotulo: "Lo que cuentan quienes ya pasaron por aquí",
};

// Cómo es el proceso, contado con lo que el propio sistema hace en cada paso.
export const PASOS = [
  { t: "Eliges con quién y cuándo",
    d: "Puedes ver el perfil de cada psicólogo y sus horarios libres, o contarnos qué necesitas y te ayudamos a elegir." },
  { t: "Coordinación te confirma",
    d: "Te escribimos al número que dejaste para confirmar horario, sede y profesional, y enviarte los medios de pago. No pagas nada al reservar." },
  { t: "Tu primera consulta",
    d: "Entre 30 y 45 minutos para conocer a quien te acompañará. De ahí sale tu plan de terapia." },
  { t: "El acompañamiento",
    d: "Las sesiones duran entre 50 minutos y una hora. La frecuencia la propone tu psicólogo según lo que estén trabajando, y se ajusta contigo." },
];

// Testimonios publicados por el equipo en su web, con el nombre con que firman.
export const TESTIMONIOS = [
  {
    nombre: "Fiorella Guido",
    texto:
      "Decidir por sanar internamente me costó mucho, siempre creí que el tema de la salud mental era algo superficial y solo para personas que realmente estaban mal. Sin embargo, llegó un punto en el que lo que sentía internamente me estaba afectando en muchas áreas de mi vida, y aunque fue complicado empecé terapia. Mi psicóloga me acompañó sin juzgarme ni decirme que estaba exagerando o minimizando mis emociones; al contrario, las validaba todas y realmente era un espacio en el que siempre me sentí libre y segura de hablar. Realmente Ítaca Conversemos es un espacio libre y seguro para empezar a sanar el interior, y hoy soy más consciente de que la salud mental y emocional es tan importante como la física.",
  },
  {
    nombre: "Francesca Duran",
    texto:
      "Desde el principio me he sentido muy cómoda y en confianza para poder conversar sobre todo lo que me aquejaba, y en cada sesión me daba herramientas para usar en mi día a día. Poco a poco he podido ser más consciente del impacto que tienen mis emociones en mí misma y en las personas que me rodean, la manera cómo expresarme y ser eficiente en mis comunicaciones. Me enseñó la importancia de conocerme a mí misma, que es la base de todo gran cambio. Sigo en un camino de aprendizaje, de subidas y bajadas, pero estoy muy dispuesta a mejorar siempre, a conocerme y valorarme.",
  },
  {
    nombre: "Lanie Salas",
    texto:
      "Yo era de esas personas que pensaba que hablar con psicólogos era porque estabas loco o no sabías manejarte. Luego de escuchar a mi amiga, sumergirme en lecturas y buscar información, me topé con un reel donde, a su tierna manera, nos invitaban a dar el paso. ¿Cuál era? El de reconocer que necesitaba ayuda y que ellos podían darme la mano. Llegué a Ítaca Conversemos con temor a ser juzgada y con vergüenza; sin embargo, todos mis prejuicios se esfumaron: me descubrí, me entendí y me perdoné. Darse cuenta del porqué de las cosas fue liberador.",
  },
  {
    nombre: "Vanessa Gutierrez",
    texto:
      "Ir a terapia fue la mejor decisión que tomé en la vida. A fines del año 2020 estaba pasando por constantes crisis existenciales, las cuales me hacían sentir que no podía más, hasta que decidí comunicarme para decir que había tomado la decisión de llevar terapia psicológica. Tuve la gran oportunidad de ser atendida por una gran psicóloga, quien me brindó las herramientas necesarias para afrontar ciertas circunstancias. No ha sido nada fácil, pero gracias a sus consejos hay un antes y un después en mí. Por eso siempre les digo a todos que se vive «un día a la vez».",
  },
];

export const QUIENES_SOMOS = {
  eyebrow: "Conócenos y da el primer paso",
  titulo: "Un espacio seguro para mirar dentro y sanar.",
  entrada: [
    "Conversemos es un espacio creado para ti: un lugar donde podemos cuestionarnos, informarnos y conversar sin miedo a ser juzgados, con un acompañamiento seguro y real.",
    "Aquí encontrarás diferentes opciones para lo que necesitas, presenciales en Lima y Piura o por videollamada.",
  ],

  queHacemosTitulo: "¿Qué hacemos?",
  queHacemosEntrada: "Trabajamos todos los temas relacionados a salud mental y bienestar personal.",
  // La línea de cada servicio describe en qué consiste; no promete resultados.
  queHacemos: [
    { nombre: "Terapia individual", icono: "individual",
      detalle: "Sesiones de entre 50 minutos y una hora, presenciales o por videollamada." },
    { nombre: "Terapia grupal", icono: "grupal",
      detalle: "Reuniones con personas que atraviesan dificultades similares, con la guía de un psicólogo del equipo." },
    { nombre: "Terapia de pareja", icono: "pareja",
      detalle: "Sesiones para los dos, con profesionales del equipo que atienden consultas de pareja." },
    { nombre: "Orientación vocacional", icono: "vocacional",
      detalle: "Acompañamiento para decidir qué estudiar o hacia dónde seguir." },
    { nombre: "Desarrollo personal", icono: "desarrollo",
      detalle: "Un espacio para trabajar en ti, más allá de una crisis puntual." },
    { nombre: "Talleres y charlas psicoeducativas", icono: "talleres",
      detalle: "Encuentros para informar y prevenir, dentro de nuestra área de promoción." },
  ],

  areasTitulo: "¿En qué áreas trabajamos?",
  areasEntrada: "Nuestro trabajo se ordena en tres frentes que se sostienen entre sí.",
  areas: [
    { titulo: "Promoción de la salud física y mental",
      detalle: "Generamos conciencia sobre la importancia de la salud mental." },
    { titulo: "Prevención de trastornos y enfermedades mentales",
      detalle: "Informamos y educamos para prevenir problemas con tu bienestar mental." },
    { titulo: "Intervención psicoterapéutica",
      detalle: "Brindamos ayuda profesional a través del apoyo psicoterapéutico." },
  ],

  modeloEyebrow: "Cómo acompañamos",
  modeloTitulo: "Modelo de atención psicológico integrativo",
  modeloCita: "Buscamos siempre desarrollar una relación humana y real de cada paciente con su psicoterapeuta.",
  modelo: [
    "Este modelo tiene como finalidad intervenir y ayudar tomando en cuenta a cada persona como un todo, no sólo una situación o crisis actual que estés experimentando: buscamos tu bienestar en todos los niveles.",
    "Por eso, en cada proceso consideramos todo tu ser.",
  ],
  dimensiones: ["Mente", "Cuerpo", "Pensamientos", "Emociones", "Historia de vida"],

  creenciasEyebrow: "Lo que nos sostiene",
  creenciasTitulo: "En lo que creemos",
  creencias: [
    { icono: "objetivo", texto: "Cada conversación tiene un objetivo: mejorar el entorno de la vida de cada persona que confía en nosotros." },
    { icono: "comunidad", texto: "Somos una comunidad, creada para apoyarnos mutuamente." },
    { icono: "aprendizaje", texto: "Cada hora de acompañamiento emocional es una hora de aprendizaje y fortalecimiento." },
  ],

  cierreTitulo: "¿Damos el primer paso juntos?",
  cierreTexto: "Eliges la sede, el psicólogo y el horario que mejor te queden. Coordinación confirma contigo antes de la sesión, y no pagas nada al reservar.",
};

export const TERAPIAS = {
  rotulo: "El momento es ahora",
  titulo: "Encuentra la paz en tiempos difíciles",
  entradaTitulo: "Aquí podrás encontrar un espacio ideal creado para ti",
  entradaRotulo: "Conoce cuál se adapta a tus necesidades",
  cuerpo:
    "Nuestro cuerpo se comunica con nosotros: desde el interior nos envía señales de que no estamos del todo bien. Puede ser un nudo en la garganta, un dolor de estómago o de cabeza, que nos dificultan hacer las cosas que nos gustan. A veces no sabemos qué está pasando, así que decidimos ignorarlo o esperamos a que pase por sí solo. Sin embargo, cuando el dolor no se detiene, nos damos cuenta de que ya no podemos más. Huir de lo que nuestro cuerpo siente ocasiona que terminemos desconectados y sin saber qué hacer.",
  paraTitulo: "Terapias para",
  para: ["Niños", "Adolescentes", "Adultos", "Adultos mayores", "Parejas"],
  temasTitulo: "Si sientes que debes trabajar alguno de estos temas, este espacio es para ti",
  temas: [
    "Autoestima e inseguridades", "Estrés y ansiedad", "Depresión", "Dependencia emocional",
    "Preocupación excesiva", "Gestión de emociones y pensamientos", "Maltrato físico o psicológico",
    "Trauma", "Heridas de la infancia", "Sensación de vacío e inestabilidad", "Creencias limitantes",
    "Conflictos de pareja", "Aceptación y perdón", "Trastornos de la conducta alimentaria", "Fobias",
    "Problemas familiares", "Exploración de tu sexualidad", "Crecimiento personal", "Adicciones",
    "Somatizaciones", "Manejo de los conflictos", "Duelos (pareja, familia, perinatal)",
  ],
  // Sesión Brújula. El texto es el mismo con el que el equipo la explica por
  // WhatsApp: si la web dijera otra cosa, quien pregunta por los dos canales
  // recibiría dos versiones de un mismo servicio.
  brujulaRotulo: "Antes de empezar",
  brujulaTitulo: "Sesión Brújula",
  brujulaEntrada:
    "A veces sabemos que necesitamos ayuda, pero no sabemos por dónde empezar. La Sesión Brújula es una sesión de evaluación y orientación con un psicólogo de nuestro equipo, especializado en evaluación y orientación clínica, que conoce a todos los terapeutas. No es una sesión de terapia ni un diagnóstico: es el paso ideal para quien no sabe por dónde empezar.",
  brujulaIncluye: [
    { t: "Una entrevista profunda", d: "Para entender lo que estás atravesando, con calma y sin apuro." },
    { t: "Pruebas psicológicas", d: "Para conocer cómo está hoy tu bienestar emocional." },
    { t: "Exploración de tu contexto", d: "Qué quieres trabajar y cómo te relacionas con la terapia." },
    { t: "Una recomendación para ti", d: "El terapeuta y el enfoque que mejor se ajustan a tu caso, y un pequeño mapa para empezar con más seguridad y menos ensayo y error." },
  ],
  brujulaPara:
    "Es para ti si no sabes por dónde empezar, si tuviste malas experiencias previas en terapia, o si quieres una orientación personalizada antes de elegir psicólogo.",
  brujulaDiferencia:
    "La primera consulta es conocer a tu psicólogo. La Brújula es que alguien que conoce a todo el equipo te ayude a descubrir cuál psicólogo y qué enfoque te convienen.",
  circuloTitulo: "Círculo de Aliados",
  circuloRotulo: "Terapia grupal",
  circuloEntrada:
    "Reuniones terapéuticas grupales con personas que experimentan dificultades similares. Encuentra un espacio de confianza y una red de apoyo donde puedas expresarte y encontrar estrategias para afrontar las distintas situaciones con la guía de un psicólogo de nuestro equipo.",
  circulos: [
    {
      nombre: "Corazón valiente",
      preguntas: "¿Estuviste en una relación insana? ¿Te costó salir y sientes culpa por no haberte ido antes? ¿La culpa y el miedo te invaden? ¿Sientes miedo de volver a tener una relación después de esta experiencia?",
      texto: "Corazón valiente acoge a todas aquellas personas que lograron salir de un vínculo que les generó mucho dolor. Es un espacio en el cual podemos acompañarnos y juntos volver a recuperar la luz que un día alguien apagó.",
    },
    {
      nombre: "Nuevo Horizonte",
      preguntas: "¿Sientes que tienes temas pendientes de tu pasado? ¿No encuentras respuesta a comportamientos inconscientes que tienes con los demás? ¿Sientes que cargas con una mochila pesada que no te permite avanzar? ¿Has sentido un vacío en tu interior y buscas constantemente cómo llenarlo?",
      texto: "Nuevo Horizonte es el espacio para quienes están en busca de respuestas y quieren mirar atrás con compasión y amor para soltar y avanzar.",
    },
    {
      nombre: "Espejo",
      preguntas: "¿Sientes que no te gusta tu cuerpo? ¿Crees que nunca alcanzarás el ideal de belleza? ¿Te cuesta encontrar aspectos de ti para amar? ¿No sabes cómo empezar a cuidarte? ¿Te sientes inseguro al momento de hablar o expresarte?",
      texto: "Espejo es el espacio para quienes reconocen la importancia de tener confianza en sí mismos y quieren empezar en el camino de la aceptación y el amor propio.",
    },
  ],
  cierreRotulo: "No estás solo o sola",
  cierreTitulo: "Sabemos que estás aquí por un motivo",
  cierre: [
    "Si estás aquí es porque algo dentro de ti quiere dar un gran paso, y qué gusto nos da recibirte. Te abrazamos mucho por ser tan valiente. Empecemos el viaje, conversemos.",
    "Has llegado a un lugar seguro que recibe a personas que, por alguna razón, están sintiendo un ruido en su interior y quieren aprender a reconciliarse con él. Te invitamos a sentirte en compañía, porque es muy importante que sepas que no estás solo o sola en este proceso.",
    "Todos en algún momento de la vida pasamos por situaciones difíciles, circunstancias que nos superan y que pueden generar frustración y dolor. Sabemos que estas etapas nos agotan y nos dejan totalmente apagados emocionalmente; es por eso que queremos ayudarte a sanar esa herida que no te permite encontrar la paz y calma que tanto te mereces.",
    "Te prometemos ser para ti la compañía ideal durante el proceso que te toque vivir, que será único, especial y diferente al de los demás, porque es solo tuyo. Abraza este momento como el inicio de una nueva etapa en tu vida, porque a partir de ahora aprenderás a comprenderte y mirarte con más bondad.",
  ],
};

export const PREGUNTAS = {
  titulo: "Preguntas frecuentes",
  rotulo: "Aquí podrás resolver tus dudas",
  entrada: "Lo que más nos preguntan antes de una primera consulta. Si te queda algo, escríbenos: preferimos que preguntes a que te quedes con la duda.",
};

export const PSICOLOGOS = {
  titulo: "Nuestros psicólogos",
  rotulo: "Conócelos un poco más aquí",
  entrada: "Este es el equipo que atiende hoy en Lima y Piura. Puedes elegir por sede, leer el perfil de cada uno y reservar directamente con quien prefieras.",
};

// ── Faro · tamizaje escolar ──────────────────────────────────────────────────
// Landing B2B: quien la lee es el director o el psicólogo de un colegio, no un
// paciente. Por eso no hay "reserva tu cita" en ninguna parte, y por eso se dice
// desde el principio lo que el servicio NO hace: un director que se entera
// después de que no recibirá los nombres se siente engañado, y con razón.
export const FARO = {
  hero: ["Bienestar emocional", "escolar, con una", "mirada preventiva"],
  bajada: "Faro evalúa las necesidades emocionales de los estudiantes de secundaria para que el colegio pueda acompañar mejor, y a tiempo.",
  cta: "Solicitar información",

  queEsTitulo: "Qué es un tamizaje",
  queEs: [
    "Una evaluación preventiva breve, aplicada por psicólogos colegiados, que identifica señales que merecen una mirada más cercana.",
    "Quince minutos por estudiante, una vez al año. Con eso la institución sabe dónde están las necesidades y qué grados requieren atención, en lugar de enterarse cuando el problema ya es visible.",
  ],
  noEs: [
    ["No diagnostica.", "Ningún estudiante sale de aquí con una etiqueta."],
    ["No entrega listas de alumnos.", "El colegio recibe el panorama por grado, nunca nombres junto a resultados."],
    ["No reemplaza una evaluación clínica.", "Es una primera mirada, no un informe psicológico."],
    ["No sustituye la convivencia escolar.", "Las obligaciones de la institución siguen siendo suyas."],
  ],

  pasosTitulo: "Cómo funciona",
  pasos: [
    { n: "01", t: "Consentimiento informado", d: "El colegio recoge la autorización de los apoderados y el asentimiento de cada estudiante. Entregamos los formatos listos." },
    { n: "02", t: "Aplicación", d: "Por aulas, en horario de tutoría, con el tutor presente y personal nuestro acompañando." },
    { n: "03", t: "Análisis profesional", d: "Un psicólogo colegiado revisa los resultados y clasifica lo que requiere atención." },
    { n: "04", t: "Informe institucional", d: "Panorama por grado y sección, con recomendaciones priorizadas y reunión de devolución." },
    { n: "05", t: "Acompañamiento", d: "Evaluación individual de los casos identificados, talleres por grado y capacitación a tutores." },
  ],

  areasTitulo: "Qué se evalúa",
  areas: [
    { t: "Estado de ánimo", d: "Indicadores emocionales de las últimas dos semanas." },
    { t: "Ansiedad", d: "Preocupación, nerviosismo y dificultad para relajarse." },
    { t: "Convivencia escolar", d: "Experiencias de maltrato entre pares, vividas o ejercidas." },
    { t: "Señales de riesgo", d: "Preguntas directas de tamizaje, con protocolo de atención inmediata." },
  ],

  cifras: [
    { v: 15, suf: " min", r: "Duración por estudiante" },
    { v: 4, suf: "", r: "Áreas evaluadas" },
    { v: 42, suf: "", r: "Preguntas en total" },
  ],

  procesoTitulo: "Proceso de implementación",
  proceso: [
    { t: "Reunión con el colegio", d: "Treinta minutos para conocer la institución y ajustar el alcance." },
    { t: "Convenio y protocolo", d: "Se firman antes de aplicar nada. El protocolo define quién responde ante una alerta, y en cuánto tiempo." },
    { t: "Consentimientos", d: "El colegio los recoge. Sin autorización firmada, ese estudiante no participa." },
    { t: "Aplicación", d: "Por aulas, en horario de tutoría." },
    { t: "Informe y devolución", d: "Quince días hábiles, más una reunión con el equipo directivo." },
  ],

  seguridadTitulo: "Privacidad",
  seguridadLead: "Son datos de salud mental de menores. El diseño del servicio parte de ahí, no lo agrega al final.",
  seguridad: [
    { t: "Consentimiento antes que nada", d: "Autorización firmada del apoderado y asentimiento del propio estudiante. Cualquiera de los dos puede retirarse en cualquier momento, sin consecuencias." },
    { t: "El colegio recibe agregados", d: "Porcentajes por grado y sección. Nunca el nombre de un estudiante junto a un resultado. Profesores y tutores no ven nada individual." },
    { t: "Protocolo firmado ante alertas", d: "Si aparece una señal de riesgo, hay una ruta escrita y con plazos. Detectar sin poder responder es peor que no detectar." },
    { t: "Ley N.° 29733", d: "Tratamiento de datos sensibles con acceso restringido, finalidad declarada y derecho a solicitar eliminación." },
  ],

  formTitulo: "Conversemos sobre su institución",
  formBajada: "Le escribimos para conocer las necesidades del colegio y preparar una propuesta a su medida. Sin compromiso.",
  gracias: "Gracias por escribirnos. Nuestro equipo se comunicará con usted para conocer las necesidades de su institución y preparar una propuesta adecuada.",
};
