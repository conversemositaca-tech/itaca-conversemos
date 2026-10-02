// node --test src/ui/   (runner nativo de Node, sin dependencias)
import { test } from "node:test";
import assert from "node:assert/strict";
import { tipoDeAviso, textoDeAviso, duracionDeAviso } from "./aviso.js";

test("los mensajes de fallo son error aunque no empiecen con 'Error'", () => {
  for (const m of [
    "Error: algo",
    "No se pudo enviar el WhatsApp",
    "No puedes cambiar tu propio rol",
    "No tienes permiso para eliminar pagos.",
    "Ya tiene un cobro registrado",
    "Falta el teléfono del paciente",
  ]) {
    assert.equal(tipoDeAviso(m), "error", m);
  }
});

test("los éxitos siguen siendo éxito", () => {
  for (const m of ["Cobro registrado ✓", "Estado: Confirmada ✓", "Sesión cancelada", "Nota guardada"]) {
    assert.equal(tipoDeAviso(m), "success", m);
  }
});

test("advertencias e información", () => {
  assert.equal(tipoDeAviso("Atención: la línea de Lima está caída"), "warning");
  assert.equal(tipoDeAviso("Sin cambios"), "info");
});

test("el tipo explícito manda", () => {
  assert.equal(tipoDeAviso("Cobro registrado", "warning"), "warning");
  assert.equal(tipoDeAviso("No se pudo", "info"), "info");
  assert.equal(tipoDeAviso("No se pudo", "inventado"), "error");
});

test("texto limpio y duración por tipo", () => {
  assert.equal(textoDeAviso("Error: Sin conexión"), "Sin conexión");
  assert.equal(textoDeAviso("Guardado ✓"), "Guardado");
  assert.ok(duracionDeAviso("error") > duracionDeAviso("success"));
});
