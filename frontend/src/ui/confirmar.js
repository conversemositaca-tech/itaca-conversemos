import { createElement } from "react";
import { createRoot } from "react-dom/client";
import DialogoConfirmar from "./DialogoConfirmar";

// Confirmación explícita antes de una acción con consecuencias:
//   if (!(await confirmar({ titulo, mensaje, confirmarTexto, peligro: true }))) return;
// Escape o "Volver" = no. En acciones de peligro el foco empieza en "Volver",
// así un Enter apurado no confirma.
export function confirmar({ titulo, mensaje, confirmarTexto = "Confirmar", cancelarTexto = "Volver", peligro = false }) {
  return new Promise((resolver) => {
    const nodo = document.createElement("div");
    document.body.appendChild(nodo);
    const raiz = createRoot(nodo);
    const cerrar = (valor) => {
      raiz.unmount();
      nodo.remove();
      resolver(valor);
    };
    raiz.render(createElement(DialogoConfirmar, {
      titulo, mensaje, confirmarTexto, cancelarTexto, peligro, onRespuesta: cerrar,
    }));
  });
}
