// FLUJO 2 · «offer a ride».
//
// **AQUI SE VE LA REGLA 5 EN VIVO**: el embedding se calcula AL ESCRIBIR, no al buscar. Es el
// argumento de coste que la propuesta le vendio al cliente (seccion E, control 1), y este
// endpoint es la unica forma de ense~narlo funcionando: publicas un viaje, se embebe una vez, y
// a partir de ahi aparece en las busquedas sin costar ni una llamada mas.
//
// REESCRITO EL 15-SEP-2026: aceptaba un «plan» (titulo, categoria de concierto, artista) y la
// barra decia «Offer a ride». Cuatro agentes del programa de UX lo marcaron como el vocabulario
// de otro producto. Ahora acepta un VIAJE: de donde, adonde, cuando, cuantas plazas, a cuanto el
// km — lo que pide el encargo del cliente literalmente («30-60 min before leaving, the driver
// indicates the route he will take. How many places are available»).
import { exigirSesion, entorno, escribir } from "../utils/sesion";
import { centroDe, ciudadDe } from "../utils/bd";

/** km entre dos [lon, lat], con el +18 % de rodeo urbano que usa el sembrador. */
function kmEntre(a: [number, number], b: [number, number]): number {
	const r = 6371;
	const p1 = (a[1] * Math.PI) / 180;
	const p2 = (b[1] * Math.PI) / 180;
	const dp = ((b[1] - a[1]) * Math.PI) / 180;
	const dl = ((b[0] - a[0]) * Math.PI) / 180;
	const h =
		Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
	return Math.round(2 * r * Math.asin(Math.sqrt(h)) * 1.18 * 10) / 10;
}

/** «Neukolln» → «Neukolln»; «berlin» → «Berlin». Para el titulo, no para buscar. */
const bonito = (t: string) =>
	t
		.trim()
		.replace(/\s+/g, " ")
		.replace(/(^|[\s-])(\p{L})/gu, (m) => m.toUpperCase());

export default defineEventHandler(async (event) => {
	const yo = exigirSesion(event);
	const b = await readBody<any>(event);

	const desde = String(b?.desde ?? "").trim();
	const hacia = String(b?.hacia ?? "").trim();
	const origen = centroDe(desde, yo.city);
	const destino = centroDe(hacia, null);
	if (!desde || !hacia)
		throw createError({
			statusCode: 400,
			statusMessage: "a ride needs a from and a to",
		});
	if (!origen || !destino) {
		throw createError({
			statusCode: 400,
			statusMessage:
				"unknown place — try a district or a city name (Neukölln, Mitte, Berlin…)",
		});
	}

	const dias = Math.min(60, Math.max(0, Number(b?.dia_offset ?? 1)));
	const hora = /^\d{2}:\d{2}$/.test(String(b?.hora ?? ""))
		? String(b.hora)
		: "08:00";
	const plazas = Math.min(4, Math.max(1, Number(b?.seats_open ?? 2)));
	const precioKm = Math.min(
		0.5,
		Math.max(0.05, Number(b?.precio_por_km ?? 0.1)),
	);
	const recurrente = b?.recurrente === "weekdays" ? "weekdays" : null;
	const nota = String(b?.nota ?? "")
		.trim()
		.slice(0, 240);
	const idioma = /[äöüß]/i.test(nota) || b?.lang === "de" ? "de" : "en";

	// La hora de salida, EN HORA DE BERLIN (regla que costo un fallo el 15-sep: en UTC, «08:00»
	// salia como «10:00» en la pantalla). Se toma el dia de Berlin, se le suman los dias, y se
	// construye el instante con el desfase que Berlin tiene ESE dia (horario de verano incluido).
	const hoyBerlin = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Berlin" }).format(new Date()); // YYYY-MM-DD
	const diaLocal = new Date(`${hoyBerlin}T12:00:00Z`);
	diaLocal.setUTCDate(diaLocal.getUTCDate() + dias);
	const fechaLocal = diaLocal.toISOString().slice(0, 10);
	const desfase = (new Intl.DateTimeFormat("en-US", { timeZone: "Europe/Berlin", timeZoneName: "longOffset" })
		.formatToParts(diaLocal)
		.find((p) => p.type === "timeZoneName")?.value ?? "GMT+01:00").replace("GMT", "") || "+01:00";
	const startsAt = new Date(`${fechaLocal}T${hora}:00${desfase}`);
	const [hh] = hora.split(":").map(Number);

	const km = kmEntre(origen, destino);
	const ciudad = bonito(ciudadDe(desde) ?? yo.city);
	const titulo = recurrente
		? `${hh < 12 ? (idioma === "de" ? "Jeden Morgen" : "Every morning") : idioma === "de" ? "Jeden Abend" : "Every evening"} ${bonito(desde)} → ${bonito(hacia)}, ${hora}`
		: `${bonito(desde)} → ${bonito(hacia)}, ${hora}`;
	const descripcion =
		nota ||
		(idioma === "de"
			? "Ich fahre die Strecke sowieso. Wer mitkommen will, sagt kurz Bescheid."
			: "I drive this route anyway. Say the word and I will stop where I already stop.");
	const categoria =
		(hh >= 6 && hh <= 10) || (hh >= 16 && hh <= 19) ? "commute" : "errands";
	const etiquetas = [categoria, "rideshare"];

	// El texto que se embebe es el mismo que usa el sembrador: titulo, descripcion, sujeto,
	// etiquetas y categoria. Si divergieran, un viaje publicado a mano rankearia distinto que uno
	// sembrado, y la demo dejaria de ser comparable consigo misma.
	const texto = [
		titulo,
		descripcion,
		bonito(hacia),
		etiquetas.join(" "),
		categoria,
	].join(" · ");

	const env = entorno(event);
	const r = await fetch("https://integrate.api.nvidia.com/v1/embeddings", {
		method: "POST",
		headers: {
			Authorization: `Bearer ${env.NVIDIA_API_KEY}`,
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			model: "nvidia/nemotron-3-embed-1b",
			input: [texto],
			input_type: "passage", // pasaje, no consulta: el modelo es asimetrico
			truncate: "END",
			encoding_format: "float",
		}),
		signal: AbortSignal.timeout(8_000),
	});
	if (!r.ok)
		throw createError({
			statusCode: 502,
			statusMessage: "the ride could not be indexed right now — try again",
		});
	const emb = (await r.json()).data[0].embedding as number[];

	const [creado] = await escribir(event, "plans", {
		id: crypto.randomUUID(),
		owner_id: yo.id,
		title: titulo,
		description: descripcion,
		desc_lang: idioma,
		category: categoria,
		origin_city: ciudad,
		dest_city: bonito(ciudadDe(hacia) ?? ciudad),
		is_travel: false,
		venue: bonito(hacia),
		geo: `SRID=4326;POINT(${destino[0]} ${destino[1]})`,
		origin_geo: `SRID=4326;POINT(${origen[0]} ${origen[1]})`,
		ruta: `SRID=4326;LINESTRING(${origen[0]} ${origen[1]},${destino[0]} ${destino[1]})`,
		via: [],
		distancia_km: km,
		precio_por_km: precioKm,
		recurrente,
		date_precision: "exact",
		starts_at: startsAt.toISOString(),
		ends_at: new Date(startsAt.getTime() + 60 * 60 * 1000).toISOString(),
		radius_km: 2,
		seats_open: plazas,
		subject: bonito(hacia),
		tags: etiquetas,
		budget_band: "low",
		pace: "relaxed",
		language_pref: [idioma],
		embedding: `[${emb.map((x) => x.toFixed(6)).join(",")}]`,
	});
	return {
		plan: creado,
		embebido_al_escribir: true,
		dimension: emb.length,
		km,
		precio_total: Math.round(km * precioKm * 100) / 100,
	};
});
