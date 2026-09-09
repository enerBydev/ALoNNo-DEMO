// Endpoint de salud. Helder pidio una URL de health en el proyecto anterior, y ademas es
// lo que permite decidir si un despliegue quedo bien sin abrir el navegador.
export default defineEventHandler(() => ({
  estado: 'ok',
  servicio: 'alonno-demo',
  hora: new Date().toISOString(),
}))
