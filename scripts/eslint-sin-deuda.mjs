// Compara la salida JSON de ESLint con scripts/eslint-baseline.json.
// Regla "ninguna deuda nueva": un archivo no puede tener MÁS errores que su
// línea base (falla, código 1); más avisos se reportan pero no fallan.
//
//   node scripts/eslint-sin-deuda.mjs <salida-eslint.json>
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const linea = JSON.parse(readFileSync(join(raiz, "scripts", "eslint-baseline.json"), "utf8"));
const salida = JSON.parse(readFileSync(process.argv[2], "utf8"));

const errores = [];
const avisos = [];
let totE = 0;
let totA = 0;
for (const f of salida) {
  const ruta = f.filePath.replaceAll("\\", "/");
  const rel = ruta.slice(ruta.lastIndexOf("/frontend/") + 1);
  const base = linea.archivos[rel] || { errores: 0, avisos: 0 };
  totE += f.errorCount;
  totA += f.warningCount;
  if (f.errorCount > base.errores) errores.push(`${rel}: ${f.errorCount} errores (línea base ${base.errores})`);
  if (f.warningCount > base.avisos) avisos.push(`${rel}: ${f.warningCount} avisos (línea base ${base.avisos})`);
}

console.log(`ESLint: ${totE} errores / ${totA} avisos (línea base ${linea.total.errores} / ${linea.total.avisos})`);
for (const a of avisos) console.log(`AVISO  ${a}`);
for (const e of errores) console.log(`FALLA  ${e}`);
process.exit(errores.length ? 1 : 0);
