// La ficha de un conductor: quien es, que conduce, que dicen de el, y adonde va.
//
// La reputacion se calcula AQUI y no en la pantalla. El material ya existia —`valoraciones` con
// 1.232 rese~nas bilingues, `verification`, `completed_plans`, `desde_offset`— y no llegaba a
// ninguna parte: la ficha ense~naba «verification 3/3», que es una representacion interna, y
// nada mas. `pickando.docx` pide «driver rating & review» con nombre propio.
import { tabla } from "../../utils/sesion";

/** Meses de antiguedad -> «Member since March 2024». La se~nal de permanencia mas barata que
 *  existe, y ya estaba en el seed sin que nadie la ense~nara. */
function miembroDesde(meses: number | null): string | null {
	if (meses == null) return null;
	const d = new Date();
	d.setMonth(d.getMonth() - meses);
	return d.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

export default defineEventHandler(async (event) => {
	const id = getRouterParam(event, "id")!;
	const [persona] = await tabla<any>(event, `profiles?id=eq.${id}&select=*`);
	if (!persona)
		throw createError({
			statusCode: 404,
			statusMessage: "esa persona no existe",
		});

	const suyos = await tabla<any>(
		event,
		"plans?owner_id=eq." +
			id +
			"&select=id,title,category,origin_city,dest_city,venue,starts_at,seats_open," +
			"distancia_km,precio_por_km,via,recurrente&order=starts_at.asc",
	);
	const apuntada = await tabla<any>(
		event,
		`intereses?persona_id=eq.${id}&select=plan:plans(id,title,category,dest_city,starts_at)`,
	);

	// Las rese~nas, con el nombre de quien las escribio. Una nota sin frases es un numero sin
	// prueba; lo que convence a un pasajero es leer a otra persona.
	const recibidas = await tabla<any>(
		event,
		"valoraciones?conductor_id=eq." +
			id +
			"&select=id,estrellas,texto,texto_lang,dia_offset,creado,autor:profiles!valoraciones_autor_id_fkey(id,display_name)" +
			"&order=creado.desc&limit=40",
	);

	// LA RECIPROCIDAD, que es lo que distingue un coche compartido de un taxi: este conductor
	// tambien valora a quien se sube. Sale de las valoraciones donde EL es el autor.
	const escritas = await tabla<any>(
		event,
		`valoraciones?autor_id=eq.${id}&select=estrellas`,
	);

	const reparto = [5, 4, 3, 2, 1].map((n) => ({
		estrellas: n,
		cuantas: recibidas.filter((r) => r.estrellas === n).length,
	}));

	delete persona.embedding;
	delete persona.fts;

	return {
		persona,
		planes: suyos,
		apuntada: apuntada.map((a) => a.plan).filter(Boolean),
		reputacion: {
			// Con menos de 3 valoraciones NO hay nota: un 5,0 de una persona no es mejor que un 4,7 de
			// treinta y siete. Declarar «nuevo» es mas creible, y es la regla 8 aplicada a la interfaz.
			nota: (persona.notas_conteo ?? 0) >= 3 ? Number(persona.nota) : null,
			conteo: persona.notas_conteo ?? 0,
			reparto,
			viajes: persona.completed_plans ?? 0,
			// Las verificaciones CON NOMBRE, y las que faltan tambien: un hecho comprobable vale mas
			// que la fraccion «3/3» que se ense~naba antes.
			verificaciones: [
				{
					clave: "id",
					etiqueta: "ID document",
					hecha: (persona.verification ?? 0) >= 1,
				},
				{
					clave: "phone",
					etiqueta: "Phone",
					hecha: (persona.verification ?? 0) >= 2,
				},
				{
					clave: "email",
					etiqueta: "Email",
					hecha: (persona.verification ?? 0) >= 3,
				},
			],
			miembro_desde: miembroDesde(persona.desde_offset ?? null),
			coche: persona.coche ?? null,
			plazas_coche: persona.plazas_coche ?? null,
			conduce: Boolean(persona.conduce),
			valora_a_sus_pasajeros_con: escritas.length
				? Math.round(
						(escritas.reduce((s, e) => s + e.estrellas, 0) / escritas.length) *
							10,
					) / 10
				: null,
		},
		// Solo las tres primeras llegan a la pantalla; se mandan cinco por si alguna viene vacia.
		resenas: recibidas.slice(0, 5).map((r) => ({
			id: r.id,
			estrellas: r.estrellas,
			texto: r.texto,
			idioma: r.texto_lang,
			hace_dias: Math.abs(r.dia_offset ?? 0),
			autor: r.autor?.display_name ?? null,
			autor_id: r.autor?.id ?? null,
		})),
	};
});
