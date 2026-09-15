// Endpoint de salud. El cliente pidio una URL de health en el proyecto anterior, y ademas es lo que
// permite decidir si un despliegue quedo bien sin abrir el navegador.
//
// UNA SONDA QUE NO PUEDE ESTAR EN ROJO NO ES UNA SONDA. La version anterior devolvia
// `estado: 'ok'` como constante: respondio `ok` en 0,29 s mientras `/api/buscar` llevaba 92 s
// colgada (critica de DevOps, 11-sep-2026). Ahora `estado` se CALCULA de lo que se comprueba, y
// el codigo HTTP acompa~na: 503 si la base no contesta, 200 con `estado: 'degradado'` si el
// proveedor de IA no responde — porque la demo sigue en pie sin el, a reglas, y eso hay que
// poder distinguirlo de una caida.
//
// Cada comprobacion lleva su tiempo en ms, que es lo que de verdad se mira cuando algo va lento.
export default defineEventHandler(async (event) => {
	const env = {
		...process.env,
		...((event.context as Record<string, any>).cloudflare?.env ?? {}),
	} as Record<string, string | undefined>;

	const medir = async (
		f: () => Promise<string>,
	): Promise<{ estado: string; ms: number }> => {
		const t0 = Date.now();
		try {
			return { estado: await f(), ms: Date.now() - t0 };
		} catch (e) {
			return {
				estado: `inalcanzable: ${(e as Error).message}`.slice(0, 120),
				ms: Date.now() - t0,
			};
		}
	};

	// La base: una lectura real, con techo. Sin techo, esta sonda heredaba el cuelgue que
	// pretendia detectar.
	const bd = await medir(async () => {
		if (!env.SUPABASE_URL || !env.SUPABASE_SECRET_KEY) return "sin credencial";
		const r = await fetch(
			`${env.SUPABASE_URL}/rest/v1/profiles?select=id&limit=1`,
			{
				headers: {
					apikey: env.SUPABASE_SECRET_KEY,
					Authorization: `Bearer ${env.SUPABASE_SECRET_KEY}`,
				},
				signal: AbortSignal.timeout(4_000),
			},
		);
		return r.ok ? "ok" : `error ${r.status}`;
	});

	// El proveedor de IA: la llamada mas barata que existe (un embedding de una palabra), con un
	// techo corto. Es la que se degrada de verdad, y la que antes nadie miraba.
	const ia = await medir(async () => {
		if (!env.NVIDIA_API_KEY) return "sin credencial";
		const r = await fetch("https://integrate.api.nvidia.com/v1/embeddings", {
			method: "POST",
			headers: {
				Authorization: `Bearer ${env.NVIDIA_API_KEY}`,
				"Content-Type": "application/json",
			},
			body: JSON.stringify({
				model: "nvidia/nemotron-3-embed-1b",
				input: ["ping"],
				input_type: "query",
			}),
			signal: AbortSignal.timeout(5_000),
		});
		return r.ok ? "ok" : `error ${r.status}`;
	});

	const estado =
		bd.estado !== "ok" ? "caido" : ia.estado !== "ok" ? "degradado" : "ok";
	if (estado === "caido") setResponseStatus(event, 503);

	return {
		estado,
		servicio: "match-engine",
		bd: bd.estado,
		bd_ms: bd.ms,
		ia: ia.estado,
		ia_ms: ia.ms,
		// Lo que significa cada estado, para quien lo lea sin este fichero delante.
		leyenda: {
			ok: "base e IA responden",
			degradado:
				"la base responde; la IA no. La busqueda sigue, a reglas y sin explicaciones",
			caido: "la base no responde. Nada funciona",
		},
		region_bd: "eu-central-1 (Frankfurt)",
		hora: new Date().toISOString(),
	};
});
