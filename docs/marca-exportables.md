# Identidad visual de los exportables (Gerencia y futuros módulos)

Resumen operativo del **Manual de Identidad Corporativa de Itaca Conversemos**
(Agencia Deb) aplicado a los archivos que genera el sistema (Excel, PDF, Word,
PowerPoint). La implementación vive en `frontend/src/exportGerencia.js`
(constante `MARCA`). Cuando se agregue exportación a otro módulo, reutilizar
`MARCA` y estos patrones; no inventar colores ni fuentes.

## Paleta (4 colores + blanco, gama monocromática del celeste)

| Rol | Hex | Uso en los exportables |
|---|---|---|
| Celeste 1 (primario) | `#00B8D8` | Títulos, barra de acento junto a encabezados, cabeceras de tabla (texto blanco), serie principal de gráficos, número de página |
| Celeste 2 (claro) | `#D7F4FA` | Fondo de tarjetas KPI y bloques destacados. Solo relleno: nunca texto ni líneas |
| Gris | `#6E6E6E` | Texto secundario, etiquetas, pies, ejes; es el gris del wordmark ITACA |
| Negro | `#343434` | Texto principal y cifras (nunca negro puro) |
| Blanco | `#FFFFFF` | Fondo de todo (láminas, páginas, hojas) |

Apoyos permitidos, solo como tintes del celeste: `#66D4E8` (segunda serie),
`#F1FBFD` (filas alternas / fondos muy suaves), `#DCEFF4` (líneas, pistas).
**No hay semáforo** rojo/verde/ámbar en el manual: los estados se expresan con
celeste/gris y texto. Si Gerencia aprueba un semáforo, decidirlo aparte.

## Tipografía

- **Montserrat** (la del manual): Bold para títulos y cifras, Regular para
  cuerpo, con fallback `Century Gothic → Segoe UI → Arial` en Office. El PDF
  la carga desde Google Fonts. Office sustituye sola si no está instalada.
- **Salsabila** (script) solo para el lema en redes; en exportables el lema
  "Te cambia la vida" va en Montserrat Bold, mayúsculas, espaciado (como en
  el deck de la clínica).
- **Aniron** es la letra del logo: el logo entra siempre como imagen, nunca
  se reconstruye con texto.

## Logotipo

Archivos oficiales en `frontend/public/`: `itaca-logo-v.png` (principal,
539×417, transparente) e `itaca-logo-h.png` (horizontal, 620×224).

- Principal: portada y cierre del PowerPoint, portada del Word.
- Horizontal: cabecera de cada lámina, encabezado de página (Word),
  hoja Resumen (Excel), cabecera del PDF.
- Siempre a color positivo sobre blanco, proporción bloqueada, opacidad 100 %,
  sin sombra ni rotación. Mínimos: principal 24 mm / 90 px; horizontal
  45 mm / 170 px. Área de respeto ≈ un módulo "a" del wordmark por lado.
- Combinaciones permitidas (manual p. 08): a color sobre blanco o sobre
  celeste claro; monocromo celeste; negativo blanco sobre celeste sólido.
  Prohibido: otros colores, otros fondos, contenedores blancos sobre imagen,
  transparencias, degradados, sombras, 3D, rotaciones.

## Patrones tomados del deck real de la clínica

- Fondo blanco plano en todas las láminas; títulos en celeste bold; texto de
  apoyo en gris; logo principal centrado en portada/cierre y horizontal
  arriba a la izquierda en contenido.
- Formatos impresos de la clínica: cabecera de tabla en celeste sólido con
  texto blanco en mayúsculas → mismo criterio en los cuatro formatos.
- Manual: barra vertical celeste a la izquierda de los títulos de sección;
  pie con texto gris a la izquierda y número de página en celeste bold a la
  derecha.

## Pendientes de decisión de Gerencia (no resueltos por el manual)

1. Semáforo de estados (rojo/verde) para KPIs: el deck lo usa a veces, el
   manual no lo contempla.
2. Versión del logo sin "CONVERSEMOS" que aparece en la portada del deck: no
   está en el manual; se usa la principal completa.
3. Texturas: el manual las declara "de uso exclusivo" pero no hay archivos
   vectoriales; no se reproducen a ojo.

Especificación completa (77 páginas leídas, con medidas y dudas): generada el
2026-09-04; pedirla si hace falta el detalle.
