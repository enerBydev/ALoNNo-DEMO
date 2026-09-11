// Traducir una rese~na. Tres lineas de servidor, y es la demostracion mas natural del
// emparejamiento entre idiomas que tiene la demo.
//
// Las 1.232 rese~nas del seed estan mezcladas en aleman y en ingles a proposito. Ense~narle a un
// usuario ingles una rese~na alemana con un boton que SI funciona dice, sin un solo parrafo de
// marketing, que el sistema no traduce para buscar: entiende los dos idiomas a la vez y traduce
// solo cuando una persona lo pide.
//
// El proveedor ya esta conectado, asi que esto no es un endpoint nuevo de verdad: es una llamada
// mas al mismo modelo de la Capa 4.
import { chatJson } from "../utils/ia";
import { entorno } from "../utils/sesion";

export default defineEventHandler(async (event) => {
	const cuerpo = await readBody<{ texto?: string; a?: string }>(event);
	const texto = String(cuerpo?.texto ?? "").trim();
	const a = cuerpo?.a === "de" ? "German" : "English";
	if (!texto)
		throw createError({ statusCode: 400, statusMessage: "falta el texto" });
	// Una rese~na del seed son dos lineas. Un techo bajo cierra la puerta a que alguien mande un
	// libro por este endpoint, que es lo que convierte una comodidad en una factura.
	if (texto.length > 400)
		throw createError({
			statusCode: 413,
			statusMessage: "texto demasiado largo",
		});

	const { json, uso } = await chatJson(
		entorno(event),
		`Translate the user's short review into ${a}. Keep it natural and keep the tone. ` +
			'Return JSON: {"texto": "<the translation>"}. Nothing else.',
		texto,
		160,
	);
	return { texto: String(json?.texto ?? "").trim() || null, ms: uso.ms };
});
