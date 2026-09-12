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
  titulo: "¿Quiénes somos?",
  rotulo: "Conócenos y da el primer paso",
  parrafos: [
    "Conversemos es un espacio creado para ti. Es un espacio dedicado para cuidar de nuestra salud mental y para todos los que buscan un espacio para mirar dentro y sanar. Conversemos es un espacio donde podemos cuestionarnos, informarnos y conversar sin miedo a ser juzgados y con un acompañamiento seguro y real.",
    "En Conversemos podrás encontrar diferentes opciones para ti, esperando de corazón poder ayudarte con lo que necesitas.",
  ],
  queHacemosTitulo: "¿Qué hacemos?",
  queHacemosEntrada: "Trabajamos todos los temas relacionados a salud mental y bienestar personal:",
  queHacemos: [
    "Terapia individual",
    "Terapia grupal",
    "Terapia de pareja",
    "Orientación vocacional",
    "Desarrollo personal",
    "Talleres y charlas psicoeducativas",
  ],
  creenciasTitulo: "En lo que creemos",
  creencias: [
    "Cada conversación tiene un objetivo: mejorar el entorno de la vida de cada persona que confía en nosotros.",
    "Somos una comunidad, creada para apoyarnos mutuamente.",
    "Cada hora de ayuda emocional es una hora de aprendizaje y fortalecimiento.",
  ],
  areasTitulo: "¿En qué áreas trabajamos?",
  areas: [
    "Promoción de la salud física y mental.",
    "Prevención de trastornos y enfermedades mentales.",
    "Intervención psicoterapéutica.",
  ],
  modeloTitulo: "Modelo de atención psicológico integrativo",
  modelo: [
    "En Ítaca Conversemos implementamos el Modelo de atención psicológico integrativo.",
    "Este modelo tiene como finalidad intervenir y ayudar tomando en cuenta a cada persona como un todo, no sólo una situación o crisis actual que estés experimentando: buscamos tu bienestar en todos los niveles, considerando todo tu ser —mente, cuerpo, pensamientos, emociones e historia de vida—. Buscamos siempre desarrollar una relación humana y real de cada paciente con su psicoterapeuta.",
  ],
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
