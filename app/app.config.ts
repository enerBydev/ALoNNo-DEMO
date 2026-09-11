// El tema de Nuxt UI. `marca` es la rampa definida en `app/assets/css/main.css`, anclada en el
// verde petroleo `#0B5F5A` que la critica de UI/UX eligio y midio (7,5:1 sobre blanco).
//
// Sin esto, Nuxt UI pinta todo en su verde esmeralda de fabrica.
export default defineAppConfig({
	ui: {
		colors: {
			primary: "marca",
			neutral: "slate",
		},
	},
});
